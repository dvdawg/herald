"""FastAPI app for Herald test UI."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.web.news_service import HeraldNewsService
from src.web.schemas import NewsRequest, NewsResponse, RunRequest, RunResponse
from src.web.service import HeraldWebService

app = FastAPI(title="Herald Test API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = HeraldWebService()
news_service = HeraldNewsService()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/run", response_model=RunResponse)
def run_pipeline(payload: RunRequest) -> RunResponse:
    try:
        return service.run(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": str(exc),
            },
        ) from exc


@app.post("/api/news", response_model=NewsResponse)
def run_news(payload: NewsRequest) -> NewsResponse:
    try:
        return news_service.run(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": str(exc),
            },
        ) from exc
