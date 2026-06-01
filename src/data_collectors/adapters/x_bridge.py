"""X (Twitter) via RSS bridge — opt-in through env vars."""
from __future__ import annotations

import os
from typing import List

import requests

from src.data_collectors.adapters.base import FetchedItem
from src.data_collectors.adapters.rss import RSSFetcher


class XBridgeFetcher:
    def __init__(self):
        self._rss = RSSFetcher()

    def fetch(self, spec, session: requests.Session, timeout: float) -> List[FetchedItem]:
        url = os.getenv("HERALD_X_RSS_LATEST_URL")
        if not url:
            raise RuntimeError("X feed not configured (set HERALD_X_RSS_LATEST_URL)")
        # Reuse RSS parser with a synthetic spec.
        class _Spec:
            id = spec.id
            url_ = url
            @property
            def url(self_inner):
                return url
        return self._rss.fetch(_Spec(), session, timeout)
