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
