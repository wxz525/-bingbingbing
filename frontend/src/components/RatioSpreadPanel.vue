<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { getMarketIndicator, getMarketIndicators } from '@/api/market'
import MarketIndicatorChart from '@/components/MarketIndicatorChart.vue'
import type { MarketIndicator, MarketIndicatorSummary } from '@/types/market'
import { isAbortError } from '@/utils/format'
import {
  cleanSeries,
  computeStatistics,
  formatIndicatorValue,
  formatSpreadValue,
  getIndicatorDefinition,
  groupIndicatorDefinitions,
  INDICATOR_MAP,
  INDICATOR_DEFINITIONS,
  MIN_SAMPLE_SIZE,
  normalizeSeries,
  percentileLabel,
  percentileZone,
  rebaseSeries,
  signedDigits,
  sparklinePath,
  type IndicatorGroupKey,
  type IndicatorKind,
  type IndicatorStatistics,
  type Point,
  type SpreadUnit,
  type IndicatorDisplayOptions,
} from '@/utils/indicatorAnalysis'

const props = defineProps<{
  activeKey: string
  days: number | null
  rangeLabel: string
}>()

const emit = defineEmits<{
  (event: 'update:activeKey', key: string): void
}>()

type FilterKey = 'all' | IndicatorGroupKey

const FILTER_OPTIONS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'commodity', label: '商品' },
  { key: 'equity_style', label: '股票' },
  { key: 'cross_market', label: '跨市场' },
  { key: 'rates', label: '利率' },
]

/** 历史统计默认使用近 3 年，与走势图所选区间区分 */
const STATS_DAYS = 1096
const ORDER = new Map(INDICATOR_DEFINITIONS.map((item, index) => [item.key, index]))

const items = ref<MarketIndicatorSummary[]>([])
const series = ref<MarketIndicator | null>(null)
const statsSeries = ref<MarketIndicator | null>(null)
const sparklines = ref<Record<string, Point[]>>({})
const itemsLoading = ref(false)
const seriesLoading = ref(false)
const statsLoading = ref(false)
const itemsError = ref('')
const seriesError = ref('')
const statsError = ref('')
const filter = ref<FilterKey>('all')
const mode = ref<'raw' | 'normalized'>('raw')
const spreadUnit = ref<SpreadUnit>('bp')
const insightOpen = ref(true)

let itemsController: AbortController | null = null
let seriesController: AbortController | null = null
let statsController: AbortController | null = null
let sparklineController: AbortController | null = null

const meta = computed(() => getIndicatorDefinition(props.activeKey))
const isSpread = computed(() => meta.value?.kind === 'spread')
const supportsNormalized = computed(() => meta.value?.standardized ?? false)
const isNormalized = computed(() => supportsNormalized.value && mode.value === 'normalized')
const statsDays = computed<number | null>(() => (props.days === null ? null : STATS_DAYS))
const statsWindowLabel = computed(() => (props.days === null ? '全部历史' : '近 3 年'))

const displayOptions = computed<IndicatorDisplayOptions>(() => ({
  kind: (meta.value?.kind ?? 'ratio') as IndicatorKind,
  spreadUnit: spreadUnit.value,
  normalized: isNormalized.value,
}))

const displayUnit = computed(() => {
  if (isSpread.value) {
    return spreadUnit.value
  }
  return isNormalized.value ? '指数（基期=100）' : '倍'
})

const rawPoints = computed<Point[]>(() => cleanSeries(series.value?.points))
const displayPoints = computed<Point[]>(() =>
  isNormalized.value ? normalizeSeries(rawPoints.value) : rawPoints.value,
)
const baseValue = computed(() => (rawPoints.value.length ? rawPoints.value[0][1] : null))

const statsPoints = computed<Point[]>(() => {
  const clean = cleanSeries(statsSeries.value?.points)
  if (!clean.length) {
    return []
  }
  if (!isNormalized.value) {
    return clean
  }
  if (baseValue.value === null) {
    return []
  }
  return rebaseSeries(clean, baseValue.value)
})

const statistics = computed<IndicatorStatistics | null>(() => {
  const points = statsPoints.value
  if (!points.length) {
    return null
  }
  const current = displayPoints.value.length
    ? displayPoints.value[displayPoints.value.length - 1][1]
    : undefined
  return computeStatistics(
    points.map(([, value]) => value),
    current,
  )
})

