"""FastAPI app for Herald web UI."""
from __future__ import annotations

import logging
import os
import secrets

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.web.news_service import HeraldNewsService
from src.web.scheduler import NewsScheduler
from src.web.schemas import (
    FeedResponse,
    MeResponse,
    NewsRequest,
    NewsResponse,
    PaperRequest,
    PaperResponse,
    RefreshResponse,
    SignalRequest,
    SourceListResponse,
    TagListResponse,
    TrendingResponse,
)

logger = logging.getLogger(__name__)

USER_COOKIE_NAME = "herald_uid"


app = FastAPI(title="Herald API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

news_service = HeraldNewsService()
scheduler = NewsScheduler()


@app.on_event("startup")
def on_startup() -> None:
    if os.getenv("HERALD_DISABLE_SCHEDULER", "0") not in {"1", "true", "TRUE"}:
        scheduler.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    scheduler.stop()


def _ensure_user_id(request: Request, response: Response) -> str:
    explicit = request.headers.get("X-Herald-User")
    if explicit:
        return explicit
    existing = request.cookies.get(USER_COOKIE_NAME)
    if existing:
        return existing
    uid = secrets.token_urlsafe(12)
    response.set_cookie(
        USER_COOKIE_NAME,
        uid,
        max_age=60 * 60 * 24 * 365,
        httponly=False,
        samesite="lax",
    )
    return uid


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "scheduler": scheduler.status}


@app.post("/api/news", response_model=NewsResponse)
def run_news(payload: NewsRequest, request: Request, response: Response) -> NewsResponse:
    user_id = _ensure_user_id(request, response)
    try:
        return news_service.run(payload, user_id=user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"status": "error", "message": str(exc)}) from exc


@app.get("/api/news/sources", response_model=SourceListResponse)
def list_sources() -> SourceListResponse:
    return news_service.list_sources()


@app.get("/api/news/tags", response_model=TagListResponse)
def list_tags() -> TagListResponse:
    return news_service.list_tags()


@app.get("/api/news/feeds/{tag}", response_model=FeedResponse)
def tag_feed(
    tag: str,
    request: Request,
    response: Response,
    window: str = "24h",
    limit: int = 20,
) -> FeedResponse:
    user_id = _ensure_user_id(request, response)
    try:
        return news_service.tag_feed(tag=tag, window=window, limit=limit, user_id=user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"status": "error", "message": f"Unknown tag: {tag}"})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"status": "error", "message": str(exc)}) from exc


@app.get("/api/news/trending", response_model=TrendingResponse)
def trending(hours_back: int = 24, min_sources: int = 2, limit: int = 10) -> TrendingResponse:
    return news_service.trending_feed(hours_back=hours_back, min_sources=min_sources, limit=limit)


@app.post("/api/news/signal")
def post_signal(payload: SignalRequest, request: Request, response: Response) -> dict:
    user_id = _ensure_user_id(request, response)
    return news_service.record_signal(user_id, payload.article_id, payload.kind)


@app.get("/api/me", response_model=MeResponse)
def me(request: Request, response: Response) -> MeResponse:
    user_id = _ensure_user_id(request, response)
    return news_service.profile(user_id)


@app.post("/api/news/refresh", response_model=RefreshResponse)
def trigger_refresh() -> RefreshResponse:
    summary = scheduler.refresh_once()
    return RefreshResponse(summary=summary)


@app.get("/api/news/status")
def scheduler_status() -> dict:
    return scheduler.status


@app.post("/api/papers/search", response_model=PaperResponse)
def search_papers(payload: PaperRequest) -> PaperResponse:
    try:
        return news_service.search_papers(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"status": "error", "message": str(exc)}) from exc


@app.get("/api/papers/sources", response_model=SourceListResponse)
def list_paper_sources() -> SourceListResponse:
    return news_service.list_paper_sources()
