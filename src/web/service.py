"""Thin service adapter for the Herald pipeline web API."""
import time
from typing import Any, Dict, List, Optional

from src.pipeline import HeraldPipeline
from src.web.schemas import RunRequest, RunResponse, RunDebug, RankedArticle


class HeraldWebService:
    """Adapter layer that normalizes pipeline output for web clients."""

    def __init__(self, pipeline: Optional[HeraldPipeline] = None):
        self.pipeline = pipeline or HeraldPipeline()

    @staticmethod
    def _format_authors(authors: List[Any]) -> List[str]:
        formatted: List[str] = []
        for author in authors or []:
            if isinstance(author, dict):
                formatted.append(str(author.get("full_name", author)))
            else:
                formatted.append(str(author))
        return formatted

    @staticmethod
    def _to_str_or_none(value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def _normalize_result(self, article: Dict[str, Any], score: float, rank: int) -> RankedArticle:
        return RankedArticle(
            rank=rank,
            score=float(score),
            title=str(article.get("title", "Unknown title")),
            arxiv_id=self._to_str_or_none(article.get("arxiv_id") or article.get("entry_id")),
            published=self._to_str_or_none(article.get("published")),
            authors=self._format_authors(article.get("authors", [])),
            summary=self._to_str_or_none(article.get("abstract") or article.get("summary")),
            pdf_url=self._to_str_or_none(article.get("pdf_url")),
            citation_count=article.get("citation_count"),
            ranking_features=article.get("ranking_features"),
            ranking_explanation=article.get("ranking_explanation"),
            raw_article=article,
        )

    def run(self, payload: RunRequest) -> RunResponse:
        started = time.perf_counter()

        ranked = self.pipeline.search_and_rank(
            query=payload.query,
            max_results=payload.max_results,
            weights=payload.weights,
            process_metadata=payload.process_metadata,
            process_text=payload.process_text,
        )

        top_k = payload.top_k or len(ranked)
        sliced = ranked[:top_k]
        normalized = [
            self._normalize_result(article=article, score=score, rank=index + 1)
            for index, (article, score) in enumerate(sliced)
        ]

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        debug = RunDebug(
            total_results=len(ranked),
            returned_results=len(normalized),
            total_ms=elapsed_ms,
            params={
                "query": payload.query,
                "max_results": payload.max_results,
                "top_k": payload.top_k,
                "process_metadata": payload.process_metadata,
                "process_text": payload.process_text,
                "weights": payload.weights,
            },
        )
        return RunResponse(query=payload.query, results=normalized, debug=debug)
