<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { getMarketSeries, listMarketAssets } from '@/api/market'
import MarketLineChart from '@/components/MarketLineChart.vue'
import type { MarketAsset, MarketSeries } from '@/types/market'
import { isAbortError } from '@/utils/format'

type RangeKey = '1m' | '3m' | '1y' | '3y' | 'all'

const RANGE_OPTIONS: { label: string; value: RangeKey; days: number | null }[] = [
  { label: '近1月', value: '1m', days: 31 },
  { label: '近3月', value: '3m', days: 92 },
  { label: '近1年', value: '1y', days: 366 },
  { label: '近3年', value: '3y', days: 1096 },
  { label: '全部', value: 'all', days: null },
]

const assets = ref<MarketAsset[]>([])
const keyword = ref('')
const selectedName = ref('')
const series = ref<MarketSeries | null>(null)
const range = ref<RangeKey>('1y')
const loading = ref(false)
const assetLoading = ref(false)
const errorMessage = ref('')

let seriesController: AbortController | null = null

const filteredGroups = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  const groups: { category: string; items: MarketAsset[] }[] = []
  const index = new Map<string, number>()

  for (const asset of assets.value) {
    if (text) {
      const hit =
        asset.name.toLowerCase().includes(text) ||
        (asset.wind_code ?? '').toLowerCase().includes(text)
      if (!hit) {
        continue
      }
    }
    if (!index.has(asset.category)) {
      index.set(asset.category, groups.length)
      groups.push({ category: asset.category, items: [] })
    }
    groups[index.get(asset.category)!].items.push(asset)
  }
  return groups
})

const selectedAsset = computed(
  () => assets.value.find((asset) => asset.name === selectedName.value) ?? null,
)

const visiblePoints = computed<[string, number][]>(() => {
  const all = series.value?.points ?? []
  const option = RANGE_OPTIONS.find((item) => item.value === range.value)
  if (!all.length || !option?.days) {
    return all
  }
  const lastDate = Date.parse(all[all.length - 1][0])
  const cutoff = lastDate - option.days * 24 * 60 * 60 * 1000
  const startIndex = all.findIndex((point) => Date.parse(point[0]) >= cutoff)
  return startIndex <= 0 ? all : all.slice(startIndex)
})

const latestPoint = computed(() =>
  visiblePoints.value.length ? visiblePoints.value[visiblePoints.value.length - 1] : null,
)

const stats = computed(() => {
  const points = visiblePoints.value
  if (points.length < 2) {
    return null
  }
  const first = points[0][1]
  const last = points[points.length - 1][1]
  const values = points.map((point) => point[1])
  const isYield = series.value?.field === 'yield'
  const delta = last - first
  return {
    firstDate: points[0][0],
    lastDate: points[points.length - 1][0],
    latest: last,
    max: Math.max(...values),
    min: Math.min(...values),
    changeText: isYield
      ? `${delta >= 0 ? '+' : ''}${(delta * 100).toFixed(1)}bp`
      : `${delta >= 0 ? '+' : ''}${((delta / (first || 1)) * 100).toFixed(2)}%`,
    rising: delta >= 0,
    count: points.length,
    isYield,
  }
})

const TRADING_DAYS = 252
const RISK_FREE_RATE = 0.02

function dailyReturns(values: number[]): number[] {
  const returns: number[] = []
  for (let index = 1; index < values.length; index += 1) {
    const previous = values[index - 1]
    if (previous !== 0) {
      returns.push(values[index] / previous - 1)
    }
  }
  return returns
}

function annualizedReturn(values: number[]): number | null {
  if (values.length < 20 || values[0] <= 0) {
    return null
  }
  const growth = values[values.length - 1] / values[0]
  return growth ** (TRADING_DAYS / (values.length - 1)) - 1
}

function annualizedVolatility(values: number[]): number | null {
  const returns = dailyReturns(values)
  if (returns.length < 20) {
    return null
  }
  const mean = returns.reduce((sum, item) => sum + item, 0) / returns.length
  const variance =
    returns.reduce((sum, item) => sum + (item - mean) ** 2, 0) / (returns.length - 1)
  return Math.sqrt(variance) * Math.sqrt(TRADING_DAYS)
}

