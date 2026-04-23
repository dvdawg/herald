"""Service adapter for Herald news aggregation endpoints."""
import time
from typing import Any, Dict, List, Optional

from src.data_collectors.news_collector import NewsCollector
from src.web.schemas import NewsDebug, NewsItem, NewsRequest, NewsResponse


class HeraldNewsService:
    """Normalizes news collector output for web clients."""

    def __init__(self, collector: Optional[NewsCollector] = None):
        self.collector = collector or NewsCollector()

    @staticmethod
    def _to_str_or_none(value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def _normalize_item(self, item: Dict[str, Any], rank: int) -> NewsItem:
        return NewsItem(
            rank=rank,
            score=float(item.get("score", 0.0)),
            title=str(item.get("title", "Untitled")),
            summary=self._to_str_or_none(item.get("summary")),
            url=self._to_str_or_none(item.get("url")),
            source=str(item.get("source", "unknown")),
            source_label=str(item.get("source_label", item.get("source", "Unknown"))),
            author=self._to_str_or_none(item.get("author")),
            published=self._to_str_or_none(item.get("published")),
            tags=[str(tag) for tag in item.get("tags", []) if tag],
            score_points=item.get("score_points"),
            comment_count=item.get("comment_count"),
            raw_item=item.get("raw_item") or {},
        )

    def run(self, payload: NewsRequest) -> NewsResponse:
        started = time.perf_counter()
        items, unavailable_sources, source_counts = self.collector.collect(
            query=payload.query or "",
            sources=payload.sources,
            limit=payload.limit,
            hours_back=payload.hours_back,
        )

        normalized = [self._normalize_item(item, index + 1) for index, item in enumerate(items)]
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        debug = NewsDebug(
            total_candidates=sum(source_counts.values()),
            returned_results=len(normalized),
            total_ms=elapsed_ms,
            source_counts=source_counts,
            unavailable_sources=unavailable_sources,
            params={
                "query": payload.query,
                "limit": payload.limit,
                "hours_back": payload.hours_back,
                "sources": payload.sources,
            },
        )
        return NewsResponse(query=payload.query or "", results=normalized, debug=debug)
