"""Service adapter for Herald news endpoints, backed by the article store."""
from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

from src.data_collectors.sources import SourceRegistry
from src.data_collectors.tags import TagRegistry, TagSpec
from src.data_processors.news_embedder import NewsEmbedder
from src.ranking_engine.news_ranker import NewsRanker, RankedArticle, UserContext
from src.ranking_engine.paper_ranker import PaperRanker, RankedPaper
from src.ranking_engine.trending import TrendingDetector
from src.storage.article_store import ArticleStore, StoredArticle
from src.storage.profile_store import UserProfile, UserProfileStore
from src.storage.signals_store import SignalsStore
from src.web.schemas import (
    FeedResponse,
    MeResponse,
    NewsDebug,
    NewsItem,
    NewsMode,
    NewsRequest,
    NewsResponse,
    NewsSource,
    NewsTag,
    PaperItem,
    PaperRequest,
    PaperResponse,
    SourceListResponse,
    TagListResponse,
    TopSource,
    TopTag,
    TrendingCluster,
    TrendingResponse,
)

logger = logging.getLogger(__name__)

MIN_SIGNALS_FOR_YOU = 3
WINDOW_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}


class HeraldNewsService:
    def __init__(
        self,
        store: Optional[ArticleStore] = None,
        signals: Optional[SignalsStore] = None,
        profiles: Optional[UserProfileStore] = None,
        ranker: Optional[NewsRanker] = None,
        embedder: Optional[NewsEmbedder] = None,
        trending: Optional[TrendingDetector] = None,
        registry: Optional[SourceRegistry] = None,
        tag_registry: Optional[TagRegistry] = None,
    ):
        self.store = store or ArticleStore()
        self.signals = signals or SignalsStore()
        self.profiles = profiles or UserProfileStore(conn=self.store.conn)
        self.registry = registry or SourceRegistry.from_yaml()
        self.tag_registry = tag_registry or TagRegistry.from_yaml()
        self.ranker = ranker or NewsRanker(
            store=self.store, registry=self.registry, tag_registry=self.tag_registry
        )
        self.embedder = embedder or NewsEmbedder(store=self.store)
        self.trending = trending or TrendingDetector(store=self.store)
        self._news_source_ids = self.registry.ids_by_category("news")
        self._paper_source_ids = self.registry.ids_by_category("paper")
        self.paper_ranker = PaperRanker(store=self.store, registry=self.registry)

    # --- shape helpers ---

    def _source_label(self, source_id: str) -> str:
        spec = self.registry.get(source_id)
        return spec.label if spec else source_id

    def _normalize(self, ranked: RankedArticle, rank: int) -> NewsItem:
        article = ranked.article
        return NewsItem(
            rank=rank,
            article_id=article.id,
            score=ranked.score,
            title=article.title,
            summary=article.summary or None,
            url=article.url,
            source=article.source_id,
            source_label=self._source_label(article.source_id),
            author=article.author,
            published=article.published_at,
            tags=article.tags,
            score_points=article.score_points,
            comment_count=article.comment_count,
            cluster_id=article.cluster_id,
            features=ranked.features,
        )

    def _stored_to_item(self, article: StoredArticle, rank: int) -> NewsItem:
        return NewsItem(
            rank=rank,
            article_id=article.id,
            score=0.0,
            title=article.title,
            summary=article.summary or None,
            url=article.url,
            source=article.source_id,
            source_label=self._source_label(article.source_id),
            author=article.author,
            published=article.published_at,
            tags=article.tags,
            score_points=article.score_points,
            comment_count=article.comment_count,
            cluster_id=article.cluster_id,
        )

    # --- preference cache ---

    def _build_user_ctx(self, user_id: str) -> UserContext:
        profile = self._get_or_refresh_profile(user_id)
        hidden = set(self.signals.hidden_article_ids(user_id))
        return UserContext(
            user_id=user_id,
            centroid=profile.centroid if profile else None,
            source_affinity=profile.source_affinity if profile else {},
            tag_affinity=profile.tag_affinity if profile else {},
            hidden_ids=hidden,
        )

    def _get_or_refresh_profile(self, user_id: str) -> Optional[UserProfile]:
        if self.profiles.is_fresh(user_id):
            return self.profiles.get(user_id)
        return self._recompute_profile(user_id)

    def _recompute_profile(self, user_id: str) -> Optional[UserProfile]:
        signal_count = self.profiles.signal_count(user_id)
        last_signal_at = self.profiles.latest_signal_at(user_id)
        if signal_count == 0:
            self.profiles.save(
                user_id,
                centroid=None,
                source_affinity={},
                tag_affinity={},
                signal_count=0,
                last_signal_at=last_signal_at,
            )
            return self.profiles.get(user_id)

        positive_ids = self.signals.positive_article_ids(user_id)
        embeddings = self.store.load_embeddings_for(positive_ids) if positive_ids else {}
        centroid = self.signals.affinity_centroid(user_id, embeddings)
        source_aff = self.signals.source_affinity(user_id)
        tag_aff = self._compute_tag_affinity(user_id, positive_ids)
        self.profiles.save(
            user_id,
            centroid=centroid,
            source_affinity=source_aff,
            tag_affinity=tag_aff,
            signal_count=signal_count,
            last_signal_at=last_signal_at,
        )
        return self.profiles.get(user_id)

    def _compute_tag_affinity(self, user_id: str, positive_ids: List[int]) -> Dict[str, float]:
        if not positive_ids:
            return {}
        articles = self.store.by_ids(positive_ids)
        counts: Dict[str, float] = {}
        for article in articles:
            text_lower = (article.title + " " + (article.summary or "")).lower()
            source_tags_lower = {t.lower() for t in (article.tags or [])}
            for tag in self.tag_registry.all():
                if tag.matches(text_lower=text_lower, source_tags_lower=source_tags_lower):
                    counts[tag.id] = counts.get(tag.id, 0.0) + 1.0
        if not counts:
            return {}
        peak = max(counts.values())
        return {tid: v / peak for tid, v in counts.items()}

    # --- mode resolution ---

    def _resolve_mode(self, requested: NewsMode, user_id: Optional[str]) -> tuple:
        """Returns (effective_mode, fell_back_flag, user_ctx_or_None)."""
        if requested != "for_you" or not user_id:
            return "discover", False, None
        signal_count = self.profiles.signal_count(user_id)
        if signal_count < MIN_SIGNALS_FOR_YOU:
            return "discover", True, None
        return "for_you", False, self._build_user_ctx(user_id)

    # --- main endpoints ---

    def run(self, payload: NewsRequest, user_id: Optional[str] = None) -> NewsResponse:
        started = time.perf_counter()
        query = (payload.query or "").strip()
        tag_spec = self._resolve_tag(payload.tag) if payload.tag else None
        query_vec = self._maybe_encode_query(query)

        mode_used, fell_back, user_ctx = self._resolve_mode(payload.mode, user_id)
        # Default to news-category sources only; paper sources surface via /api/papers/*.
        requested_sources = payload.sources or None
        sources = requested_sources if requested_sources else self._news_source_ids
        ranked = self._dispatch_rank(
            mode_used=mode_used,
            user_ctx=user_ctx,
            query=query,
            query_vec=query_vec,
            sources=sources,
            tag=tag_spec,
            limit=payload.limit or 20,
            hours_back=payload.hours_back or 72,
        )
        normalized = [self._normalize(item, idx + 1) for idx, item in enumerate(ranked)]
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        debug = NewsDebug(
            total_candidates=self.store.total_articles(),
            returned_results=len(normalized),
            total_ms=elapsed_ms,
            source_counts=self.store.source_counts(),
            unavailable_sources=[],
            mode_used=mode_used,
            fell_back_to_discover=fell_back,
            params={
                "query": payload.query,
                "limit": payload.limit,
                "hours_back": payload.hours_back,
                "sources": payload.sources,
                "tag": payload.tag,
                "requested_mode": payload.mode,
                "user_id": user_id,
                "used_semantic": query_vec is not None,
            },
        )
        return NewsResponse(query=query, mode=mode_used, results=normalized, debug=debug)

    def tag_feed(self, *, tag: str, window: str, limit: int, user_id: Optional[str]) -> FeedResponse:
        spec = self._resolve_tag(tag)
        if spec is None:
            raise KeyError(tag)
        hours_back = WINDOW_HOURS.get(window, 24)
        started = time.perf_counter()
        ranked = self.ranker.rank_discover(
            tag=spec,
            limit=limit,
            hours_back=hours_back,
            sources=self._news_source_ids,
        )
        normalized = [self._normalize(item, idx + 1) for idx, item in enumerate(ranked)]
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        debug = NewsDebug(
            total_candidates=self.store.total_articles(),
            returned_results=len(normalized),
            total_ms=elapsed_ms,
            source_counts=self.store.source_counts(),
            unavailable_sources=[],
            mode_used="discover",
            fell_back_to_discover=False,
            params={
                "tag": tag,
                "window": window,
                "hours_back": hours_back,
                "limit": limit,
                "user_id": user_id,
            },
        )
        return FeedResponse(tag=spec.id, window=window, results=normalized, debug=debug)

    def list_sources(self) -> SourceListResponse:
        # Surface only news-category sources in the news UI's source picker.
        return SourceListResponse(
            sources=[
                NewsSource(id=s.id, label=s.label, kind=s.kind, importance=s.importance)
                for s in self.registry.by_category("news")
            ]
        )

    def list_tags(self) -> TagListResponse:
        return TagListResponse(
            tags=[
                NewsTag(id=t.id, label=t.label, description=t.description)
                for t in self.tag_registry.all()
            ]
        )

    def trending_feed(self, hours_back: int = 24, min_sources: int = 2, limit: int = 10) -> TrendingResponse:
        clusters = self.trending.top_trending(
            hours_back=hours_back,
            min_sources=min_sources,
            limit=limit,
            sources=self._news_source_ids,
        )
        out: List[TrendingCluster] = []
        for cluster in clusters:
            members = [self._stored_to_item(member, idx + 1) for idx, member in enumerate(cluster.members)]
            out.append(
                TrendingCluster(
                    cluster_id=cluster.cluster_id,
                    score=cluster.score,
                    article_count=cluster.article_count,
                    sources=cluster.sources,
                    representative=members[0] if members else None,
                    members=members,
                )
            )
        return TrendingResponse(clusters=out)

    # --- paper search ---

    def search_papers(self, payload: PaperRequest) -> PaperResponse:
        started = time.perf_counter()
        query = (payload.query or "").strip()
        query_vec = self._maybe_encode_query(query)
        sources = payload.sources or None
        if sources:
            sources = [s for s in sources if s in self._paper_source_ids]
        ranked = self.paper_ranker.search(
            query=query,
            query_vec=query_vec,
            sources=sources,
            limit=payload.limit or 20,
            days_back=payload.days_back or 60,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        results = [
            PaperItem(
                rank=idx + 1,
                article_id=r.article.id,
                score=r.score,
                title=r.article.title,
                summary=r.article.summary or None,
                url=r.article.url,
                source=r.article.source_id,
                source_label=self._source_label(r.article.source_id),
                author=r.article.author,
                published=r.article.published_at,
                tags=r.article.tags,
                features=r.features,
            )
            for idx, r in enumerate(ranked)
        ]
        # total_candidates here = articles in the paper corpus seen so far.
        candidate_count = sum(
            self.store.source_counts().get(sid, 0) for sid in self._paper_source_ids
        )
        return PaperResponse(
            query=query, results=results, total_candidates=candidate_count, total_ms=elapsed_ms
        )

    def list_paper_sources(self) -> SourceListResponse:
        return SourceListResponse(
            sources=[
                NewsSource(id=s.id, label=s.label, kind=s.kind, importance=s.importance)
                for s in self.registry.by_category("paper")
            ]
        )

    def record_signal(self, user_id: str, article_id: int, kind: str) -> Dict[str, Any]:
        self.signals.record(user_id, article_id, kind)
        self.profiles.invalidate(user_id)
        return {"status": "ok"}

    def profile(self, user_id: str) -> MeResponse:
        profile = self._get_or_refresh_profile(user_id)
        if profile is None or not profile.has_profile:
            return MeResponse(
                user_id=user_id,
                has_profile=False,
                signal_count=profile.signal_count if profile else 0,
                updated_at=profile.updated_at if profile else None,
            )

        top_tags = [
            TopTag(
                id=tid,
                label=(self.tag_registry.get(tid).label if self.tag_registry.get(tid) else tid),
                weight=round(float(w), 3),
            )
            for tid, w in sorted(profile.tag_affinity.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ]
        top_sources = [
            TopSource(id=sid, label=self._source_label(sid), weight=round(float(w), 3))
            for sid, w in sorted(profile.source_affinity.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ]
        return MeResponse(
            user_id=user_id,
            has_profile=True,
            signal_count=profile.signal_count,
            top_tags=top_tags,
            top_sources=top_sources,
            updated_at=profile.updated_at,
        )

    # --- internals ---

    def _resolve_tag(self, tag_id: Optional[str]) -> Optional[TagSpec]:
        if not tag_id:
            return None
        return self.tag_registry.get(tag_id)

    def _maybe_encode_query(self, query: str) -> Optional[np.ndarray]:
        if not query:
            return None
        try:
            return self.embedder.encode_query(query)
        except Exception:
            logger.exception("Query embedding failed; falling back to lexical only")
            return None

    def _dispatch_rank(
        self,
        *,
        mode_used: NewsMode,
        user_ctx: Optional[UserContext],
        query: str,
        query_vec: Optional[np.ndarray],
        sources: Optional[List[str]],
        tag: Optional[TagSpec],
        limit: int,
        hours_back: int,
    ) -> List[RankedArticle]:
        if mode_used == "for_you" and user_ctx is not None:
            return self.ranker.rank_for_you(
                user_ctx=user_ctx,
                query=query,
                query_vec=query_vec,
                sources=sources,
                tag=tag,
                limit=limit,
                hours_back=hours_back,
            )
        return self.ranker.rank_discover(
            query=query,
            query_vec=query_vec,
            sources=sources,
            tag=tag,
            limit=limit,
            hours_back=hours_back,
        )
