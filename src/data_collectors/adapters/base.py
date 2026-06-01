"""Shared adapter types."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Protocol

import requests

DEFAULT_TIMEOUT = 8.0
DEFAULT_USER_AGENT = "herald-news-collector/0.2"


@dataclass
class FetchedItem:
    """Raw fetched item before storage normalization."""

    source_id: str
    title: str
    url: str
    summary: str = ""
    published: Optional[dt.datetime] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    score_points: Optional[int] = None
    comment_count: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class Fetcher(Protocol):
    """Interface implemented by every adapter."""

    def fetch(self, spec, session: requests.Session, timeout: float) -> List[FetchedItem]:
        ...


def parse_datetime(value: Any) -> Optional[dt.datetime]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    candidates = [text]
    if text.endswith("Z"):
        candidates.insert(0, text.replace("Z", "+00:00"))
    for candidate in candidates:
        try:
            parsed = dt.datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc)
        except ValueError:
            continue
    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def http_get(session: requests.Session, url: str, *, timeout: float, params: Optional[Dict] = None) -> requests.Response:
    response = session.get(
        url,
        params=params,
        timeout=timeout,
        headers={"User-Agent": DEFAULT_USER_AGENT},
    )
    response.raise_for_status()
    return response
