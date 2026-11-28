<script setup lang="ts">
import { computed, ref } from 'vue'

import type { MarketCompareSeries } from '@/types/market'

const props = defineProps<{
  dates: string[]
  items: MarketCompareSeries[]
}>()

const CHART_COLORS = ['#409eff', '#e6a23c', '#8b6ce6', '#13c2c2', '#eb2f96']

const WIDTH = 960
const HEIGHT = 360
const PADDING = { left: 62, right: 18, top: 26, bottom: 30 }
const plotWidth = WIDTH - PADDING.left - PADDING.right
const plotHeight = HEIGHT - PADDING.top - PADDING.bottom

const hoverIndex = ref<number | null>(null)

const yDomain = computed(() => {
  let min = 100
  let max = 100
  for (const item of props.items) {
    for (const value of item.values) {
      if (value === null) {
        continue
      }
      min = Math.min(min, value)
      max = Math.max(max, value)
    }
  }
  const span = max - min || 1
  return { min: min - span * 0.08, max: max + span * 0.08 }
})

function xFor(index: number): number {
  const count = props.dates.length
  if (count <= 1) {
    return PADDING.left + plotWidth / 2
  }
  return PADDING.left + (index / (count - 1)) * plotWidth
}

function yFor(value: number): number {
  const { min, max } = yDomain.value
  return PADDING.top + ((max - value) / (max - min)) * plotHeight
}

const paths = computed(() =>
  props.items.map((item, seriesIndex) => {
    const parts: string[] = []
    let started = false
    item.values.forEach((value, index) => {
      if (value === null) {
        started = false
        return
      }
      parts.push(`${started ? 'L' : 'M'}${xFor(index).toFixed(1)},${yFor(value).toFixed(1)}`)
      started = true
    })
    return {
      name: item.name,
      color: CHART_COLORS[seriesIndex % CHART_COLORS.length],
      d: parts.join(' '),
      totalReturn: item.total_return,
      latest: item.latest_value,
    }
  }),
)

const yTicks = computed(() => {
  const { min, max } = yDomain.value
  const count = 4
  return Array.from({ length: count + 1 }, (_, index) => {
    const value = min + ((max - min) * index) / count
    return { value, y: yFor(value), text: value.toFixed(0) }
  })
})

const xLabels = computed(() => {
  const count = props.dates.length
  if (!count) {
    return []
  }
  const slots = Math.min(6, count)
  return Array.from({ length: slots }, (_, index) => {
    const position = Math.round((index * (count - 1)) / (slots - 1 || 1))
    return { index: position, x: xFor(position), text: props.dates[position] }
  })
})

const hoveredPoints = computed(() => {
  const index = hoverIndex.value
  if (index === null) {
    return []
  }
  return props.items.map((item, seriesIndex) => {
    const value = item.values[index]
    return {
      name: item.name,
      color: CHART_COLORS[seriesIndex % CHART_COLORS.length],
      value,
      x: xFor(index),
      y: value === null ? null : yFor(value),
    }
  })
})

const tooltipStyle = computed(() => {
  const index = hoverIndex.value
  if (index === null) {
    return {}
  }
  return { left: `${xFor(index)}px` }
})

const crosshairX = computed(() => (hoverIndex.value === null ? 0 : xFor(hoverIndex.value)))

const hoveredDate = computed(() => {
  const index = hoverIndex.value
  return index === null ? '' : (props.dates[index] ?? '')
})

function handleMove(event: MouseEvent): void {
  if (props.dates.length < 2) {
    return
  }
  const svg = event.currentTarget as SVGSVGElement
  const rect = svg.getBoundingClientRect()
  const ratio = (event.clientX - rect.left - PADDING.left) / plotWidth
  const index = Math.round(ratio * (props.dates.length - 1))
  hoverIndex.value = Math.min(Math.max(index, 0), props.dates.length - 1)
}

function clearHover(): void {
  hoverIndex.value = null
}

function formatChange(change: number): string {
  return `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`
}
</script>

