export interface MarketAsset {
  name: string
  category: string
  wind_code: string | null
  field: string
  start_date: string
  end_date: string
  row_count: number
}

export interface MarketAssetListResponse {
  items: MarketAsset[]
}

export interface MarketSeries {
  name: string
  category: string
  wind_code: string | null
  field: string
  start_date: string
  end_date: string
  points: [string, number][]
}

export interface MarketCompareSeries {
  name: string
  category: string
  base_date: string
  base_value: number
  latest_value: number
  total_return: number
  values: (number | null)[]
}

export interface MarketCompareResponse {
  days: number | null
  start_date: string | null
  end_date: string | null
  dates: string[]
  items: MarketCompareSeries[]
}

export interface MarketRankingItem {
  name: string
  category: string
  start_date: string
  end_date: string
  start_value: number
  end_value: number
  return_rate: number
  sample_count: number
}

export interface MarketRankingResponse {
  days: number | null
  start_date: string | null
  end_date: string | null
  items: MarketRankingItem[]
}

export interface MarketIndicatorSummary {
  key: string
  name: string
  kind: 'ratio' | 'spread'
  unit: string
  description: string
  latest: number
  latest_date: string
  change: number
  change_pct: number | null
  point_count: number
}

export interface MarketIndicatorListResponse {
  days: number | null
  items: MarketIndicatorSummary[]
}

export interface MarketIndicator {
  key: string
  name: string
  kind: 'ratio' | 'spread'
  unit: string
  description: string
  start_date: string
  end_date: string
  latest: number
  change: number
  min_value: number
  max_value: number
  points: [string, number][]
}
