<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  points: [string, number][]
  unit: string
  kind: 'ratio' | 'spread'
}>()

const WIDTH = 960
const HEIGHT = 360
const PADDING = { left: 68, right: 18, top: 20, bottom: 30 }
const plotWidth = WIDTH - PADDING.left - PADDING.right
const plotHeight = HEIGHT - PADDING.top - PADDING.bottom

const hoverIndex = ref<number | null>(null)

const yDomain = computed(() => {
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY
  for (const [, value] of props.points) {
    min = Math.min(min, value)
    max = Math.max(max, value)
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return { min: 0, max: 1 }
  }
  const span = max - min || Math.abs(max) * 0.1 || 1
  return { min: min - span * 0.1, max: max + span * 0.1 }
})

function xFor(index: number): number {
  const count = props.points.length
  if (count <= 1) {
    return PADDING.left + plotWidth / 2
  }
  return PADDING.left + (index / (count - 1)) * plotWidth
}

function yFor(value: number): number {
  const { min, max } = yDomain.value
  return PADDING.top + ((max - value) / (max - min)) * plotHeight
}

function formatValue(value: number): string {
  return props.unit === 'pp' ? `${value.toFixed(2)} pp` : `${value.toFixed(2)} ${props.unit}`
}

const linePath = computed(() => {
  const parts: string[] = []
  props.points.forEach(([, value], index) => {
    parts.push(`${index === 0 ? 'M' : 'L'}${xFor(index).toFixed(1)},${yFor(value).toFixed(1)}`)
  })
  return parts.join(' ')
})

const areaPath = computed(() => {
  if (!props.points.length) {
    return ''
  }
  const first = xFor(0).toFixed(1)
  const last = xFor(props.points.length - 1).toFixed(1)
  const bottom = (PADDING.top + plotHeight).toFixed(1)
  return `${linePath.value} L${last},${bottom} L${first},${bottom} Z`
})

const yTicks = computed(() => {
  const { min, max } = yDomain.value
  const count = 4
  return Array.from({ length: count + 1 }, (_, index) => {
    const value = min + ((max - min) * index) / count
    return { value, y: yFor(value), text: value.toFixed(props.kind === 'spread' ? 1 : 0) }
  })
})

const xLabels = computed(() => {
  const count = props.points.length
  if (!count) {
    return []
  }
  const slots = Math.min(6, count)
  return Array.from({ length: slots }, (_, index) => {
    const position = Math.round((index * (count - 1)) / (slots - 1 || 1))
    return { index: position, x: xFor(position), text: props.points[position][0] }
  })
})

const zeroY = computed(() => {
  const { min, max } = yDomain.value
  return min <= 0 && max >= 0 ? yFor(0) : null
})

const hoveredPoint = computed(() => {
  const index = hoverIndex.value
  if (index === null) {
    return null
  }
  const point = props.points[index]
  if (!point) {
    return null
  }
  return {
    date: point[0],
    value: point[1],
    change: point[1] - props.points[0][1],
    x: xFor(index),
    y: yFor(point[1]),
  }
})

function handleMove(event: MouseEvent): void {
  if (props.points.length < 2) {
    return
  }
  const svg = event.currentTarget as SVGSVGElement
  const rect = svg.getBoundingClientRect()
  const ratio = (event.clientX - rect.left - PADDING.left) / plotWidth
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
  return { left: `${point.x}px` }
})
</script>

<template>
  <div class="indicator-chart" data-testid="market-indicator-chart">
    <div class="indicator-chart__canvas">
      <svg
        :width="WIDTH"
        :height="HEIGHT"
        class="indicator-chart__svg"
        role="img"
        aria-label="比值利差走势"
        @mousemove="handleMove"
        @mouseleave="clearHover"
      >
        <line
          v-for="(tick, index) in yTicks"
          :key="`g-${index}`"
          :x1="PADDING.left"
          :x2="WIDTH - PADDING.right"
          :y1="tick.y"
          :y2="tick.y"
          class="indicator-chart__grid"
        />
        <line
          v-if="zeroY !== null"
          :x1="PADDING.left"
          :x2="WIDTH - PADDING.right"
          :y1="zeroY"
          :y2="zeroY"
          class="indicator-chart__zero"
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
          :y="HEIGHT - PADDING.bottom + 18"
          class="indicator-chart__axis-text"
          text-anchor="middle"
        >
          {{ label.text }}
        </text>

        <path :d="areaPath" class="indicator-chart__area" />
        <path :d="linePath" class="indicator-chart__line" />

        <g v-if="hoveredPoint">
          <line
            :x1="hoveredPoint.x"
            :x2="hoveredPoint.x"
            :y1="PADDING.top"
            :y2="HEIGHT - PADDING.bottom"
            class="indicator-chart__crosshair"
          />
          <circle :cx="hoveredPoint.x" :cy="hoveredPoint.y" r="3.5" class="indicator-chart__dot" />
        </g>

        <text
          v-if="!points.length"
          :x="WIDTH / 2"
          :y="HEIGHT / 2"
          class="indicator-chart__empty"
          text-anchor="middle"
        >
          该指标在所选区间内没有足够数据
        </text>
      </svg>

      <div v-if="hoveredPoint" class="indicator-chart__tooltip" :style="tooltipStyle">
        <div class="indicator-chart__tooltip-date">{{ hoveredPoint.date }}</div>
        <div class="indicator-chart__tooltip-value">{{ formatValue(hoveredPoint.value) }}</div>
        <div class="indicator-chart__tooltip-change">
          区间变化
          <b :class="hoveredPoint.change >= 0 ? 'is-up' : 'is-down'">
            {{ hoveredPoint.change >= 0 ? '+' : '' }}{{ hoveredPoint.change.toFixed(2) }}
          </b>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.indicator-chart {
  width: 100%;
  overflow-x: auto;
}

.indicator-chart__canvas {
  position: relative;
  width: 960px;
}

.indicator-chart__svg {
  display: block;
  cursor: crosshair;
}

.indicator-chart__grid {
  stroke: #ebeef5;
  stroke-width: 1;
}

.indicator-chart__zero {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 4 3;
}

.indicator-chart__axis-text {
  font-size: 10px;
  fill: #909399;
}

.indicator-chart__area {
  fill: #409eff;
  fill-opacity: 0.08;
}

.indicator-chart__line {
  fill: none;
  stroke: #409eff;
  stroke-width: 1.8;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.indicator-chart__crosshair {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.indicator-chart__dot {
  fill: #409eff;
}

.indicator-chart__empty {
  font-size: 13px;
  fill: #909399;
}

.indicator-chart__tooltip {
  position: absolute;
  top: 6px;
  z-index: 2;
  min-width: 140px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  color: #606266;
  pointer-events: none;
  transform: translate(-50%, 0);
}

.indicator-chart__tooltip-date {
  margin-bottom: 4px;
  font-weight: 600;
  color: #303133;
}

.indicator-chart__tooltip-value {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.indicator-chart__tooltip-change {
  margin-top: 2px;
}

.indicator-chart__tooltip-change b {
  font-weight: 600;
}

.is-up {
  color: #f56c6c;
}

.is-down {
  color: #67c23a;
}
</style>
