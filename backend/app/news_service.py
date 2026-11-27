from datetime import date
from typing import Any

from app.errors import NewsNotFound, SummaryNotFound
from app.news_repository import NewsIndexRepository, SummaryRepository
from app.schemas import (
    NewsDetailResponse,
    NewsListItem,
    NewsListResponse,
    NewsMetaResponse,
    SentimentOverviewResponse,
    SentimentPoint,
    SentimentSeriesResponse,
    SentimentSummaryPoint,
    SentimentTopicOverview,
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
        topics: list[str],
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
            topics,
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

    def sentiment_overview(self) -> SentimentOverviewResponse:
        """全量主题情绪概览：新闻（SQLite 聚合）+ 资金流摘要（标签过滤）。"""
        news_rows = self._news.sentiment_topic_overview()
        summary_stats: dict[str, dict[str, int]] = {}
        for item in self._summaries.items_matching(None, None, None):
            sentiment = item.get("sentiment")
            if sentiment not in ("bullish", "bearish", "neutral"):
                sentiment = "neutral"
            for key in set(item.get("topics", [])):
                stats = summary_stats.setdefault(
                    key, {"total": 0, "bullish": 0, "bearish": 0, "neutral": 0}
                )
                stats["total"] += 1
                stats[sentiment] += 1

        topics = []
        for row in news_rows:
            key = row["topic"]
            summary = summary_stats.get(
                key, {"total": 0, "bullish": 0, "bearish": 0, "neutral": 0}
            )
            topics.append(
                SentimentTopicOverview(
                    topic=key,
                    news_total=int(row["total"]),
                    news_bullish=int(row["bullish"]),
                    news_bearish=int(row["bearish"]),
                    news_neutral=int(row["neutral"]),
                    summary_total=summary["total"],
                    summary_bullish=summary["bullish"],
                    summary_bearish=summary["bearish"],
                    summary_neutral=summary["neutral"],
                )
            )
        return SentimentOverviewResponse(topics=topics)

    def sentiment_series(
        self,
        topic: str,
        start_date: str | None,
        end_date: str | None,
        bucket: str,
    ) -> SentimentSeriesResponse:
        """主题情绪走势：按日/周聚合新闻情绪，并叠加该主题的资金流摘要观点。"""
        normalized = topic.strip()
        rows = self._news.sentiment_series(normalized, start_date, end_date, bucket)
        points = []
        for row in rows:
            bullish, bearish = int(row["bullish"]), int(row["bearish"])
            directional = bullish + bearish
            score = (bullish - bearish) / directional if directional else 0.0
            points.append(
                SentimentPoint(
                    date=str(row["date"]),
                    bullish=bullish,
                    bearish=bearish,
                    neutral=int(row["neutral"]),
                    total=int(row["total"]),
                    score=round(score, 4),
                )
            )
        summaries = [
            SentimentSummaryPoint(
                name=str(item["name"]),
                date=_to_date(item.get("date")),
                institution=item.get("institution"),
                title=str(item["title"]),
                sentiment=item.get("sentiment"),
            )
            for item in self._summaries.items_matching(normalized, start_date, end_date)
        ]
        return SentimentSeriesResponse(
            topic=normalized, bucket=bucket, points=points, summaries=summaries
        )
