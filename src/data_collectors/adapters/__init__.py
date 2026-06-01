"""Fetcher adapters registered by source kind."""
from typing import Callable, Dict, List

from src.data_collectors.adapters.base import FetchedItem, Fetcher
from src.data_collectors.adapters.rss import RSSFetcher
from src.data_collectors.adapters.hackernews import HackerNewsFetcher
from src.data_collectors.adapters.anthropic_news import AnthropicNewsFetcher
from src.data_collectors.adapters.x_bridge import XBridgeFetcher

_REGISTRY: Dict[str, Fetcher] = {
    "rss": RSSFetcher(),
    "hackernews": HackerNewsFetcher(),
    "anthropic": AnthropicNewsFetcher(),
    "x-bridge": XBridgeFetcher(),
}


def get_fetcher(kind: str) -> Fetcher:
    fetcher = _REGISTRY.get(kind)
    if fetcher is None:
        raise KeyError(f"No adapter registered for kind={kind!r}")
    return fetcher


def register(kind: str, fetcher: Fetcher) -> None:
    _REGISTRY[kind] = fetcher


__all__ = ["FetchedItem", "Fetcher", "get_fetcher", "register"]
