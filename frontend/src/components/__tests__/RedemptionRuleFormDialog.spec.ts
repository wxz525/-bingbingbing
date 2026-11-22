import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RedemptionRuleFormDialog from '@/components/RedemptionRuleFormDialog.vue'
import { makeRule } from '@/test/fixtures'
import type { RedemptionRule, RedemptionRulePayload } from '@/types/fundArchive'

function mountDialog(props: Record<string, unknown> = {}) {
  return mount(RedemptionRuleFormDialog, {
    props: {
      modelValue: true,
      fundCode: '000001',
      rule: makeRule(),
      submitting: false,
      error: null,
      ...props,
    },
  })
}

function fieldInput(wrapper: VueWrapper, key: string) {
  const host = wrapper.get(`[data-testid="field-${key}"]`)
  if (host.element.matches('input, textarea')) {
    return host
  }
  return host.get('input, textarea')
}

function inputValue(wrapper: VueWrapper, key: string): string {
  return (fieldInput(wrapper, key).element as HTMLInputElement).value
}

async function fill(wrapper: VueWrapper, key: string, value: string): Promise<void> {
  await fieldInput(wrapper, key).setValue(value)
}

function emittedPayload(wrapper: VueWrapper): RedemptionRulePayload {
  const events = wrapper.emitted('submit')
  expect(events).toBeTruthy()
  return events![0][0] as RedemptionRulePayload
}

describe('申赎要素编辑弹窗', () => {
  it('AC-05 回显当前规则，并把 expected_rule_id / expected_version_no 传给后端', async () => {
    const rule = makeRule({ rule_id: 10, version_no: 1, source_type: 'ETL' })
    const wrapper = mountDialog({ rule })

    expect(inputValue(wrapper, 'min_purchase_amount')).toBe('100.00')
    expect(inputValue(wrapper, 'min_redeem_shares')).toBe('1.0000')

    await wrapper.get('[data-testid="submit-rule-button"]').trigger('click')

    const payload = emittedPayload(wrapper)
    expect(payload.expected_rule_id).toBe(10)
    expect(payload.expected_version_no).toBe(1)
    expect(payload.min_purchase_amount).toBe('100.00')
    expect(payload.daily_purchase_limit).toBeNull()
    expect(JSON.stringify(payload)).not.toContain('--')
  })

  it('AC-14 首次新增时 expected_rule_id 为 null、expected_version_no 为 0', async () => {
    const wrapper = mountDialog({ rule: null })

    expect(inputValue(wrapper, 'min_purchase_amount')).toBe('')

    await fill(wrapper, 'min_purchase_amount', '500.00')
    await wrapper.get('[data-testid="submit-rule-button"]').trigger('click')

    const payload = emittedPayload(wrapper)
    expect(payload.expected_rule_id).toBeNull()
    expect(payload.expected_version_no).toBe(0)
    expect(payload.min_purchase_amount).toBe('500.00')
    expect(payload.remark).toBeNull()
  })

  it('AC-08 客户端基础校验拦截非法金额，不提交', async () => {
    const wrapper = mountDialog()

    await fill(wrapper, 'min_purchase_amount', '-1')
    await wrapper.get('[data-testid="submit-rule-button"]').trigger('click')

    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.text()).toContain('最低申购金额必须是合法的非负十进制数')
  })

  it('提交中按钮置灰禁用，且不会重复提交', async () => {
    const wrapper = mountDialog({ submitting: true })
    const button = wrapper.get('[data-testid="submit-rule-button"]')

    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')

    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('AC-07 保存失败时保留用户已填写内容并展示异常提示', async () => {
    const wrapper = mountDialog()

    await fill(wrapper, 'min_purchase_amount', '888.88')
    await wrapper.setProps({
      error: {
        status: 500,
        code: 'DATABASE_ERROR',
        message: '数据库操作失败',
        fieldErrors: {},
      },
    })

    expect(inputValue(wrapper, 'min_purchase_amount')).toBe('888.88')
    expect(wrapper.get('[data-testid="save-error-alert"]').text()).toContain('数据库操作失败')
  })

  it('AC-07 后端字段错误展示在对应输入项，输入不被清空', async () => {
    const wrapper = mountDialog()

    await fill(wrapper, 'redeem_fee_rate', '120')
    await wrapper.setProps({
      error: {
        status: 400,
        code: 'VALIDATION_ERROR',
        message: '请求参数校验失败',
        fieldErrors: { redeem_fee_rate: '必须小于或等于 100' },
      },
    })

    expect(wrapper.text()).toContain('必须小于或等于 100')
    expect(inputValue(wrapper, 'redeem_fee_rate')).toBe('120')
  })

  it('AC-09 409 冲突展示固定提示文案，且不覆盖用户输入', async () => {
    const wrapper = mountDialog({ rule: makeRule({ rule_id: 20, version_no: 3 }) })

    await fill(wrapper, 'min_purchase_amount', '300.00')
    await wrapper.setProps({
      error: {
        status: 409,
        code: 'VERSION_CONFLICT',
        message: '申赎要素已更新，请刷新后重试',
        fieldErrors: {},
      },
    })

    expect(wrapper.get('[data-testid="conflict-alert"]').text()).toContain(
      '当前规则已被其他人修改，请刷新页面后重新编辑',
    )
    expect(inputValue(wrapper, 'min_purchase_amount')).toBe('300.00')
  })

  it('金额与份额按后端字符串原样回显，不做浮点转换', () => {
    const wrapper = mountDialog({
      rule: makeRule({
        min_purchase_amount: '0.00',
        min_holding_shares: '0.0000',
        purchase_fee_rate: '0.150000',
      }),
    })

    expect(inputValue(wrapper, 'min_purchase_amount')).toBe('0.00')
    expect(inputValue(wrapper, 'min_holding_shares')).toBe('0.0000')
    expect(inputValue(wrapper, 'purchase_fee_rate')).toBe('0.150000')
  })

  it('空规则字段在表单中为空输入，绝不预填 --', async () => {
    const rule: RedemptionRule = makeRule({ remark: null, daily_purchase_limit: null })
    const wrapper = mountDialog({ rule })

    expect(inputValue(wrapper, 'daily_purchase_limit')).toBe('')
    expect(inputValue(wrapper, 'remark')).toBe('')

    await wrapper.get('[data-testid="submit-rule-button"]').trigger('click')
    const payload = emittedPayload(wrapper)
    expect(payload.daily_purchase_limit).toBeNull()
    expect(payload.remark).toBeNull()
  })
})
