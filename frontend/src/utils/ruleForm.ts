import type { RuleFormModel } from '@/constants/redemption'
import type { RedemptionRule, RedemptionRulePayload, RedemptionStatus } from '@/types/fundArchive'

const DECIMAL_PATTERN = /^\d+(?:\.\d+)?$/
const DAY_PATTERN = /^\d+$/
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

const DECIMAL_LIMITS: Record<string, { scale: number; label: string }> = {
  min_purchase_amount: { scale: 2, label: '最低申购金额' },
  min_additional_purchase_amount: { scale: 2, label: '追加申购最低金额' },
  daily_purchase_limit: { scale: 2, label: '单日申购上限' },
  min_redeem_shares: { scale: 4, label: '最低赎回份额' },
  min_holding_shares: { scale: 4, label: '最低持有份额' },
  purchase_fee_rate: { scale: 6, label: '申购费率' },
  redeem_fee_rate: { scale: 6, label: '赎回费率' },
}

const DAY_FIELDS = [
  'purchase_confirm_days',
  'redeem_confirm_days',
  'redeem_arrival_days',
] as const

function toNullableText(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

function toNullableInt(value: string): number | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : Number.parseInt(trimmed, 10)
}

function toNullableStatus(value: string): RedemptionStatus | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : (trimmed as RedemptionStatus)
}

/**
 * 组装 PUT 请求体：空输入统一转 null，绝不把视图占位符 `--` 传给后端。
 * 金额/费率/份额保留用户输入的字符串，不做浮点转换。
 */
export function buildRulePayload(
  form: RuleFormModel,
  rule: RedemptionRule | null,
): RedemptionRulePayload {
  return {
    expected_rule_id: rule?.rule_id ?? null,
    expected_version_no: rule?.version_no ?? 0,
    purchase_status: toNullableStatus(form.purchase_status),
    redeem_status: toNullableStatus(form.redeem_status),
    min_purchase_amount: toNullableText(form.min_purchase_amount),
    min_additional_purchase_amount: toNullableText(form.min_additional_purchase_amount),
    daily_purchase_limit: toNullableText(form.daily_purchase_limit),
    min_redeem_shares: toNullableText(form.min_redeem_shares),
    min_holding_shares: toNullableText(form.min_holding_shares),
    purchase_fee_rate: toNullableText(form.purchase_fee_rate),
    redeem_fee_rate: toNullableText(form.redeem_fee_rate),
    purchase_confirm_days: toNullableInt(form.purchase_confirm_days),
    redeem_confirm_days: toNullableInt(form.redeem_confirm_days),
    redeem_arrival_days: toNullableInt(form.redeem_arrival_days),
    effective_date: toNullableText(form.effective_date),
    remark: toNullableText(form.remark),
  }
}

function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0
}

function isValidDate(text: string): boolean {
  const [yearText, monthText, dayText] = text.split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  if (month < 1 || month > 12 || day < 1) {
    return false
  }
  const daysInMonth = [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return day <= daysInMonth[month - 1]
}

/** 客户端基础校验，与服务端字段规则保持一致；服务端仍为最终校验方。 */
export function validateRuleForm(form: RuleFormModel): Record<string, string> {
  const errors: Record<string, string> = {}

  for (const [field, limit] of Object.entries(DECIMAL_LIMITS)) {
    const value = form[field as keyof RuleFormModel].trim()
    if (value === '') {
      continue
    }
    if (!DECIMAL_PATTERN.test(value)) {
      errors[field] = `${limit.label}必须是合法的非负十进制数`
      continue
    }
    const fraction = value.split('.')[1] ?? ''
    if (fraction.length > limit.scale) {
      errors[field] = `${limit.label}小数位不得超过 ${limit.scale} 位`
      continue
    }
    if (
      (field === 'purchase_fee_rate' || field === 'redeem_fee_rate') &&
      Number(value) > 100
    ) {
      errors[field] = `${limit.label}必须小于或等于 100`
    }
  }

  for (const field of DAY_FIELDS) {
    const value = form[field].trim()
    if (value === '') {
      continue
    }
    if (!DAY_PATTERN.test(value) || Number(value) > 32767) {
      errors[field] = '天数必须是 0～32767 之间的整数'
    }
  }

  const effectiveDate = form.effective_date.trim()
  if (effectiveDate !== '' && (!DATE_PATTERN.test(effectiveDate) || !isValidDate(effectiveDate))) {
    errors.effective_date = '生效日期必须使用 YYYY-MM-DD 格式'
  }

  if (form.remark.trim().length > 512) {
    errors.remark = '备注去除首尾空白后不得超过 512 字符'
  }

  return errors
}
