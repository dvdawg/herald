"""Smoke tests for the news storage + ingest pipeline."""
import datetime as dt
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.data_collectors.adapters.base import FetchedItem
from src.storage import get_db
from src.storage.article_store import ArticleStore, canonicalize_url
from src.storage.signals_store import SignalsStore


@pytest.fixture
def store(monkeypatch):
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "test.db"
    monkeypatch.setenv("HERALD_DB_PATH", str(db_path))
    # Ensure fresh schema init per test
    import src.storage.db as db_module
    db_module._initialized_paths.clear()
    conn = get_db(db_path)
    yield ArticleStore(conn)
    conn.close()
    tmp.cleanup()


def _make_item(source_id="hackernews", url="https://example.com/post", title="Title"):
    return FetchedItem(
        source_id=source_id,
        title=title,
        url=url,
        summary="Some summary text",
        published=dt.datetime.now(dt.timezone.utc),
    )


def test_canonicalize_strips_tracking_and_www():
    url = "https://www.example.com/article/?utm_source=x&id=42"
    assert canonicalize_url(url) == "https://example.com/article?id=42"


def test_upsert_dedups_by_canonical_url(store):
    item_a = _make_item(url="https://example.com/post?utm_source=twitter")
    item_b = _make_item(url="https://www.example.com/post/")
    id_a, created_a = store.upsert_article(item_a)
    id_b, created_b = store.upsert_article(item_b)
    assert created_a is True
    assert created_b is False
    assert id_a == id_b


def test_dedup_across_sources_by_title_hash(store):
    item_a = _make_item(url="https://a.example.com/x", source_id="hackernews", title="Big launch today")
    item_b = _make_item(url="https://b.example.com/y", source_id="hackernews", title="Big Launch Today")
    id_a, _ = store.upsert_article(item_a)
    id_b, created_b = store.upsert_article(item_b)
    assert created_b is False
    assert id_a == id_b


def test_embeddings_round_trip(store):
    item = _make_item()
    article_id, _ = store.upsert_article(item)
    vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    store.save_embedding(article_id, vec, "test-model")
    loaded = store.load_embedding(article_id)
    assert loaded is not None
    np.testing.assert_allclose(loaded, vec)


def test_signal_centroid(store):
    signals = SignalsStore(store.conn)
    a1, _ = store.upsert_article(_make_item(url="https://example.com/1"))
    a2, _ = store.upsert_article(_make_item(url="https://example.com/2", title="Other"))
    vec1 = np.array([1.0, 0.0], dtype=np.float32)
    vec2 = np.array([0.0, 1.0], dtype=np.float32)
    embeddings = {a1: vec1, a2: vec2}
    signals.record("user-1", a1, "click")
    signals.record("user-1", a2, "like")
    centroid = signals.affinity_centroid("user-1", embeddings)
    assert centroid is not None
    assert centroid.shape == (2,)
    assert abs(float(np.linalg.norm(centroid)) - 1.0) < 1e-5


def test_recent_filters_by_hours(store):
    fresh = _make_item(url="https://example.com/fresh")
    store.upsert_article(fresh)
    stale = _make_item(url="https://example.com/stale")
    store.upsert_article(stale)
    # Force one record into the past.
    store.conn.execute(
        "UPDATE articles SET published_at = ? WHERE url_canonical LIKE ?",
        ((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)).isoformat(), "%stale"),
    )
    recent = store.recent(hours_back=24)
    urls = {a.url for a in recent}
    assert "https://example.com/fresh" in urls
    assert "https://example.com/stale" not in urls
