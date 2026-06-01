"""Tests for the discover/for_you ranker."""
import datetime as dt
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.data_collectors.adapters.base import FetchedItem
from src.data_collectors.sources import SourceRegistry, SourceSpec
from src.data_collectors.tags import TagRegistry, TagSpec
from src.ranking_engine.news_ranker import NewsRanker, UserContext
from src.storage import get_db
from src.storage.article_store import ArticleStore
from src.storage.signals_store import SignalsStore


@pytest.fixture
def store(monkeypatch):
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "test.db"
    monkeypatch.setenv("HERALD_DB_PATH", str(db_path))
    import src.storage.db as db_module
    db_module._initialized_paths.clear()
    conn = get_db(db_path)
    yield ArticleStore(conn)
    conn.close()
    tmp.cleanup()


def _make_item(source_id, url, title, summary="", tags=None, hours_old=1):
    return FetchedItem(
        source_id=source_id,
        title=title,
        url=url,
        summary=summary,
        published=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_old),
        tags=tags or [],
    )


def _registry():
    return SourceRegistry([
        SourceSpec(id="hn", kind="hackernews", label="HN", importance=0.7),
        SourceSpec(id="vrg", kind="rss", label="The Verge", importance=0.68),
    ])


def _tag_registry():
    return TagRegistry([
        TagSpec(id="ai", label="AI", keywords=["llm", "gpt"], source_tags=["ai"]),
        TagSpec(id="security", label="Security", keywords=["vulnerability", "breach"]),
    ])


def test_discover_orders_by_importance_and_recency(store):
    store.upsert_article(_make_item("hn", "https://e/a", "Major AI launch announced", "Big release", hours_old=1))
    store.upsert_article(_make_item("vrg", "https://e/b", "Local diner reopens", "Slow food news", hours_old=24))
    ranker = NewsRanker(store=store, registry=_registry(), tag_registry=_tag_registry())
    ranked = ranker.rank_discover(limit=5, hours_back=48)
    assert ranked[0].article.title == "Major AI launch announced"


def test_discover_filters_by_tag(store):
    store.upsert_article(_make_item("hn", "https://e/a", "GPT-5 rumors", hours_old=1))
    store.upsert_article(_make_item("hn", "https://e/b", "Local diner reopens", hours_old=1))
    ranker = NewsRanker(store=store, registry=_registry(), tag_registry=_tag_registry())
    ai_tag = ranker.tag_registry.get("ai")
    ranked = ranker.rank_discover(tag=ai_tag, hours_back=48)
    assert len(ranked) == 1
    assert "GPT" in ranked[0].article.title


def test_for_you_hides_user_hides(store):
    a1, _ = store.upsert_article(_make_item("hn", "https://e/a", "Story one", hours_old=1))
    a2, _ = store.upsert_article(_make_item("hn", "https://e/b", "Story two", hours_old=1))
    ranker = NewsRanker(store=store, registry=_registry(), tag_registry=_tag_registry())
    ctx = UserContext(
        user_id="u",
        centroid=None,
        source_affinity={},
        tag_affinity={},
        hidden_ids={a1},
    )
    ranked = ranker.rank_for_you(user_ctx=ctx, hours_back=48)
    ids = {r.article.id for r in ranked}
    assert a1 not in ids
    assert a2 in ids


def test_for_you_uses_tag_affinity(store):
    store.upsert_article(_make_item("hn", "https://e/a", "GPT model news", hours_old=2))
    store.upsert_article(_make_item("vrg", "https://e/b", "Local diner reopens", hours_old=1))
    ranker = NewsRanker(store=store, registry=_registry(), tag_registry=_tag_registry())
    ctx = UserContext(
        user_id="u",
        centroid=None,
        source_affinity={},
        tag_affinity={"ai": 1.0},
        hidden_ids=set(),
    )
    ranked = ranker.rank_for_you(user_ctx=ctx, hours_back=48)
    assert ranked[0].article.title == "GPT model news"


def test_query_overlap_lifts_matching_article(store):
    store.upsert_article(_make_item("hn", "https://e/a", "Kubernetes 1.30 released", hours_old=12))
    store.upsert_article(_make_item("vrg", "https://e/b", "Latest gadget review", hours_old=1))
    ranker = NewsRanker(store=store, registry=_registry(), tag_registry=_tag_registry())
    ranked = ranker.rank_discover(query="kubernetes", hours_back=48)
    assert ranked[0].article.title.startswith("Kubernetes")


def test_corroboration_rewards_multi_source_cluster(store):
    """Two sources covering the same story should outrank a single-source story."""
    a1, _ = store.upsert_article(_make_item("hn", "https://e/a", "OpenAI launches new model", hours_old=2))
    a2, _ = store.upsert_article(_make_item("vrg", "https://e/b", "OpenAI announces new model", hours_old=2))
    solo, _ = store.upsert_article(_make_item("hn", "https://e/c", "Different unrelated news", hours_old=1))
    # Simulate clustering: a1 + a2 share a cluster; solo gets its own.
    store.create_cluster_with_members(cluster_id=1, article_ids=[a1, a2]) if hasattr(
        store, "create_cluster_with_members"
    ) else None
    # Direct DB mutation since the store doesn't expose a "set cluster" helper.
    store.conn.execute("UPDATE articles SET cluster_id = 100 WHERE id IN (?, ?)", (a1, a2))
    store.conn.execute("UPDATE articles SET cluster_id = 101 WHERE id = ?", (solo,))

    ranker = NewsRanker(store=store, registry=_registry(), tag_registry=_tag_registry())
    ranked = ranker.rank_discover(limit=5, hours_back=48)
    # The clustered articles should outscore the solo one.
    by_id = {r.article.id: r for r in ranked}
    assert by_id[a1].features["corroboration"] > by_id[solo].features["corroboration"]


def test_velocity_rewards_recent_burst(store):
    """A cluster whose articles are all very recent should score velocity > 0."""
    burst1, _ = store.upsert_article(_make_item("hn", "https://e/x", "Breaking story", hours_old=0))
    burst2, _ = store.upsert_article(_make_item("vrg", "https://e/y", "Breaking story coverage", hours_old=0))
    store.conn.execute("UPDATE articles SET cluster_id = 200 WHERE id IN (?, ?)", (burst1, burst2))
    ranker = NewsRanker(store=store, registry=_registry(), tag_registry=_tag_registry())
    ranked = ranker.rank_discover(limit=5, hours_back=48)
    by_id = {r.article.id: r for r in ranked}
    assert by_id[burst1].features["velocity"] > 0


def test_mmr_drops_near_duplicates(store):
    """When two articles are semantically identical, MMR keeps one out of the top slots."""
    a1, _ = store.upsert_article(_make_item("hn", "https://e/a", "Big AI model launches", hours_old=1))
    a2, _ = store.upsert_article(_make_item("vrg", "https://e/b", "Major AI model debuts", hours_old=1))
    a3, _ = store.upsert_article(_make_item("vrg", "https://e/c", "Unrelated story about chips", hours_old=1))
    # Same embedding for a1 and a2 (perfectly correlated), different for a3.
    same = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    other = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    store.save_embedding(a1, same, "test-model")
    store.save_embedding(a2, same, "test-model")
    store.save_embedding(a3, other, "test-model")

    ranker = NewsRanker(store=store, registry=_registry(), tag_registry=_tag_registry())
    ranked = ranker.rank_discover(limit=2, hours_back=48)
    ids = [r.article.id for r in ranked]
    # MMR should pick exactly one of {a1, a2} plus a3, not both duplicates.
    assert a3 in ids
    assert (a1 in ids) ^ (a2 in ids)
