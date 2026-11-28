/**
 * 比值 / 利差研究相关的纯函数派生计算。
 *
 * 所有函数只做前端派生：不修改后端返回的原始数值，
 * 不生成任何虚构数据；数据不足时返回 null / 空数组，由调用方展示「样本不足」。
 */

export type IndicatorKind = 'ratio' | 'spread'
export type SpreadUnit = 'bp' | 'pp'
export type IndicatorGroupKey = 'commodity' | 'equity_style' | 'cross_market' | 'rates'

export interface IndicatorGroup {
  key: IndicatorGroupKey
  label: string
  caption: string
}

export interface IndicatorDefinition {
  key: string
  name: string
  english: string
  kind: IndicatorKind
  group: IndicatorGroupKey
  /** 分子资产（接口 INDICATOR_DEFINITIONS 中的 numerator，用于资产相关性匹配） */
  numerator: string
  /** 分母资产 */
  denominator: string
  /** 计算方式，一句话 */
  formula: string
  /** 概览区的一句话研究意义 */
  summary: string
  /** 指标定义 */
  definition: string
  /** 研究价值 */
  researchValue: string
  /** 数值上升的含义 */
  rising: string
  /** 数值下降的含义 */
  falling: string
  /** 数据来源与计算口径 */
  caliber: string
  /** 使用限制 */
  caveat: string
  /** 是否支持「相对强弱（基期=100）」模式 */
  standardized: boolean
  /** 后端单位换算口径是否待核验 */
  caliberPending: boolean
}

export const INDICATOR_GROUPS: readonly IndicatorGroup[] = [
  {
    key: 'commodity',
    label: '商品与风险偏好',
    caption: '贵金属相对定价与工业需求',
  },
  {
    key: 'equity_style',
    label: '股票市场风格',
    caption: '大小盘、成长价值与科技权重',
  },
  {
    key: 'cross_market',
    label: '跨市场相对表现',
    caption: '不同股票市场之间的相对强弱',
  },
  {
    key: 'rates',
    label: '利率与期限结构',
    caption: '经济体利差与收益率曲线形态',
  },
]

const STOCK_RATIO_CAVEAT =
  '指数点位受基点与编制方式影响，原始比值的绝对水平不能直接用于判断估值高低；跨国指数对比未做汇率调整，仅反映本币价格指数相对表现。'