function annualizedVolatilityBp(values: number[]): number | null {
  if (values.length < 21) {
    return null
  }
  const changes: number[] = []
  for (let index = 1; index < values.length; index += 1) {
    changes.push((values[index] - values[index - 1]) * 100)
  }
  const mean = changes.reduce((sum, item) => sum + item, 0) / changes.length
  const variance =
    changes.reduce((sum, item) => sum + (item - mean) ** 2, 0) / (changes.length - 1)
  return Math.sqrt(variance) * Math.sqrt(TRADING_DAYS)
}

function maxDrawdown(
  points: [string, number][],
): { value: number; peakDate: string; troughDate: string } | null {
  if (points.length < 2) {
    return null
  }
  let peak = points[0][1]
  let peakIndex = 0
  let worst = 0
  let worstPeakIndex = 0
  let worstTroughIndex = 0
  for (let index = 1; index < points.length; index += 1) {
    const value = points[index][1]
    if (value > peak) {
      peak = value
      peakIndex = index
    }
    const drawdown = peak === 0 ? 0 : value / peak - 1
    if (drawdown < worst) {
      worst = drawdown
      worstPeakIndex = peakIndex
      worstTroughIndex = index
    }
  }
  return {
    value: worst,
    peakDate: points[worstPeakIndex][0],
    troughDate: points[worstTroughIndex][0],
  }
}

function movingAverageSeries(values: number[], period: number): number[] {
  const factor = 2 / (period + 1)
  const result = [values[0]]
  for (let index = 1; index < values.length; index += 1) {
    result.push(values[index] * factor + result[index - 1] * (1 - factor))
  }
  return result
}

function computeRsi(values: number[], period = 14): number | null {
  if (values.length <= period) {
    return null
  }
  let gain = 0
  let loss = 0
  for (let index = 1; index <= period; index += 1) {
    const delta = values[index] - values[index - 1]
    if (delta >= 0) {
      gain += delta
    } else {
      loss -= delta
    }
  }
  let averageGain = gain / period
  let averageLoss = loss / period
  for (let index = period + 1; index < values.length; index += 1) {
    const delta = values[index] - values[index - 1]
    averageGain = (averageGain * (period - 1) + Math.max(delta, 0)) / period
    averageLoss = (averageLoss * (period - 1) + Math.max(-delta, 0)) / period
  }
  if (averageLoss === 0) {
    return 100
  }
  return 100 - 100 / (1 + averageGain / averageLoss)
}

function computeMacd(
  values: number[],
): { dif: number; dea: number; histogram: number } | null {
  if (values.length < 35) {
    return null
  }
  const fast = movingAverageSeries(values, 12)
  const slow = movingAverageSeries(values, 26)
  const dif = values.map((_, index) => fast[index] - slow[index])
  const dea = movingAverageSeries(dif, 9)
  const lastIndex = values.length - 1
  return {
    dif: dif[lastIndex],
    dea: dea[lastIndex],
    histogram: (dif[lastIndex] - dea[lastIndex]) * 2,
  }
}

interface MetricCard {
  label: string
  value: string
  hint: string
  tone?: 'up' | 'down'
}

