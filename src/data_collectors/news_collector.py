"""News aggregation helpers for the Herald web UI."""
import datetime as dt
import html
from html.parser import HTMLParser
import logging
import math
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
ANTHROPIC_DATE_RE = re.compile(
    r"(?P<date>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})\s*(?P<body>.+)"
)
ANTHROPIC_CATEGORY_RE = re.compile(
    r"^(?:Announcements|Alignment Science|Company|Economic Research|Education|Policy|Product|Research|Societal Impacts|"
    r"Responsibility|Responsibility & Safety|Safety)\s*"
)


class _LinkTextParser(HTMLParser):
    """Collect anchor text and href values from source listing pages."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: List[Dict[str, str]] = []
        self._current_href: Optional[str] = None
        self._text_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag != "a" or self._current_href is not None:
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href:
            self._current_href = href
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return

        text = " ".join(" ".join(self._text_parts).split())
        if text:
            self.links.append({"href": self._current_href, "text": html.unescape(text)})
        self._current_href = None
        self._text_parts = []


class NewsCollector:
    """Collects and lightly ranks current-events items from public sources."""

    ALL_SOURCE_IDS = [
        "hackernews",
        "lobsters",
        "reddit-programming",
        "reddit-technology",
        "techcrunch",
        "openai-news",
        "anthropic-news",
        "google-blog",
        "google-developers",
        "google-research",
        "google-deepmind",
        "nvidia-blog",
        "nvidia-news",
        "nvidia-generative-ai",
        "nvidia-developer",
        "huggingface-blog",
        "microsoft-ai",
        "x",
    ]
    SOURCE_IMPORTANCE = {
        "openai-news": 0.88,
        "anthropic-news": 0.86,
        "google-deepmind": 0.86,
        "google-research": 0.82,
        "nvidia-news": 0.8,
        "microsoft-ai": 0.78,
        "nvidia-generative-ai": 0.76,
        "google-blog": 0.74,
        "google-developers": 0.72,
        "nvidia-blog": 0.72,
        "nvidia-developer": 0.68,
        "techcrunch": 0.66,
        "huggingface-blog": 0.64,
        "hackernews": 0.62,
        "reddit-technology": 0.58,
        "reddit-programming": 0.56,
        "lobsters": 0.54,
        "x": 0.5,
    }
    IMPORTANCE_TERMS = {
        "regulation": 1.0,
        "policy": 0.9,
        "lawsuit": 1.0,
        "court": 0.75,
        "ban": 0.8,
        "security": 0.85,
        "breach": 1.0,
        "vulnerability": 0.9,
        "outage": 0.9,
        "acquires": 0.95,
        "acquisition": 0.95,
        "merger": 0.85,
        "funding": 0.8,
        "ipo": 0.9,
        "earnings": 0.75,
        "layoffs": 0.8,
        "launches": 0.85,
        "launch": 0.85,
        "releases": 0.8,
        "release": 0.8,
        "announces": 0.7,
        "model": 0.65,
        "benchmark": 0.7,
        "frontier": 0.75,
        "research": 0.6,
        "chip": 0.7,
        "gpu": 0.7,
        "datacenter": 0.72,
        "robot": 0.65,
        "agent": 0.62,
        "open-source": 0.72,
        "open": 0.38,
        "source": 0.38,
        "safety": 0.72,
        "alignment": 0.7,
    }
    FEED_SOURCES = {
        "openai-news": ("https://openai.com/news/rss.xml", "OpenAI News"),
        "google-blog": ("https://blog.google/rss/", "Google Blog"),
        "google-developers": ("https://developers.googleblog.com/feeds/posts/default?alt=rss", "Google Developers Blog"),
        "google-research": ("https://research.google/blog/rss/", "Google Research Blog"),
        "google-deepmind": ("https://deepmind.google/blog/rss.xml", "Google DeepMind Blog"),
        "nvidia-blog": ("https://feeds.feedburner.com/nvidiablog", "NVIDIA Blog"),
        "nvidia-news": ("https://nvidianews.nvidia.com/all-news.xml", "NVIDIA Newsroom"),
        "nvidia-generative-ai": ("https://nvidianews.nvidia.com/cats/generative_al.xml", "NVIDIA Generative AI"),
        "nvidia-developer": ("https://developer.nvidia.com/blog/feed/", "NVIDIA Developer Blog"),
        "huggingface-blog": ("https://huggingface.co/blog/feed.xml", "Hugging Face Blog"),
        "microsoft-ai": ("https://blogs.microsoft.com/ai/feed/", "Microsoft AI Blog"),
    }

    def __init__(
        self,
        config: Optional[ConfigLoader] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or ConfigLoader()
        self.session = session or requests.Session()
        self.timeout = float(self.config.get("news.request_timeout_seconds", 8.0))
        self.default_sources = list(
            self.config.get(
                "news.default_sources",
                self.ALL_SOURCE_IDS,
            )
        )
        self.max_items_per_source = int(self.config.get("news.max_items_per_source", 30))

    def collect(
        self,
        query: str = "",
        sources: Optional[Iterable[str]] = None,
        limit: int = 20,
        hours_back: int = 72,
    ) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, int]]:
        """Fetch and rank items from the requested sources."""
        selected_sources = list(sources or self.default_sources)
        normalized_query = query.strip()
        unavailable_sources: List[str] = []
        source_counts: Dict[str, int] = {}
        items: List[Dict[str, Any]] = []

        for source_name in selected_sources:
            fetcher = getattr(self, f"_fetch_{source_name.replace('-', '_')}", None)
            if fetcher is None and source_name not in self.FEED_SOURCES:
                unavailable_sources.append(source_name)
                continue

            try:
                if fetcher is not None:
                    source_items = fetcher(normalized_query, hours_back)
                else:
                    source_items = self._fetch_named_feed(source_name, normalized_query, hours_back)
            except Exception as exc:
                logger.warning("Failed to fetch %s news: %s", source_name, exc)
                unavailable_sources.append(source_name)
                continue

            source_counts[source_name] = len(source_items)
            items.extend(source_items)

        ranked = []
        seen_urls = set()
        for item in items:
            url = item.get("url")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            ranked.append(item)

        self._annotate_cross_source_signals(ranked)
        for item in ranked:
            item["score"] = self._score_item(item, normalized_query)

        ranked.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return ranked[:limit], unavailable_sources, source_counts

    def _fetch_hackernews(self, query: str, hours_back: int) -> List[Dict[str, Any]]:
        now = dt.datetime.now(dt.timezone.utc)
        if query:
            payload = self._get_json(
                "https://hn.algolia.com/api/v1/search_by_date",
                {"query": query, "tags": "story", "hitsPerPage": self.max_items_per_source},
            )
            hits = payload.get("hits", [])
        else:
            payload = self._get_json(
                "https://hn.algolia.com/api/v1/search",
                {"tags": "front_page", "hitsPerPage": self.max_items_per_source},
            )
            hits = payload.get("hits", [])

        items = []
        for hit in hits:
            published = self._parse_datetime(hit.get("created_at"))
            if not self._within_hours(published, hours_back, now):
                continue
            item = {
                "title": hit.get("title") or hit.get("story_title") or "Untitled",
                "summary": hit.get("story_text") or hit.get("comment_text") or "",
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "published": self._to_iso(published),
                "author": hit.get("author"),
                "source": "hackernews",
                "source_label": "Hacker News",
                "score_points": hit.get("points"),
                "comment_count": hit.get("num_comments"),
                "tags": ["front-page"] if not query else self._tokenize(query),
                "raw_item": hit,
            }
            if query and not self._matches_query(item, query):
                continue
            items.append(item)
        return items

    def _fetch_lobsters(self, query: str, hours_back: int) -> List[Dict[str, Any]]:
        feed = self._get_text("https://lobste.rs/rss")
        parsed = self._parse_feed(feed, default_source="lobsters", default_label="Lobsters")
        return self._post_process_feed_items(parsed, query, hours_back)

    def _fetch_reddit_programming(self, query: str, hours_back: int) -> List[Dict[str, Any]]:
        feed = self._get_text("https://www.reddit.com/r/programming/.rss")
        parsed = self._parse_feed(feed, default_source="reddit-programming", default_label="Reddit /r/programming")
        return self._post_process_feed_items(parsed, query, hours_back)

    def _fetch_reddit_technology(self, query: str, hours_back: int) -> List[Dict[str, Any]]:
        feed = self._get_text("https://www.reddit.com/r/technology/.rss")
        parsed = self._parse_feed(feed, default_source="reddit-technology", default_label="Reddit /r/technology")
        return self._post_process_feed_items(parsed, query, hours_back)

    def _fetch_techcrunch(self, query: str, hours_back: int) -> List[Dict[str, Any]]:
        feed = self._get_text("https://techcrunch.com/feed/")
        parsed = self._parse_feed(feed, default_source="techcrunch", default_label="TechCrunch")
        return self._post_process_feed_items(parsed, query, hours_back)

    def _fetch_named_feed(self, source_name: str, query: str, hours_back: int) -> List[Dict[str, Any]]:
        url, label = self.FEED_SOURCES[source_name]
        feed = self._get_text(url)
        parsed = self._parse_feed(feed, default_source=source_name, default_label=label)
        return self._post_process_feed_items(parsed, query, hours_back)

    def _fetch_anthropic_news(self, query: str, hours_back: int) -> List[Dict[str, Any]]:
        page = self._get_text("https://www.anthropic.com/news")
        parsed = self._parse_anthropic_news_page(page)
        return self._post_process_feed_items(parsed, query, hours_back)

    def _fetch_x(self, query: str, hours_back: int) -> List[Dict[str, Any]]:
        template = os.getenv("HERALD_X_RSS_SEARCH_URL") if query else os.getenv("HERALD_X_RSS_LATEST_URL")
        if not template:
            raise RuntimeError("X feed is not configured")

        url = template.format(query=urllib.parse.quote_plus(query))
        feed = self._get_text(url)
        parsed = self._parse_feed(feed, default_source="x", default_label="X")
        return self._post_process_feed_items(parsed, query, hours_back)

    def _post_process_feed_items(
        self,
        items: List[Dict[str, Any]],
        query: str,
        hours_back: int,
    ) -> List[Dict[str, Any]]:
        now = dt.datetime.now(dt.timezone.utc)
        filtered = []
        for item in items[: self.max_items_per_source]:
            published = self._parse_datetime(item.get("published"))
            if not self._within_hours(published, hours_back, now):
                continue
            item["published"] = self._to_iso(published)
            if query and not self._matches_query(item, query):
                continue
            filtered.append(item)
        return filtered

    def _get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = self.session.get(
            url,
            params=params,
            timeout=self.timeout,
            headers={"User-Agent": "herald-news-ui/0.1"},
        )
        response.raise_for_status()
        return response.json()

    def _get_text(self, url: str) -> str:
        response = self.session.get(
            url,
            timeout=self.timeout,
            headers={"User-Agent": "herald-news-ui/0.1"},
        )
        response.raise_for_status()
        return response.text

    def _parse_feed(
        self,
        xml_text: str,
        default_source: str,
        default_label: str,
    ) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_text)
        items: List[Dict[str, Any]] = []

        channel = root.find("channel")
        if channel is not None:
            for node in channel.findall("item"):
                items.append(
                    {
                        "title": self._child_text(node, "title") or "Untitled",
                        "summary": self._child_text(node, "description") or "",
                        "url": self._child_text(node, "link") or self._url_guid(node),
                        "published": self._child_text(node, "pubDate"),
                        "author": self._child_text(node, "author") or self._child_text(node, "{http://purl.org/dc/elements/1.1/}creator"),
                        "source": default_source,
                        "source_label": default_label,
                        "tags": [category.text for category in node.findall("category") if category.text],
                        "raw_item": {"guid": self._child_text(node, "guid")},
                    }
                )
            return items

        for entry in root.findall("atom:entry", ATOM_NS):
            link = ""
            for link_node in entry.findall("atom:link", ATOM_NS):
                rel = link_node.attrib.get("rel", "alternate")
                if rel == "alternate":
                    link = link_node.attrib.get("href", "")
                    break

            author = ""
            author_node = entry.find("atom:author/atom:name", ATOM_NS)
            if author_node is not None and author_node.text:
                author = author_node.text

            items.append(
                {
                    "title": self._child_text(entry, "atom:title", ATOM_NS) or "Untitled",
                    "summary": (
                        self._child_text(entry, "atom:summary", ATOM_NS)
                        or self._child_text(entry, "atom:content", ATOM_NS)
                        or ""
                    ),
                    "url": link,
                    "published": (
                        self._child_text(entry, "atom:published", ATOM_NS)
                        or self._child_text(entry, "atom:updated", ATOM_NS)
                    ),
                    "author": author or None,
                    "source": default_source,
                    "source_label": default_label,
                    "tags": [
                        category.attrib.get("term")
                        for category in entry.findall("atom:category", ATOM_NS)
                        if category.attrib.get("term")
                    ],
                    "raw_item": {"id": self._child_text(entry, "atom:id", ATOM_NS)},
                }
            )

        return items

    def _parse_anthropic_news_page(self, html_text: str) -> List[Dict[str, Any]]:
        parser = _LinkTextParser()
        parser.feed(html_text)

        items: List[Dict[str, Any]] = []
        seen_urls = set()
        for link in parser.links:
            href = link["href"]
            if href == "/news" or not (href.startswith("/news/") or href.startswith("https://www.anthropic.com/news/")):
                continue

            url = urllib.parse.urljoin("https://www.anthropic.com", href)
            if url in seen_urls:
                continue

            text = link["text"]
            match = ANTHROPIC_DATE_RE.search(text)
            if not match:
                continue

            published = match.group("date")
            title = match.group("body").strip()
            title = ANTHROPIC_CATEGORY_RE.sub("", title).strip()
            if not title:
                continue

            seen_urls.add(url)
            items.append(
                {
                    "title": title,
                    "summary": "",
                    "url": url,
                    "published": published,
                    "author": None,
                    "source": "anthropic-news",
                    "source_label": "Anthropic News",
                    "tags": [],
                    "raw_item": {"href": href},
                }
            )

        return items

    @staticmethod
    def _child_text(node: ET.Element, selector: str, namespaces: Optional[Dict[str, str]] = None) -> Optional[str]:
        child = node.find(selector, namespaces or {})
        if child is None or child.text is None:
            return None
        return child.text.strip()

    @staticmethod
    def _url_guid(node: ET.Element) -> Optional[str]:
        guid = NewsCollector._child_text(node, "guid")
        if guid and guid.startswith(("http://", "https://")):
            return guid
        return None

    @staticmethod
    def _tokenize(value: str) -> List[str]:
        return TOKEN_RE.findall(value.lower())

    def _matches_query(self, item: Dict[str, Any], query: str) -> bool:
        query_terms = set(self._tokenize(query))
        if not query_terms:
            return True

        haystack = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("summary", "")),
                str(item.get("url", "")),
                " ".join(item.get("tags", [])),
            ]
        ).lower()
        haystack_terms = set(self._tokenize(haystack))
        return bool(query_terms & haystack_terms)

    def _annotate_cross_source_signals(self, items: List[Dict[str, Any]]) -> None:
        token_sets = [set(self._tokenize(str(item.get("title", "")))) for item in items]
        for index, item in enumerate(items):
            item_source = item.get("source")
            item_tokens = token_sets[index]
            matched_sources = set()
            if len(item_tokens) < 3:
                item["cross_source_count"] = 0
                continue

            for other_index, other in enumerate(items):
                if other_index == index or other.get("source") == item_source:
                    continue

                other_tokens = token_sets[other_index]
                if len(other_tokens) < 3:
                    continue

                overlap = len(item_tokens & other_tokens)
                union = len(item_tokens | other_tokens)
                if union and overlap / union >= 0.32:
                    matched_sources.add(str(other.get("source", "")))

            item["cross_source_count"] = len(matched_sources)

    def _importance_language_score(self, item: Dict[str, Any]) -> float:
        text = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("summary", "")),
                " ".join(item.get("tags", [])),
            ]
        ).lower()
        tokens = set(self._tokenize(text))
        phrase_score = 0.0
        if "open source" in text:
            phrase_score += self.IMPORTANCE_TERMS["open-source"]
        if "data center" in text:
            phrase_score += self.IMPORTANCE_TERMS["datacenter"]

        token_score = sum(weight for token, weight in self.IMPORTANCE_TERMS.items() if token in tokens)
        return min((token_score + phrase_score) / 4.0, 1.0)

    def _score_item(self, item: Dict[str, Any], query: str) -> float:
        published = self._parse_datetime(item.get("published"))
        age_hours = 168.0
        if published is not None:
            age_seconds = max((dt.datetime.now(dt.timezone.utc) - published).total_seconds(), 0.0)
            age_hours = age_seconds / 3600.0

        recency_score = math.exp(-age_hours / 48.0)
        engagement_raw = float((item.get("score_points") or 0) + (item.get("comment_count") or 0))
        engagement_score = min(math.log1p(engagement_raw) / math.log1p(500.0), 1.0) if engagement_raw else 0.0
        source_score = self.SOURCE_IMPORTANCE.get(str(item.get("source", "")), 0.5)
        importance_score = self._importance_language_score(item)
        cross_source_score = min(float(item.get("cross_source_count") or 0) / 3.0, 1.0)

        query_overlap = 0.0
        query_terms = set(self._tokenize(query))
        if query_terms:
            haystack_terms = set(
                self._tokenize(
                    " ".join(
                        [
                            str(item.get("title", "")),
                            str(item.get("summary", "")),
                            " ".join(item.get("tags", [])),
                        ]
                    )
                )
            )
            if haystack_terms:
                query_overlap = len(query_terms & haystack_terms) / len(query_terms)

        if query_terms:
            return round(
                (query_overlap * 0.52)
                + (recency_score * 0.2)
                + (engagement_score * 0.12)
                + (source_score * 0.08)
                + (importance_score * 0.06)
                + (cross_source_score * 0.02),
                4,
            )

        return round(
            (importance_score * 0.32)
            + (recency_score * 0.28)
            + (source_score * 0.18)
            + (engagement_score * 0.14)
            + (cross_source_score * 0.08),
            4,
        )

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[dt.datetime]:
        if value is None:
            return None
        if isinstance(value, dt.datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=dt.timezone.utc)
            return value.astimezone(dt.timezone.utc)

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

    @staticmethod
    def _within_hours(
        published: Optional[dt.datetime],
        hours_back: int,
        now: dt.datetime,
    ) -> bool:
        if published is None:
            return True
        return published >= now - dt.timedelta(hours=hours_back)

    @staticmethod
    def _to_iso(value: Optional[dt.datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.astimezone(dt.timezone.utc).isoformat()
