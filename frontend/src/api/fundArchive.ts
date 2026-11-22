import type {
  ApiErrorBody,
  FundArchiveDetail,
  FundArchiveListResponse,
  RedemptionRulePayload,
} from '@/types/fundArchive'
import { isAbortError } from '@/utils/format'

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000'

export const CONFLICT_MESSAGE = '当前规则已被其他人修改，请刷新页面后重新编辑'
export const NOT_FOUND_MESSAGE = '基金不存在或暂无档案'

/** 仅暴露本模块所需的三个后端接口路径。 */
export const FUND_ARCHIVE_PATHS = {
  list: '/api/v1/fund-archives',
  detail: (fundCode: string) => `/api/v1/fund-archives/${encodeURIComponent(fundCode)}`,
  redemptionRule: (fundCode: string) =>
    `/api/v1/fund-archives/${encodeURIComponent(fundCode)}/redemption-rule`,
}

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  const base = configured && configured.trim() ? configured.trim() : DEFAULT_BASE_URL
  return base.replace(/\/+$/, '')
}

export class ApiRequestError extends Error {
  readonly status: number
  readonly code: string
  readonly fieldErrors: Record<string, string>

  constructor(
    status: number,
    code: string,
    message: string,
    fieldErrors: Record<string, string> = {},
  ) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.code = code
    this.fieldErrors = fieldErrors
  }

  get isConflict(): boolean {
    return this.status === 409 || this.code === 'VERSION_CONFLICT'
  }

  get isNotFound(): boolean {
    return this.status === 404 || this.code === 'FUND_NOT_FOUND'
  }
}

function defaultMessageForStatus(status: number): string {
  if (status === 404) {
    return NOT_FOUND_MESSAGE
  }
  if (status === 409) {
    return CONFLICT_MESSAGE
  }
  if (status >= 500) {
    return '服务异常，请稍后重试'
  }
  return `请求失败（HTTP ${status}）`
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(init.headers ? (init.headers as Record<string, string>) : {}),
  }
  if (init.body !== undefined && init.body !== null) {
    headers['Content-Type'] = 'application/json'
  }

  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, { ...init, headers })
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
    const body = (payload ?? {}) as ApiErrorBody
    throw new ApiRequestError(
      response.status,
      body.code ?? `HTTP_${response.status}`,
      body.message ?? defaultMessageForStatus(response.status),
      body.field_errors ?? {},
    )
  }

  return payload as T
}

export function listFundArchives(
  params: { keyword?: string; page?: number; pageSize?: number } = {},
  signal?: AbortSignal,
): Promise<FundArchiveListResponse> {
  const search = new URLSearchParams()
  if (params.keyword) {
    search.set('keyword', params.keyword)
  }
  search.set('page', String(params.page ?? 1))
  search.set('page_size', String(params.pageSize ?? 20))

  return requestJson<FundArchiveListResponse>(
    `${FUND_ARCHIVE_PATHS.list}?${search.toString()}`,
    { method: 'GET', signal },
  )
}

export function getFundArchive(
  fundCode: string,
  signal?: AbortSignal,
): Promise<FundArchiveDetail> {
  return requestJson<FundArchiveDetail>(FUND_ARCHIVE_PATHS.detail(fundCode), {
    method: 'GET',
    signal,
  })
}

export function saveRedemptionRule(
  fundCode: string,
  payload: RedemptionRulePayload,
): Promise<FundArchiveDetail> {
  return requestJson<FundArchiveDetail>(FUND_ARCHIVE_PATHS.redemptionRule(fundCode), {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
