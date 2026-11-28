import type { MarketAssetListResponse, MarketScatterResponse, MarketSeries } from '@/types/market'
import { ApiRequestError, getApiBaseUrl } from '@/api/http'
import { isAbortError } from '@/utils/format'

export const MARKET_PATHS = {
  assets: '/api/v1/market/assets',
  series: (name: string) => `/api/v1/market/series/${encodeURIComponent(name)}`,
  scatter: (days: number | null) =>
    days === null ? '/api/v1/market/scatter' : `/api/v1/market/scatter?days=${days}`,
}

async function requestJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }
    throw new ApiRequestError(0, 'NETWORK_ERROR', '网络异常，请检查后端服务是否可用')
  }

  const raw = await response.text()
  let payload: unknown = null
  if (raw) {
    try {
      payload = JSON.parse(raw) as unknown
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    const body = (payload ?? {}) as { code?: string; message?: string }
    throw new ApiRequestError(
      response.status,
      body.code ?? `HTTP_${response.status}`,
      body.message ?? '行情数据加载失败',
    )
  }

  return payload as T
}

export function listMarketAssets(signal?: AbortSignal): Promise<MarketAssetListResponse> {
  return requestJson<MarketAssetListResponse>(MARKET_PATHS.assets, signal)
}

export function getMarketSeries(name: string, signal?: AbortSignal): Promise<MarketSeries> {
  return requestJson<MarketSeries>(MARKET_PATHS.series(name), signal)
}

export function getMarketScatter(
  days: number | null,
  signal?: AbortSignal,
): Promise<MarketScatterResponse> {
  return requestJson<MarketScatterResponse>(MARKET_PATHS.scatter(days), signal)
}