const rangeStats = computed(() => {
  const points = displayPoints.value
  if (!points.length) {
    return null
  }
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY
  for (const [, value] of points) {
    min = Math.min(min, value)
    max = Math.max(max, value)
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return null
  }
  const first = points[0]
  const last = points[points.length - 1]
  return {
    firstDate: first[0],
    lastDate: last[0],
    firstValue: first[1],
    latest: last[1],
    min,
    max,
    count: points.length,
    change: last[1] - first[1],
  }
})

const filteredGroups = computed(() => {
  const wanted = items.value.filter(
    (item) => filter.value === 'all' || INDICATOR_MAP[item.key]?.group === filter.value,
  )
  const keys = wanted.map((item) => item.key)
  return groupIndicatorDefinitions(keys).map((entry) => ({
    ...entry,
    items: [...entry.items]
      .sort((a, b) => (ORDER.get(a.key) ?? 99) - (ORDER.get(b.key) ?? 99))
      .map((definition) => ({
        definition,
        summary: wanted.find((item) => item.key === definition.key) ?? null,
      })),
  }))
})

const statisticsNote = computed(() => {
  if (statsLoading.value) {
    return '历史统计计算中'
  }
  if (statsError.value) {
    return '历史统计暂不可用'
  }
  if (!statsSeries.value) {
    return '暂无历史样本'
  }
  if (!statistics.value) {
    return `样本不足（${statsPoints.value.length} 个交易日，至少需要 ${MIN_SAMPLE_SIZE} 个）`
  }
  return ''
})

const statisticsRange = computed(() => {
  const start = statsSeries.value?.start_date ?? ''
  const end = statsSeries.value?.end_date ?? ''
  if (!start || !end) {
    return ''
  }
  return `${start} ~ ${end}`
})

const percentileValue = computed<number | null>(() => {
  const stats = statistics.value
  if (!stats || stats.percentile === null) {
    return null
  }
  return Math.min(Math.max(stats.percentile, 0), 100)
})

const percentileText = computed(() => {
  const value = percentileValue.value
  if (value === null) {
    return '--'
  }
  return `${value.toFixed(1)}%`
})

const percentileTone = computed(() => {
  const value = percentileValue.value
  if (value === null) {
    return 'unknown'
  }
  return percentileZone(value)
})

const changeText = computed(() => {
  const stats = rangeStats.value
  if (!stats || !Number.isFinite(stats.change)) {
    return '--'
  }
  if (isSpread.value) {
    return formatSpreadValue(stats.change, spreadUnit.value, { signed: true })
  }
  if (isNormalized.value) {
    return `${signedDigits(stats.latest - 100, 2)}%`
  }
  if (!Number.isFinite(stats.firstValue) || stats.firstValue === 0) {
    return signedDigits(stats.change, 2)
  }
  return `${signedDigits((stats.change / stats.firstValue) * 100, 2)}%`
})

const changeHint = computed(() => {
  const stats = rangeStats.value
  if (!stats) {
    return '--'
  }
  if (isSpread.value) {
    const secondary = spreadUnit.value === 'bp' ? 'pp' : 'bp'
    return `${stats.firstDate} 起 · 另计 ${formatSpreadValue(stats.change, secondary, { signed: true })}`
  }
  if (isNormalized.value) {
    return `${stats.firstDate} 起 · 相对基期`
  }
  return `${stats.firstDate} 起 · 绝对变化 ${signedDigits(stats.change, 2)}`
})

const changeDirection = computed(() => {
  const stats = rangeStats.value
  if (!stats || !Number.isFinite(stats.change) || stats.change === 0) {
    return 'flat'
  }
  return stats.change > 0 ? 'up' : 'down'
})

function formatValue(value: number | null | undefined): string {
  return formatIndicatorValue(value, { ...displayOptions.value, withUnit: !isNormalized.value })
}

function formatPlain(value: number | null | undefined): string {
  return formatIndicatorValue(value, displayOptions.value)
}

function formatTooltipValue(value: number): string {
  return formatValue(value)
}

function listValue(item: MarketIndicatorSummary | null): string {
  if (!item) {
    return '--'
  }
  return item.kind === 'spread'
    ? formatSpreadValue(item.latest, 'bp')
    : formatIndicatorValue(item.latest, { kind: 'ratio' })
}

function listChange(item: MarketIndicatorSummary | null): string {
  if (!item) {
    return '--'
  }
  if (item.kind === 'spread') {
    return formatSpreadValue(item.change, 'bp', { signed: true })
  }
  if (item.change_pct !== null && Number.isFinite(item.change_pct)) {
    const sign = item.change_pct > 0 ? '+' : ''
    return `${sign}${item.change_pct.toFixed(2)}%`
  }
  const sign = item.change > 0 ? '+' : ''
  return `${sign}${item.change.toFixed(2)}`
}

