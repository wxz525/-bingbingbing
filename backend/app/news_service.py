from datetime import date
from typing import Any

from app.errors import NewsNotFound, SummaryNotFound
from app.news_repository import NewsIndexRepository, SummaryRepository
from app.schemas import (
    NewsDetailResponse,
    NewsListItem,
    NewsListResponse,
    NewsMetaResponse,
    SummaryDetailResponse,
    SummaryListItem,
    SummaryListResponse,
)


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _news_item(payload: dict[str, Any]) -> NewsListItem:
    return NewsListItem(
        id=str(payload["id"]),
        date=_to_date(payload.get("date")),
        title=str(payload["title"]),
        source=payload.get("source"),
        stocks=[str(code) for code in payload.get("stocks", [])],
        topics=list(payload.get("topics", [])),
        market_level=payload.get("market_level"),
        sentiment=payload.get("sentiment"),
    )


def _summary_item(payload: dict[str, Any]) -> SummaryListItem:
    return SummaryListItem(
        name=str(payload["name"]),
        date=_to_date(payload.get("date")),
        institution=payload.get("institution"),
        title=str(payload["title"]),
        topics=list(payload.get("topics", [])),
        market_level=payload.get("market_level"),
        sentiment=payload.get("sentiment"),
    )


class NewsService:
    def __init__(self, news: NewsIndexRepository, summaries: SummaryRepository) -> None:
        self._news = news
        self._summaries = summaries

    def list_news(
        self,
        keyword: str | None,
        start_date: str | None,
        end_date: str | None,
        topic: str | None,
        level: str | None,
        sentiment: str | None,
        page: int,
        page_size: int,
    ) -> NewsListResponse:
        normalized = keyword.strip() if keyword else None
        rows, total = self._news.list_news(
            normalized or None,
            start_date or None,
            end_date or None,
            topic or None,
            level or None,
            sentiment or None,
            page,
            page_size,
        )
        snapshot = self._news.status_snapshot()
        return NewsListResponse(
            items=[_news_item(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
            indexing=snapshot["status"] == "building",
            indexed_rows=int(snapshot["indexed_rows"]),
        )

    def get_news(self, news_id: str) -> NewsDetailResponse:
        row = self._news.get_news(news_id.strip())
        if row is None:
            raise NewsNotFound()
        item = _news_item(row)
        return NewsDetailResponse(**item.model_dump(), content=str(row["content"]))

    def get_meta(self) -> NewsMetaResponse:
        payload = self._news.meta()
        return NewsMetaResponse(
            total=int(payload["total"]),
            min_date=_to_date(payload.get("min_date")),
            max_date=_to_date(payload.get("max_date")),
            source_count=int(payload["source_count"]),
            status=str(payload["status"]),
            indexed_rows=int(payload["indexed_rows"]),
            cache_ready=bool(payload["cache_ready"]),
        )

    def list_summaries(
        self,
        keyword: str | None,
        topic: str | None,
        level: str | None,
        sentiment: str | None,
        page: int,
        page_size: int,
    ) -> SummaryListResponse:
        normalized = keyword.strip() if keyword else None
        rows, total = self._summaries.list_summaries(
            normalized or None,
            topic or None,
            level or None,
            sentiment or None,
            page,
            page_size,
        )
        return SummaryListResponse(
            items=[_summary_item(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_summary(self, name: str) -> SummaryDetailResponse:
        row = self._summaries.get_summary(name.strip())
        if row is None:
            raise SummaryNotFound()
        item = _summary_item(row)
        return SummaryDetailResponse(**item.model_dump(), content=str(row["content"]))