<template>
  <div class="compare" data-testid="market-compare-chart">
    <div class="compare__legend">
      <span v-for="line in paths" :key="line.name" class="legend-item">
        <i class="legend-line" :style="{ background: line.color }"></i>
        {{ line.name }}
        <b :class="line.totalReturn >= 0 ? 'is-up' : 'is-down'">
          {{ formatChange(line.totalReturn * 100) }}
        </b>
      </span>
    </div>

    <div class="compare__canvas">
      <svg
        :width="WIDTH"
        :height="HEIGHT"
        class="compare__svg"
        role="img"
        aria-label="多标的归一化对比"
        @mousemove="handleMove"
        @mouseleave="clearHover"
      >
        <line
          v-for="(tick, index) in yTicks"
          :key="`y-${index}`"
          :x1="PADDING.left"
          :x2="WIDTH - PADDING.right"
          :y1="tick.y"
          :y2="tick.y"
          class="compare__grid"
        />
        <line
          :x1="PADDING.left"
          :x2="WIDTH - PADDING.right"
          :y1="yFor(100)"
          :y2="yFor(100)"
          class="compare__baseline"
        />
        <text
          v-for="(tick, index) in yTicks"
          :key="`yt-${index}`"
          :x="PADDING.left - 10"
          :y="tick.y + 3"
          class="compare__axis-text"
          text-anchor="end"
        >
          {{ tick.text }}
        </text>
        <text
          v-for="(label, index) in xLabels"
          :key="`xt-${index}`"
          :x="label.x"
          :y="HEIGHT - PADDING.bottom + 18"
          class="compare__axis-text"
          text-anchor="middle"
        >
          {{ label.text }}
        </text>

        <path v-for="line in paths" :key="line.name" :d="line.d" :stroke="line.color" class="compare__line" />

        <g v-if="hoverIndex !== null">
          <line
            :x1="crosshairX"
            :x2="crosshairX"
            :y1="PADDING.top"
            :y2="HEIGHT - PADDING.bottom"
            class="compare__crosshair"
          />
          <circle
            v-for="point in hoveredPoints"
            :key="`p-${point.name}`"
            v-show="point.y !== null"
            :cx="point.x"
            :cy="point.y ?? 0"
            r="3.5"
            :fill="point.color"
          />
        </g>

        <text
          v-if="!items.length"
          :x="WIDTH / 2"
          :y="HEIGHT / 2"
          class="compare__empty"
          text-anchor="middle"
        >
          勾选 2 个以上标的开始对比
        </text>
      </svg>

      <div v-if="hoverIndex !== null" class="compare__tooltip" :style="tooltipStyle">
        <div class="compare__tooltip-date">{{ hoveredDate }}</div>
        <div v-for="point in hoveredPoints" :key="`t-${point.name}`" class="compare__tooltip-row">
          <i class="legend-dot" :style="{ background: point.color }"></i>
          <span class="compare__tooltip-name">{{ point.name }}</span>
          <b v-if="point.value !== null" :class="point.value >= 100 ? 'is-up' : 'is-down'">
            {{ formatChange(point.value - 100) }}
          </b>
          <b v-else>—</b>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.compare {
  width: 100%;
  overflow-x: auto;
}

.compare__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 6px;
  font-size: 12px;
  color: #606266;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.legend-line {
  display: inline-block;
  width: 14px;
  height: 3px;
  border-radius: 2px;
}

.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.compare__canvas {
  position: relative;
  width: 960px;
}

.compare__svg {
  display: block;
  cursor: crosshair;
}

.compare__grid {
  stroke: #ebeef5;
  stroke-width: 1;
}

.compare__baseline {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 4 3;
}

.compare__axis-text {
  font-size: 10px;
  fill: #909399;
}

.compare__line {
  fill: none;
  stroke-width: 1.8;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.compare__crosshair {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.compare__empty {
  font-size: 13px;
  fill: #909399;
}

.compare__tooltip {
  position: absolute;
  top: 6px;
  z-index: 2;
  min-width: 150px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  color: #606266;
  pointer-events: none;
  transform: translate(-50%, 0);
}

.compare__tooltip-date {
  margin-bottom: 4px;
  font-weight: 600;
  color: #303133;
}

.compare__tooltip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1.7;
}

.compare__tooltip-name {
  flex: 1;
  min-width: 72px;
}

.compare__tooltip-row b {
  font-weight: 600;
}

.is-up {
  color: #f56c6c;
}

.is-down {
  color: #67c23a;
}
</style>
