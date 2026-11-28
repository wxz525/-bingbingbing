import { describe, expect, it } from 'vitest'

import {
  cleanSeries,
  computeStatistics,
  formatAxisDate,
  formatAxisValue,
  formatIndicatorChange,
  formatIndicatorValue,
  formatNormalizedChange,
  formatSpreadValue,
  indicatorsForAsset,
  MIN_SAMPLE_SIZE,
  normalizeSeries,
  percentileLabel,
  percentileRank,
  quantile,
  rebaseSeries,
  sparklinePath,
  toBasisPoints,
} from '@/utils/indicatorAnalysis'

const SPREAD_OPTIONS = { kind: 'spread' as const, spreadUnit: 'bp' as const }
const RATIO_OPTIONS = { kind: 'ratio' as const }

function series(values: number[]): [string, number][] {
  return values.map((value, index) => [
    `2024-01-${String(index + 1).padStart(2, '0')}`,
    value,
  ])
}

describe('cleanSeries', () => {
  it('过滤非有限数值与非法日期并按日期升序', () => {
    const points: [string, number][] = [
      ['2024-01-03', 3],
      ['2024-01-01', 1],
      ['bad-date', 2],
      ['2024-01-04', Number.NaN],
      ['2024-01-05', Number.POSITIVE_INFINITY],
      ['2024-01-02', 2],
    ]
    expect(cleanSeries(points)).toEqual([
      ['2024-01-01', 1],
      ['2024-01-02', 2],
      ['2024-01-03', 3],
    ])
  })

  it('空输入返回空数组', () => {
    expect(cleanSeries(null)).toEqual([])
    expect(cleanSeries(undefined)).toEqual([])
    expect(cleanSeries([])).toEqual([])
  })

  it('同一日期只保留一条', () => {
    expect(
      cleanSeries([
        ['2024-01-01', 1],
        ['2024-01-01', 9],
      ]),
    ).toEqual([['2024-01-01', 1]])
  })
})

describe('normalizeSeries', () => {
  it('以区间首个有效值为基期换算为 100', () => {
    const result = normalizeSeries([
      ['2024-01-02', 200],
      ['2024-01-03', 250],
      ['2024-01-04', 150],
    ])
    expect(result).toEqual([
      ['2024-01-02', 100],
      ['2024-01-03', 125],
      ['2024-01-04', 75],
    ])
  })

  it('基期为 0 或数据为空时返回空数组', () => {
    expect(normalizeSeries([['2024-01-02', 0], ['2024-01-03', 5]])).toEqual([])
    expect(normalizeSeries([])).toEqual([])
  })

  it('输入乱序时按日期排序后再取基期', () => {
    const result = normalizeSeries([
      ['2024-01-04', 300],
      ['2024-01-02', 100],
      ['2024-01-03', 200],
    ])
    expect(result[0]).toEqual(['2024-01-02', 100])
    expect(result[2]).toEqual(['2024-01-04', 300])
  })

  it('rebaseSeries 以指定基期换算更长的统计序列', () => {
    expect(
      rebaseSeries(
        [
          ['2023-01-02', 50],
          ['2024-01-02', 200],
        ],
        100,
      ),
    ).toEqual([
      ['2023-01-02', 50],
      ['2024-01-02', 200],
    ])
    expect(rebaseSeries([['2024-01-02', 200]], 0)).toEqual([])
  })
})

describe('quantile / percentileRank / computeStatistics', () => {
  it('线性插值分位数', () => {
    const sorted = [1, 2, 3, 4]
    expect(quantile(sorted, 0)).toBe(1)
    expect(quantile(sorted, 0.5)).toBe(2.5)
    expect(quantile(sorted, 1)).toBe(4)
  })

  it('分位数函数对空样本返回 NaN', () => {
    expect(Number.isNaN(quantile([], 0.5))).toBe(true)
  })

  it('当前值的分位为小于等于该值的样本占比', () => {
    expect(percentileRank([1, 2, 3, 4], 2)).toBe(50)
    expect(percentileRank([1, 2, 3, 4], 10)).toBe(100)
    expect(percentileRank([], 2)).toBeNull()
    expect(percentileRank([1, 2], Number.NaN)).toBeNull()
  })

  it('样本量不足 20 时返回 null', () => {
    expect(computeStatistics([1, 2, 3], 3)).toBeNull()
    expect(MIN_SAMPLE_SIZE).toBe(20)
  })

  it('计算均值、中位数、分位、标准差与 Z-score', () => {
    const values = Array.from({ length: 24 }, (_, index) => index + 1)
    const stats = computeStatistics(values, 24)
    expect(stats).not.toBeNull()
    expect(stats?.count).toBe(24)
    expect(stats?.mean).toBe(12.5)
    expect(stats?.median).toBe(12.5)
    expect(stats?.q25).toBeCloseTo(6.75, 6)
    expect(stats?.q75).toBeCloseTo(18.25, 6)
    expect(stats?.min).toBe(1)
    expect(stats?.max).toBe(24)
    expect(stats?.stdDev).toBeCloseTo(7.0711, 3)
    expect(stats?.percentile).toBe(100)
    expect(stats?.zScore).toBeCloseTo(1.626, 3)
  })

  it('标准差为零时 Z-score 返回 null，避免除零', () => {
    const stats = computeStatistics(Array.from({ length: 20 }, () => 5), 5)
    expect(stats?.stdDev).toBe(0)
    expect(stats?.zScore).toBeNull()
    expect(stats?.percentile).toBe(100)
  })

  it('统计时忽略非有限数值', () => {
    const values = [...Array.from({ length: 20 }, (_, index) => index + 1), Number.NaN]
    expect(computeStatistics(values, 20)?.count).toBe(20)
  })
})

