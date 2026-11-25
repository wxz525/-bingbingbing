<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  points: [string, number][]
  field: string
}>()

type SeriesKey = 'close' | 'ma5' | 'ma20' | 'ma60' | 'boll'

const visible = ref<Record<SeriesKey, boolean>>({
  close: true,
  ma5: false,
  ma20: false,
  ma60: false,
  boll: false,
})

function toggleSeries(key: SeriesKey): void {
  visible.value[key] = !visible.value[key]
}

const WIDTH = 960
const HEIGHT = 340
const PADDING = { left: 62, right: 18, top: 18, bottom: 30 }

const plotWidth = WIDTH - PADDING.left - PADDING.right
const plotHeight = HEIGHT - PADDING.top - PADDING.bottom

const values = computed(() => props.points.map((point) => point[1]))

function movingAverage(period: number): (number | null)[] {
  const list = values.value
  const result: (number | null)[] = new Array(list.length).fill(null)
  let sum = 0
  for (let index = 0; index < list.length; index += 1) {
    sum += list[index]
    if (index >= period) {
      sum -= list[index - period]
    }
    if (index >= period - 1) {
      result[index] = sum / period
    }
  }
  return result
}

const ma5 = computed(() => movingAverage(5))
const ma20 = computed(() => movingAverage(20))
const ma60 = computed(() => movingAverage(60))

const BOLL_PERIOD = 20
const BOLL_MULTIPLIER = 2

const boll = computed(() => {
  const list = values.value
  const middle = movingAverage(BOLL_PERIOD)
  const upper: (number | null)[] = new Array(list.length).fill(null)
  const lower: (number | null)[] = new Array(list.length).fill(null)
  for (let index = BOLL_PERIOD - 1; index < list.length; index += 1) {
    const window = list.slice(index - BOLL_PERIOD + 1, index + 1)
    const mean = middle[index] as number
    const variance = window.reduce((sum, item) => sum + (item - mean) ** 2, 0) / BOLL_PERIOD
    const deviation = Math.sqrt(variance) * BOLL_MULTIPLIER
    upper[index] = mean + deviation
    lower[index] = mean - deviation
  }
  return { middle, upper, lower }
})

const overlayValues = computed(() => {
  const seriesList: (number | null)[][] = []
  if (visible.value.ma5) {
    seriesList.push(ma5.value)
  }
  if (visible.value.ma20) {
    seriesList.push(ma20.value)
  }
  if (visible.value.ma60) {
    seriesList.push(ma60.value)
  }
  if (visible.value.boll) {
    seriesList.push(boll.value.upper, boll.value.lower)
  }
  const all: number[] = []
  for (const series of seriesList) {
    for (const value of series) {
      if (value !== null) {
        all.push(value)
      }
    }
  }
  return all
})

const minValue = computed(() => {
  const all = overlayValues.value.concat(visible.value.close ? values.value : [])
  return all.length ? Math.min(...all) : 0
})
const maxValue = computed(() => {
  const all = overlayValues.value.concat(visible.value.close ? values.value : [])
  return all.length ? Math.max(...all) : 1
})

const scale = computed(() => {
  const span = maxValue.value - minValue.value
  const padding = span === 0 ? Math.abs(maxValue.value || 1) * 0.1 : span * 0.08
  return {
    min: minValue.value - padding,
    max: maxValue.value + padding,
  }
})

function xFor(index: number): number {
  const count = props.points.length
  if (count <= 1) {
    return PADDING.left + plotWidth / 2
  }
  return PADDING.left + (index / (count - 1)) * plotWidth
}

function yFor(value: number): number {
  const { min, max } = scale.value
  const span = max === min ? 1 : max - min
  return PADDING.top + (1 - (value - min) / span) * plotHeight
}

