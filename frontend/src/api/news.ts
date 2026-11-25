import type {
  NewsDetail,
  NewsListResponse,
  NewsMeta,
  SummaryDetail,
  SummaryListResponse,
} from '@/types/news'
import { ApiRequestError, getApiBaseUrl } from '@/api/fundArchive'
import { isAbortError } from '@/utils/format'

export const NEWS_PATHS = {
  meta: '/api/v1/news/meta',
  list: '/api/v1/news',
  detail: (newsId: string) => `/api/v1/news/${encodeURIComponent(newsId)}`,
  summaries: '/api/v1/summaries',
  summaryDetail: (name: string) => `/api/v1/summaries/${encodeURIComponent(name)}`,
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
      body.message ?? '资讯数据加载失败',
    )
  }

  return payload as T
}

export function getNewsMeta(signal?: AbortSignal): Promise<NewsMeta> {
  return requestJson<NewsMeta>(NEWS_PATHS.meta, signal)
}

export function listNews(
  params: {
    keyword?: string
    start?: string
    end?: string
    page?: number
    pageSize?: number
  } = {},
  signal?: AbortSignal,
): Promise<NewsListResponse> {
  const search = new URLSearchParams()
  if (params.keyword) {
    search.set('q', params.keyword)
  }
  if (params.start) {
    search.set('start', params.start)
  }
  if (params.end) {
    search.set('end', params.end)
  }
  search.set('page', String(params.page ?? 1))
  search.set('page_size', String(params.pageSize ?? 20))
  return requestJson<NewsListResponse>(`${NEWS_PATHS.list}?${search.toString()}`, signal)
}

export function getNews(newsId: string, signal?: AbortSignal): Promise<NewsDetail> {
  return requestJson<NewsDetail>(NEWS_PATHS.detail(newsId), signal)
}

export function listSummaries(
  params: { keyword?: string; page?: number; pageSize?: number } = {},
  signal?: AbortSignal,
): Promise<SummaryListResponse> {
  const search = new URLSearchParams()
  if (params.keyword) {
    search.set('q', params.keyword)
  }
  search.set('page', String(params.page ?? 1))
  search.set('page_size', String(params.pageSize ?? 20))
  return requestJson<SummaryListResponse>(`${NEWS_PATHS.summaries}?${search.toString()}`, signal)
}

export function getSummary(name: string, signal?: AbortSignal): Promise<SummaryDetail> {
  return requestJson<SummaryDetail>(NEWS_PATHS.summaryDetail(name), signal)
}
