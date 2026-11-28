<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { formatAxisDate } from '@/utils/indicatorAnalysis'

const props = withDefaults(
  defineProps<{
    points: [string, number][]
    unit?: string
    kind?: 'ratio' | 'spread'
    /** 历史均值参考线 */
    meanValue?: number | null
    /** 25%–75% 历史分位阴影带 */
    quantileBand?: { low: number; high: number } | null
    /** 利差零轴 / 标准化 100 基准 */
    baseline?: number | null
    baselineLabel?: string
    valueFormatter?: (value: number) => string
    emptyText?: string
    height?: number
  }>(),
  {
    unit: '',
    kind: 'ratio',
    meanValue: null,
    quantileBand: null,
    baseline: null,
    baselineLabel: '',
    valueFormatter: undefined,
    emptyText: '所选区间没有可用数据',
    height: 380,
  },
)

const PADDING = { left: 62, right: 22, top: 24, bottom: 34 }
const MIN_WIDTH = 320

const wrapper = ref<HTMLDivElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)
const containerWidth = ref(960)
const hoverIndex = ref<number | null>(null)

let observer: ResizeObserver | null = null

onMounted(() => {
  if (!wrapper.value) {
    return
  }
  const update = () => {
    const width = wrapper.value?.clientWidth ?? 0
    if (width > 0) {
      containerWidth.value = Math.max(width, MIN_WIDTH)
    }
  }
  update()
  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(update)
    observer.observe(wrapper.value)
  } else {
    window.addEventListener('resize', update)
  }
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})

const width = computed(() => Math.max(containerWidth.value, MIN_WIDTH))
const plotWidth = computed(() => width.value - PADDING.left - PADDING.right)
const plotHeight = computed(() => props.height - PADDING.top - PADDING.bottom)

function fallbackFormat(value: number): string {
  if (!Number.isFinite(value)) {
    return '--'
  }
  if (props.kind === 'spread') {
    return `${value.toFixed(2)} ${props.unit || 'pp'}`
  }
  return `${value.toFixed(2)} ${props.unit || '倍'}`
}

const formatValue = (value: number): string =>
  props.valueFormatter ? props.valueFormatter(value) : fallbackFormat(value)

const yDomain = computed(() => {
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY
  for (const [, value] of props.points) {
    if (!Number.isFinite(value)) {
      continue
    }
    min = Math.min(min, value)
    max = Math.max(max, value)
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return { min: 0, max: 1 }
  }
  if (min === max) {
    const span = Math.abs(max) * 0.02 || 1
    return { min: min - span, max: max + span }
  }
  const span = max - min
  return { min: min - span * 0.08, max: max + span * 0.08 }
})

function xFor(index: number): number {
  const count = props.points.length
  if (count <= 1) {
    return PADDING.left + plotWidth.value / 2
  }
  return PADDING.left + (index / (count - 1)) * plotWidth.value
}

function yFor(value: number): number {
  const { min, max } = yDomain.value
  if (max === min) {
    return PADDING.top + plotHeight.value / 2
  }
  return PADDING.top + ((max - value) / (max - min)) * plotHeight.value
}

const linePath = computed(() => {
  const parts: string[] = []
  props.points.forEach(([, value], index) => {
    if (!Number.isFinite(value)) {
      return
    }
    parts.push(`${index === 0 ? 'M' : 'L'}${xFor(index).toFixed(1)},${yFor(value).toFixed(1)}`)
  })
  return parts.join(' ')
})

const areaPath = computed(() => {
  if (props.points.length < 2) {
    return ''
  }
  const first = xFor(0).toFixed(1)
  const last = xFor(props.points.length - 1).toFixed(1)
  const bottom = (PADDING.top + plotHeight.value).toFixed(1)
  return `${linePath.value} L${last},${bottom} L${first},${bottom} Z`
})

const yTicks = computed(() => {
  const { min, max } = yDomain.value
  const count = 4
  return Array.from({ length: count + 1 }, (_, index) => {
    const value = min + ((max - min) * index) / count
    return { value, y: yFor(value), text: formatTick(value) }
  })
})

function formatTick(value: number): string {
  if (props.kind === 'spread') {
    return props.unit === 'bp' ? (value * 100).toFixed(0) : value.toFixed(2)
  }
  return value.toFixed(Math.abs(value) >= 100 ? 1 : 2)
}

const spanDays = computed(() => {
  if (props.points.length < 2) {
    return 0
  }
  const first = Date.parse(props.points[0][0])
  const last = Date.parse(props.points[props.points.length - 1][0])
  if (!Number.isFinite(first) || !Number.isFinite(last)) {
    return 0
  }
  return Math.abs(last - first) / (24 * 60 * 60 * 1000)
})

const xLabels = computed(() => {
  const count = props.points.length
  if (!count) {
    return []
  }
  const slots = Math.min(
    props.points.length,
    Math.max(2, Math.min(7, Math.floor(plotWidth.value / 90))),
  )
  return Array.from({ length: slots }, (_, index) => {
    const position = Math.round((index * (count - 1)) / (slots - 1 || 1))
    return {
      index: position,
      x: xFor(position),
      text: formatAxisDate(props.points[position][0], spanDays.value),
    }
  })
})

