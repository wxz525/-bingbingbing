const DEFAULT_BASE_URL = 'http://127.0.0.1:8000'

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
}
