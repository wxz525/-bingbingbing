<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  points: [string, number][]
  field: string
}>()

const WIDTH = 960
const HEIGHT = 340
const PADDING = { left: 62, right: 18, top: 18, bottom: 30 }

const plotWidth = WIDTH - PADDING.left - PADDING.right
const plotHeight = HEIGHT - PADDING.top - PADDING.bottom

const values = computed(() => props.points.map((point) => point[1]))
const minValue = computed(() => (values.value.length ? Math.min(...values.value) : 0))
const maxValue = computed(() => (values.value.length ? Math.max(...values.value) : 1))

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

      <path :d="areaPath" fill="url(#market-area-gradient)" />
      <path :d="linePath" class="market-chart__line" />

      <g v-if="hoverPoint">
        <line
          :x1="(hoverPoint.x / 100) * WIDTH"
          :x2="(hoverPoint.x / 100) * WIDTH"
          :y1="PADDING.top"
          :y2="PADDING.top + plotHeight"
          class="market-chart__crosshair"
        />
        <circle
          :cx="(hoverPoint.x / 100) * WIDTH"
          :cy="(hoverPoint.y / 100) * HEIGHT"
          r="4"
          class="market-chart__dot"
        />
      </g>
    </svg>

    <div
      v-if="hoverPoint"
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
