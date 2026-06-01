"""Background news refresh loop.

Spawned by the FastAPI app on startup. Runs ingest → embed → cluster.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import threading
import time
from typing import Optional

from src.data_collectors.ingest import NewsIngester
from src.data_processors.news_embedder import NewsEmbedder
from src.ranking_engine.trending import TrendingDetector
from src.storage.article_store import ArticleStore

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 15 * 60


class NewsScheduler:
    def __init__(
        self,
        interval_seconds: Optional[int] = None,
        embed_on_start: bool = True,
    ):
        self.interval = interval_seconds or int(
            os.getenv("HERALD_REFRESH_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)
        )
        self.embed_on_start = embed_on_start
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_run: Optional[dt.datetime] = None
        self._last_status: dict = {}

    @property
    def status(self) -> dict:
        return {
            "running": self._thread is not None and self._thread.is_alive(),
            "interval_seconds": self.interval,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_status": self._last_status,
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="herald-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def refresh_once(self, sources=None) -> dict:
        ingester = NewsIngester()
        embedder = NewsEmbedder(store=ingester.store)
        trending = TrendingDetector(store=ingester.store)

        start = time.perf_counter()
        ingest_results = ingester.run(sources)
        ingest_ms = int((time.perf_counter() - start) * 1000)

        embed_start = time.perf_counter()
        embedded = embedder.embed_pending()
        embed_ms = int((time.perf_counter() - embed_start) * 1000)

        cluster_start = time.perf_counter()
        clustered = trending.assign_clusters()
        cluster_ms = int((time.perf_counter() - cluster_start) * 1000)

        store = ArticleStore()
        summary = {
            "ingested": [r.__dict__ for r in ingest_results],
            "ingest_ms": ingest_ms,
            "embedded_count": embedded,
            "embed_ms": embed_ms,
            "clustered_count": clustered,
            "cluster_ms": cluster_ms,
            "total_articles": store.total_articles(),
        }
        self._last_run = dt.datetime.now(dt.timezone.utc)
        self._last_status = summary
        return summary

    def _run(self) -> None:
        if self.embed_on_start:
            try:
                logger.info("Initial news refresh starting")
                self.refresh_once()
            except Exception:
                logger.exception("Initial refresh failed")

        while not self._stop.is_set():
            if self._stop.wait(self.interval):
                break
            try:
                self.refresh_once()
            except Exception:
                logger.exception("Scheduled refresh failed")
