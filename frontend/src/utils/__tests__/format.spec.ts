import { describe, expect, it } from 'vitest'

import { displayStatus, displayText, isEmptyValue } from '@/utils/format'

describe('统一展示格式化（AC-10）', () => {
  it('null、undefined、空字符串统一展示为 --', () => {
    expect(displayText(null)).toBe('--')
    expect(displayText(undefined)).toBe('--')
    expect(displayText('')).toBe('--')
  })

  it('仅含空白的字符串展示为 --', () => {
    expect(displayText('   ')).toBe('--')
    expect(isEmptyValue('\t\n')).toBe(true)
  })

  it('数值 0 原样展示，绝不变成 --', () => {
    expect(displayText(0)).toBe('0')
    expect(isEmptyValue(0)).toBe(false)
  })

  it('布尔 false 原样展示，绝不变成 --', () => {
    expect(displayText(false)).toBe('false')
    expect(isEmptyValue(false)).toBe(false)
  })

  it('金额、费率、份额字符串原样展示，不转数字', () => {
    expect(displayText('0.0000')).toBe('0.0000')
    expect(displayText('0.150000')).toBe('0.150000')
    expect(displayText('100.00')).toBe('100.00')
  })

  it('申赎状态空值展示 --，已知状态展示中文，未知值原样展示', () => {
    expect(displayStatus(null)).toBe('--')
    expect(displayStatus('OPEN')).toBe('开放')
    expect(displayStatus('UNKNOWN')).toBe('UNKNOWN')
  })
})
