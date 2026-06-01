"""News ranker with corpus-IDF salience, cluster velocity, BM25, and MMR diversification.

Two public modes — `rank_discover` and `rank_for_you` — share the same feature
pipeline. Differences are which features participate in the final score and a
single user-affinity term for for_you.

Math notes:
- recency: exp(-Δh / τ) with τ scaled to the requested window
- corroboration: log1p(distinct_sources_in_cluster) / log1p(K)  — saturating
- velocity: count_recent / count_total within the window's recent third
- salience: TF-IDF over the candidate corpus (title boosted)
- query lexical: BM25 over the same corpus
- query semantic: dot product against a normalized query embedding
- final reranking: greedy MMR with λ trading score vs. diversity
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

import numpy as np

from src.data_collectors.sources import SourceRegistry, SourceSpec
from src.data_collectors.tags import TagRegistry, TagSpec
from src.ranking_engine.text_features import bm25_score, compute_idf, tfidf_salience, tokenize
from src.storage.article_store import ArticleStore, StoredArticle
from src.utils.config_loader import ConfigLoader

CORROBORATION_CEILING = 6
DEFAULT_MMR_LAMBDA = 0.72
MMR_POOL_MULTIPLIER = 3


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


def _published_or_discovered(article: StoredArticle) -> Optional[dt.datetime]:
    return _parse_iso(article.published_at) or _parse_iso(article.discovered_at)


@dataclass
class RankedArticle:
    article: StoredArticle
    score: float
    features: Dict[str, float]


@dataclass
class UserContext:
    """Bundle of cached preference data passed to rank_for_you()."""
    user_id: str
    centroid: Optional[np.ndarray]
    source_affinity: Dict[str, float]
    tag_affinity: Dict[str, float]
    hidden_ids: set


@dataclass
class _ClusterStats:
    total: int = 0
    recent: int = 0
    sources: Set[str] = field(default_factory=set)


@dataclass
class _RankContext:
    """Per-request computation cache shared across feature scoring."""
    articles: List[StoredArticle]
    docs_text: List[str]
    idf: Dict[str, float]
    bm25: Optional[np.ndarray]
    embeddings: Dict[int, np.ndarray]
    cluster_stats: Dict[int, _ClusterStats]
    hours_back: int
    tau_hours: float
    velocity_window_hours: float
    now: dt.datetime


class NewsRanker:
    def __init__(
        self,
        store: Optional[ArticleStore] = None,
        registry: Optional[SourceRegistry] = None,
        tag_registry: Optional[TagRegistry] = None,
        config: Optional[ConfigLoader] = None,
    ):
        self.store = store or ArticleStore()
        self.registry = registry or SourceRegistry.from_yaml()
        self.tag_registry = tag_registry or TagRegistry.from_yaml()
        self.config = config or ConfigLoader()
        self._source_index: Dict[str, SourceSpec] = {s.id: s for s in self.registry.all()}

    # --- candidate fetch + tag filter ---

    def source_importance(self, source_id: str) -> float:
        spec = self._source_index.get(source_id)
        return spec.importance if spec else 0.5

    def _article_matches_tag(self, article: StoredArticle, tag: TagSpec) -> bool:
        text_lower = (article.title + " " + (article.summary or "")).lower()
        source_tags_lower = {t.lower() for t in (article.tags or [])}
        return tag.matches(text_lower=text_lower, source_tags_lower=source_tags_lower)

    def _tag_match_quality(self, article: StoredArticle, tag: TagSpec) -> float:
        if not tag:
            return 0.0
        title_lower = article.title.lower()
        summary_lower = (article.summary or "").lower()
        source_tags_lower = {t.lower() for t in (article.tags or [])}
        score = 0.0
        for kw in tag.keywords:
            if not kw:
                continue
            if kw in title_lower:
                score += 1.0
            elif kw in summary_lower:
                score += 0.5
        for st in tag.source_tags:
            if st.lower() in source_tags_lower:
                score += 0.4
        # 3 strong matches saturate.
        return float(min(score / 3.0, 1.0))

    def _candidates(
        self,
        *,
        sources: Optional[Iterable[str]],
        hours_back: int,
        tag: Optional[TagSpec],
        candidate_pool: int,
    ) -> List[StoredArticle]:
        fetch_limit = candidate_pool * 3 if tag else candidate_pool
        articles = self.store.recent(hours_back=hours_back, sources=sources, limit=fetch_limit)
        if tag:
            articles = [a for a in articles if self._article_matches_tag(a, tag)]
            articles = articles[:candidate_pool]
        return articles

    # --- context build ---

    def _build_context(
        self,
        *,
        articles: List[StoredArticle],
        query_terms: List[str],
        query_vec: Optional[np.ndarray],
        hours_back: int,
    ) -> _RankContext:
        now = dt.datetime.now(dt.timezone.utc)
        tau_hours = max(12.0, hours_back / 4.0)
        velocity_window_hours = max(2.0, hours_back / 3.0)

        docs_text = [self._article_text(a) for a in articles]
        tokens_per_doc = [tokenize(t) for t in docs_text]
        idf = compute_idf(tokens_per_doc)

        bm25: Optional[np.ndarray] = None
        if query_terms:
            bm25 = bm25_score(docs_text, query_terms)

        embeddings: Dict[int, np.ndarray] = {}
        # Always load embeddings if any are present — needed for MMR and (when set)
        # query/centroid similarity.
        embeddings = self.store.load_embeddings_for([a.id for a in articles])

        cluster_stats = self._cluster_stats(articles, now=now, velocity_window_hours=velocity_window_hours)

        return _RankContext(
            articles=articles,
            docs_text=docs_text,
            idf=idf,
            bm25=bm25,
            embeddings=embeddings,
            cluster_stats=cluster_stats,
            hours_back=hours_back,
            tau_hours=tau_hours,
            velocity_window_hours=velocity_window_hours,
            now=now,
        )

    def _article_text(self, article: StoredArticle) -> str:
        return f"{article.title}\n{article.summary or ''}"

    def _cluster_stats(
        self,
        articles: List[StoredArticle],
        *,
        now: dt.datetime,
        velocity_window_hours: float,
    ) -> Dict[int, _ClusterStats]:
        stats: Dict[int, _ClusterStats] = defaultdict(_ClusterStats)
        recent_cutoff = now - dt.timedelta(hours=velocity_window_hours)
        for article in articles:
            cid = article.cluster_id
            if cid is None:
                continue
            s = stats[cid]
            s.total += 1
            s.sources.add(article.source_id)
            published = _published_or_discovered(article)
            if published and published >= recent_cutoff:
                s.recent += 1
        return stats

    # --- per-article features ---

    def _recency(self, article: StoredArticle, *, now: dt.datetime, tau_hours: float) -> float:
        published = _published_or_discovered(article)
        if published is None:
            return 0.0
        age_hours = max((now - published).total_seconds() / 3600.0, 0.0)
        return float(math.exp(-age_hours / tau_hours))

    def _corroboration(self, article: StoredArticle, cluster_stats: Dict[int, _ClusterStats]) -> float:
        if article.cluster_id is None:
            return 0.0
        stats = cluster_stats.get(article.cluster_id)
        if stats is None or not stats.sources:
            return 0.0
        return float(math.log1p(len(stats.sources)) / math.log1p(CORROBORATION_CEILING))

    def _velocity(self, article: StoredArticle, cluster_stats: Dict[int, _ClusterStats]) -> float:
        if article.cluster_id is None:
            return 0.0
        stats = cluster_stats.get(article.cluster_id)
        if stats is None or stats.total == 0:
            return 0.0
        # Fraction of the cluster's articles that landed in the recent third.
        # A cluster bursting *now* scores near 1; an old steady-state cluster scores near 1/3.
        ratio = stats.recent / stats.total
        # Re-center so steady-state ≈ 0: tanh((ratio - 1/3) * 3) clamped.
        centered = math.tanh((ratio - (1.0 / 3.0)) * 3.0)
        return float(max(centered, 0.0))

    def _engagement(self, article: StoredArticle) -> float:
        engagement_raw = float((article.score_points or 0) + (article.comment_count or 0))
        if engagement_raw <= 0:
            return 0.0
        return float(min(math.log1p(engagement_raw) / math.log1p(500.0), 1.0))

    def _semantic_query(
        self, article: StoredArticle, query_vec: Optional[np.ndarray], embeddings: Dict[int, np.ndarray]
    ) -> float:
        if query_vec is None:
            return 0.0
        vec = embeddings.get(article.id)
        if vec is None:
            return 0.0
        return float(max(np.dot(vec, query_vec), 0.0))

    def _semantic_affinity(
        self, article: StoredArticle, centroid: Optional[np.ndarray], embeddings: Dict[int, np.ndarray]
    ) -> float:
        if centroid is None:
            return 0.0
        vec = embeddings.get(article.id)
        if vec is None:
            return 0.0
        return float(max(np.dot(vec, centroid), 0.0))

    # --- scoring ---

    def _score_one(
        self,
        article: StoredArticle,
        doc_idx: int,
        *,
        ctx: _RankContext,
        query_terms: List[str],
        query_vec: Optional[np.ndarray],
        tag: Optional[TagSpec],
        for_you: bool,
        user_ctx: Optional[UserContext],
    ) -> RankedArticle:
        recency = self._recency(article, now=ctx.now, tau_hours=ctx.tau_hours)
        source_authority = self.source_importance(article.source_id)
        corroboration = self._corroboration(article, ctx.cluster_stats)
        velocity = self._velocity(article, ctx.cluster_stats)
        salience = tfidf_salience(article.title, article.summary or "", ctx.idf)
        engagement = self._engagement(article)
        tag_quality = self._tag_match_quality(article, tag) if tag else 0.0

        query_lex = float(ctx.bm25[doc_idx]) if ctx.bm25 is not None else 0.0
        query_sem = self._semantic_query(article, query_vec, ctx.embeddings)
        has_query = bool(query_terms) or query_vec is not None

        source_bump = 0.0
        tag_bump = 0.0
        semantic_affinity = 0.0
        if for_you and user_ctx is not None:
            semantic_affinity = self._semantic_affinity(article, user_ctx.centroid, ctx.embeddings)
            source_bump = float(user_ctx.source_affinity.get(article.source_id, 0.0))
            if user_ctx.tag_affinity:
                tag_bump = self._best_user_tag_match(article, user_ctx.tag_affinity)

        if for_you:
            if has_query:
                score = (
                    0.24 * query_sem
                    + 0.18 * query_lex
                    + 0.14 * semantic_affinity
                    + 0.10 * recency
                    + 0.08 * corroboration
                    + 0.06 * salience
                    + 0.06 * source_authority
                    + 0.04 * velocity
                    + 0.04 * engagement
                    + 0.03 * tag_bump
                    + 0.02 * source_bump
                    + 0.01 * tag_quality
                )
            else:
                score = (
                    0.22 * semantic_affinity
                    + 0.16 * recency
                    + 0.14 * corroboration
                    + 0.12 * salience
                    + 0.10 * source_authority
                    + 0.08 * velocity
                    + 0.06 * engagement
                    + 0.06 * tag_bump
                    + 0.04 * source_bump
                    + 0.02 * tag_quality
                )
        else:
            if has_query:
                score = (
                    0.28 * query_sem
                    + 0.22 * query_lex
                    + 0.14 * recency
                    + 0.10 * source_authority
                    + 0.08 * salience
                    + 0.06 * corroboration
                    + 0.06 * engagement
                    + 0.04 * velocity
                    + 0.02 * tag_quality
                )
            else:
                score = (
                    0.22 * salience
                    + 0.20 * recency
                    + 0.18 * corroboration
                    + 0.14 * source_authority
                    + 0.12 * velocity
                    + 0.08 * engagement
                    + 0.06 * tag_quality
                )

        features = {
            "recency": round(recency, 4),
            "source_authority": round(source_authority, 4),
            "corroboration": round(corroboration, 4),
            "velocity": round(velocity, 4),
            "salience": round(salience, 4),
            "engagement": round(engagement, 4),
            "tag_quality": round(tag_quality, 4),
            "query_lex": round(query_lex, 4),
            "query_sem": round(query_sem, 4),
        }
        if for_you:
            features.update(
                {
                    "semantic_affinity": round(semantic_affinity, 4),
                    "source_affinity": round(source_bump, 4),
                    "tag_affinity": round(tag_bump, 4),
                }
            )
        return RankedArticle(article=article, score=round(float(score), 4), features=features)

    def _best_user_tag_match(self, article: StoredArticle, tag_affinity: Dict[str, float]) -> float:
        best = 0.0
        for tag_id, weight in tag_affinity.items():
            spec = self.tag_registry.get(tag_id)
            if spec and self._article_matches_tag(article, spec):
                best = max(best, float(weight))
        return best

    # --- MMR diversification ---

    def _diversify_mmr(
        self,
        ranked: List[RankedArticle],
        *,
        embeddings: Dict[int, np.ndarray],
        limit: int,
        lambda_mmr: float = DEFAULT_MMR_LAMBDA,
    ) -> List[RankedArticle]:
        if len(ranked) <= limit:
            return ranked
        # Operate on a top-N pool to keep this cheap.
        pool_size = max(limit * MMR_POOL_MULTIPLIER, limit + 5)
        pool = ranked[:pool_size]
        if not embeddings:
            return pool[:limit]

        selected: List[RankedArticle] = []
        remaining = list(pool)
        # Pre-fetch each pool member's embedding (may be None).
        vec_for: Dict[int, Optional[np.ndarray]] = {
            r.article.id: embeddings.get(r.article.id) for r in pool
        }

        while remaining and len(selected) < limit:
            if not selected:
                pick = remaining.pop(0)
                selected.append(pick)
                continue
            best_idx = 0
            best_mmr = -math.inf
            for i, candidate in enumerate(remaining):
                cand_vec = vec_for.get(candidate.article.id)
                max_sim = 0.0
                if cand_vec is not None:
                    for chosen in selected:
                        chosen_vec = vec_for.get(chosen.article.id)
                        if chosen_vec is None:
                            continue
                        sim = float(np.dot(cand_vec, chosen_vec))
                        if sim > max_sim:
                            max_sim = sim
                mmr = lambda_mmr * candidate.score - (1.0 - lambda_mmr) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i
            selected.append(remaining.pop(best_idx))
        return selected

    # --- public entry points ---

    def rank_discover(
        self,
        *,
        query: str = "",
        query_vec: Optional[np.ndarray] = None,
        sources: Optional[Iterable[str]] = None,
        tag: Optional[TagSpec] = None,
        limit: int = 20,
        hours_back: int = 72,
        candidate_pool: int = 400,
    ) -> List[RankedArticle]:
        articles = self._candidates(
            sources=sources, hours_back=hours_back, tag=tag, candidate_pool=candidate_pool
        )
        if not articles:
            return []

        query_terms = tokenize(query) if query else []
        ctx = self._build_context(
            articles=articles, query_terms=query_terms, query_vec=query_vec, hours_back=hours_back
        )

        scored = [
            self._score_one(
                article,
                idx,
                ctx=ctx,
                query_terms=query_terms,
                query_vec=query_vec,
                tag=tag,
                for_you=False,
                user_ctx=None,
            )
            for idx, article in enumerate(ctx.articles)
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return self._diversify_mmr(scored, embeddings=ctx.embeddings, limit=limit)

    def rank_for_you(
        self,
        *,
        user_ctx: UserContext,
        query: str = "",
        query_vec: Optional[np.ndarray] = None,
        sources: Optional[Iterable[str]] = None,
        tag: Optional[TagSpec] = None,
        limit: int = 20,
        hours_back: int = 72,
        candidate_pool: int = 400,
    ) -> List[RankedArticle]:
        articles = self._candidates(
            sources=sources, hours_back=hours_back, tag=tag, candidate_pool=candidate_pool
        )
        articles = [a for a in articles if a.id not in user_ctx.hidden_ids]
        if not articles:
            return []

        query_terms = tokenize(query) if query else []
        ctx = self._build_context(
            articles=articles, query_terms=query_terms, query_vec=query_vec, hours_back=hours_back
        )

        scored = [
            self._score_one(
                article,
                idx,
                ctx=ctx,
                query_terms=query_terms,
                query_vec=query_vec,
                tag=tag,
                for_you=True,
                user_ctx=user_ctx,
            )
            for idx, article in enumerate(ctx.articles)
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return self._diversify_mmr(scored, embeddings=ctx.embeddings, limit=limit)

    def rank(
        self,
        *,
        mode: str = "discover",
        user_ctx: Optional[UserContext] = None,
        **kwargs,
    ) -> List[RankedArticle]:
        if mode == "for_you" and user_ctx is not None:
            return self.rank_for_you(user_ctx=user_ctx, **kwargs)
        return self.rank_discover(**kwargs)