export const INDICATOR_DEFINITIONS: readonly IndicatorDefinition[] = [
  {
    key: 'gold_silver',
    name: '金银比',
    english: 'Gold / Silver Ratio',
    kind: 'ratio',
    group: 'commodity',
    numerator: 'COMEX黄金期货',
    denominator: 'COMEX白银期货',
    formula: '黄金价格 ÷ 白银价格',
    summary: '黄金与白银的相对价格，用于观察两种贵金属的相对强弱。',
    definition:
      '以同一报价币种与同一重量单位表示的黄金价格除以白银价格，衡量一单位白银可兑换的黄金数量。',
    researchValue:
      '黄金的避险与储备属性更强，白银的工业需求占比更高。该比值可用于观察市场在避险与工业需求之间的偏好变化，并辅助判断贵金属内部相对定价状态。',
    rising: '数值上升表示白银相对黄金走弱，或黄金相对白银走强。',
    falling: '数值下降表示白银相对黄金走强，或黄金相对白银走弱。',
    caliber: '取 COMEX 黄金期货与 COMEX 白银期货的收盘价，按交易日取交集后相除。',
    caveat:
      '需确认分子分母报价币种与重量单位一致；期货主力合约切换会造成序列跳变，短周期比较时应留意换月影响。',
    standardized: false,
    caliberPending: false,
  },
  {
    key: 'gold_copper',
    name: '金铜比',
    english: 'Gold / Copper Ratio',
    kind: 'ratio',
    group: 'commodity',
    numerator: 'COMEX黄金期货',
    denominator: 'COMEX铜期货',
    formula: '黄金价格 ÷ 铜价格',
    summary: '黄金与铜的相对价格，用于观察避险偏好与工业需求预期的相对变化。',
    definition:
      '黄金价格除以铜价格，把偏避险的贵金属与偏工业需求的工业金属放在同一尺度下比较。',
    researchValue:
      '铜对制造业与投资周期更敏感，黄金对避险与流动性更敏感。该比值可用于观察市场对增长预期与避险需求的相对侧重。',
    rising: '数值上升表示铜相对黄金走弱，工业需求预期相对偏弱或避险需求相对偏强。',
    falling: '数值下降表示铜相对黄金走强，工业需求预期相对改善。',
    caliber:
      'COMEX 黄金期货（美元/盎司）÷ COMEX 铜期货（美元/磅），两端重量单位不同且合约乘数不同，后端未提供明确换算说明。',
    caveat:
      '数据口径待核验：分子分母的重量单位与合约规格不一致，比值的绝对水平不具备直接经济含义，只宜观察趋势方向；不得据此推断确定性的宏观结论。',
    standardized: false,
    caliberPending: true,
  },
  {
    key: 'csi300_csi500',
    name: '沪深300 / 中证500',
    english: 'CSI 300 / CSI 500 Ratio',
    kind: 'ratio',
    group: 'equity_style',
    numerator: '沪深300',
    denominator: '中证500',
    formula: '沪深300 指数 ÷ 中证500 指数',
    summary: '大盘与中盘风格的相对表现，用于观察资金在两种市值风格之间的偏好。',
    definition:
      '沪深300 代表沪深两市大市值蓝筹，中证500 代表中盘股，两者点位相除得到风格比价。',
    researchValue:
      '用于观察市场风格轮动：比值抬升通常与资金偏向大盘蓝筹同时出现，比值回落则更常见于中小盘相对占优的阶段。',
    rising: '数值上升表示沪深300 相对中证500 走强，大盘风格相对占优。',
    falling: '数值下降表示中证500 相对沪深300 走强，中盘风格相对占优。',
    caliber: '沪深300 与中证500 收盘点位，按交易日取交集后相除，均为人民币计价价格指数。',
    caveat: STOCK_RATIO_CAVEAT,
    standardized: true,
    caliberPending: false,
  },
  {
    key: 'chinext_csi300',
    name: '创业板指 / 沪深300',
    english: 'ChiNext / CSI 300 Ratio',
    kind: 'ratio',
    group: 'equity_style',
    numerator: '创业板指',
    denominator: '沪深300',
    formula: '创业板指 ÷ 沪深300 指数',
    summary: '成长与价值风格的相对表现，用于观察成长板块相对大盘蓝筹的强弱。',
    definition: '创业板指与沪深300 收盘点位相除，反映成长风格资产相对大盘蓝筹的价格表现。',
    researchValue:
      '可用于观察成长 / 价值风格的相对强弱，以及风险偏好变化时资金在两类风格之间的迁移。',
    rising: '数值上升表示创业板指相对沪深300 走强，成长风格相对占优。',
    falling: '数值下降表示创业板指相对沪深300 走弱，价值或大盘风格相对占优。',
    caliber: '创业板指与沪深300 收盘点位，按交易日取交集后相除，均为人民币计价价格指数。',
    caveat: STOCK_RATIO_CAVEAT,
    standardized: true,
    caliberPending: false,
  },
  {
    key: 'nasdaq_spx',
    name: '纳指100 / 标普500',
    english: 'Nasdaq 100 / S&P 500 Ratio',
    kind: 'ratio',
    group: 'equity_style',
    numerator: '纳斯达克100',
    denominator: '标普500',
    formula: '纳斯达克100 指数 ÷ 标普500 指数',
    summary: '科技权重与大盘宽基的相对表现，用于观察美股内部风格结构。',
    definition: '纳斯达克100 与标普500 收盘点位相除，衡量科技权重较高的指数相对宽基指数的强弱。',
    researchValue:
      '用于观察美股科技板块相对整体市场的强弱，以及利率与盈利预期变化下的风格切换。',
    rising: '数值上升表示科技权重板块相对宽基走强。',
    falling: '数值下降表示科技权重板块相对宽基走弱，宽基相对占优。',
    caliber: '纳斯达克100 与标普500 收盘点位，按交易日取交集后相除，均为美元计价价格指数。',
    caveat: STOCK_RATIO_CAVEAT,
    standardized: true,
    caliberPending: false,
  },
  {
    key: 'hsi_csi300',
    name: '恒生指数 / 沪深300',
    english: 'Hang Seng / CSI 300 Ratio',
    kind: 'ratio',
    group: 'cross_market',
    numerator: '恒生指数',
    denominator: '沪深300',
    formula: '恒生指数 ÷ 沪深300 指数',
    summary: '港股与 A 股的相对表现，用于观察两个市场的相对强弱。',
    definition: '恒生指数与沪深300 收盘点位相除，比较港股与 A 股大市值板块的价格表现。',
    researchValue:
      '用于观察港股与 A 股之间的相对资金流向与风险偏好差异，辅助跨市场配置研究。',
    rising: '数值上升表示港股相对 A 股走强。',
    falling: '数值下降表示 A 股相对港股走强。',
    caliber:
      '恒生指数（港元）与沪深300（人民币）收盘点位相除，未做汇率转换，属于本币价格指数的相对表现。',
    caveat: STOCK_RATIO_CAVEAT,
    standardized: true,
    caliberPending: false,
  },
  {
    key: 'spx_csi300',
    name: '标普500 / 沪深300',
    english: 'S&P 500 / CSI 300 Ratio',
    kind: 'ratio',
    group: 'cross_market',
    numerator: '标普500',
    denominator: '沪深300',
    formula: '标普500 指数 ÷ 沪深300 指数',
    summary: '中美权益市场的相对表现，用于观察两个市场的相对强弱。',
    definition: '标普500 与沪深300 收盘点位相除，比较中美股票市场大市值板块的价格表现。',
    researchValue:
      '用于观察中美权益市场的相对表现差异，结合利率与盈利周期研究跨市场相对强弱。',
    rising: '数值上升表示美股相对 A 股走强。',
    falling: '数值下降表示 A 股相对美股走强。',
    caliber:
      '标普500（美元）与沪深300（人民币）收盘点位相除，未做汇率调整，属于本币价格指数的相对表现。',
    caveat:
      '数据未做汇率转换，汇率波动会同时影响比值，不能把比值变化全部归因于股市表现；原始比值的绝对水平不具备估值含义。',
    standardized: true,
    caliberPending: false,
  },
  {
    key: 'cn_us_10y',
    name: '中美10年期国债利差',
    english: 'China–US 10Y Yield Spread',
    kind: 'spread',
    group: 'rates',
    numerator: '中国10年国债收益率',
    denominator: '美国10年期国债收益率',
    formula: '中国10年期国债收益率 − 美国10年期国债收益率',
    summary: '中美两个经济体长端无风险利率之差，用于观察利率环境差异。',
    definition: '以相同期限（10年）的中美国债收益率为两端，做差得到跨市场利差。',
    researchValue:
      '用于观察中美长端利率环境的相对变化，辅助分析跨境资金成本与利率周期差异。',
    rising: '数值上升表示中美长端利差上行（中国相对美国更高，或负利差幅度收窄）。',
    falling: '数值下降表示中美长端利差下行（中国相对美国更低，或负利差幅度扩大）。',
    caliber: '中国10年期国债收益率 − 美国10年期国债收益率，单位百分点（pp），按交易日取交集。',
    caveat:
      '利差可能长期为负：负值区间内数值上升意味着倒挂幅度收窄，而不是「利差扩大」。判断扩大 / 收窄应看绝对差距的变化，不要只看数值正负。',
    standardized: false,
    caliberPending: false,
  },
  {
    key: 'cn_term_10y_1y',
    name: '中国期限利差 10Y−1Y',
    english: 'China 10Y–1Y Term Spread',
    kind: 'spread',
    group: 'rates',
    numerator: '中国10年国债收益率',
    denominator: '中国1年国债收益率',
    formula: '中国10年期国债收益率 − 中国1年期国债收益率',
    summary: '中国国债收益率曲线的陡峭程度，用于观察短端与长端的相对定价。',
    definition: '同一经济体不同期限国债收益率之差，10Y−1Y 是常用的曲线陡峭度衡量方式。',
    researchValue:
      '用于观察货币政策预期与经济增长预期在曲线上的体现；曲线倒挂时该利差转负。',
    rising: '数值上升表示曲线变陡（长端相对短端更高，或倒挂幅度收窄）。',
    falling: '数值下降表示曲线变平（长端相对短端更低，或倒挂幅度扩大）。',
    caliber: '中国10年期国债收益率 − 中国1年期国债收益率，单位百分点（pp），按交易日取交集。',
    caveat:
      '倒挂时利差为负：负值区间内数值上升代表倒挂收窄，不代表曲线陡峭化幅度扩大。应结合两端收益率水平解读，不要单独把利差当作经济衰退的确定性信号。',
    standardized: false,
    caliberPending: false,
  },
  {
    key: 'cn_term_30y_10y',
    name: '中国期限利差 30Y−10Y',
    english: 'China 30Y–10Y Term Spread',
    kind: 'spread',
    group: 'rates',
    numerator: '中国30年国债收益率',
    denominator: '中国10年国债收益率',
    formula: '中国30年期国债收益率 − 中国10年期国债收益率',
    summary: '超长端相对 10 年期的期限溢价，用于观察长端曲线形态。',
    definition: '30 年期与 10 年期国债收益率之差，反映超长端相对中长端的定价差异。',
    researchValue:
      '用于观察超长端供需、久期偏好与长期通胀预期变化，辅助判断长端曲线形态。',
    rising: '数值上升表示超长端相对 10 年期上行，期限溢价走阔。',
    falling: '数值下降表示超长端相对 10 年期下行，期限溢价收窄。',
    caliber: '中国30年期国债收益率 − 中国10年期国债收益率，单位百分点（pp），按交易日取交集。',
    caveat:
      '超长端流动性相对较弱，单日波动可能偏大；不宜用短周期变化推断长期利率趋势。',
    standardized: false,
    caliberPending: false,
  },
  {
    key: 'cn_de_10y',
    name: '中德10年期国债利差',
    english: 'China–Germany 10Y Yield Spread',
    kind: 'spread',
    group: 'rates',
    numerator: '中国10年国债收益率',
    denominator: '德国10年期国债收益率',
    formula: '中国10年期国债收益率 − 德国10年期国债收益率',
    summary: '中德长端利率之差，用于观察两个经济体利率环境的相对差异。',
    definition: '以相同期限的中德国债收益率为两端，做差得到跨市场利差。',
    researchValue:
      '用于比较中国与欧元区核心经济体的长端利率环境，观察相对利率周期与资金成本差异。',
    rising: '数值上升表示中国长端利率相对德国更高，或负利差幅度收窄。',
    falling: '数值下降表示中国长端利率相对德国更低，或负利差幅度扩大。',
    caliber: '中国10年期国债收益率 − 德国10年期国债收益率，单位百分点（pp），按交易日取交集。',
    caveat:
      '负值区间内数值上升代表倒挂收窄，而非利差扩大；两国假期不同会导致交易日对齐后的样本减少。',
    standardized: false,
    caliberPending: false,
  },
  {
    key: 'us_de_10y',
    name: '美德10年期国债利差',
    english: 'US–Germany 10Y Yield Spread',
    kind: 'spread',
    group: 'rates',
    numerator: '美国10年期国债收益率',
    denominator: '德国10年期国债收益率',
    formula: '美国10年期国债收益率 − 德国10年期国债收益率',
    summary: '美债与德债长端利率之差，用于观察美元与欧元区核心利率的相对变化。',
    definition: '以相同期限的美德国债收益率为两端，做差得到跨市场利差。',
    researchValue:
      '用于观察美欧长端利率环境差异，辅助分析跨市场利率与汇率背景。',
    rising: '数值上升表示美国长端利率相对德国更高，利差走阔。',
    falling: '数值下降表示美国长端利率相对德国更低，利差收窄。',
    caliber: '美国10年期国债收益率 − 德国10年期国债收益率，单位百分点（pp），按交易日取交集。',
    caveat:
      '利差变化同时受两国货币政策与通胀预期影响，不能单独据此推断汇率方向。',
    standardized: false,
    caliberPending: false,
  },
]

