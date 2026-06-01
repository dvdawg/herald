"""Tests for the paper ranker."""
import datetime as dt
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.data_collectors.adapters.base import FetchedItem
from src.data_collectors.sources import SourceRegistry, SourceSpec
from src.ranking_engine.paper_ranker import PaperRanker
from src.storage import get_db
from src.storage.article_store import ArticleStore


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


def _make_item(source_id, url, title, summary="", days_old=1):
    return FetchedItem(
        source_id=source_id,
        title=title,
        url=url,
        summary=summary,
        published=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_old),
        tags=[],
    )


def _registry():
    return SourceRegistry([
        SourceSpec(id="arxiv", kind="rss", label="arXiv", importance=0.66, category="paper"),
        SourceSpec(id="hn", kind="hackernews", label="HN", importance=0.7, category="news"),
    ])


def test_search_returns_only_paper_sources(store):
    store.upsert_article(_make_item("arxiv", "https://e/a", "Diffusion transformers", "Paper on diffusion"))
    store.upsert_article(_make_item("hn", "https://e/b", "Diffusion transformers post", "News article"))
    ranker = PaperRanker(store=store, registry=_registry())
    results = ranker.search(query="diffusion", days_back=7)
    sources = {r.article.source_id for r in results}
    assert sources == {"arxiv"}


def test_query_relevance_dominates_paper_ranking(store):
    store.upsert_article(_make_item("arxiv", "https://e/a", "Paper on retrieval-augmented generation"))
    store.upsert_article(_make_item("arxiv", "https://e/b", "Paper on protein folding"))
    ranker = PaperRanker(store=store, registry=_registry())
    results = ranker.search(query="retrieval augmented", days_back=7)
    assert results[0].article.title.startswith("Paper on retrieval-augmented")


def test_browsing_mode_falls_back_to_recency(store):
    store.upsert_article(_make_item("arxiv", "https://e/a", "Older paper", days_old=20))
    store.upsert_article(_make_item("arxiv", "https://e/b", "Newer paper", days_old=1))
    ranker = PaperRanker(store=store, registry=_registry())
    results = ranker.search(query="", days_back=60)
    assert results[0].article.title == "Newer paper"