function listDirection(item: MarketIndicatorSummary | null): 'up' | 'down' | 'flat' {
  if (!item || !Number.isFinite(item.change) || item.change === 0) {
    return 'flat'
  }
  return item.change > 0 ? 'up' : 'down'
}

function sparkPath(key: string): string {
  return sparklinePath(sparklines.value[key], 62, 18, 1)
}

async function loadItems(): Promise<void> {
  itemsController?.abort()
  const controller = new AbortController()
  itemsController = controller
  itemsLoading.value = true
  itemsError.value = ''
  try {
    const response = await getMarketIndicators(props.days, controller.signal)
    if (itemsController !== controller) {
      return
    }
    items.value = response.items
    if (!response.items.length) {
      series.value = null
      statsSeries.value = null
    }
    ensureActiveKey()
    void loadSparklines()
  } catch (error) {
    if (isAbortError(error) || itemsController !== controller) {
      return
    }
    items.value = []
    itemsError.value = error instanceof Error ? error.message : '指标列表加载失败'
  } finally {
    if (itemsController === controller) {
      itemsLoading.value = false
    }
  }
}

function ensureActiveKey(): void {
  const known = items.value.filter((item) => INDICATOR_MAP[item.key])
  if (!known.length) {
    return
  }
  if (known.some((item) => item.key === props.activeKey)) {
    return
  }
  emit('update:activeKey', known[0].key)
}

async function loadSeries(): Promise<void> {
  if (!props.activeKey) {
    return
  }
  seriesController?.abort()
  const controller = new AbortController()
  seriesController = controller
  seriesLoading.value = true
  seriesError.value = ''
  series.value = null
  try {
    const response = await getMarketIndicator(props.activeKey, props.days, controller.signal)
    if (seriesController !== controller) {
      return
    }
    series.value = response
  } catch (error) {
    if (isAbortError(error) || seriesController !== controller) {
      return
    }
    seriesError.value = error instanceof Error ? error.message : '指标走势加载失败'
  } finally {
    if (seriesController === controller) {
      seriesLoading.value = false
    }
  }
}

async function loadStats(): Promise<void> {
  if (!props.activeKey) {
    return
  }
  statsController?.abort()
  const controller = new AbortController()
  statsController = controller
  statsLoading.value = true
  statsError.value = ''
  statsSeries.value = null
  try {
    const response = await getMarketIndicator(props.activeKey, statsDays.value, controller.signal)
    if (statsController !== controller) {
      return
    }
    statsSeries.value = response
  } catch (error) {
    if (isAbortError(error) || statsController !== controller) {
      return
    }
    statsError.value = error instanceof Error ? error.message : '历史统计加载失败'
  } finally {
    if (statsController === controller) {
      statsLoading.value = false
    }
  }
}

async function loadSparklines(): Promise<void> {
  const keys = items.value.map((item) => item.key)
  sparklineController?.abort()
  if (!keys.length) {
    sparklines.value = {}
    return
  }
  const controller = new AbortController()
  sparklineController = controller
  const next: Record<string, Point[]> = {}
  await Promise.all(
    keys.map(async (key) => {
      try {
        const response = await getMarketIndicator(key, props.days, controller.signal)
        if (controller.signal.aborted) {
          return
        }
        // 微型趋势图只使用真实历史点，最多保留最近 60 个
        next[key] = cleanSeries(response.points).slice(-60)
      } catch {
        // 单个指标请求失败时不显示微型图，不生成替代曲线
      }
    }),
  )
  if (sparklineController !== controller) {
    return
  }
  sparklines.value = next
}

function selectIndicator(key: string): void {
  if (key === props.activeKey) {
    return
  }
  emit('update:activeKey', key)
}

function retryList(): void {
  void loadItems()
  void loadSeries()
  void loadStats()
}

function retrySeries(): void {
  void loadSeries()
  void loadStats()
}

watch(
  () => props.activeKey,
  () => {
    mode.value = 'raw'
    void loadSeries()
    void loadStats()
  },
)

watch(
  () => props.days,
  () => {
    void loadItems()
    void loadSeries()
    void loadStats()
  },
)

onMounted(() => {
  void loadItems()
  void loadSeries()
  void loadStats()
})

onBeforeUnmount(() => {
  itemsController?.abort()
  seriesController?.abort()
  statsController?.abort()
  sparklineController?.abort()
})
</script>

