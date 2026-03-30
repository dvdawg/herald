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
