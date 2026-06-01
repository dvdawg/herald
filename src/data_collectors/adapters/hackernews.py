"""Hacker News Algolia API adapter."""
from __future__ import annotations

from typing import List

import requests

from src.data_collectors.adapters.base import FetchedItem, http_get, parse_datetime


class HackerNewsFetcher:
    def fetch(self, spec, session: requests.Session, timeout: float) -> List[FetchedItem]:
        params = {"tags": "front_page", "hitsPerPage": 50}
        response = http_get(
            session,
            "https://hn.algolia.com/api/v1/search",
            timeout=timeout,
            params=params,
        )
        payload = response.json()
        hits = payload.get("hits", [])
        items = []
        for hit in hits:
            published = parse_datetime(hit.get("created_at"))
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            title = hit.get("title") or hit.get("story_title") or "Untitled"
            items.append(
                FetchedItem(
                    source_id=spec.id,
                    title=title,
                    url=url,
                    summary=(hit.get("story_text") or "") or (hit.get("comment_text") or ""),
                    published=published,
                    author=hit.get("author"),
                    tags=["front-page"],
                    score_points=hit.get("points"),
                    comment_count=hit.get("num_comments"),
                    extra={"object_id": hit.get("objectID")},
                )
            )
        return items