<template>
  <div class="ratio-panel">
    <aside class="ratio-panel__nav">
      <div class="ratio-panel__filters">
        <button
          v-for="option in FILTER_OPTIONS"
          :key="option.key"
          type="button"
          class="filter-chip"
          :class="{ 'filter-chip--active': filter === option.key }"
          @click="filter = option.key"
        >
          {{ option.label }}
        </button>
      </div>

      <div v-if="itemsError" class="inline-state">
        <p class="inline-state__text">{{ itemsError }}</p>
        <button type="button" class="ghost-button" @click="retryList">重新加载</button>
      </div>

      <div v-else-if="itemsLoading && !items.length" class="nav-skeleton">
        <div v-for="index in 6" :key="index" class="nav-skeleton__row" />
      </div>

      <div v-else-if="!filteredGroups.length" class="inline-state">
        <p class="inline-state__text">暂无匹配的比值或利差指标</p>
      </div>

      <nav v-else class="indicator-nav">
        <div v-for="entry in filteredGroups" :key="entry.group.key" class="indicator-nav__group">
          <div class="indicator-nav__head">
            <span class="indicator-nav__title">{{ entry.group.label }}</span>
            <span class="indicator-nav__caption">{{ entry.group.caption }}</span>
          </div>
          <button
            v-for="row in entry.items"
            :key="row.definition.key"
            type="button"
            class="indicator-row"
            :class="{ 'indicator-row--active': row.definition.key === activeKey }"
            @click="selectIndicator(row.definition.key)"
          >
            <span class="indicator-row__body">
              <span class="indicator-row__name">{{ row.definition.name }}</span>
              <span class="indicator-row__figures">
                <span class="indicator-row__value">{{ listValue(row.summary) }}</span>
                <span class="indicator-row__change" :class="`is-${listDirection(row.summary)}`">
                  {{
                    listDirection(row.summary) === 'up'
                      ? '↑'
                      : listDirection(row.summary) === 'down'
                        ? '↓'
                        : '·'
                  }}
                  {{ listChange(row.summary) }}
                </span>
              </span>
            </span>
            <svg
              v-if="sparkPath(row.definition.key)"
              class="indicator-row__spark"
              width="62"
              height="18"
              viewBox="0 0 62 18"
              aria-hidden="true"
            >
              <path :d="sparkPath(row.definition.key)" />
            </svg>
          </button>
        </div>
      </nav>

      <p class="ratio-panel__nav-note">
        指标由现有行情序列按交易日对齐折算，区间跟随上方「{{ rangeLabel }}」。
      </p>
    </aside>

    <section class="ratio-panel__main">
      <template v-if="!meta">
        <div class="inline-state inline-state--large">
          <p class="inline-state__text">请选择左侧指标开始研究</p>
        </div>
      </template>

      <template v-else>
        <header class="study-head">
          <div class="study-head__titles">
            <div class="study-head__name-row">
              <h3 class="study-head__name">{{ meta.name }}</h3>
              <span class="study-head__english">{{ meta.english }}</span>
              <span v-if="meta.caliberPending" class="badge badge--warn">数据口径待核验</span>
            </div>
            <p class="study-head__formula">
              计算方式：{{ meta.formula }}
              <span class="study-head__assets">
                分子 {{ meta.numerator }} · 分母 {{ meta.denominator }}
              </span>
            </p>
            <p class="study-head__summary">{{ meta.summary }}</p>
          </div>

          <div class="study-head__controls">
            <div v-if="supportsNormalized" class="toggle-group" role="group" aria-label="比值显示模式">
              <button
                type="button"
                class="toggle-group__item"
                :class="{ 'toggle-group__item--active': !isNormalized }"
                @click="mode = 'raw'"
              >
                原始比值
              </button>
              <button
                type="button"
                class="toggle-group__item"
                :class="{ 'toggle-group__item--active': isNormalized }"
                @click="mode = 'normalized'"
              >
                相对强弱 · 基期=100
              </button>
            </div>
            <div v-if="isSpread" class="toggle-group" role="group" aria-label="利差单位">
              <button
                type="button"
                class="toggle-group__item"
                :class="{ 'toggle-group__item--active': spreadUnit === 'bp' }"
                @click="spreadUnit = 'bp'"
              >
                bp
              </button>
              <button
                type="button"
                class="toggle-group__item"
                :class="{ 'toggle-group__item--active': spreadUnit === 'pp' }"
                @click="spreadUnit = 'pp'"
              >
                pp
              </button>
            </div>
          </div>
        </header>

        <p v-if="isNormalized" class="study-note">
          相对强弱 = 当前原始比值 ÷ 区间首个有效比值 × 100。大于 100 表示分子资产相对基期表现更强，小于 100
          表示分母资产相对基期更强；基期为 {{ rangeStats?.firstDate ?? '区间首个有效交易日' }}。
        </p>
        <p v-else-if="isSpread" class="study-note">
          利差以基点（bp）为主，1pp = 100bp。本页数值升降只描述利差方向；「扩大 / 收窄」需结合绝对差距判断，负利差区间尤其如此。
        </p>

        <div v-if="seriesError" class="inline-state inline-state--large">
          <p class="inline-state__text">{{ seriesError }}</p>
          <button type="button" class="ghost-button" @click="retrySeries">重新加载</button>
        </div>

        <template v-else>
          <div class="metrics">
            <div class="metric">
              <span class="metric__label">
                {{ isNormalized ? '最新相对强弱' : '最新值' }}
              </span>
              <span class="metric__value">
                {{ rangeStats ? formatValue(rangeStats.latest) : '--' }}
              </span>
              <span class="metric__hint">
                {{ rangeStats?.lastDate ?? '暂无数据' }} · {{ displayUnit }}
              </span>
            </div>
            <div class="metric">
              <span class="metric__label">区间变化</span>
              <span class="metric__value metric__value--change" :class="`is-${changeDirection}`">
                {{ changeText }}
              </span>
              <span class="metric__hint">
                {{ changeHint }}
              </span>
            </div>
            <div class="metric">
              <span class="metric__label">历史分位数</span>
              <span class="metric__value">{{ percentileText }}</span>
              <span class="metric__hint">{{ percentileLabel(percentileValue) }}</span>
            </div>
            <div class="metric metric--wide">
              <span class="metric__label">区间最高 / 最低</span>
              <span class="metric__value metric__value--small">
                {{ rangeStats ? formatValue(rangeStats.max) : '--' }} /
                {{ rangeStats ? formatValue(rangeStats.min) : '--' }}
              </span>
              <span class="metric__hint">样本 {{ rangeStats?.count ?? 0 }} 个交易日</span>
            </div>
          </div>

          <p class="study-meta">
            数据截止 {{ rangeStats?.lastDate ?? '--' }} · 区间样本
            {{ rangeStats?.count ?? 0 }} 个交易日 · 历史统计参考区间 {{ statsWindowLabel }}
            <template v-if="statisticsRange">（{{ statisticsRange }}）</template>
            · 统计样本 {{ statsPoints.length }} 个交易日
          </p>

          <section class="chart-card">
            <div class="chart-card__head">
              <div>
                <h4 class="chart-card__title">
                  {{ isNormalized ? '相对强弱走势（基期=100）' : '历史走势' }}
                </h4>
                <p class="chart-card__sub">
                  单位 {{ displayUnit }} · 横轴 {{ rangeLabel }} · 悬停查看单日数值
                </p>
              </div>
              <div class="chart-legend">
                <span class="chart-legend__item chart-legend__item--line">走势</span>
                <span class="chart-legend__item chart-legend__item--mean">
                  历史均值（{{ statsWindowLabel }}）
                </span>
                <span class="chart-legend__item chart-legend__item--band">25%–75% 分位</span>
                <span
                  v-if="isSpread || isNormalized"
                  class="chart-legend__item chart-legend__item--baseline"
                >
                  {{ isSpread ? '零轴' : '基期 100' }}
                </span>
              </div>
            </div>

            <div class="chart-card__body">
              <MarketIndicatorChart
                :points="displayPoints"
                :unit="isSpread ? spreadUnit : '倍'"
                :kind="meta.kind"
                :mean-value="statistics ? statistics.mean : null"
                :quantile-band="
                  statistics ? { low: statistics.q25, high: statistics.q75 } : null
                "
                :baseline="isSpread ? 0 : isNormalized ? 100 : null"
                :baseline-label="isSpread ? '零轴' : isNormalized ? '基期 100' : ''"
                :value-formatter="formatTooltipValue"
                empty-text="所选区间内没有足够的历史数据"
              />
              <div v-if="seriesLoading" class="chart-loading">走势加载中…</div>
            </div>

            <p class="chart-card__foot">
              历史均值与 25%–75% 分位带基于{{ statsWindowLabel }}历史样本计算，属于统计参考区间，不是预测区间，也不构成置信区间。
            </p>
          </section>

          <section class="position-card">
            <div class="position-card__head">
              <h4 class="position-card__title">历史位置</h4>
              <span class="position-card__stat">
                当前分位
                <b :class="`position-tone--${percentileTone}`">{{ percentileText }}</b>
                · {{ percentileLabel(percentileValue) }}
              </span>
            </div>

            <div v-if="percentileValue === null" class="inline-state">
              <p class="inline-state__text">{{ statisticsNote || '暂无历史分位' }}</p>
            </div>

            <template v-else>
              <div class="position-bar">
                <div class="position-bar__track">
                  <span class="position-bar__segment position-bar__segment--low">历史偏低</span>
                  <span class="position-bar__segment position-bar__segment--mid">历史中位</span>
                  <span class="position-bar__segment position-bar__segment--high">历史偏高</span>
                  <i
                    class="position-bar__marker"
                    :style="{ left: `${percentileValue}%` }"
                    :class="`position-tone--${percentileTone}`"
                  />
                </div>
                <div class="position-bar__scale">
                  <span>0%</span>
                  <span>25%</span>
                  <span>75%</span>
                  <span>100%</span>
                </div>
              </div>
              <div class="position-card__meta">
                <span>参考区间 {{ statsWindowLabel }}：{{ statisticsRange || '--' }}</span>
                <span>样本 {{ statistics?.count ?? 0 }} 个交易日</span>
                <span v-if="statistics">
                  中位 {{ formatPlain(statistics.median) }} · 均值
                  {{ formatPlain(statistics.mean) }}
                </span>
                <span v-if="statistics?.zScore !== null && statistics?.zScore !== undefined">
                  Z-score {{ statistics.zScore.toFixed(2) }}
                </span>
              </div>
              <p class="position-card__foot">
                历史分位数仅表示当前数值在所选历史样本中的相对位置，不代表未来涨跌概率。
              </p>
            </template>
          </section>

          <section class="insight">
            <button
              type="button"
              class="insight__toggle"
              :aria-expanded="insightOpen"
              @click="insightOpen = !insightOpen"
            >
              <span>指标解读</span>
              <span class="insight__toggle-icon">{{ insightOpen ? '收起' : '展开' }}</span>
            </button>

            <div v-if="insightOpen" class="insight__body">
              <div class="insight__item">
                <h5>指标定义</h5>
                <p>{{ meta.definition }}</p>
              </div>
              <div class="insight__item">
                <h5>计算公式</h5>
                <p>{{ meta.formula }}</p>
                <p class="insight__sub">分子：{{ meta.numerator }} · 分母：{{ meta.denominator }}</p>
              </div>
              <div class="insight__item">
                <h5>研究价值</h5>
                <p>{{ meta.researchValue }}</p>
              </div>
              <div class="insight__item">
                <h5>数值上升</h5>
                <p>{{ meta.rising }}</p>
              </div>
              <div class="insight__item">
                <h5>数值下降</h5>
                <p>{{ meta.falling }}</p>
              </div>
              <div class="insight__item">
                <h5>数据来源与计算口径</h5>
                <p>{{ meta.caliber }}</p>
                <p v-if="meta.caliberPending" class="insight__warn">
                  当前后端未提供明确的单位换算说明，本项目不修改原始数值，仅标注待核验。
                </p>
              </div>
              <div class="insight__item insight__item--wide">
                <h5>使用限制</h5>
                <p>{{ meta.caveat }}</p>
              </div>
            </div>
          </section>
        </template>
      </template>
    </section>
  </div>
