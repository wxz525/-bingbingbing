from fastapi import APIRouter, Query, Request

from app.schemas import (
    MarketAssetListResponse,
    MarketSeriesResponse,
    NewsDetailResponse,
    NewsListResponse,
    NewsMetaResponse,
    SummaryDetailResponse,
    SummaryListResponse,
)

market_router = APIRouter(prefix="/api/v1/market", tags=["market"])

news_router = APIRouter(prefix="/api/v1", tags=["news"])


def _market_service(request: Request):
    return request.app.state.market_service


def _news_service(request: Request):
    return request.app.state.news_service


@market_router.get("/assets", response_model=MarketAssetListResponse)
def list_market_assets(request: Request) -> MarketAssetListResponse:
    return _market_service(request).list_assets()


@market_router.get("/series/{name}", response_model=MarketSeriesResponse)
def get_market_series(request: Request, name: str) -> MarketSeriesResponse:
    return _market_service(request).get_series(name)


@news_router.get("/news/meta", response_model=NewsMetaResponse)
def get_news_meta(request: Request) -> NewsMetaResponse:
    return _news_service(request).get_meta()


@news_router.get("/news", response_model=NewsListResponse)
def list_news(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
    start: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    topics: str | None = Query(default=None),
    level: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> NewsListResponse:
    topic_list = [t.strip() for t in topics.split(",") if t.strip()] if topics else []
    return _news_service(request).list_news(q, start, end, topic_list, level, sentiment, page, page_size)


@news_router.get("/news/{news_id}", response_model=NewsDetailResponse)
def get_news(request: Request, news_id: str) -> NewsDetailResponse:
    return _news_service(request).get_news(news_id)


@news_router.get("/summaries", response_model=SummaryListResponse)
def list_summaries(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
    topic: str | None = Query(default=None),
    level: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SummaryListResponse:
    return _news_service(request).list_summaries(q, topic, level, sentiment, page, page_size)


@news_router.get("/summaries/{name}", response_model=SummaryDetailResponse)
def get_summary(request: Request, name: str) -> SummaryDetailResponse:
    return _news_service(request).get_summary(name)
