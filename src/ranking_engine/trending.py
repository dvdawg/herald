"""Greedy embedding-based clustering for trending detection."""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.storage.article_store import ArticleStore, StoredArticle

logger = logging.getLogger(__name__)


@dataclass
class TrendingCluster:
    cluster_id: int
    representative: StoredArticle
    article_count: int
    sources: List[str]
    members: List[StoredArticle]
    score: float


class TrendingDetector:
    """Maintains incremental clusters and surfaces those that span multiple sources."""

    def __init__(self, store: Optional[ArticleStore] = None, similarity_threshold: float = 0.72):
        self.store = store or ArticleStore()
        self.similarity_threshold = similarity_threshold

    def assign_clusters(self, batch_size: int = 256) -> int:
        """Greedy assignment of unclustered articles to existing or new clusters."""
        unclustered = self.store.conn.execute(
            """
            SELECT a.id FROM articles a
            JOIN embeddings e ON e.article_id = a.id
            WHERE a.cluster_id IS NULL
            ORDER BY a.discovered_at DESC
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()
        if not unclustered:
            return 0

        cluster_records = self.store.all_clusters()
        cluster_centroids: Dict[int, np.ndarray] = {cid: vec for cid, vec, _ in cluster_records}
        cluster_counts: Dict[int, int] = {cid: count for cid, _, count in cluster_records}

        assigned = 0
        for row in unclustered:
            article_id = row["id"]
            vec = self.store.load_embedding(article_id)
            if vec is None:
                continue

            best_id: Optional[int] = None
            best_sim = -1.0
            for cid, centroid in cluster_centroids.items():
                sim = float(np.dot(vec, centroid))
                if sim > best_sim:
                    best_sim = sim
                    best_id = cid

            if best_id is not None and best_sim >= self.similarity_threshold:
                count = cluster_counts[best_id]
                new_centroid = (cluster_centroids[best_id] * count + vec) / (count + 1)
                norm = np.linalg.norm(new_centroid)
                if norm:
                    new_centroid = new_centroid / norm
                cluster_centroids[best_id] = new_centroid
                cluster_counts[best_id] = count + 1
                self.store.set_cluster(article_id, best_id)
                self.store.update_cluster(best_id, new_centroid, count + 1)
            else:
                new_id = self.store.create_cluster(vec)
                cluster_centroids[new_id] = vec
                cluster_counts[new_id] = 1
                self.store.set_cluster(article_id, new_id)
            assigned += 1

        logger.info("Assigned %d articles to clusters", assigned)
        return assigned

    def top_trending(
        self,
        hours_back: int = 24,
        min_sources: int = 2,
        limit: int = 10,
        sources: Optional[List[str]] = None,
    ) -> List[TrendingCluster]:
        cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_back)).isoformat()
        params: List = [cutoff]
        source_clause = ""
        if sources:
            placeholders = ",".join("?" for _ in sources)
            source_clause = f" AND source_id IN ({placeholders})"
            params.extend(sources)
        params.extend([min_sources, limit * 2])
        rows = self.store.conn.execute(
            f"""
            SELECT cluster_id, COUNT(DISTINCT source_id) AS source_count, COUNT(*) AS article_count
            FROM articles
            WHERE cluster_id IS NOT NULL AND COALESCE(published_at, discovered_at) >= ?
            {source_clause}
            GROUP BY cluster_id
            HAVING source_count >= ?
            ORDER BY source_count DESC, article_count DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

        clusters: List[TrendingCluster] = []
        for row in rows:
            cluster_id = row["cluster_id"]
            members = self.store.cluster_articles(cluster_id, limit=6)
            if not members:
                continue
            sources = sorted({m.source_id for m in members})
            score = float(row["source_count"]) + 0.1 * float(row["article_count"])
            clusters.append(
                TrendingCluster(
                    cluster_id=cluster_id,
                    representative=members[0],
                    article_count=row["article_count"],
                    sources=sources,
                    members=members,
                    score=score,
                )
            )
        clusters.sort(key=lambda c: c.score, reverse=True)
        return clusters[:limit]
