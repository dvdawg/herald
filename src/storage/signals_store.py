"""User signal persistence — clicks, views, hides."""
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Dict, Iterable, List, Optional

import numpy as np

from src.storage.db import get_db


SIGNAL_WEIGHTS = {
    "click": 1.0,
    "dwell": 0.5,
    "view": 0.1,
    "hide": -1.5,
    "like": 1.5,
}


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class SignalsStore:
    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self.conn = conn or get_db()

    def record(self, user_id: str, article_id: int, kind: str, weight: Optional[float] = None) -> None:
        w = weight if weight is not None else SIGNAL_WEIGHTS.get(kind, 1.0)
        self.conn.execute(
            "INSERT INTO signals(user_id, article_id, kind, weight, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, article_id, kind, w, _now_iso()),
        )

    def recent_signals(
        self,
        user_id: str,
        *,
        days_back: int = 30,
        kinds: Optional[Iterable[str]] = None,
    ) -> List[sqlite3.Row]:
        cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_back)).isoformat()
        params: List = [user_id, cutoff]
        clause = ""
        if kinds:
            kinds_list = list(kinds)
            placeholders = ",".join("?" for _ in kinds_list)
            clause = f" AND kind IN ({placeholders})"
            params.extend(kinds_list)
        return self.conn.execute(
            f"SELECT article_id, kind, weight, created_at FROM signals "
            f"WHERE user_id = ? AND created_at >= ?{clause} ORDER BY created_at DESC",
            params,
        ).fetchall()

    def hidden_article_ids(self, user_id: str, days_back: int = 30) -> List[int]:
        rows = self.recent_signals(user_id, days_back=days_back, kinds=["hide"])
        return [r["article_id"] for r in rows]

    def affinity_centroid(
        self,
        user_id: str,
        embeddings: Dict[int, np.ndarray],
        *,
        days_back: int = 30,
    ) -> Optional[np.ndarray]:
        """Weighted centroid of recent positive-signal embeddings."""
        signals = self.recent_signals(user_id, days_back=days_back)
        weighted_sum: Optional[np.ndarray] = None
        total_weight = 0.0
        for row in signals:
            vec = embeddings.get(row["article_id"])
            if vec is None:
                continue
            w = float(row["weight"])
            if w <= 0:
                continue
            weighted_sum = vec * w if weighted_sum is None else weighted_sum + vec * w
            total_weight += w
        if weighted_sum is None or total_weight <= 0:
            return None
        centroid = weighted_sum / total_weight
        norm = np.linalg.norm(centroid)
        if norm == 0:
            return None
        return centroid / norm

    def positive_article_ids(self, user_id: str, days_back: int = 30) -> List[int]:
        rows = self.recent_signals(user_id, days_back=days_back)
        return [r["article_id"] for r in rows if float(r["weight"]) > 0]

    def source_affinity(self, user_id: str, days_back: int = 30) -> Dict[str, float]:
        """Weighted source counts → normalized importance bumps."""
        rows = self.conn.execute(
            """
            SELECT a.source_id as source_id, SUM(s.weight) as total
            FROM signals s
            JOIN articles a ON a.id = s.article_id
            WHERE s.user_id = ? AND s.created_at >= ?
            GROUP BY a.source_id
            """,
            (
                user_id,
                (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_back)).isoformat(),
            ),
        ).fetchall()
        if not rows:
            return {}
        totals = {r["source_id"]: float(r["total"]) for r in rows if r["total"] is not None}
        max_total = max((abs(v) for v in totals.values()), default=1.0)
        return {sid: v / max_total for sid, v in totals.items()}