const extraCards = computed<MetricCard[]>(() => {
  const points = visiblePoints.value
  if (points.length < 2) {
    return []
  }
  const values = points.map((point) => point[1])
  const isYield = series.value?.field === 'yield'
  const cards: MetricCard[] = []
  const rsi = computeRsi(values)
  const macd = computeMacd(values)

  if (isYield) {
    const volatilityBp = annualizedVolatilityBp(values)
    cards.push({
      label: '年化波动',
      value: volatilityBp === null ? '—' : `${volatilityBp.toFixed(1)}bp`,
      hint: '日变动标准差 × √252',
    })
  } else {
    const annualReturn = annualizedReturn(values)
    const volatility = annualizedVolatility(values)
    const drawdown = maxDrawdown(points)
    const sharpe =
      annualReturn !== null && volatility !== null && volatility > 0
        ? (annualReturn - RISK_FREE_RATE) / volatility
        : null
    cards.push({
      label: '年化收益率',
      value:
        annualReturn === null
          ? '—'
          : `${annualReturn >= 0 ? '+' : ''}${(annualReturn * 100).toFixed(2)}%`,
      hint: '按 252 个交易日年化',
      tone: annualReturn === null ? undefined : annualReturn >= 0 ? 'up' : 'down',
    })
    cards.push({
      label: '年化波动率',
      value: volatility === null ? '—' : `${(volatility * 100).toFixed(2)}%`,
      hint: '日收益标准差 × √252',
    })
    cards.push({
      label: '最大回撤',
      value: drawdown === null ? '—' : `${(drawdown.value * 100).toFixed(2)}%`,
      hint: drawdown === null ? '区间过短' : `${drawdown.peakDate} → ${drawdown.troughDate}`,
    })
    cards.push({
      label: '夏普比率',
      value: sharpe === null ? '—' : sharpe.toFixed(2),
      hint: `无风险利率按 ${(RISK_FREE_RATE * 100).toFixed(1)}%`,
    })
  }

  cards.push({
    label: 'RSI(14)',
    value: rsi === null ? '—' : rsi.toFixed(1),
    hint: rsi === null ? '数据不足 15 个交易日' : rsi >= 70 ? '超买区间' : rsi <= 30 ? '超卖区间' : '中性区间',
  })
  cards.push({
    label: 'MACD(12,26,9)',
    value: macd === null ? '—' : `${macd.histogram >= 0 ? '+' : ''}${macd.histogram.toFixed(3)}`,
    hint: macd === null ? '数据不足 35 个交易日' : `DIF ${macd.dif.toFixed(3)} / DEA ${macd.dea.toFixed(3)}`,
    tone: macd === null ? undefined : macd.histogram >= 0 ? 'up' : 'down',
  })
  return cards
})

