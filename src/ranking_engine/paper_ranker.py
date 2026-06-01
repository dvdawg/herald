"""Ranker for paper sources (arxiv etc.).

Separated from the news ranker because paper search has different priors:
query relevance dominates, recency decays much slower than news, and the
"importance language" / engagement / corroboration signals don't apply.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import numpy as np

from src.data_collectors.sources import SourceRegistry, SourceSpec
from src.ranking_engine.text_features import bm25_score, tokenize
from src.storage.article_store import ArticleStore, StoredArticle

# Half-life (in days) for paper recency. Much longer than news — a paper
# from two weeks ago is still very relevant if it matches the query.
PAPER_RECENCY_HALF_LIFE_DAYS = 14.0


def _parse_iso(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except ValueError:
        return None


@dataclass
class RankedPaper:
    article: StoredArticle
    score: float
    features: Dict[str, float]


class PaperRanker:
    def __init__(
        self,
        store: Optional[ArticleStore] = None,
        registry: Optional[SourceRegistry] = None,
    ):
        self.store = store or ArticleStore()
        self.registry = registry or SourceRegistry.from_yaml()
        self._paper_source_ids = self.registry.ids_by_category("paper")
        self._source_index: Dict[str, SourceSpec] = {s.id: s for s in self.registry.all()}

    def search(
        self,
        *,
        query: str = "",
        query_vec: Optional[np.ndarray] = None,
        sources: Optional[Iterable[str]] = None,
        limit: int = 20,
        days_back: int = 60,
        candidate_pool: int = 400,
    ) -> List[RankedPaper]:
        target_sources = list(sources) if sources else self._paper_source_ids
        if not target_sources:
            return []

        articles = self.store.recent(
            hours_back=days_back * 24, sources=target_sources, limit=candidate_pool
        )
        if not articles:
            return []

        query_terms = tokenize(query)
        # Build a BM25 corpus over the candidates so queries are scored against
        # what's actually in the search pool, not a static dictionary.
        docs = [self._article_text(a) for a in articles]
        bm25 = bm25_score(docs, query_terms) if query_terms else None

        embeddings: Dict[int, np.ndarray] = {}
        if query_vec is not None:
            embeddings = self.store.load_embeddings_for([a.id for a in articles])

        ranked: List[RankedPaper] = []
        for idx, article in enumerate(articles):
            recency = self._recency_score(article)
            source_authority = self._source_importance(article.source_id)
            lexical = float(bm25[idx]) if bm25 is not None else 0.0
            semantic = 0.0
            if query_vec is not None:
                vec = embeddings.get(article.id)
                if vec is not None:
                    semantic = max(float(np.dot(vec, query_vec)), 0.0)

            has_query = bool(query_terms) or query_vec is not None
            if has_query:
                # Query-relevance dominates for paper search.
                score = (
                    0.45 * semantic
                    + 0.35 * lexical
                    + 0.10 * recency
                    + 0.10 * source_authority
                )
            else:
                # Browsing mode — surface recent papers from authoritative sources.
                score = 0.55 * recency + 0.45 * source_authority

            ranked.append(
                RankedPaper(
                    article=article,
                    score=round(float(score), 4),
                    features={
                        "recency": round(recency, 4),
                        "source_authority": round(source_authority, 4),
                        "lexical": round(lexical, 4),
                        "semantic": round(semantic, 4),
                    },
                )
            )

        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked[:limit]

    def _article_text(self, article: StoredArticle) -> str:
        return f"{article.title}\n{article.summary or ''}"

    def _source_importance(self, source_id: str) -> float:
        spec = self._source_index.get(source_id)
        return spec.importance if spec else 0.5

    def _recency_score(self, article: StoredArticle) -> float:
        published = _parse_iso(article.published_at) or _parse_iso(article.discovered_at)
        if published is None:
            return 0.0
        age_days = max((dt.datetime.now(dt.timezone.utc) - published).total_seconds() / 86400.0, 0.0)
        # Exponential decay with PAPER_RECENCY_HALF_LIFE_DAYS half-life.
        return float(0.5 ** (age_days / PAPER_RECENCY_HALF_LIFE_DAYS))
