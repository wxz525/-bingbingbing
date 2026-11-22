import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiRequestError,
  CONFLICT_MESSAGE,
  getApiBaseUrl,
  getFundArchive,
  saveRedemptionRule,
} from '@/api/fundArchive'
import { createRuleFormModel } from '@/constants/redemption'
import { makeRule } from '@/test/fixtures'
import { buildRulePayload } from '@/utils/ruleForm'

function mockResponse(status: number, body: unknown): ReturnType<typeof vi.fn> {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? '' : JSON.stringify(body)),
  })
}

describe('基金档案接口客户端', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('AC-13 仅访问后端基金档案接口，使用环境配置的基础地址', async () => {
    const fetchMock = mockResponse(200, makeRule())
    vi.stubGlobal('fetch', fetchMock)

    await getFundArchive('000001')

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`${getApiBaseUrl()}/api/v1/fund-archives/000001`)
    expect(init.method).toBe('GET')
    expect(String(url)).not.toMatch(/mysql|clickhouse|minio|gy_meta/i)
    expect(JSON.stringify(init.headers)).not.toMatch(/password|secret|token/i)
  })

  it('AC-09 409 冲突映射为 VERSION_CONFLICT，且保留后端错误码', async () => {
    vi.stubGlobal(
      'fetch',
      mockResponse(409, {
        code: 'VERSION_CONFLICT',
        message: '申赎要素已更新，请刷新后重试',
        field_errors: {},
      }),
    )

    const error = await saveRedemptionRule('000001', {} as never).catch((reason) => reason)

    expect(error).toBeInstanceOf(ApiRequestError)
    expect((error as ApiRequestError).status).toBe(409)
    expect((error as ApiRequestError).isConflict).toBe(true)
    expect(CONFLICT_MESSAGE).toBe('当前规则已被其他人修改，请刷新页面后重新编辑')
  })

  it('404 映射为 isNotFound，供页面清空为 --', async () => {
    vi.stubGlobal(
      'fetch',
      mockResponse(404, { code: 'FUND_NOT_FOUND', message: '基金不存在', field_errors: {} }),
    )

    const error = await getFundArchive('999999').catch((reason) => reason)

    expect((error as ApiRequestError).isNotFound).toBe(true)
    expect((error as ApiRequestError).status).toBe(404)
  })

  it('AC-11 500 非 JSON 响应给出明确异常消息', async () => {
    vi.stubGlobal('fetch', mockResponse(500, undefined))

    const error = await getFundArchive('000001').catch((reason) => reason)

    expect((error as ApiRequestError).status).toBe(500)
    expect((error as ApiRequestError).message).toBe('服务异常，请稍后重试')
  })

  it('网络异常映射为 NETWORK_ERROR', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const error = await getFundArchive('000001').catch((reason) => reason)

    expect((error as ApiRequestError).code).toBe('NETWORK_ERROR')
  })

  it('保存请求体只包含后端契约字段，空输入转 null，绝不包含视图占位符 --', () => {
    const rule = makeRule()
    const form = createRuleFormModel(rule)
    form.daily_purchase_limit = ''
    form.remark = '   '

    const payload = buildRulePayload(form, rule)
    const serialized = JSON.stringify(payload)

    expect(payload.expected_rule_id).toBe(12)
    expect(payload.expected_version_no).toBe(2)
    expect(payload.daily_purchase_limit).toBeNull()
    expect(payload.remark).toBeNull()
    expect(payload.min_purchase_amount).toBe('100.00')
    expect(serialized).not.toContain('--')
    expect(Object.keys(payload)).not.toContain('source_type')
    expect(Object.keys(payload)).not.toContain('is_deleted')
  })
})
