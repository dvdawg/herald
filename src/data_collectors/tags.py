"""Curated tag taxonomy loaded from config/tags.yaml.

A tag matches when any keyword appears in the article's title+summary
(case-insensitive substring), or any source_tag matches the article's
emitted tags.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TagSpec:
    id: str
    label: str
    description: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    source_tags: List[str] = field(default_factory=list)

    def matches(self, *, text_lower: str, source_tags_lower: set) -> bool:
        for kw in self.keywords:
            if kw and kw in text_lower:
                return True
        if self.source_tags and source_tags_lower:
            for tag in self.source_tags:
                if tag.lower() in source_tags_lower:
                    return True
        return False


class TagRegistry:
    def __init__(self, tags: Iterable[TagSpec]):
        self._tags: Dict[str, TagSpec] = {t.id: t for t in tags}

    @classmethod
    def from_yaml(cls, path: Optional[Path] = None) -> "TagRegistry":
        if path is None:
            path = Path(__file__).resolve().parents[2] / "config" / "tags.yaml"
        with open(path, "r") as fh:
            data = yaml.safe_load(fh) or {}
        entries = []
        for raw in data.get("tags", []):
            entries.append(
                TagSpec(
                    id=raw["id"],
                    label=raw.get("label", raw["id"]),
                    description=raw.get("description"),
                    keywords=[k.lower() for k in raw.get("keywords", [])],
                    source_tags=list(raw.get("source_tags", [])),
                )
            )
        logger.info("Loaded %d tags from %s", len(entries), path)
        return cls(entries)

    def all(self) -> List[TagSpec]:
        return list(self._tags.values())

    def get(self, tag_id: str) -> Optional[TagSpec]:
        return self._tags.get(tag_id)

    def ids(self) -> List[str]:
        return list(self._tags.keys())
