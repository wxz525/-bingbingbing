import type { RedemptionRule } from '@/types/fundArchive'

export type RedemptionFieldKey =
  | 'purchase_status'
  | 'redeem_status'
  | 'min_purchase_amount'
  | 'min_additional_purchase_amount'
  | 'daily_purchase_limit'
  | 'min_redeem_shares'
  | 'min_holding_shares'
  | 'purchase_fee_rate'
  | 'redeem_fee_rate'
  | 'purchase_confirm_days'
  | 'redeem_confirm_days'
  | 'redeem_arrival_days'
  | 'effective_date'
  | 'remark'

export type RuleFormControl = 'status' | 'decimal' | 'integer' | 'date' | 'textarea'

export interface RuleFormField {
  key: RedemptionFieldKey
  label: string
  control: RuleFormControl
  placeholder?: string
}

/** 申赎要素只读展示字段；生效日期在元信息区展示，备注单独占整行。 */
export const REDEMPTION_DISPLAY_FIELDS: Array<{
  key: RedemptionFieldKey
  label: string
  kind: 'status' | 'text'
}> = [
  { key: 'purchase_status', label: '申购状态', kind: 'status' },
  { key: 'redeem_status', label: '赎回状态', kind: 'status' },
  { key: 'min_purchase_amount', label: '最低申购金额（元）', kind: 'text' },
  { key: 'min_additional_purchase_amount', label: '追加申购最低金额（元）', kind: 'text' },
  { key: 'daily_purchase_limit', label: '单日申购上限（元）', kind: 'text' },
  { key: 'min_redeem_shares', label: '最低赎回份额（份）', kind: 'text' },
  { key: 'min_holding_shares', label: '最低持有份额（份）', kind: 'text' },
  { key: 'purchase_fee_rate', label: '申购费率（%）', kind: 'text' },
  { key: 'redeem_fee_rate', label: '赎回费率（%）', kind: 'text' },
  { key: 'purchase_confirm_days', label: '申购确认天数（天）', kind: 'text' },
  { key: 'redeem_confirm_days', label: '赎回确认天数（天）', kind: 'text' },
  { key: 'redeem_arrival_days', label: '赎回到账天数（天）', kind: 'text' },
]

/** 编辑弹窗控件定义，字段顺序与后端 complete replace 语义一致。 */
export const RULE_FORM_FIELDS: RuleFormField[] = [
  { key: 'purchase_status', label: '申购状态', control: 'status' },
  { key: 'redeem_status', label: '赎回状态', control: 'status' },
  {
    key: 'min_purchase_amount',
    label: '最低申购金额（元）',
    control: 'decimal',
    placeholder: '如 100.00',
  },
  {
    key: 'min_additional_purchase_amount',
    label: '追加申购最低金额（元）',
    control: 'decimal',
    placeholder: '如 100.00',
  },
  {
    key: 'daily_purchase_limit',
    label: '单日申购上限（元）',
    control: 'decimal',
    placeholder: '留空表示未提供',
  },
  {
    key: 'min_redeem_shares',
    label: '最低赎回份额（份）',
    control: 'decimal',
    placeholder: '如 1.0000',
  },
  {
    key: 'min_holding_shares',
    label: '最低持有份额（份）',
    control: 'decimal',
    placeholder: '如 0.0000',
  },
  {
    key: 'purchase_fee_rate',
    label: '申购费率（%）',
    control: 'decimal',
    placeholder: '0～100，如 0.150000',
  },
  {
    key: 'redeem_fee_rate',
    label: '赎回费率（%）',
    control: 'decimal',
    placeholder: '0～100，如 0.500000',
  },
  {
    key: 'purchase_confirm_days',
    label: '申购确认天数（天）',
    control: 'integer',
    placeholder: '非负整数',
  },
  {
    key: 'redeem_confirm_days',
    label: '赎回确认天数（天）',
    control: 'integer',
    placeholder: '非负整数',
  },
  {
    key: 'redeem_arrival_days',
    label: '赎回到账天数（天）',
    control: 'integer',
    placeholder: '非负整数',
  },
  { key: 'effective_date', label: '生效日期', control: 'date', placeholder: 'YYYY-MM-DD' },
  { key: 'remark', label: '备注', control: 'textarea', placeholder: '最多 512 字符' },
]

export const STATUS_OPTIONS = [
  { label: '开放', value: 'OPEN' },
  { label: '关闭', value: 'CLOSED' },
  { label: '暂停', value: 'SUSPENDED' },
]

export type RuleFormModel = Record<RedemptionFieldKey, string>

/** 从后端规则构建表单，金额/费率/份额保持原始字符串。 */
export function createRuleFormModel(rule: RedemptionRule | null): RuleFormModel {
  const read = (key: RedemptionFieldKey): string => {
    const value = rule?.[key]
    return value === null || value === undefined ? '' : String(value)
  }

  return {
    purchase_status: read('purchase_status'),
    redeem_status: read('redeem_status'),
    min_purchase_amount: read('min_purchase_amount'),
    min_additional_purchase_amount: read('min_additional_purchase_amount'),
    daily_purchase_limit: read('daily_purchase_limit'),
    min_redeem_shares: read('min_redeem_shares'),
    min_holding_shares: read('min_holding_shares'),
    purchase_fee_rate: read('purchase_fee_rate'),
    redeem_fee_rate: read('redeem_fee_rate'),
    purchase_confirm_days: read('purchase_confirm_days'),
    redeem_confirm_days: read('redeem_confirm_days'),
    redeem_arrival_days: read('redeem_arrival_days'),
    effective_date: read('effective_date'),
    remark: read('remark'),
  }
}
