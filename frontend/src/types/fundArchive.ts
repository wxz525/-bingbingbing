export type FundStatus = 'NORMAL' | 'SUSPENDED' | 'TERMINATED'
export type RedemptionStatus = 'OPEN' | 'CLOSED' | 'SUSPENDED'
export type RuleSourceType = 'MANUAL' | 'ETL'

/** 基金基础信息，与后端 FundBasicInfo 契约一致。 */
export interface FundBasicInfo {
  fund_code: string
  fund_name: string
  fund_type?: string | null
  manager_name?: string | null
  custodian_name?: string | null
  establish_date?: string | null
  currency?: string | null
  fund_status?: FundStatus | string | null
}

/**
 * 申赎规则。金额、费率、份额均为后端序列化的十进制字符串，
 * 前端只做原样展示，不转数字、不做浮点运算。
 */
export interface RedemptionRule {
  rule_id: number
  version_no: number
  source_type: RuleSourceType | string
  purchase_status?: RedemptionStatus | string | null
  redeem_status?: RedemptionStatus | string | null
  min_purchase_amount?: string | null
  min_additional_purchase_amount?: string | null
  daily_purchase_limit?: string | null
  min_redeem_shares?: string | null
  min_holding_shares?: string | null
  purchase_fee_rate?: string | null
  redeem_fee_rate?: string | null
  purchase_confirm_days?: number | null
  redeem_confirm_days?: number | null
  redeem_arrival_days?: number | null
  effective_date?: string | null
  remark?: string | null
}

export interface FundArchiveDetail {
  basic_info: FundBasicInfo
  redemption_rule: RedemptionRule | null
}

export interface FundArchiveListResponse {
  items: FundBasicInfo[]
  page: number
  page_size: number
  total: number
}

/** PUT /redemption-rule 的请求体，字段与后端 complete replace 语义一致。 */
export interface RedemptionRulePayload {
  expected_rule_id: number | null
  expected_version_no: number
  purchase_status: RedemptionStatus | null
  redeem_status: RedemptionStatus | null
  min_purchase_amount: string | null
  min_additional_purchase_amount: string | null
  daily_purchase_limit: string | null
  min_redeem_shares: string | null
  min_holding_shares: string | null
  purchase_fee_rate: string | null
  redeem_fee_rate: string | null
  purchase_confirm_days: number | null
  redeem_confirm_days: number | null
  redeem_arrival_days: number | null
  effective_date: string | null
  remark: string | null
}

export interface ApiErrorBody {
  code?: string
  message?: string
  field_errors?: Record<string, string>
}

/** 查询异常状态，用于区块清空、提示与重试。 */
export interface DetailErrorState {
  status: number
  message: string
}

/** 保存异常状态，用于编辑弹窗内提示，不清空用户输入。 */
export interface SaveErrorState {
  status: number
  code: string
  message: string
  fieldErrors: Record<string, string>
}
