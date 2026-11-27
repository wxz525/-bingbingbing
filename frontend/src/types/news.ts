export interface NewsListItem {
  id: string
  date: string | null
  title: string
  source: string | null
  stocks: string[]
  topics: string[]
  market_level: string | null
  sentiment: string | null
}

export interface NewsListResponse {
  items: NewsListItem[]
  page: number
  page_size: number
  total: number
  indexing: boolean
  indexed_rows: number
}

export interface NewsDetail extends NewsListItem {
  content: string
}

export interface NewsMeta {
  total: number
  min_date: string | null
  max_date: string | null
  source_count: number
  status: string
  indexed_rows: number
  cache_ready: boolean
}

export interface SummaryListItem {
  name: string
  date: string | null
  institution: string | null
  title: string
  topics: string[]
  market_level: string | null
  sentiment: string | null
}

export interface SummaryListResponse {
  items: SummaryListItem[]
  page: number
  page_size: number
  total: number
}

export interface SummaryDetail extends SummaryListItem {
  content: string
}

export interface SentimentTopicOverview {
  topic: string
  news_total: number
  news_bullish: number
  news_bearish: number
  news_neutral: number
  summary_total: number
  summary_bullish: number
  summary_bearish: number
  summary_neutral: number
}

export interface SentimentOverviewResponse {
  topics: SentimentTopicOverview[]
}

export interface SentimentPoint {
  date: string
  bullish: number
  bearish: number
  neutral: number
  total: number
  score: number
}

export interface SentimentSummaryPoint {
  name: string
  date: string | null
  institution: string | null
  title: string
  sentiment: string | null
}

export interface SentimentSeriesResponse {
  topic: string
  bucket: string
  points: SentimentPoint[]
  summaries: SentimentSummaryPoint[]
}