export const INDICATOR_MAP: Record<string, IndicatorDefinition> = Object.fromEntries(
  INDICATOR_DEFINITIONS.map((item) => [item.key, item]),
)

export function getIndicatorDefinition(key: string): IndicatorDefinition | null {
  return INDICATOR_MAP[key] ?? null
}

/** 与给定行情标的直接相关的指标（分子或分母为该标的） */
export function indicatorsForAsset(assetName: string): IndicatorDefinition[] {
  if (!assetName) {
    return []
  }
  return INDICATOR_DEFINITIONS.filter(
    (item) => item.numerator === assetName || item.denominator === assetName,
  )
}

/** 按分组顺序返回给定 key 列表对应的指标定义 */
export function groupIndicatorDefinitions(keys: readonly string[]): {
  group: IndicatorGroup
  items: IndicatorDefinition[]
}[] {
  const keySet = new Set(keys)
  return INDICATOR_GROUPS.map((group) => ({
    group,
    items: INDICATOR_DEFINITIONS.filter((item) => item.group === group.key && keySet.has(item.key)),
  })).filter((entry) => entry.items.length > 0)
}

/** 样本量低于该阈值时不计算统计量，由界面展示「样本不足」 */
export const MIN_SAMPLE_SIZE = 20

export type Point = [string, number]

