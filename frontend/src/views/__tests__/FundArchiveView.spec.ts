import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/fundArchive', async () => {
  const actual = await vi.importActual<typeof import('@/api/fundArchive')>('@/api/fundArchive')
  return {
    ...actual,
    listFundArchives: vi.fn(),
    getFundArchive: vi.fn(),
    saveRedemptionRule: vi.fn(),
  }
})

import {
  ApiRequestError,
  getFundArchive,
  listFundArchives,
  saveRedemptionRule,
} from '@/api/fundArchive'
import FundSearchBar from '@/components/FundSearchBar.vue'
import RedemptionRuleFormDialog from '@/components/RedemptionRuleFormDialog.vue'
import RedemptionRulePanel from '@/components/RedemptionRulePanel.vue'
import { createRuleFormModel } from '@/constants/redemption'
import { makeBasicInfo, makeDetail, makeRule } from '@/test/fixtures'
import type { FundArchiveDetail } from '@/types/fundArchive'
import { buildRulePayload } from '@/utils/ruleForm'
import FundArchiveView from '@/views/FundArchiveView.vue'

const mockedList = vi.mocked(listFundArchives)
const mockedDetail = vi.mocked(getFundArchive)
const mockedSave = vi.mocked(saveRedemptionRule)

async function mountView(): Promise<VueWrapper> {
  const wrapper = mount(FundArchiveView)
  await flushPromises()
  return wrapper
}

async function selectFund(wrapper: VueWrapper, fundCode: string): Promise<void> {
  wrapper.findComponent(FundSearchBar).vm.$emit('select', fundCode)
  await flushPromises()
  await nextTick()
}

beforeEach(() => {
  mockedList.mockReset()
  mockedDetail.mockReset()
  mockedSave.mockReset()
  mockedList.mockResolvedValue({
    items: [makeBasicInfo(), makeBasicInfo({ fund_code: '000002', fund_name: '第二只基金' })],
    page: 1,
    page_size: 20,
    total: 2,
  })
})