</template>

<style scoped>
.ratio-panel {
  --syn-page: #f5f7fa;
  --syn-surface: #ffffff;
  --syn-surface-2: #f7f9fc;
  --syn-brand: #409eff;
  --syn-highlight: #409eff;
  --syn-accent: #909399;
  --syn-text: #303133;
  --syn-text-2: #909399;
  --syn-line: #ebeef5;
  display: grid;
  grid-template-columns: minmax(252px, 24%) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  color: var(--syn-text);
}

.ratio-panel__nav {
  position: sticky;
  top: 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 40px);
  padding: 14px;
  border: 1px solid var(--syn-line);
  border-radius: 8px;
  background: var(--syn-surface);
  overflow-y: auto;
}

.ratio-panel__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.filter-chip {
  padding: 4px 10px;
  border: 1px solid var(--syn-line);
  border-radius: 999px;
  background: transparent;
  color: var(--syn-text-2);
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease, background-color 0.15s ease;
}

.filter-chip:hover {
  color: var(--syn-text);
  border-color: var(--syn-highlight);
}

.filter-chip--active {
  background: #ecf5ff;
  border-color: var(--syn-brand);
  color: var(--syn-highlight);
}

.indicator-nav {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.indicator-nav__group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.indicator-nav__head {
  padding-left: 8px;
  margin-bottom: 2px;
}

.indicator-nav__title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--syn-text-2);
}

