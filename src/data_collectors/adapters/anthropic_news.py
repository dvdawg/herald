"""Anthropic news HTML adapter (no RSS feed)."""
from __future__ import annotations

import html
import re
import urllib.parse
from html.parser import HTMLParser
from typing import List, Optional, Tuple

import requests

from src.data_collectors.adapters.base import FetchedItem, http_get, parse_datetime

DATE_RE = re.compile(
    r"(?P<date>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})\s*(?P<body>.+)"
)
CATEGORY_RE = re.compile(
    r"^(?:Announcements|Alignment Science|Company|Economic Research|Education|Policy|Product|Research|Societal Impacts|"
    r"Responsibility|Responsibility & Safety|Safety)\s*"
)


class _LinkTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._href: Optional[str] = None
        self._parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a" or self._href is not None:
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or self._href is None:
            return
        text = " ".join(" ".join(self._parts).split())
        if text:
            self.links.append((self._href, html.unescape(text)))
        self._href = None
        self._parts = []


class AnthropicNewsFetcher:
    def fetch(self, spec, session: requests.Session, timeout: float) -> List[FetchedItem]:
        url = spec.url or "https://www.anthropic.com/news"
        response = http_get(session, url, timeout=timeout)
        parser = _LinkTextParser()
        parser.feed(response.text)
        items: List[FetchedItem] = []
        seen = set()
        for href, text in parser.links:
            if href == "/news" or not (href.startswith("/news/") or href.startswith("https://www.anthropic.com/news/")):
                continue
            full_url = urllib.parse.urljoin("https://www.anthropic.com", href)
            if full_url in seen:
                continue
            match = DATE_RE.search(text)
            if not match:
                continue
            title = CATEGORY_RE.sub("", match.group("body")).strip()
            if not title:
                continue
            seen.add(full_url)
            items.append(
                FetchedItem(
                    source_id=spec.id,
                    title=title,
                    url=full_url,
                    summary="",
                    published=parse_datetime(match.group("date")),
                )
            )
        return items