/**
 * 清洗接口返回的 points：剔除非法日期、非有限数值、重复日期，并按日期升序排列。
 * 不补点、不插值、不改变数值。
 */
export function cleanSeries(
  points: readonly (readonly [string, number])[] | null | undefined,
): Point[] {
  if (!points?.length) {
    return []
  }
  const valid: Point[] = []
  for (const point of points) {
    if (!point || point.length < 2) {
      continue
    }
    const [date, value] = point
    if (typeof date !== 'string' || typeof value !== 'number') {
      continue
    }
    if (!Number.isFinite(value) || !Number.isFinite(Date.parse(date))) {
      continue
    }
    valid.push([date, value])
  }
  valid.sort((a, b) => Date.parse(a[0]) - Date.parse(b[0]))
  const result: Point[] = []
  const seen = new Set<string>()
  for (const point of valid) {
    if (seen.has(point[0])) {
      continue
    }
    seen.add(point[0])
    result.push(point)
  }
  return result
}

/**
 * 相对强弱序列：以区间内首个有效数值为基期，换算为基期 = 100。
 * 基期非有限值或为 0 时返回空数组，避免出现无穷大 / NaN。
 */
export function normalizeSeries(
  points: readonly (readonly [string, number])[] | null | undefined,
): Point[] {
  const clean = cleanSeries(points)
  if (!clean.length) {
    return []
  }
  const base = clean[0][1]
  if (!Number.isFinite(base) || base === 0) {
    return []
  }
  return clean.map(([date, value]) => [date, (value / base) * 100])
}