.indicator-nav__caption {
  display: block;
  margin-top: 2px;
  font-size: 10px;
  color: #c0c4cc;
}

.indicator-row {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 7px 8px 7px 10px;
  border: 1px solid transparent;
  border-radius: 5px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.indicator-row::before {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  bottom: 7px;
  width: 2px;
  border-radius: 2px;
  background: transparent;
}

.indicator-row:hover {
  background: #f5f7fa;
}

.indicator-row--active {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.indicator-row--active::before {
  background: var(--syn-highlight);
}

.indicator-row__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.indicator-row__name {
  overflow: hidden;
  font-size: 12px;
  color: var(--syn-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.indicator-row--active .indicator-row__name {
  color: var(--syn-highlight);
  font-weight: 600;
}

.indicator-row__figures {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-variant-numeric: tabular-nums;
}

.indicator-row__value {
  font-size: 12px;
  color: var(--syn-text);
}

.indicator-row__change {
  font-size: 11px;
  color: var(--syn-text-2);
}

.is-up,
.is-down,
.is-flat {
  color: var(--syn-text-2);
}

.indicator-row__spark {
  flex: 0 0 62px;
  height: 18px;
  opacity: 0.75;
}

.indicator-row__spark path {
  fill: none;
  stroke: var(--syn-accent);
  stroke-width: 1.2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.indicator-row--active .indicator-row__spark path {
  stroke: var(--syn-highlight);
}

.ratio-panel__nav-note {
  margin: 0;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
  font-size: 10px;
  line-height: 1.6;
  color: #909399;
}

.nav-skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-skeleton__row {
  height: 34px;
  border-radius: 5px;
  background: linear-gradient(90deg, #f0f2f5, #e4e7ed, #f0f2f5);
  background-size: 200% 100%;
  animation: synapse-shimmer 1.4s ease-in-out infinite;
}

@keyframes synapse-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.ratio-panel__main {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.study-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--syn-line);
  border-radius: 8px;
  background: var(--syn-surface);
}

.study-head__name-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}

.study-head__name {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--syn-text);
}

.study-head__english {
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--syn-text-2);
}

.badge {
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 10px;
  line-height: 1.5;
}

.badge--warn {
  border: 1px solid #f5dab1;
  background: #fdf6ec;
  color: #e6a23c;
}

.study-head__formula {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--syn-text-2);
}

.study-head__assets {
  margin-left: 8px;
  color: #909399;
}

.study-head__summary {
  margin: 6px 0 0;
  max-width: 62ch;
  font-size: 13px;
  line-height: 1.65;
  color: var(--syn-text);
}

.study-head__controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.toggle-group {
  display: inline-flex;
  padding: 2px;
  border: 1px solid var(--syn-line);
  border-radius: 5px;
  background: var(--syn-page);
}

.toggle-group__item {
  padding: 5px 10px;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: var(--syn-text-2);
  font-size: 12px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.toggle-group__item:hover {
  color: var(--syn-text);
}

.toggle-group__item--active {
  background: #ecf5ff;
  color: var(--syn-highlight);
}

.study-note {
  margin: 0;
  padding: 9px 12px;
  border-left: 2px solid var(--syn-accent);
  background: #f5f7fa;
  font-size: 12px;
  line-height: 1.65;
  color: var(--syn-text-2);
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid var(--syn-line);
  border-radius: 6px;
  background: var(--syn-surface-2);
}

.metric--wide {
  min-width: 0;
}

.metric__label {
  font-size: 11px;
  letter-spacing: 0.03em;
  color: var(--syn-text-2);
}

.metric__value {
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--syn-text);
  font-variant-numeric: tabular-nums;
}

.metric__value--small {
  font-size: 15px;
  line-height: 1.5;
}

.metric__value em {
  margin-left: 4px;
  font-style: normal;
  font-size: 11px;
  font-weight: 400;
  color: var(--syn-text-2);
}

.metric__value--change {
  color: var(--syn-text);
}

.metric__hint {
  font-size: 11px;
  color: #909399;
}

.study-meta {
  margin: 0;
  font-size: 11px;
  line-height: 1.6;
  color: #909399;
}

.chart-card {
  padding: 16px 18px 14px;
  border: 1px solid var(--syn-line);
  border-radius: 8px;
  background: var(--syn-surface);
}

.chart-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.chart-card__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--syn-text);
}