function formatValue(value: number, isYield: boolean): string {
  if (isYield) {
    return `${value.toFixed(3)}%`
  }
  return value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

async function loadAssets(): Promise<void> {
  assetLoading.value = true
  errorMessage.value = ''
  try {
    const response = await listMarketAssets()
    assets.value = response.items
    if (!assets.value.length) {
      errorMessage.value = '未在数据目录中找到行情文件'
      return
    }
    const preferred = assets.value.find((asset) => asset.name === '沪深300') ?? assets.value[0]
    await selectAsset(preferred.name)
  } catch (error) {
    if (!isAbortError(error)) {
      errorMessage.value = error instanceof Error ? error.message : '行情数据加载失败'
    }
  } finally {
    assetLoading.value = false
  }
}

async function selectAsset(name: string): Promise<void> {
  if (selectedName.value === name && series.value) {
    return
  }
  selectedName.value = name
  loading.value = true
  errorMessage.value = ''
  seriesController?.abort()
  const controller = new AbortController()
  seriesController = controller
  try {
    const response = await getMarketSeries(name, controller.signal)
    series.value = response
  } catch (error) {
    if (!isAbortError(error)) {
      errorMessage.value = error instanceof Error ? error.message : '行情序列加载失败'
      series.value = null
    }
  } finally {
    if (seriesController === controller) {
      loading.value = false
    }
  }
}

onMounted(loadAssets)
</script>

<template>
  <div class="market-view">
    <aside class="market-view__aside">
      <el-input
        v-model="keyword"
        class="market-view__search"
        placeholder="搜索名称或 Wind 代码"
        clearable
      />

      <div v-loading="assetLoading" class="market-view__assets">
        <div v-for="group in filteredGroups" :key="group.category" class="market-group">
          <div class="market-group__title">
            <span>{{ group.category }}</span>
            <span class="market-group__count">{{ group.items.length }}</span>
          </div>
          <button
            v-for="asset in group.items"
            :key="asset.name"
            type="button"
            class="market-item"
            :class="{ 'market-item--active': asset.name === selectedName }"
            @click="selectAsset(asset.name)"
          >
            <span class="market-item__name">{{ asset.name }}</span>
            <span class="market-item__meta">{{ asset.wind_code ?? asset.field }}</span>
          </button>
        </div>

        <el-empty
          v-if="!assetLoading && !filteredGroups.length"
          description="没有匹配的行情标的"
          :image-size="72"
        />
      </div>
    </aside>

    <section class="market-view__main">
      <div class="market-view__header">
        <div class="market-view__title-block">
          <h2 class="market-view__title">{{ selectedAsset?.name ?? '行情看板' }}</h2>
          <div class="market-view__subtitle">
            <span v-if="selectedAsset">{{ selectedAsset.category }} · {{ selectedAsset.wind_code }}</span>
            <el-tag v-if="selectedAsset" size="small" type="info" effect="plain">
              {{ selectedAsset.field === 'yield' ? '收益率' : '收盘价' }}
            </el-tag>
          </div>
        </div>

        <el-radio-group v-model="range" size="small">
          <el-radio-button v-for="option in RANGE_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <div v-if="stats" class="market-stats">
        <div class="market-stat">
          <span class="market-stat__label">最新值</span>
          <span class="market-stat__value">{{ formatValue(stats.latest, stats.isYield) }}</span>
          <span class="market-stat__hint">{{ latestPoint?.[0] }}</span>
        </div>
        <div class="market-stat">
          <span class="market-stat__label">区间涨跌</span>
          <span class="market-stat__value" :class="stats.rising ? 'is-up' : 'is-down'">
            {{ stats.changeText }}
          </span>
          <span class="market-stat__hint">{{ stats.firstDate }} 起</span>
        </div>
        <div class="market-stat">
          <span class="market-stat__label">区间最高 / 最低</span>
          <span class="market-stat__value market-stat__value--small">
            {{ formatValue(stats.max, stats.isYield) }} / {{ formatValue(stats.min, stats.isYield) }}
          </span>
          <span class="market-stat__hint">样本 {{ stats.count }} 条</span>
        </div>
        <div class="market-stat">
          <span class="market-stat__label">数据区间</span>
          <span class="market-stat__value market-stat__value--small">
            {{ selectedAsset?.start_date }} ~ {{ selectedAsset?.end_date }}
          </span>
          <span class="market-stat__hint">共 {{ selectedAsset?.row_count }} 条</span>
        </div>
        <div v-for="card in extraCards" :key="card.label" class="market-stat">
          <span class="market-stat__label">{{ card.label }}</span>
          <span
            class="market-stat__value"
            :class="card.tone ? (card.tone === 'up' ? 'is-up' : 'is-down') : ''"
          >
            {{ card.value }}
          </span>
          <span class="market-stat__hint">{{ card.hint }}</span>
        </div>
      </div>

      <el-alert
        v-if="errorMessage"
        class="market-view__alert"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
      />

      <div v-loading="loading" class="market-view__chart">
        <MarketLineChart
          v-if="visiblePoints.length"
          :points="visiblePoints"
          :field="series?.field ?? 'close'"
        />
        <el-empty
          v-else-if="!loading && !errorMessage"
          description="选择左侧标的后展示走势"
          :image-size="90"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.market-view {
  display: flex;
  gap: 16px;
  align-items: stretch;
}

.market-view__aside {
  flex: 0 0 240px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.market-view__assets {
  flex: 1;
  max-height: 620px;
  overflow-y: auto;
  padding-right: 4px;
}

.market-group {
  margin-bottom: 14px;
}

.market-group__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #909399;
}

.market-group__count {
  font-weight: 400;
}

.market-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #303133;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.market-item:hover {
  background: #f5f7fa;
}

.market-item--active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
}

.market-item__meta {
  font-size: 11px;
  color: #c0c4cc;
}

.market-view__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.market-view__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.market-view__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.market-view__subtitle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.market-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.market-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f7f9fc;
}

.market-stat__label {
  font-size: 12px;
  color: #909399;
}

.market-stat__value {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.market-stat__value--small {
  font-size: 14px;
}

.market-stat__hint {
  font-size: 11px;
  color: #c0c4cc;
}

.is-up {
  color: #f56c6c;
}

.is-down {
  color: #67c23a;
}

.market-view__chart {
  min-height: 360px;
}

@media (max-width: 900px) {
  .market-view {
    flex-direction: column;
  }

  .market-view__aside {
    flex: none;
  }

  .market-view__assets {
    max-height: 240px;
  }
}
</style>