describe('基金档案页面', () => {
  it('AC-01 选择基金后同时展示基础信息区块与申赎要素区块', async () => {
    mockedDetail.mockResolvedValue(makeDetail())
    const wrapper = await mountView()

    await selectFund(wrapper, '000001')

    expect(wrapper.find('[data-testid="fund-search-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="basic-info-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="redemption-rule-panel"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="basic-fund_code"]').text()).toBe('000001')
    expect(wrapper.get('[data-testid="basic-fund_name"]').text()).toBe('示例基金')
    expect(wrapper.get('[data-testid="rule-source"]').text()).toBe('MANUAL')
    expect(wrapper.get('[data-testid="rule-version"]').text()).toBe('2')
    expect(wrapper.get('[data-testid="rule-effective-date"]').text()).toBe('2026-11-21')
    expect(mockedDetail).toHaveBeenCalledWith('000001', expect.any(AbortSignal))
  })

  it('AC-02 无申赎规则时区块保留、字段为 --，仍可新增首条人工规则', async () => {
    mockedDetail.mockResolvedValue(
      makeDetail({
        basic_info: makeBasicInfo({ fund_code: '000002', fund_name: '第二只基金' }),
        redemption_rule: null,
      }),
    )
    const wrapper = await mountView()

    await selectFund(wrapper, '000002')

    expect(wrapper.get('[data-testid="basic-fund_code"]').text()).toBe('000002')
    expect(wrapper.get('[data-testid="rule-source"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-version"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-effective-date"]').text()).toBe('--')

    const editButton = wrapper.get('[data-testid="edit-rule-button"]')
    expect(editButton.text()).toBe('新增申赎要素')
    expect(editButton.attributes('disabled')).toBeUndefined()
  })

  it('AC-10 托管人 null、备注空串展示 --，零值字段展示 0', async () => {
    mockedDetail.mockResolvedValue(
      makeDetail({
        basic_info: makeBasicInfo({ custodian_name: null }),
        redemption_rule: makeRule({
          min_holding_shares: '0.0000',
          redeem_arrival_days: 0,
          remark: '',
        }),
      }),
    )
    const wrapper = await mountView()

    await selectFund(wrapper, '000001')

    expect(wrapper.get('[data-testid="basic-custodian_name"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-remark"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-min_holding_shares"]').text()).toBe('0.0000')
    expect(wrapper.get('[data-testid="rule-redeem_arrival_days"]').text()).toBe('0')
  })

  it('AC-11 详情 500 时清空为 --、展示异常提示与重试按钮，重试后恢复', async () => {
    mockedDetail.mockRejectedValueOnce(
      new ApiRequestError(500, 'DATABASE_ERROR', '数据库操作失败'),
    )
    const wrapper = await mountView()

    await selectFund(wrapper, '000001')

    expect(wrapper.get('[data-testid="detail-error-alert"]').text()).toContain('数据库操作失败')
    expect(wrapper.get('[data-testid="basic-fund_name"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-source"]').text()).toBe('--')
    expect(wrapper.find('[data-testid="basic-info-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="redemption-rule-panel"]').exists()).toBe(true)

    mockedDetail.mockResolvedValueOnce(makeDetail())
    await wrapper.get('[data-testid="retry-button"]').trigger('click')
    await flushPromises()

    expect(mockedDetail).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="basic-fund_name"]').text()).toBe('示例基金')
    expect(wrapper.find('[data-testid="detail-error-alert"]').exists()).toBe(false)
  })

  it('AC-11 详情 404 时清空区块内容为 --，不展示重试按钮', async () => {
    mockedDetail.mockRejectedValueOnce(
      new ApiRequestError(404, 'FUND_NOT_FOUND', '基金不存在'),
    )
    const wrapper = await mountView()

    await selectFund(wrapper, '000001')

    expect(wrapper.get('[data-testid="detail-error-alert"]').text()).toContain('基金不存在')
    expect(wrapper.get('[data-testid="basic-fund_code"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-min_purchase_amount"]').text()).toBe('--')
    expect(wrapper.find('[data-testid="retry-button"]').exists()).toBe(false)
  })

  it('切换基金时取消上一个详情请求，旧响应不会覆盖当前基金', async () => {
    const firstRequest: { signal?: AbortSignal } = {}
    let resolveFirst: (value: FundArchiveDetail) => void = () => {}
    mockedDetail.mockImplementationOnce((_fundCode, signal) => {
      firstRequest.signal = signal
      return new Promise<FundArchiveDetail>((resolve) => {
        resolveFirst = resolve
      })
    })
    mockedDetail.mockResolvedValueOnce(
      makeDetail({
        basic_info: makeBasicInfo({ fund_code: '000002', fund_name: '第二只基金' }),
        redemption_rule: makeRule({ rule_id: 99, version_no: 7, source_type: 'ETL' }),
      }),
    )

    const wrapper = await mountView()
    wrapper.findComponent(FundSearchBar).vm.$emit('select', '000001')
    wrapper.findComponent(FundSearchBar).vm.$emit('select', '000002')
    await flushPromises()
    await nextTick()

    expect(firstRequest.signal?.aborted).toBe(true)
    expect(wrapper.get('[data-testid="basic-fund_name"]').text()).toBe('第二只基金')
    expect(wrapper.get('[data-testid="rule-source"]').text()).toBe('ETL')
    expect(wrapper.get('[data-testid="rule-version"]').text()).toBe('7')

    // 迟到的旧响应必须被忽略。
    resolveFirst(makeDetail({ basic_info: makeBasicInfo({ fund_code: '000001' }) }))
    await flushPromises()
    await nextTick()

    expect(wrapper.get('[data-testid="basic-fund_name"]').text()).toBe('第二只基金')
    expect(wrapper.get('[data-testid="rule-version"]').text()).toBe('7')
  })

  it('AC-09 保存返回 409 时弹窗保持打开、提示冲突且不覆盖输入', async () => {
    mockedDetail.mockResolvedValue(makeDetail())
    mockedSave.mockRejectedValueOnce(
      new ApiRequestError(409, 'VERSION_CONFLICT', '申赎要素已更新，请刷新后重试'),
    )

    const wrapper = await mountView()
    await selectFund(wrapper, '000001')

    wrapper.findComponent(RedemptionRulePanel).vm.$emit('edit')
    await flushPromises()
    await nextTick()

    const dialog = wrapper.findComponent(RedemptionRuleFormDialog)
    expect(dialog.props('modelValue')).toBe(true)

    const rule = makeRule()
    dialog.vm.$emit('submit', buildRulePayload(createRuleFormModel(rule), rule))
    await flushPromises()
    await nextTick()

    expect(mockedSave).toHaveBeenCalledWith(
      '000001',
      expect.objectContaining({ expected_rule_id: 12, expected_version_no: 2 }),
    )
    expect(dialog.props('modelValue')).toBe(true)
    expect(dialog.props('error')).toMatchObject({ status: 409, code: 'VERSION_CONFLICT' })
    // 详情数据未被 409 响应覆盖。
    expect(wrapper.get('[data-testid="rule-version"]').text()).toBe('2')
  })

  it('保存成功后以响应刷新当前版本并关闭弹窗', async () => {
    mockedDetail.mockResolvedValue(makeDetail())
    mockedSave.mockResolvedValue(
      makeDetail({ redemption_rule: makeRule({ rule_id: 13, version_no: 3 }) }),
    )

    const wrapper = await mountView()
    await selectFund(wrapper, '000001')

    wrapper.findComponent(RedemptionRulePanel).vm.$emit('edit')
    await flushPromises()

    const dialog = wrapper.findComponent(RedemptionRuleFormDialog)
    const rule = makeRule()
    dialog.vm.$emit('submit', buildRulePayload(createRuleFormModel(rule), rule))
    await flushPromises()
    await nextTick()

    expect(dialog.props('modelValue')).toBe(false)
    expect(wrapper.get('[data-testid="rule-version"]').text()).toBe('3')
  })
})