.chart-card__sub {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--syn-text-2);
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 11px;
  color: var(--syn-text-2);
}

.chart-legend__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chart-legend__item::before {
  content: '';
  width: 14px;
  height: 0;
  border-top: 2px solid var(--syn-highlight);
}

.chart-legend__item--mean::before {
  border-top: 1px dashed var(--syn-text-2);
}

.chart-legend__item--band::before {
  height: 8px;
  border: none;
  background: rgba(144, 147, 153, 0.2);
}

.chart-legend__item--baseline::before {
  border-top: 1px dashed var(--syn-accent);
}

.chart-card__body {
  position: relative;
}

.chart-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.75);
  font-size: 12px;
  color: var(--syn-text-2);
}

.chart-card__foot {
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.6;
  color: #909399;
}

.position-card {
  padding: 16px 18px;
  border: 1px solid var(--syn-line);
  border-radius: 8px;
  background: var(--syn-surface);
}

.position-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.position-card__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--syn-text);
}

.position-card__stat {
  font-size: 12px;
  color: var(--syn-text-2);
}

.position-card__stat b {
  font-variant-numeric: tabular-nums;
}

.position-tone--low {
  color: #409eff;
}

.position-tone--mid {
  color: #303133;
}

.position-tone--high {
  color: #e6a23c;
}

