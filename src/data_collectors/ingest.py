"""Concurrent ingest pipeline: registry → adapters → store."""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import logging
import threading
from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests

from src.data_collectors.adapters import FetchedItem, get_fetcher
from src.data_collectors.sources import SourceRegistry, SourceSpec
from src.storage.article_store import ArticleStore
from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    source_id: str
    fetched: int
    new: int
    error: Optional[str] = None


class NewsIngester:
    """Pulls from sources and persists new articles."""

    def __init__(
        self,
        registry: Optional[SourceRegistry] = None,
        store: Optional[ArticleStore] = None,
        config: Optional[ConfigLoader] = None,
        session: Optional[requests.Session] = None,
        max_workers: int = 8,
    ):
        self.registry = registry or SourceRegistry.from_yaml()
        self.store = store or ArticleStore()
        self.config = config or ConfigLoader()
        self.session = session or requests.Session()
        self.timeout = float(self.config.get("news.request_timeout_seconds", 8.0))
        self.max_items_per_source = int(self.config.get("news.max_items_per_source", 30))
        self.max_workers = max_workers
        self._lock = threading.Lock()

    def run(self, source_ids: Optional[Iterable[str]] = None) -> List[IngestResult]:
        specs = self.registry.select(source_ids)
        results: List[IngestResult] = []
        with cf.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._run_one, spec): spec for spec in specs}
            for future in cf.as_completed(futures):
                results.append(future.result())
        return results

    def _run_one(self, spec: SourceSpec) -> IngestResult:
        started = dt.datetime.now(dt.timezone.utc)
        try:
            fetcher = get_fetcher(spec.kind)
            items = fetcher.fetch(spec, self.session, self.timeout)
            items = items[: self.max_items_per_source]
            new_count = 0
            with self._lock:
                for item in items:
                    if not item.url:
                        continue
                    _, created = self.store.upsert_article(item)
                    if created:
                        new_count += 1
                self.store.record_ingest_run(spec.id, len(items), new_count, started)
            return IngestResult(spec.id, len(items), new_count)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ingest failed for %s: %s", spec.id, exc)
            with self._lock:
                self.store.record_ingest_run(spec.id, 0, 0, started, error=str(exc))
            return IngestResult(spec.id, 0, 0, error=str(exc))
