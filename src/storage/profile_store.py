"""Cached user-preference profiles (centroid + source/tag affinities).

The cache is invalidated whenever a fresh signal has arrived since
`last_signal_at`. Cheap to read; recomputed lazily by the news service.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from src.storage.db import get_db


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass
class UserProfile:
    user_id: str
    centroid: Optional[np.ndarray]
    source_affinity: Dict[str, float]
    tag_affinity: Dict[str, float]
    signal_count: int
    last_signal_at: Optional[str]
    updated_at: Optional[str]

    @property
    def has_profile(self) -> bool:
        return self.signal_count > 0 and (
            self.centroid is not None or bool(self.source_affinity) or bool(self.tag_affinity)
        )


class UserProfileStore:
    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self.conn = conn or get_db()

    def latest_signal_at(self, user_id: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT MAX(created_at) AS ts FROM signals WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["ts"] if row and row["ts"] else None

    def signal_count(self, user_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM signals WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(row["n"]) if row else 0

    def get(self, user_id: str) -> Optional[UserProfile]:
        row = self.conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return None
        centroid = None
        if row["centroid"] is not None and row["dim"]:
            centroid = np.frombuffer(row["centroid"], dtype=np.float32, count=row["dim"])
        return UserProfile(
            user_id=row["user_id"],
            centroid=centroid,
            source_affinity=json.loads(row["source_affinity_json"] or "{}"),
            tag_affinity=json.loads(row["tag_affinity_json"] or "{}"),
            signal_count=int(row["signal_count"] or 0),
            last_signal_at=row["last_signal_at"],
            updated_at=row["updated_at"],
        )

    def is_fresh(self, user_id: str) -> bool:
        profile = self.get(user_id)
        if not profile:
            return False
        latest = self.latest_signal_at(user_id)
        if latest is None:
            return True
        return profile.last_signal_at == latest

    def save(
        self,
        user_id: str,
        *,
        centroid: Optional[np.ndarray],
        source_affinity: Dict[str, float],
        tag_affinity: Dict[str, float],
        signal_count: int,
        last_signal_at: Optional[str],
    ) -> None:
        vec_bytes = None
        dim = None
        if centroid is not None:
            vec = np.asarray(centroid, dtype=np.float32).reshape(-1)
            vec_bytes = vec.tobytes()
            dim = int(vec.shape[0])
        self.conn.execute(
            """
            INSERT INTO user_profiles
                (user_id, centroid, dim, source_affinity_json, tag_affinity_json,
                 signal_count, last_signal_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                centroid = excluded.centroid,
                dim = excluded.dim,
                source_affinity_json = excluded.source_affinity_json,
                tag_affinity_json = excluded.tag_affinity_json,
                signal_count = excluded.signal_count,
                last_signal_at = excluded.last_signal_at,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                vec_bytes,
                dim,
                json.dumps(source_affinity or {}),
                json.dumps(tag_affinity or {}),
                int(signal_count),
                last_signal_at,
                _now_iso(),
            ),
        )

    def invalidate(self, user_id: str) -> None:
        """Force the next read to recompute by clearing last_signal_at."""
        self.conn.execute(
            "UPDATE user_profiles SET last_signal_at = NULL WHERE user_id = ?",
            (user_id,),
        )
