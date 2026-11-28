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

export interface MarketScatterPoint {
  name: string
  category: string
  wind_code: string | null
  annual_return: number
  annual_volatility: number
  sharpe: number | null
  max_drawdown: number
  start_date: string
  end_date: string
  sample_count: number
}

export interface MarketScatterResponse {
  days: number | null
  latest_date: string | null
  risk_free_rate: number
  items: MarketScatterPoint[]
  excluded: string[]
}
