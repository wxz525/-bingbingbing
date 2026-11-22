export const EMPTY_TEXT = '--'

/**
 * 空值判定仅覆盖 null、undefined 与去除空白后的空字符串。
 * 数值 0、布尔 false 必须原样展示，不能判为空。
 */
export function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return true
  }
  if (typeof value === 'string') {
    return value.trim() === ''
  }
  return false
}

/**
 * 统一展示格式化：空值展示 `--`，其余值原样转字符串。
 * 金额/费率/份额后端已是字符串，此处不做任何数值转换。
 */
export function displayText(value: unknown): string {
  if (isEmptyValue(value)) {
    return EMPTY_TEXT
  }
  return String(value)
}

const STATUS_LABELS: Record<string, string> = {
  OPEN: '开放',
  CLOSED: '关闭',
  SUSPENDED: '暂停',
}

export function displayStatus(value: unknown): string {
  if (isEmptyValue(value)) {
    return EMPTY_TEXT
  }
  return STATUS_LABELS[String(value)] ?? String(value)
}

export function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    (error as { name?: string }).name === 'AbortError'
  )
}
