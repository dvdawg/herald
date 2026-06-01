"""Pydantic schemas for the Herald web API."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# --- News pipeline ---


NewsMode = Literal["discover", "for_you"]


class NewsRequest(BaseModel):
    query: Optional[str] = Field(default="", description="Optional topic or keyword filter")
    sources: Optional[List[str]] = Field(default=None, description="Optional list of source ids")
    tag: Optional[str] = Field(default=None, description="Optional tag/topic filter id")
    mode: NewsMode = Field(default="discover", description="discover = importance + recency; for_you = preference-cached")
    limit: Optional[int] = Field(default=20, ge=1, le=100)
    hours_back: Optional[int] = Field(default=72, ge=1, le=720)


class NewsItem(BaseModel):
    rank: int
    article_id: Optional[int] = None
    score: float
    title: str
    summary: Optional[str]
    url: Optional[str]
    source: str
    source_label: str
    author: Optional[str]
    published: Optional[str]
    tags: List[str] = []
    score_points: Optional[int] = None
    comment_count: Optional[int] = None
    cluster_id: Optional[int] = None
    features: Optional[Dict[str, float]] = None


class NewsDebug(BaseModel):
    total_candidates: int
    returned_results: int
    total_ms: int
    source_counts: Dict[str, int]
    unavailable_sources: List[str]
    mode_used: NewsMode
    fell_back_to_discover: bool = False
    params: Dict[str, Any]


class NewsResponse(BaseModel):
    status: str = "ok"
    query: str
    mode: NewsMode
    results: List[NewsItem]
    debug: NewsDebug


class NewsSource(BaseModel):
    id: str
    label: str
    kind: str
    importance: float


class SourceListResponse(BaseModel):
    sources: List[NewsSource]


class NewsTag(BaseModel):
    id: str
    label: str
    description: Optional[str] = None


class TagListResponse(BaseModel):
    tags: List[NewsTag]


class FeedResponse(BaseModel):
    status: str = "ok"
    tag: str
    window: str
    results: List[NewsItem]
    debug: NewsDebug


class TrendingCluster(BaseModel):
    cluster_id: int
    score: float
    article_count: int
    sources: List[str]
    representative: Optional[NewsItem]
    members: List[NewsItem]


class TrendingResponse(BaseModel):
    status: str = "ok"
    clusters: List[TrendingCluster]


class SignalRequest(BaseModel):
    article_id: int
    kind: str = Field(..., description="click | view | dwell | hide | like")


class RefreshResponse(BaseModel):
    status: str = "ok"
    summary: Dict[str, Any]


class TopTag(BaseModel):
    id: str
    label: str
    weight: float


class TopSource(BaseModel):
    id: str
    label: str
    weight: float


class MeResponse(BaseModel):
    status: str = "ok"
    user_id: str
    has_profile: bool
    signal_count: int
    top_tags: List[TopTag] = []
    top_sources: List[TopSource] = []
    updated_at: Optional[str] = None


# --- Paper search ---


class PaperRequest(BaseModel):
    query: Optional[str] = Field(default="", description="Search query — required for relevance ranking")
    sources: Optional[List[str]] = Field(default=None, description="Limit to specific paper source ids")
    limit: Optional[int] = Field(default=20, ge=1, le=100)
    days_back: Optional[int] = Field(default=60, ge=1, le=365)


class PaperItem(BaseModel):
    rank: int
    article_id: Optional[int] = None
    score: float
    title: str
    summary: Optional[str]
    url: Optional[str]
    source: str
    source_label: str
    author: Optional[str]
    published: Optional[str]
    tags: List[str] = []
    features: Optional[Dict[str, float]] = None


class PaperResponse(BaseModel):
    status: str = "ok"
    query: str
    results: List[PaperItem]
    total_candidates: int
    total_ms: int