/** 把另一段区间的原始序列换算到给定基期的指数口径（用于标准化模式下的统计量） */
export function rebaseSeries(
  points: readonly (readonly [string, number])[] | null | undefined,
  base: number,
): Point[] {
  const clean = cleanSeries(points)
  if (!clean.length || !Number.isFinite(base) || base === 0) {
    return []
  }
  return clean.map(([date, value]) => [date, (value / base) * 100])
}

/** 线性插值分位数（与常见 PERCENTILE.INC 口径一致），入参必须已升序 */
export function quantile(sortedValues: readonly number[], q: number): number {
  if (!sortedValues.length) {
    return Number.NaN
  }
  const bounded = Math.min(Math.max(q, 0), 1)
  const position = (sortedValues.length - 1) * bounded
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  if (lower === upper) {
    return sortedValues[lower]
  }
  const weight = position - lower
  return sortedValues[lower] * (1 - weight) + sortedValues[upper] * weight
}

/** 当前值在样本中的位置：小于等于当前值的样本占比（0–100） */
export function percentileRank(sortedValues: readonly number[], current: number): number | null {
  if (!sortedValues.length || !Number.isFinite(current)) {
    return null
  }
  let count = 0
  for (const value of sortedValues) {
    if (value <= current) {
      count += 1
    }
  }
  return (count / sortedValues.length) * 100
}

