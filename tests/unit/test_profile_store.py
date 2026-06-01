"""Tests for the persisted user-preference profile cache."""
import datetime as dt
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.data_collectors.adapters.base import FetchedItem
from src.storage import get_db
from src.storage.article_store import ArticleStore
from src.storage.profile_store import UserProfileStore
from src.storage.signals_store import SignalsStore


@pytest.fixture
def conn(monkeypatch):
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "test.db"
    monkeypatch.setenv("HERALD_DB_PATH", str(db_path))
    import src.storage.db as db_module
    db_module._initialized_paths.clear()
    c = get_db(db_path)
    yield c
    c.close()
    tmp.cleanup()


def _seed_article(store, url="https://e/a"):
    item = FetchedItem(
        source_id="hn",
        title="A title",
        url=url,
        summary="",
        published=dt.datetime.now(dt.timezone.utc),
    )
    return store.upsert_article(item)[0]


def test_save_and_round_trip(conn):
    profiles = UserProfileStore(conn=conn)
    vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    profiles.save(
        user_id="u1",
        centroid=vec,
        source_affinity={"hn": 1.0},
        tag_affinity={"ai": 0.8},
        signal_count=3,
        last_signal_at="2026-01-01T00:00:00+00:00",
    )
    profile = profiles.get("u1")
    assert profile is not None
    np.testing.assert_allclose(profile.centroid, vec)
    assert profile.source_affinity == {"hn": 1.0}
    assert profile.tag_affinity == {"ai": 0.8}
    assert profile.signal_count == 3
    assert profile.has_profile is True


def test_freshness_invalidates_on_new_signal(conn):
    store = ArticleStore(conn)
    signals = SignalsStore(conn)
    profiles = UserProfileStore(conn=conn)
    aid = _seed_article(store)
    signals.record("u1", aid, "click")
    last = profiles.latest_signal_at("u1")
    profiles.save(
        user_id="u1",
        centroid=None,
        source_affinity={},
        tag_affinity={},
        signal_count=1,
        last_signal_at=last,
    )
    assert profiles.is_fresh("u1") is True
    signals.record("u1", aid, "like")
    assert profiles.is_fresh("u1") is False


def test_invalidate_clears_last_signal(conn):
    profiles = UserProfileStore(conn=conn)
    profiles.save(
        user_id="u1",
        centroid=None,
        source_affinity={},
        tag_affinity={},
        signal_count=1,
        last_signal_at="2026-01-01T00:00:00+00:00",
    )
    profiles.invalidate("u1")
    profile = profiles.get("u1")
    assert profile.last_signal_at is None
