from datetime import date

from pydantic import BaseModel


class MarketAssetInfo(BaseModel):
    name: str
    category: str
    wind_code: str | None = None
    field: str
    start_date: date
    end_date: date
    row_count: int


class MarketAssetListResponse(BaseModel):
    items: list[MarketAssetInfo]


class MarketSeriesResponse(BaseModel):
    name: str
    category: str
    wind_code: str | None = None
    field: str
    start_date: date
    end_date: date
    points: list[tuple[str, float]]


class MarketScatterPoint(BaseModel):
    name: str
    category: str
    wind_code: str | None = None
    annual_return: float
    annual_volatility: float
    sharpe: float | None = None
    max_drawdown: float
    start_date: date
    end_date: date
    sample_count: int


class MarketScatterResponse(BaseModel):
    days: int | None = None
    latest_date: date | None = None
    risk_free_rate: float
    items: list[MarketScatterPoint]
    excluded: list[str] = []


class NewsListItem(BaseModel):
    id: str
    date: date | None
    title: str
    source: str | None = None
    stocks: list[str] = []
    topics: list[str] = []
    market_level: str | None = None
    sentiment: str | None = None


class NewsListResponse(BaseModel):
    items: list[NewsListItem]
    page: int
    page_size: int
    total: int
    indexing: bool = False
    indexed_rows: int = 0


class NewsDetailResponse(NewsListItem):
    content: str


class NewsMetaResponse(BaseModel):
    total: int
    min_date: date | None = None
    max_date: date | None = None
    source_count: int
    status: str
    indexed_rows: int
    cache_ready: bool


class SummaryListItem(BaseModel):
    name: str
    date: date | None
    institution: str | None = None
    title: str
    topics: list[str] = []
    market_level: str | None = None
    sentiment: str | None = None


class SummaryListResponse(BaseModel):
    items: list[SummaryListItem]
    page: int
    page_size: int
    total: int


class SummaryDetailResponse(SummaryListItem):
    content: str


class SentimentTopicOverview(BaseModel):
    topic: str
    news_total: int
    news_bullish: int
    news_bearish: int
    news_neutral: int
    summary_total: int
    summary_bullish: int
    summary_bearish: int
    summary_neutral: int


class SentimentOverviewResponse(BaseModel):
    topics: list[SentimentTopicOverview]


class SentimentPoint(BaseModel):
    date: str
    bullish: int
    bearish: int
    neutral: int
    total: int
    score: float


class SentimentSummaryPoint(BaseModel):
    name: str
    date: date | None
    institution: str | None = None
    title: str
    sentiment: str | None = None


class SentimentSeriesResponse(BaseModel):
    topic: str
    bucket: str
    points: list[SentimentPoint]
    summaries: list[SentimentSummaryPoint]