const linePath = computed(() =>
  props.points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${xFor(index).toFixed(1)},${yFor(point[1]).toFixed(1)}`)
    .join(' '),
)

const areaPath = computed(() => {
  if (!props.points.length) {
    return ''
  }
  const last = props.points.length - 1
  return `${linePath.value} L${xFor(last).toFixed(1)},${PADDING.top + plotHeight} L${xFor(0).toFixed(1)},${PADDING.top + plotHeight} Z`
})

function seriesPath(series: (number | null)[]): string {
  const parts: string[] = []
  series.forEach((value, index) => {
    if (value === null) {
      return
    }
    parts.push(`${parts.length === 0 ? 'M' : 'L'}${xFor(index).toFixed(1)},${yFor(value).toFixed(1)}`)
  })
  return parts.join(' ')
}

const maPaths = computed(() => ({
  ma5: seriesPath(ma5.value),
  ma20: seriesPath(ma20.value),
  ma60: seriesPath(ma60.value),
}))

const bollPaths = computed(() => ({
  upper: seriesPath(boll.value.upper),
  middle: seriesPath(boll.value.middle),
  lower: seriesPath(boll.value.lower),
}))

const bandAreaPath = computed(() => {
  const upper = boll.value.upper
  const lower = boll.value.lower
  const indices: number[] = []
  for (let index = 0; index < props.points.length; index += 1) {
    if (upper[index] !== null && lower[index] !== null) {
      indices.push(index)
    }
  }
  if (indices.length < 2) {
    return ''
  }
  const top = indices.map(
    (index) => `${xFor(index).toFixed(1)},${yFor(upper[index] as number).toFixed(1)}`,
  )
  const bottom = indices
    .slice()
    .reverse()
    .map((index) => `${xFor(index).toFixed(1)},${yFor(lower[index] as number).toFixed(1)}`)
  return `M${top.join(' L')} L${bottom.join(' L')} Z`
})

const extremumMarkers = computed(() => {
  const list = props.points
  if (list.length < 2) {
    return []
  }
  let maxIndex = 0
  let minIndex = 0
  list.forEach((point, index) => {
    if (point[1] > list[maxIndex][1]) {
      maxIndex = index
    }
    if (point[1] < list[minIndex][1]) {
      minIndex = index
    }
  })
  const build = (index: number, kind: 'max' | 'min') => {
    const x = xFor(index)
    const y = yFor(list[index][1])
    return {
      kind,
      x,
      y,
      labelX: Math.min(Math.max(x, PADDING.left + 52), WIDTH - PADDING.right - 52),
      labelY: kind === 'max' ? y - 9 : y + 15,
      text: `${formatValue(list[index][1])} · ${list[index][0]}`,
    }
  }
  return [build(maxIndex, 'max'), build(minIndex, 'min')]
})

function formatValue(value: number): string {
  if (props.field === 'yield') {
    return `${value.toFixed(2)}%`
  }
  if (Math.abs(value) >= 10000) {
    return `${(value / 10000).toFixed(2)}万`
  }
  return value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

const yTicks = computed(() => {
  const { min, max } = scale.value
  const steps = 5
  return Array.from({ length: steps }, (_, index) => {
    const value = min + ((max - min) * index) / (steps - 1)
    return { value, y: yFor(value), label: formatValue(value) }
  })
})

const xTicks = computed(() => {
  const count = props.points.length
  if (count === 0) {
    return []
  }
  const ratios = [0, 0.25, 0.5, 0.75, 1]
  const seen = new Set<number>()
  return ratios
    .map((ratio) => Math.round((count - 1) * ratio))
    .filter((index) => {
      if (seen.has(index)) {
        return false
      }
      seen.add(index)
      return true
    })
    .map((index) => ({
      index,
      x: xFor(index),
      label: props.points[index][0],
    }))
})

const hoverIndex = ref<number | null>(null)

function handleMove(event: MouseEvent): void {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  if (!rect.width || !props.points.length) {
    return
  }
  const ratio = (event.clientX - rect.left) / rect.width
  const x = ratio * WIDTH
  const index = Math.round(((x - PADDING.left) / plotWidth) * (props.points.length - 1))
  hoverIndex.value = Math.min(Math.max(index, 0), props.points.length - 1)
}

function handleLeave(): void {
  hoverIndex.value = null
}

const hoverPoint = computed(() => {
  if (hoverIndex.value === null || !props.points[hoverIndex.value]) {
    return null
  }
  const point = props.points[hoverIndex.value]
  return {
    date: point[0],
    value: point[1],
    x: (xFor(hoverIndex.value) / WIDTH) * 100,
    y: (yFor(point[1]) / HEIGHT) * 100,
  }
})
</script>

<template>
  <div class="market-chart" @mousemove="handleMove" @mouseleave="handleLeave">
    <div class="market-chart__legend">
      <button
        type="button"
        class="market-chart__legend-item"
        :class="{ 'is-off': !visible.close }"
        :aria-pressed="visible.close"
        @click="toggleSeries('close')"
      >
        <i class="market-chart__legend-swatch market-chart__legend-swatch--main"></i>
        {{ field === 'yield' ? '收益率' : '收盘价' }}
      </button>
      <button
        type="button"
        class="market-chart__legend-item"
        :class="{ 'is-off': !visible.ma5 }"
        :aria-pressed="visible.ma5"
        @click="toggleSeries('ma5')"
      >
        <i class="market-chart__legend-swatch market-chart__legend-swatch--ma5"></i>MA5
      </button>
      <button
        type="button"
        class="market-chart__legend-item"
        :class="{ 'is-off': !visible.ma20 }"
        :aria-pressed="visible.ma20"
        @click="toggleSeries('ma20')"
      >
        <i class="market-chart__legend-swatch market-chart__legend-swatch--ma20"></i>MA20
      </button>
      <button
        type="button"
        class="market-chart__legend-item"
        :class="{ 'is-off': !visible.ma60 }"
        :aria-pressed="visible.ma60"
        @click="toggleSeries('ma60')"
      >
        <i class="market-chart__legend-swatch market-chart__legend-swatch--ma60"></i>MA60
      </button>
      <button
        type="button"
        class="market-chart__legend-item"
        :class="{ 'is-off': !visible.boll }"
        :aria-pressed="visible.boll"
        @click="toggleSeries('boll')"
      >
        <i class="market-chart__legend-swatch market-chart__legend-swatch--boll"></i>BOLL(20,2)
      </button>
    </div>
    <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" class="market-chart__svg" role="img">
      <defs>
        <linearGradient id="market-area-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#409eff" stop-opacity="0.24" />
          <stop offset="100%" stop-color="#409eff" stop-opacity="0.02" />
        </linearGradient>
      </defs>

      <line
        v-for="tick in yTicks"
        :key="`grid-${tick.value}`"
        :x1="PADDING.left"
        :x2="WIDTH - PADDING.right"
        :y1="tick.y"
        :y2="tick.y"
        class="market-chart__grid"
      />

      <text
        v-for="tick in yTicks"
        :key="`y-${tick.value}`"
        :x="PADDING.left - 8"
        :y="tick.y + 4"
        class="market-chart__axis-label"
        text-anchor="end"
      >
        {{ tick.label }}
      </text>

      <text
        v-for="tick in xTicks"
        :key="`x-${tick.index}`"
        :x="tick.x"
        :y="HEIGHT - 8"
        class="market-chart__axis-label"
        text-anchor="middle"
      >
        {{ tick.label }}
      </text>

      <path v-if="visible.boll" :d="bandAreaPath" class="market-chart__band" />
      <path v-if="visible.close" :d="areaPath" fill="url(#market-area-gradient)" />
      <path v-if="visible.close" :d="linePath" class="market-chart__line" />

      <template v-if="visible.boll">
        <path :d="bollPaths.upper" class="market-chart__overlay market-chart__overlay--boll" />
        <path :d="bollPaths.lower" class="market-chart__overlay market-chart__overlay--boll" />
        <path :d="bollPaths.middle" class="market-chart__overlay market-chart__overlay--boll-mid" />
      </template>
      <path v-if="visible.ma60" :d="maPaths.ma60" class="market-chart__overlay market-chart__overlay--ma60" />
      <path v-if="visible.ma20" :d="maPaths.ma20" class="market-chart__overlay market-chart__overlay--ma20" />
      <path v-if="visible.ma5" :d="maPaths.ma5" class="market-chart__overlay market-chart__overlay--ma5" />

      <g v-if="visible.close">
        <g v-for="marker in extremumMarkers" :key="marker.kind">
          <circle
            :cx="marker.x"
            :cy="marker.y"
            r="3.2"
            :class="`market-chart__extremum market-chart__extremum--${marker.kind}`"
          />
          <text
            :x="marker.labelX"
            :y="marker.labelY"
            :class="`market-chart__extremum-label market-chart__extremum-label--${marker.kind}`"
            text-anchor="middle"
          >
            {{ marker.text }}
          </text>
        </g>
      </g>

      <g v-if="hoverPoint">
        <line
          :x1="(hoverPoint.x / 100) * WIDTH"
          :x2="(hoverPoint.x / 100) * WIDTH"
          :y1="PADDING.top"
          :y2="PADDING.top + plotHeight"
          class="market-chart__crosshair"
        />
        <circle
          v-if="visible.close"
          :cx="(hoverPoint.x / 100) * WIDTH"
          :cy="(hoverPoint.y / 100) * HEIGHT"
          r="4"
          class="market-chart__dot"
        />
      </g>
    </svg>

    <div
      v-if="hoverPoint && visible.close"
      class="market-chart__tooltip"
      :style="{ left: `${hoverPoint.x}%`, top: `${hoverPoint.y}%` }"
    >
      <span class="market-chart__tooltip-date">{{ hoverPoint.date }}</span>
      <span class="market-chart__tooltip-value">{{ formatValue(hoverPoint.value) }}</span>
    </div>
  </div>
</template>

<style scoped>
.market-chart {
  position: relative;
  width: 100%;
}

.market-chart__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding: 0 4px 6px;
  font-size: 12px;
  color: #606266;
}

.market-chart__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 0;
  border: 0;
  background: transparent;
  font: inherit;
  color: inherit;
  cursor: pointer;
  transition: color 0.15s, opacity 0.15s;
}

.market-chart__legend-item:hover {
  opacity: 0.75;
}

.market-chart__legend-item.is-off {
  color: #c0c4cc;
}

.market-chart__legend-item.is-off .market-chart__legend-swatch {
  opacity: 0.3;
}

.market-chart__legend-swatch {
  display: inline-block;
  width: 14px;
  height: 2px;
  border-radius: 1px;
}

.market-chart__legend-swatch--main {
  background: #409eff;
}

.market-chart__legend-swatch--ma5 {
  background: #f59f00;
}

.market-chart__legend-swatch--ma20 {
  background: #9c36b5;
}

.market-chart__legend-swatch--ma60 {
  background: #2b8a3e;
}

.market-chart__legend-swatch--boll {
  background: #a0cfff;
}

.market-chart__overlay {
  fill: none;
  stroke-width: 1.2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.market-chart__overlay--ma5 {
  stroke: #f59f00;
}

.market-chart__overlay--ma20 {
  stroke: #9c36b5;
}

.market-chart__overlay--ma60 {
  stroke: #2b8a3e;
}

.market-chart__overlay--boll {
  stroke: #a0cfff;
  stroke-dasharray: 3 3;
}

.market-chart__overlay--boll-mid {
  stroke: #909399;
  stroke-dasharray: 5 3;
}

.market-chart__band {
  fill: rgba(64, 158, 255, 0.07);
  stroke: none;
}

.market-chart__extremum {
  stroke: #ffffff;
  stroke-width: 1.5;
}

.market-chart__extremum--max {
  fill: #f56c6c;
}

.market-chart__extremum--min {
  fill: #67c23a;
}

.market-chart__extremum-label {
  font-size: 11px;
  font-weight: 600;
}

.market-chart__extremum-label--max {
  fill: #f56c6c;
}

.market-chart__extremum-label--min {
  fill: #67c23a;
}

.market-chart__svg {
  display: block;
  width: 100%;
  height: auto;
}

.market-chart__grid {
  stroke: #ebeef5;
  stroke-width: 1;
}

.market-chart__axis-label {
  fill: #909399;
  font-size: 12px;
}

.market-chart__line {
  fill: none;
  stroke: #409eff;
  stroke-width: 1.6;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.market-chart__crosshair {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.market-chart__dot {
  fill: #409eff;
  stroke: #ffffff;
  stroke-width: 2;
}

.market-chart__tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 10px));
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(48, 49, 51, 0.92);
  color: #ffffff;
  font-size: 12px;
  line-height: 1.4;
  pointer-events: none;
  white-space: nowrap;
}

.market-chart__tooltip-date {
  color: rgba(255, 255, 255, 0.7);
}

.market-chart__tooltip-value {
  font-weight: 600;
}
</style>