export interface IndicatorStatistics {
  count: number
  mean: number
  median: number
  q25: number
  q75: number
  min: number
  max: number
  stdDev: number
  percentile: number | null
  zScore: number | null
}

/**
 * 历史统计：均值、中位数、25% / 75% 分位、极值、样本标准差、当前值分位与 Z-score。
 * 有效样本少于 MIN_SAMPLE_SIZE 时返回 null（界面展示「样本不足」）。
 */
export function computeStatistics(
  values: readonly number[],
  current?: number,
): IndicatorStatistics | null {
  const clean = values.filter((value) => Number.isFinite(value))
  if (clean.length < MIN_SAMPLE_SIZE) {
    return null
  }
  const sorted = [...clean].sort((a, b) => a - b)
  const count = sorted.length
  const sum = sorted.reduce((total, value) => total + value, 0)
  const mean = sum / count
  const variance =
    sorted.reduce((total, value) => total + (value - mean) ** 2, 0) / (count - 1)
  const stdDev = Math.sqrt(variance)
  const target = Number.isFinite(current) ? (current as number) : sorted[count - 1]
  return {
    count,
    mean,
    median: quantile(sorted, 0.5),
    q25: quantile(sorted, 0.25),
    q75: quantile(sorted, 0.75),
    min: sorted[0],
    max: sorted[count - 1],
    stdDev,
    percentile: percentileRank(sorted, target),
    zScore: stdDev > 0 ? (target - mean) / stdDev : null,
  }
}

export function signedDigits(value: number, digits: number): string {
  if (!Number.isFinite(value)) {
    return '--'
  }
  const magnitude = Math.abs(value).toFixed(digits)
  if (Number(magnitude) === 0) {
    return (0).toFixed(digits)
  }
  return `${value > 0 ? '+' : '-'}${magnitude}`
}

/** 百分比点 → 基点，1pp = 100bp */
export function toBasisPoints(valueInPp: number): number {
  return valueInPp * 100
}

export function formatSpreadValue(
  valueInPp: number,
  unit: SpreadUnit,
  options: { signed?: boolean; digits?: number } = {},
): string {
  if (!Number.isFinite(valueInPp)) {
    return '--'
  }
  const converted = unit === 'bp' ? toBasisPoints(valueInPp) : valueInPp
  const digits = options.digits ?? (unit === 'bp' ? 0 : 2)
  const text = options.signed
    ? signedDigits(converted, digits)
    : converted.toFixed(digits)
  return `${text} ${unit}`
}

export interface IndicatorDisplayOptions {
  kind: IndicatorKind
  spreadUnit?: SpreadUnit
  /** 相对强弱（基期=100）模式，仅 ratio 指标可用 */
  normalized?: boolean
  signed?: boolean
  withUnit?: boolean
  digits?: number
}

export function formatIndicatorValue(
  value: number | null | undefined,
  options: IndicatorDisplayOptions,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '--'
  }
  const { kind, spreadUnit = 'bp', normalized = false, signed = false, withUnit = false } = options
  if (kind === 'spread') {
    return formatSpreadValue(value, spreadUnit, { signed })
  }
  const digits = options.digits ?? (normalized ? 1 : 2)
  const text = signed ? signedDigits(value, digits) : value.toFixed(digits)
  return withUnit && !normalized ? `${text} 倍` : text
}

