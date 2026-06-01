"""Article persistence and similarity helpers."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from src.storage.db import get_db


TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "ref", "ref_src"}


def canonicalize_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query_pairs = [
        (k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS
    ]
    query = urllib.parse.urlencode(sorted(query_pairs))
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme.lower() or "https", netloc, path, query, ""))


def title_fingerprint(title: str) -> str:
    normalized = " ".join(title.lower().split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass
class StoredArticle:
    id: int
    url: str
    url_canonical: str
    source_id: str
    title: str
    summary: str
    author: Optional[str]
    published_at: Optional[str]
    discovered_at: str
    tags: List[str]
    score_points: Optional[int]
    comment_count: Optional[int]
    extra: Dict[str, Any]
    cluster_id: Optional[int]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "StoredArticle":
        return cls(
            id=row["id"],
            url=row["url"],
            url_canonical=row["url_canonical"],
            source_id=row["source_id"],
            title=row["title"],
            summary=row["summary"] or "",
            author=row["author"],
            published_at=row["published_at"],
            discovered_at=row["discovered_at"],
            tags=json.loads(row["tags_json"] or "[]"),
            score_points=row["score_points"],
            comment_count=row["comment_count"],
            extra=json.loads(row["extra_json"] or "{}"),
            cluster_id=row["cluster_id"],
        )


class ArticleStore:
    """High-level access to the articles + embeddings + clusters tables."""

    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self.conn = conn or get_db()

    def upsert_article(self, item) -> Tuple[Optional[int], bool]:
        """Insert if new. Returns (article_id, created)."""
        canonical = canonicalize_url(item.url)
        title_hash = title_fingerprint(item.title)
        cursor = self.conn.execute(
            "SELECT id FROM articles WHERE url_canonical = ? OR (source_id = ? AND title_hash = ?) LIMIT 1",
            (canonical, item.source_id, title_hash),
        )
        existing = cursor.fetchone()
        if existing:
            return existing["id"], False

        published_iso = item.published.isoformat() if item.published else None
        cursor = self.conn.execute(
            """
            INSERT INTO articles
            (url, url_canonical, source_id, title, summary, author, published_at, discovered_at,
             tags_json, score_points, comment_count, extra_json, title_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.url,
                canonical,
                item.source_id,
                item.title,
                item.summary,
                item.author,
                published_iso,
                _now_iso(),
                json.dumps(item.tags or []),
                item.score_points,
                item.comment_count,
                json.dumps(item.extra or {}),
                title_hash,
            ),
        )
        return cursor.lastrowid, True

    def save_embedding(self, article_id: int, vector: np.ndarray, model: str) -> None:
        vec = np.asarray(vector, dtype=np.float32).reshape(-1)
        self.conn.execute(
            "INSERT OR REPLACE INTO embeddings(article_id, vector, dim, model) VALUES (?, ?, ?, ?)",
            (article_id, vec.tobytes(), int(vec.shape[0]), model),
        )

    def load_embedding(self, article_id: int) -> Optional[np.ndarray]:
        row = self.conn.execute(
            "SELECT vector, dim FROM embeddings WHERE article_id = ?", (article_id,)
        ).fetchone()
        if not row:
            return None
        return np.frombuffer(row["vector"], dtype=np.float32, count=row["dim"])

    def articles_missing_embedding(self, limit: int = 256) -> List[StoredArticle]:
        rows = self.conn.execute(
            """
            SELECT a.* FROM articles a
            LEFT JOIN embeddings e ON e.article_id = a.id
            WHERE e.article_id IS NULL
            ORDER BY a.discovered_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [StoredArticle.from_row(r) for r in rows]

    def recent(
        self,
        *,
        hours_back: int = 72,
        sources: Optional[Iterable[str]] = None,
        limit: int = 500,
    ) -> List[StoredArticle]:
        params: List[Any] = []
        clauses = []
        if hours_back:
            cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_back)).isoformat()
            clauses.append("COALESCE(published_at, discovered_at) >= ?")
            params.append(cutoff)
        if sources:
            placeholders = ",".join("?" for _ in sources)
            clauses.append(f"source_id IN ({placeholders})")
            params.extend(sources)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT * FROM articles {where} ORDER BY COALESCE(published_at, discovered_at) DESC LIMIT ?",
            params,
        ).fetchall()
        return [StoredArticle.from_row(r) for r in rows]

    def by_ids(self, ids: Iterable[int]) -> List[StoredArticle]:
        ids = list(ids)
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.conn.execute(
            f"SELECT * FROM articles WHERE id IN ({placeholders})", ids
        ).fetchall()
        return [StoredArticle.from_row(r) for r in rows]

    def load_embeddings_for(self, ids: Iterable[int]) -> Dict[int, np.ndarray]:
        ids = list(ids)
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        rows = self.conn.execute(
            f"SELECT article_id, vector, dim FROM embeddings WHERE article_id IN ({placeholders})",
            ids,
        ).fetchall()
        return {
            r["article_id"]: np.frombuffer(r["vector"], dtype=np.float32, count=r["dim"])
            for r in rows
        }

    def set_cluster(self, article_id: int, cluster_id: int) -> None:
        self.conn.execute("UPDATE articles SET cluster_id = ? WHERE id = ?", (cluster_id, article_id))

    def create_cluster(self, centroid: np.ndarray) -> int:
        vec = np.asarray(centroid, dtype=np.float32).reshape(-1)
        cursor = self.conn.execute(
            "INSERT INTO clusters(centroid, dim, member_count, last_updated) VALUES (?, ?, 1, ?)",
            (vec.tobytes(), int(vec.shape[0]), _now_iso()),
        )
        return cursor.lastrowid

    def update_cluster(self, cluster_id: int, centroid: np.ndarray, member_count: int) -> None:
        vec = np.asarray(centroid, dtype=np.float32).reshape(-1)
        self.conn.execute(
            "UPDATE clusters SET centroid = ?, dim = ?, member_count = ?, last_updated = ? WHERE id = ?",
            (vec.tobytes(), int(vec.shape[0]), member_count, _now_iso(), cluster_id),
        )

    def all_clusters(self) -> List[Tuple[int, np.ndarray, int]]:
        rows = self.conn.execute(
            "SELECT id, centroid, dim, member_count FROM clusters"
        ).fetchall()
        return [
            (r["id"], np.frombuffer(r["centroid"], dtype=np.float32, count=r["dim"]), r["member_count"])
            for r in rows
        ]

    def cluster_breakdown(self, cluster_id: int) -> Dict[str, Any]:
        sources_row = self.conn.execute(
            "SELECT DISTINCT source_id FROM articles WHERE cluster_id = ?",
            (cluster_id,),
        ).fetchall()
        count_row = self.conn.execute(
            "SELECT COUNT(*) as n FROM articles WHERE cluster_id = ?",
            (cluster_id,),
        ).fetchone()
        return {
            "cluster_id": cluster_id,
            "sources": [r["source_id"] for r in sources_row],
            "article_count": count_row["n"] if count_row else 0,
        }

    def cluster_articles(self, cluster_id: int, limit: int = 5) -> List[StoredArticle]:
        rows = self.conn.execute(
            "SELECT * FROM articles WHERE cluster_id = ? ORDER BY COALESCE(published_at, discovered_at) DESC LIMIT ?",
            (cluster_id, limit),
        ).fetchall()
        return [StoredArticle.from_row(r) for r in rows]

    def record_ingest_run(
        self,
        source_id: str,
        fetched: int,
        new: int,
        started_at: dt.datetime,
        error: Optional[str] = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO ingest_runs(source_id, started_at, finished_at, fetched_count, new_count, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                started_at.isoformat(),
                _now_iso(),
                fetched,
                new,
                error,
            ),
        )

    def total_articles(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as n FROM articles").fetchone()
        return row["n"] if row else 0

    def source_counts(self) -> Dict[str, int]:
        rows = self.conn.execute(
            "SELECT source_id, COUNT(*) as n FROM articles GROUP BY source_id"
        ).fetchall()
        return {r["source_id"]: r["n"] for r in rows}
