"""Source registry loaded from config/sources.yaml."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceSpec:
    id: str
    kind: str
    label: str
    importance: float = 0.5
    url: Optional[str] = None
    options: Optional[Dict] = None
    category: str = "news"  # "news" | "paper"


class SourceRegistry:
    """In-memory registry of news sources."""

    def __init__(self, sources: Iterable[SourceSpec]):
        self._sources: Dict[str, SourceSpec] = {s.id: s for s in sources}

    @classmethod
    def from_yaml(cls, path: Optional[Path] = None) -> "SourceRegistry":
        if path is None:
            path = Path(__file__).resolve().parents[2] / "config" / "sources.yaml"
        with open(path, "r") as fh:
            data = yaml.safe_load(fh) or {}
        entries = []
        for raw in data.get("sources", []):
            entries.append(
                SourceSpec(
                    id=raw["id"],
                    kind=raw["kind"],
                    label=raw.get("label", raw["id"]),
                    importance=float(raw.get("importance", 0.5)),
                    url=raw.get("url"),
                    options=raw.get("options"),
                    category=raw.get("category", "news"),
                )
            )
        logger.info("Loaded %d sources from %s", len(entries), path)
        return cls(entries)

    def all(self) -> List[SourceSpec]:
        return list(self._sources.values())

    def get(self, source_id: str) -> Optional[SourceSpec]:
        return self._sources.get(source_id)

    def ids(self) -> List[str]:
        return list(self._sources.keys())

    def select(self, ids: Optional[Iterable[str]]) -> List[SourceSpec]:
        if not ids:
            return self.all()
        out = []
        for sid in ids:
            spec = self._sources.get(sid)
            if spec:
                out.append(spec)
        return out

    def by_category(self, category: str) -> List[SourceSpec]:
        return [s for s in self._sources.values() if s.category == category]

    def ids_by_category(self, category: str) -> List[str]:
        return [s.id for s in self._sources.values() if s.category == category]
