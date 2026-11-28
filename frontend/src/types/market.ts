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
