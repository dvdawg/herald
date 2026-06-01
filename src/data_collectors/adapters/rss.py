"""Generic RSS/Atom adapter."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List

import requests

from src.data_collectors.adapters.base import FetchedItem, http_get, parse_datetime

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return HTML_TAG_RE.sub("", text or "").strip()


def _child_text(node: ET.Element, selector: str, namespaces=None) -> str:
    found = node.find(selector, namespaces or {})
    if found is None or found.text is None:
        return ""
    return found.text.strip()


class RSSFetcher:
    def fetch(self, spec, session: requests.Session, timeout: float) -> List[FetchedItem]:
        if not spec.url:
            raise ValueError(f"Source {spec.id} has no url")
        response = http_get(session, spec.url, timeout=timeout)
        text = response.text
        root = ET.fromstring(text)
        items: List[FetchedItem] = []

        channel = root.find("channel")
        if channel is not None:
            for node in channel.findall("item"):
                title = _child_text(node, "title") or "Untitled"
                link = _child_text(node, "link") or _child_text(node, "guid")
                if not link:
                    continue
                summary = _strip_html(_child_text(node, "description"))
                published = parse_datetime(_child_text(node, "pubDate"))
                author = _child_text(node, "author") or _child_text(node, "{http://purl.org/dc/elements/1.1/}creator") or None
                tags = [c.text for c in node.findall("category") if c.text]
                items.append(
                    FetchedItem(
                        source_id=spec.id,
                        title=title,
                        url=link,
                        summary=summary,
                        published=published,
                        author=author or None,
                        tags=tags,
                    )
                )
            return items

        for entry in root.findall("atom:entry", ATOM_NS):
            link = ""
            for link_node in entry.findall("atom:link", ATOM_NS):
                rel = link_node.attrib.get("rel", "alternate")
                if rel == "alternate":
                    link = link_node.attrib.get("href", "")
                    break
            if not link:
                continue
            title = _child_text(entry, "atom:title", ATOM_NS) or "Untitled"
            summary = _strip_html(
                _child_text(entry, "atom:summary", ATOM_NS)
                or _child_text(entry, "atom:content", ATOM_NS)
            )
            published = parse_datetime(
                _child_text(entry, "atom:published", ATOM_NS)
                or _child_text(entry, "atom:updated", ATOM_NS)
            )
            author_node = entry.find("atom:author/atom:name", ATOM_NS)
            author = author_node.text.strip() if author_node is not None and author_node.text else None
            tags = [c.attrib.get("term") for c in entry.findall("atom:category", ATOM_NS) if c.attrib.get("term")]
            items.append(
                FetchedItem(
                    source_id=spec.id,
                    title=title,
                    url=link,
                    summary=summary,
                    published=published,
                    author=author,
                    tags=tags,
                )
            )
        return items