const zeroY = computed(() => {
  if (props.baseline === null || !Number.isFinite(props.baseline)) {
    return null
  }
  const y = yFor(props.baseline)
  if (y < PADDING.top - 1 || y > PADDING.top + plotHeight.value + 1) {
    return null
  }
  return y
})

const meanY = computed(() => {
  if (props.meanValue === null || !Number.isFinite(props.meanValue)) {
    return null
  }
  const y = yFor(props.meanValue)
  if (y < PADDING.top || y > PADDING.top + plotHeight.value) {
    return null
  }
  return y
})

const bandRect = computed(() => {
  const band = props.quantileBand
  if (!band || !Number.isFinite(band.low) || !Number.isFinite(band.high)) {
    return null
  }
  const top = PADDING.top
  const bottom = PADDING.top + plotHeight.value
  const yHigh = yFor(band.high)
  const yLow = yFor(band.low)
  if (yHigh > bottom || yLow < top) {
    return null
  }
  const clippedTop = Math.max(yHigh, top)
  const clippedBottom = Math.min(yLow, bottom)
  if (clippedBottom <= clippedTop) {
    return null
  }
  return {
    y: clippedTop,
    height: clippedBottom - clippedTop,
  }
})

const latest = computed(() => {
  const count = props.points.length
  if (!count) {
    return null
  }
  const [date, value] = props.points[count - 1]
  if (!Number.isFinite(value)) {
    return null
  }
  const x = xFor(count - 1)
  const y = yFor(value)
  const alignEnd = x > width.value - 90
  return {
    date,
    value,
    x,
    y,
    textX: alignEnd ? x - 8 : x + 8,
    anchor: alignEnd ? 'end' : 'start',
    text: formatValue(value),
  }
})

const hoveredPoint = computed(() => {
  const index = hoverIndex.value
  if (index === null) {
    return null
  }
  const point = props.points[index]
  if (!point || !Number.isFinite(point[1])) {
    return null
  }
  const base = props.points[0]?.[1]
  return {
    date: point[0],
    value: point[1],
    x: xFor(index),
    y: yFor(point[1]),
    change: Number.isFinite(base) ? point[1] - base : null,
  }
})

function handleMove(event: MouseEvent): void {
  if (props.points.length < 2) {
    return
  }
  const svg = svgRef.value
  if (!svg) {
    return
  }
  const rect = svg.getBoundingClientRect()
  if (!rect.width) {
    return
  }
  // 依据实际渲染宽度换算，避免容器缩放后坐标失配
  const localX = ((event.clientX - rect.left) / rect.width) * width.value
  const ratio = (localX - PADDING.left) / plotWidth.value
  const index = Math.round(ratio * (props.points.length - 1))
  hoverIndex.value = Math.min(Math.max(index, 0), props.points.length - 1)
}

function clearHover(): void {
  hoverIndex.value = null
}

const tooltipStyle = computed(() => {
  const point = hoveredPoint.value
  if (!point) {
    return {}
  }
  const half = 96
  const clamped = Math.min(
    Math.max(point.x, half + 6),
    Math.max(width.value - half - 6, half + 6),
  )
  return { left: `${clamped}px` }
})

const changeText = computed(() => {
  const point = hoveredPoint.value
  if (!point || point.change === null) {
    return ''
  }
  if (props.kind === 'spread') {
    const converted = props.unit === 'bp' ? point.change * 100 : point.change
    const digits = props.unit === 'bp' ? 0 : 2
    return `${converted >= 0 ? '+' : ''}${converted.toFixed(digits)} ${props.unit || 'pp'}`
  }
  return `${point.change >= 0 ? '+' : ''}${point.change.toFixed(2)}`
})
</script>