.position-tone--unknown {
  color: var(--syn-text-2);
}

.position-bar {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.position-bar__track {
  position: relative;
  display: flex;
  height: 26px;
  border-radius: 4px;
  overflow: visible;
}

.position-bar__segment {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  letter-spacing: 0.04em;
  color: var(--syn-text-2);
}

.position-bar__segment--low {
  flex: 0 0 25%;
  border-radius: 4px 0 0 4px;
  background: #ecf5ff;
}

.position-bar__segment--mid {
  flex: 0 0 50%;
  background: #f5f7fa;
}

.position-bar__segment--high {
  flex: 0 0 25%;
  border-radius: 0 4px 4px 0;
  background: #fdf6ec;
}

.position-bar__marker {
  position: absolute;
  top: -4px;
  bottom: -4px;
  width: 2px;
  border-radius: 2px;
  background: currentColor;
  transform: translateX(-1px);
}

.position-bar__marker::after {
  content: '';
  position: absolute;
  left: 50%;
  top: -4px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  transform: translateX(-50%);
}

.position-bar__scale {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #c0c4cc;
}

.position-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 10px;
  font-size: 11px;
  color: var(--syn-text-2);
}

.position-card__foot {
  margin: 8px 0 0;
  font-size: 11px;
  color: #909399;
}

.insight {
  border: 1px solid var(--syn-line);
  border-radius: 8px;
  background: var(--syn-surface);
  overflow: hidden;
}

.insight__toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 12px 18px;
  border: none;
  background: transparent;
  color: var(--syn-text);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.insight__toggle-icon {
  font-size: 11px;
  font-weight: 400;
  color: var(--syn-text-2);
}

.insight__body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 24px;
  padding: 4px 18px 18px;
  border-top: 1px solid #ebeef5;
}

.insight__item h5 {
  margin: 12px 0 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--syn-highlight);
}

.insight__item p {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--syn-text-2);
}

.insight__sub {
  margin-top: 4px !important;
  font-size: 11px !important;
  color: #909399 !important;
}

.insight__warn {
  margin-top: 6px !important;
  color: #e6a23c !important;
}

.insight__item--wide {
  grid-column: 1 / -1;
}

.inline-state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 14px;
  border: 1px dashed #ebeef5;
  border-radius: 6px;
  background: #fafbfc;
}

.inline-state--large {
  align-items: center;
  justify-content: center;
  min-height: 240px;
  text-align: center;
}

.inline-state__text {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--syn-text-2);
}

.ghost-button {
  padding: 5px 12px;
  border: 1px solid var(--syn-brand);
  border-radius: 4px;
  background: #ecf5ff;
  color: var(--syn-highlight);
  font-size: 12px;
  cursor: pointer;
}

.ghost-button:hover {
  background: #d9ecff;
}

@media (max-width: 1280px) {
  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .ratio-panel {
    grid-template-columns: minmax(0, 1fr);
  }

  .ratio-panel__nav {
    position: static;
    max-height: none;
  }

  .insight__body {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .metrics {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
