import type { FundArchiveDetail, FundBasicInfo, RedemptionRule } from '@/types/fundArchive'

export function makeBasicInfo(overrides: Partial<FundBasicInfo> = {}): FundBasicInfo {
  return {
    fund_code: '000001',
    fund_name: '示例基金',
    fund_type: '混合型',
    manager_name: '示例基金管理有限公司',
    custodian_name: null,
    establish_date: '2020-01-02',
    currency: 'CNY',
    fund_status: 'NORMAL',
    ...overrides,
  }
}

export function makeRule(overrides: Partial<RedemptionRule> = {}): RedemptionRule {
  return {
    rule_id: 12,
    version_no: 2,
    source_type: 'MANUAL',
    purchase_status: 'OPEN',
    redeem_status: 'OPEN',
    min_purchase_amount: '100.00',
    min_additional_purchase_amount: '100.00',
    daily_purchase_limit: null,
    min_redeem_shares: '1.0000',
    min_holding_shares: '0.0000',
    purchase_fee_rate: '0.150000',
    redeem_fee_rate: '0.500000',
    purchase_confirm_days: 1,
    redeem_confirm_days: 1,
    redeem_arrival_days: 2,
    effective_date: '2026-11-21',
    remark: null,
    ...overrides,
  }
}

export function makeDetail(overrides: Partial<FundArchiveDetail> = {}): FundArchiveDetail {
  return {
    basic_info: makeBasicInfo(),
    redemption_rule: makeRule(),
    ...overrides,
  }
}