/** 纵轴刻度：不重复单位文字，利差按 bp 换算后再取整 */
export function formatAxisValue(value: number, options: IndicatorDisplayOptions): string {
  if (!Number.isFinite(value)) {
    return ''
  }
  const { kind, spreadUnit = 'bp', normalized = false } = options
  if (kind === 'spread') {
    return spreadUnit === 'bp'
      ? toBasisPoints(value).toFixed(0)
      : value.toFixed(2)
  }
  if (normalized) {
    return value.toFixed(0)
  }
  return value.toFixed(Math.abs(value) >= 100 ? 1 : 2)
}

export function formatAxisUnit(options: IndicatorDisplayOptions): string {
  const { kind, spreadUnit = 'bp', normalized = false } = options
  if (kind === 'spread') {
    return spreadUnit
  }
  return normalized ? '指数（基期=100）' : '倍'
}

/** 区间变化：利差显示 bp / pp 差值，比值显示绝对差值与百分比 */
export function formatIndicatorChange(
  change: number | null | undefined,
  baseValue: number | null | undefined,
  options: IndicatorDisplayOptions,
): string {
  if (change === null || change === undefined || !Number.isFinite(change)) {
    return '--'
  }
  if (options.kind === 'spread') {
    return formatSpreadValue(change, options.spreadUnit ?? 'bp', { signed: true })
  }
  const absolute = formatIndicatorValue(change, { ...options, signed: true, withUnit: false })
  if (options.normalized) {
    return `${absolute}%`
  }
  if (!baseValue || !Number.isFinite(baseValue) || baseValue === 0) {
    return absolute
  }
  const pct = (change / baseValue) * 100
  return `${absolute}（${signedDigits(pct, 2)}%）`
}

/** 相对强弱较基期的百分比变化，例如 +2.35% */
export function formatNormalizedChange(latest: number | null | undefined): string {
  if (latest === null || latest === undefined || !Number.isFinite(latest)) {
    return '--'
  }
  return `${signedDigits(latest - 100, 2)}%`
}

export type PercentileZone = 'low' | 'mid' | 'high'

export function percentileZone(percentile: number): PercentileZone {
  if (percentile < 25) {
    return 'low'
  }
  if (percentile > 75) {
    return 'high'
  }
  return 'mid'
}

export function percentileLabel(percentile: number | null): string {
  if (percentile === null || !Number.isFinite(percentile)) {
    return '样本不足'
  }
  return {
    low: '历史偏低',
    mid: '历史中位',
    high: '历史偏高',
  }[percentileZone(percentile)]
}

/** 列表内微型趋势图路径，仅使用真实序列；无有效数据返回空字符串 */
export function sparklinePath(
  points: readonly (readonly [string, number])[] | null | undefined,
  width: number,
  height: number,
  padding = 1,
): string {
  const clean = cleanSeries(points)
  if (clean.length < 2 || width <= 0 || height <= 0) {
    return ''
  }
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY
  for (const [, value] of clean) {
    min = Math.min(min, value)
    max = Math.max(max, value)
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return ''
  }
  const span = max - min || Math.abs(max) * 0.001 || 1
  const innerWidth = Math.max(width - padding * 2, 0)
  const innerHeight = Math.max(height - padding * 2, 0)
  return clean
    .map(([, value], index) => {
      const x = padding + (index / (clean.length - 1)) * innerWidth
      const y = padding + ((max - value) / span) * innerHeight
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

/** 图表横轴日期：跨度较长时显示年月，较短时显示月-日 */
export function formatAxisDate(date: string, spanDays: number): string {
  if (!date) {
    return ''
  }
  if (spanDays > 300) {
    return date.slice(2, 7)
  }
  return date.slice(5)
}