<template>
  <div ref="wrapper" class="indicator-chart" data-testid="market-indicator-chart">
    <div class="indicator-chart__canvas" :style="{ height: `${height}px` }">
      <svg
        ref="svgRef"
        :width="width"
        :height="height"
        class="indicator-chart__svg"
        role="img"
        aria-label="比值利差历史走势"
        @mousemove="handleMove"
        @mouseleave="clearHover"
      >
        <defs>
          <clipPath id="indicator-chart-plot">
            <rect
              :x="PADDING.left"
              :y="PADDING.top"
              :width="plotWidth"
              :height="plotHeight"
            />
          </clipPath>
        </defs>

        <line
          v-for="(tick, index) in yTicks"
          :key="`g-${index}`"
          :x1="PADDING.left"
          :x2="width - PADDING.right"
          :y1="tick.y"
          :y2="tick.y"
          class="indicator-chart__grid"
        />

        <text
          v-for="(tick, index) in yTicks"
          :key="`yt-${index}`"
          :x="PADDING.left - 10"
          :y="tick.y + 3"
          class="indicator-chart__axis-text"
          text-anchor="end"
        >
          {{ tick.text }}
        </text>
        <text
          v-for="(label, index) in xLabels"
          :key="`xt-${index}`"
          :x="label.x"
          :y="height - PADDING.bottom + 18"
          class="indicator-chart__axis-text"
          text-anchor="middle"
        >
          {{ label.text }}
        </text>

        <g clip-path="url(#indicator-chart-plot)">
          <rect
            v-if="bandRect"
            :x="PADDING.left"
            :y="bandRect.y"
            :width="plotWidth"
            :height="bandRect.height"
            class="indicator-chart__band"
          />
          <line
            v-if="meanY !== null"
            :x1="PADDING.left"
            :x2="width - PADDING.right"
            :y1="meanY"
            :y2="meanY"
            class="indicator-chart__mean"
          />
          <path :d="areaPath" class="indicator-chart__area" />
          <path :d="linePath" class="indicator-chart__line" />
        </g>

        <line
          v-if="zeroY !== null"
          :x1="PADDING.left"
          :x2="width - PADDING.right"
          :y1="zeroY"
          :y2="zeroY"
          class="indicator-chart__baseline"
        />
        <text
          v-if="zeroY !== null && baselineLabel"
          :x="width - PADDING.right"
          :y="zeroY - 5"
          class="indicator-chart__baseline-text"
          text-anchor="end"
        >
          {{ baselineLabel }}
        </text>

        <g v-if="latest">
          <line
            :x1="latest.x"
            :x2="latest.x"
            :y1="PADDING.top"
            :y2="PADDING.top + plotHeight"
            class="indicator-chart__latest-line"
          />
          <circle :cx="latest.x" :cy="latest.y" r="3" class="indicator-chart__latest-dot" />
          <text
            v-if="latest.y > PADDING.top + 14"
            :x="latest.textX"
            :y="latest.y - 9"
            :text-anchor="latest.anchor"
            class="indicator-chart__latest-text"
          >
            {{ latest.text }}
          </text>
        </g>

        <g v-if="hoveredPoint">
          <line
            :x1="hoveredPoint.x"
            :x2="hoveredPoint.x"
            :y1="PADDING.top"
            :y2="PADDING.top + plotHeight"
            class="indicator-chart__crosshair"
          />
          <circle :cx="hoveredPoint.x" :cy="hoveredPoint.y" r="3.5" class="indicator-chart__dot" />
        </g>

        <text
          v-if="!points.length"
          :x="width / 2"
          :y="height / 2"
          class="indicator-chart__empty"
          text-anchor="middle"
        >
          {{ emptyText }}
        </text>
      </svg>

      <div v-if="hoveredPoint" class="indicator-chart__tooltip" :style="tooltipStyle">
        <div class="indicator-chart__tooltip-date">{{ hoveredPoint.date }}</div>
        <div class="indicator-chart__tooltip-value">{{ formatValue(hoveredPoint.value) }}</div>
        <div v-if="changeText" class="indicator-chart__tooltip-change">
          较区间起点 <span>{{ changeText }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.indicator-chart {
  width: 100%;
  min-width: 0;
}

.indicator-chart__canvas {
  position: relative;
  width: 100%;
}

.indicator-chart__svg {
  display: block;
  width: 100%;
  cursor: crosshair;
  overflow: visible;
}

.indicator-chart__grid {
  stroke: #ebeef5;
  stroke-width: 1;
}

.indicator-chart__baseline {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 5 4;
  opacity: 0.9;
}

.indicator-chart__baseline-text {
  font-size: 10px;
  fill: #909399;
  letter-spacing: 0.04em;
}

.indicator-chart__band {
  fill: #909399;
  fill-opacity: 0.12;
}

.indicator-chart__mean {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 4 4;
  opacity: 0.9;
}

.indicator-chart__axis-text {
  font-size: 10px;
  fill: #909399;
  font-variant-numeric: tabular-nums;
}

.indicator-chart__area {
  fill: #409eff;
  fill-opacity: 0.08;
}

.indicator-chart__line {
  fill: none;
  stroke: #409eff;
  stroke-width: 1.6;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.indicator-chart__latest-line {
  stroke: #e4e7ed;
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.indicator-chart__latest-dot {
  fill: #409eff;
  stroke: #ffffff;
  stroke-width: 1.5;
}

.indicator-chart__latest-text {
  font-size: 10px;
  fill: #303133;
  font-variant-numeric: tabular-nums;
}

.indicator-chart__crosshair {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.indicator-chart__dot {
  fill: #409eff;
  stroke: #ffffff;
  stroke-width: 1.5;
}

.indicator-chart__empty {
  font-size: 13px;
  fill: #909399;
}

.indicator-chart__tooltip {
  position: absolute;
  top: 10px;
  z-index: 2;
  min-width: 150px;
  padding: 8px 10px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  color: #606266;
  pointer-events: none;
  transform: translateX(-50%);
}

.indicator-chart__tooltip-date {
  margin-bottom: 4px;
  color: #909399;
}

.indicator-chart__tooltip-value {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  font-variant-numeric: tabular-nums;
}

.indicator-chart__tooltip-change {
  margin-top: 2px;
}

.indicator-chart__tooltip-change span {
  color: #303133;
  font-variant-numeric: tabular-nums;
}
</style>