describe('利差单位转换', () => {
  it('1pp = 100bp', () => {
    expect(toBasisPoints(1)).toBe(100)
    expect(formatSpreadValue(1, 'pp')).toBe('1.00 pp')
    expect(formatSpreadValue(1, 'bp')).toBe('100 bp')
  })

  it('负利差换算并保留符号', () => {
    expect(formatSpreadValue(-2.65, 'bp')).toBe('-265 bp')
    expect(formatSpreadValue(-2.65, 'pp')).toBe('-2.65 pp')
    expect(formatSpreadValue(-2.65, 'bp', { signed: true })).toBe('-265 bp')
    expect(formatSpreadValue(0.123, 'bp')).toBe('12 bp')
  })

  it('非有限数值返回占位符', () => {
    expect(formatSpreadValue(Number.NaN, 'bp')).toBe('--')
    expect(formatIndicatorValue(null, SPREAD_OPTIONS)).toBe('--')
  })

  it('利差变化按所选单位同步换算', () => {
    expect(formatIndicatorChange(-0.25, 1.5, SPREAD_OPTIONS)).toBe('-25 bp')
    expect(
      formatIndicatorChange(-0.25, 1.5, { kind: 'spread', spreadUnit: 'pp' }),
    ).toBe('-0.25 pp')
  })

  it('纵轴刻度按 bp 取整', () => {
    expect(formatAxisValue(0.5, SPREAD_OPTIONS)).toBe('50')
    expect(formatAxisValue(-2.65, SPREAD_OPTIONS)).toBe('-265')
    expect(formatAxisValue(-2.65, { kind: 'spread', spreadUnit: 'pp' })).toBe('-2.65')
  })
})

describe('比值展示与标准化变化', () => {
  it('原始比值保留两位小数，可附带单位', () => {
    expect(formatIndicatorValue(1.234, RATIO_OPTIONS)).toBe('1.23')
    expect(formatIndicatorValue(1.234, { ...RATIO_OPTIONS, withUnit: true })).toBe('1.23 倍')
  })

  it('标准化模式保留一位小数', () => {
    expect(formatIndicatorValue(102.345, { ...RATIO_OPTIONS, normalized: true })).toBe('102.3')
  })

  it('标准化变化相对基期 100', () => {
    expect(formatNormalizedChange(102.35)).toBe('+2.35%')
    expect(formatNormalizedChange(97.1)).toBe('-2.90%')
    expect(formatNormalizedChange(null)).toBe('--')
  })

  it('原始比值变化同时给出绝对差与百分比', () => {
    expect(formatIndicatorChange(0.1, 2, RATIO_OPTIONS)).toBe('+0.10（+5.00%）')
    expect(formatIndicatorChange(0.1, 0, RATIO_OPTIONS)).toBe('+0.10')
  })

  it('标准化模式下的区间变化以百分比表示', () => {
    expect(
      formatIndicatorChange(2.35, 100, { ...RATIO_OPTIONS, normalized: true }),
    ).toBe('+2.4%')
  })

  it('比值纵轴精度随量级调整', () => {
    expect(formatAxisValue(1.234, RATIO_OPTIONS)).toBe('1.23')
    expect(formatAxisValue(123.45, RATIO_OPTIONS)).toBe('123.5')
    expect(formatAxisValue(102.3, { ...RATIO_OPTIONS, normalized: true })).toBe('102')
  })
})

describe('历史分位标签', () => {
  it('按 25% / 75% 划分偏低、中位、偏高', () => {
    expect(percentileLabel(10)).toBe('历史偏低')
    expect(percentileLabel(50)).toBe('历史中位')
    expect(percentileLabel(90)).toBe('历史偏高')
    expect(percentileLabel(null)).toBe('样本不足')
  })
})

describe('sparklinePath', () => {
  it('真实序列生成折线路径', () => {
    const path = sparklinePath(
      [
        ['2024-01-01', 1],
        ['2024-01-02', 2],
      ],
      10,
      10,
      0,
    )
    expect(path).toBe('M0.0,10.0 L10.0,0.0')
  })

  it('数据不足时不生成路径', () => {
    expect(sparklinePath([], 60, 20)).toBe('')
    expect(sparklinePath([['2024-01-01', 1]], 60, 20)).toBe('')
  })
})

describe('资产相关性映射', () => {
  it('沪深300 只返回与沪深300 直接相关的指标', () => {
    const keys = indicatorsForAsset('沪深300').map((item) => item.key)
    expect(keys).toEqual(['csi300_csi500', 'chinext_csi300', 'hsi_csi300', 'spx_csi300'])
    expect(keys).not.toContain('gold_silver')
    expect(keys).not.toContain('cn_us_10y')
  })

  it('黄金期货返回商品比值', () => {
    expect(indicatorsForAsset('COMEX黄金期货').map((item) => item.key)).toEqual([
      'gold_silver',
      'gold_copper',
    ])
  })

  it('未知标的返回空数组', () => {
    expect(indicatorsForAsset('美元指数')).toEqual([])
    expect(indicatorsForAsset('')).toEqual([])
  })
})

describe('日期轴格式', () => {
  it('短区间显示月-日，长区间显示年月', () => {
    expect(formatAxisDate('2024-03-05', 90)).toBe('03-05')
    expect(formatAxisDate('2024-03-05', 1000)).toBe('24-03')
  })

  it('使用 cleanSeries 后的数据绘制统计', () => {
    const points = series(Array.from({ length: 30 }, (_, index) => index + 1))
    const stats = computeStatistics(
      cleanSeries(points).map(([, value]) => value),
      30,
    )
    expect(stats?.count).toBe(30)
    expect(stats?.max).toBe(30)
  })
})
