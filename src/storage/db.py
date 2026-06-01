"""SQLite connection management and schema initialization."""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional

_lock = threading.Lock()
_initialized_paths = set()


def get_db_path() -> Path:
    env = os.getenv("HERALD_DB_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data" / "herald.db"


def get_db(path: Optional[Path] = None) -> sqlite3.Connection:
    db_path = Path(path) if path else get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    init_schema(conn, db_path)
    return conn


def init_schema(conn: sqlite3.Connection, db_path: Path) -> None:
    with _lock:
        key = str(db_path.resolve())
        if key in _initialized_paths:
            return
        conn.executescript(SCHEMA_SQL)
        _initialized_paths.add(key)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    url_canonical TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    author TEXT,
    published_at TEXT,
    discovered_at TEXT NOT NULL,
    tags_json TEXT,
    score_points INTEGER,
    comment_count INTEGER,
    extra_json TEXT,
    cluster_id INTEGER,
    title_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_canonical ON articles(url_canonical);
CREATE INDEX IF NOT EXISTS idx_articles_title_hash ON articles(title_hash);

CREATE TABLE IF NOT EXISTS embeddings (
    article_id INTEGER PRIMARY KEY,
    vector BLOB NOT NULL,
    dim INTEGER NOT NULL,
    model TEXT NOT NULL,
    FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    centroid BLOB NOT NULL,
    dim INTEGER NOT NULL,
    member_count INTEGER NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    article_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_signals_user ON signals(user_id);
CREATE INDEX IF NOT EXISTS idx_signals_article ON signals(article_id);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    fetched_count INTEGER DEFAULT 0,
    new_count INTEGER DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    centroid BLOB,
    dim INTEGER,
    source_affinity_json TEXT,
    tag_affinity_json TEXT,
    signal_count INTEGER NOT NULL DEFAULT 0,
    last_signal_at TEXT,
    updated_at TEXT NOT NULL
);
"""
