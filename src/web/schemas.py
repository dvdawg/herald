"""Pydantic schemas for the Herald test web API."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Payload for running Herald search and ranking."""

    query: str = Field(..., min_length=1, description="Search query")
    max_results: Optional[int] = Field(default=20, ge=1, le=200)
    top_k: Optional[int] = Field(default=10, ge=1, le=200)
    process_metadata: Optional[bool] = None
    process_text: Optional[bool] = None
    weights: Optional[Dict[str, float]] = None
    date_from: Optional[str] = Field(default=None, description="Start of date range (YYYY-MM-DD or YYYY-MM)")
    date_to: Optional[str] = Field(default=None, description="End of date range (YYYY-MM-DD or YYYY-MM)")


class RankedArticle(BaseModel):
    """API-safe representation of a ranked article."""

    rank: int
    score: float
    title: str
    arxiv_id: Optional[str]
    published: Optional[str]
    authors: List[str]
    summary: Optional[str]
    pdf_url: Optional[str]
    citation_count: Optional[int]
    ranking_features: Optional[Dict[str, float]] = None
    ranking_explanation: Optional[List[str]] = None
    raw_article: Dict[str, Any]


class RunDebug(BaseModel):
    """Debug metadata returned with each run."""

    total_results: int
    returned_results: int
    total_ms: int
    params: Dict[str, Any]


class RunResponse(BaseModel):
    """Successful API response for /api/run."""

    status: str = "ok"
    query: str
    results: List[RankedArticle]
    debug: RunDebug


class NewsRequest(BaseModel):
    """Payload for running Herald news aggregation."""

    query: Optional[str] = Field(default="", description="Optional topic or keyword filter")
    sources: Optional[List[str]] = Field(default=None, description="Optional list of source ids")
    limit: Optional[int] = Field(default=20, ge=1, le=100)
    hours_back: Optional[int] = Field(default=72, ge=1, le=720)


class NewsItem(BaseModel):
    """API-safe representation of an aggregated news item."""

    rank: int
    score: float
    title: str
    summary: Optional[str]
    url: Optional[str]
    source: str
    source_label: str
    author: Optional[str]
    published: Optional[str]
    tags: List[str]
    score_points: Optional[int]
    comment_count: Optional[int]
    raw_item: Dict[str, Any]


class NewsDebug(BaseModel):
    """Debug metadata returned with each news request."""

    total_candidates: int
    returned_results: int
    total_ms: int
    source_counts: Dict[str, int]
    unavailable_sources: List[str]
    params: Dict[str, Any]


class NewsResponse(BaseModel):
    """Successful API response for /api/news."""

    status: str = "ok"
    query: str
    results: List[NewsItem]
    debug: NewsDebug
