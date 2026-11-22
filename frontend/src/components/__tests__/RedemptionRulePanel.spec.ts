import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RedemptionRulePanel from '@/components/RedemptionRulePanel.vue'
import { makeRule } from '@/test/fixtures'
import type { RedemptionRule } from '@/types/fundArchive'

function mountPanel(rule: RedemptionRule | null, canEdit = true) {
  return mount(RedemptionRulePanel, {
    props: { rule, canEdit, loading: false },
  })
}

describe('申赎要素展示区块', () => {
  it('AC-01 展示来源、版本号、生效日期及业务字段', () => {
    const wrapper = mountPanel(makeRule())

    expect(wrapper.get('[data-testid="rule-source"]').text()).toBe('MANUAL')
    expect(wrapper.get('[data-testid="rule-version"]').text()).toBe('2')
    expect(wrapper.get('[data-testid="rule-effective-date"]').text()).toBe('2026-11-21')
    expect(wrapper.get('[data-testid="rule-min_purchase_amount"]').text()).toBe('100.00')
    expect(wrapper.get('[data-testid="rule-purchase_status"]').text()).toBe('开放')
  })

  it('AC-02 无申赎规则时来源、版本、生效日期和业务字段全部为 --，且可新增', () => {
    const wrapper = mountPanel(null)

    expect(wrapper.get('[data-testid="rule-source"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-version"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-effective-date"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-min_purchase_amount"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-min_holding_shares"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-remark"]').text()).toBe('--')

    const editButton = wrapper.get('[data-testid="edit-rule-button"]')
    expect(editButton.text()).toBe('新增申赎要素')
    expect(editButton.attributes('disabled')).toBeUndefined()
  })

  it('AC-03 MANUAL 来源整条展示人工规则', () => {
    const wrapper = mountPanel(
      makeRule({ rule_id: 30, version_no: 3, source_type: 'MANUAL', min_purchase_amount: '100.00' }),
    )

    expect(wrapper.get('[data-testid="rule-source"]').text()).toBe('MANUAL')
    expect(wrapper.get('[data-testid="rule-min_purchase_amount"]').text()).toBe('100.00')
  })

  it('AC-04 仅 ETL 时展示 ETL 来源与版本', () => {
    const wrapper = mountPanel(
      makeRule({ rule_id: 8, version_no: 5, source_type: 'ETL', min_purchase_amount: '1000.00' }),
    )

    expect(wrapper.get('[data-testid="rule-source"]').text()).toBe('ETL')
    expect(wrapper.get('[data-testid="rule-version"]').text()).toBe('5')
    expect(wrapper.get('[data-testid="rule-min_purchase_amount"]').text()).toBe('1000.00')
  })

  it('AC-10 零值与空串分别展示为 0 与 --', () => {
    const wrapper = mountPanel(
      makeRule({
        min_holding_shares: '0.0000',
        redeem_arrival_days: 0,
        daily_purchase_limit: null,
        remark: '',
      }),
    )

    expect(wrapper.get('[data-testid="rule-min_holding_shares"]').text()).toBe('0.0000')
    expect(wrapper.get('[data-testid="rule-redeem_arrival_days"]').text()).toBe('0')
    expect(wrapper.get('[data-testid="rule-daily_purchase_limit"]').text()).toBe('--')
    expect(wrapper.get('[data-testid="rule-remark"]').text()).toBe('--')
  })

  it('点击编辑按钮向父组件抛出 edit 事件', async () => {
    const wrapper = mountPanel(makeRule())

    await wrapper.get('[data-testid="edit-rule-button"]').trigger('click')

    expect(wrapper.emitted('edit')).toHaveLength(1)
  })
})
