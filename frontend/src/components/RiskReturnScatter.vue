<script setup lang="ts">
import { computed, ref } from 'vue'

import type { MarketScatterPoint } from '@/types/market'

const props = defineProps<{
  items: MarketScatterPoint[]
  selectedName?: string
}>()

const emit = defineEmits<{ select: [name: string] }>()

// 分类配色避开红/绿，避免与“涨红跌绿”的涨跌语义混淆。
const CATEGORY_COLORS: Record<string, string> = {
  中国权益: '#4a7cf7',
  全球权益: '#13c2c2',
  大宗商品: '#e6a23c',
  外汇: '#8b6ce6',
  另类: '#eb2f96',
  全球债券: '#f759ab',
}
const CATEGORY_ORDER = ['中国权益', '全球权益', '大宗商品', '外汇', '另类', '全球债券']
const FALLBACK_COLOR = '#a0aec0'

function colorFor(category: string): string {
  return CATEGORY_COLORS[category] ?? FALLBACK_COLOR
}

const WIDTH = 960
const HEIGHT = 380
const PADDING = { left: 68, right: 24, top: 22, bottom: 46 }
const plotWidth = WIDTH - PADDING.left - PADDING.right
const plotHeight = HEIGHT - PADDING.top - PADDING.bottom

const xMax = computed(() => {
  const maxVol = props.items.reduce((max, item) => Math.max(max, item.annual_volatility), 0)
  return maxVol > 0 ? maxVol * 1.12 : 0.1
})

const yBounds = computed(() => {
  let min = 0
  let max = 0
  for (const item of props.items) {
    min = Math.min(min, item.annual_return)
    max = Math.max(max, item.annual_return)
  }
  const padMin = Math.abs(min) * 0.12 || 0.01
  const padMax = Math.abs(max) * 0.12 || 0.01
  return { min: min - padMin, max: max + padMax }
})

function xFor(value: number): number {
  return PADDING.left + (value / xMax.value) * plotWidth
}

function yFor(value: number): number {
  const { min, max } = yBounds.value
  return PADDING.top + ((max - value) / (max - min)) * plotHeight
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

const hoveredName = ref('')

const points = computed(() =>
  props.items.map((item) => {
    const selected = item.name === props.selectedName
    const hovered = item.name === hoveredName.value
    return {
      item,
      x: xFor(item.annual_volatility),
      y: yFor(item.annual_return),
      r: selected || hovered ? 7 : 5,
      color: colorFor(item.category),
      selected,
      hovered,
      labelX: xFor(item.annual_volatility) + 9,
      labelY: yFor(item.annual_return) - 9,
    }
  }),
)

const hoveredPoint = computed(
  () => points.value.find((point) => point.hovered) ?? null,
)

const xTicks = computed(() => {
  const count = 5
  return Array.from({ length: count + 1 }, (_, index) => {
    const value = (xMax.value * index) / count
    return { value, x: xFor(value), text: `${(value * 100).toFixed(0)}%` }
  })
})

const yTicks = computed(() => {
  const { min, max } = yBounds.value
  const count = 4
  return Array.from({ length: count + 1 }, (_, index) => {
    const value = min + ((max - min) * index) / count
    return { value, y: yFor(value), text: `${(value * 100).toFixed(0)}%` }
  })
})

const zeroY = computed(() => (yBounds.value.min <= 0 ? yFor(0) : null))

const legend = computed(() => {
  const seen = new Set(props.items.map((item) => item.category))
  const known = CATEGORY_ORDER.filter((category) => seen.has(category))
  const rest = [...seen].filter((category) => !CATEGORY_ORDER.includes(category))
  return [...known, ...rest].map((category) => ({
    category,
    color: colorFor(category),
    count: props.items.filter((item) => item.category === category).length,
  }))
})

const tooltipStyle = computed(() => {
  const point = hoveredPoint.value
  if (!point) {
    return {}
  }
  return {
    left: `${point.x}px`,
    top: `${point.y - 12}px`,
  }
})
</script>

<template>
  <div class="scatter" data-testid="risk-return-scatter">
    <div class="scatter__legend">
      <span v-for="item in legend" :key="item.category" class="legend-item">
        <i class="legend-dot" :style="{ background: item.color }"></i>
        {{ item.category }}<span class="legend-count">{{ item.count }}</span>
      </span>
    </div>

    <div class="scatter__canvas">
      <svg
        :width="WIDTH"
        :height="HEIGHT"
        class="scatter__svg"
        role="img"
        aria-label="风险收益散点图"
      >
        <line
          v-for="(tick, index) in yTicks"
          :key="`yg-${index}`"
          :x1="PADDING.left"
          :x2="WIDTH - PADDING.right"
          :y1="tick.y"
          :y2="tick.y"
          class="scatter__grid"
        />
        <line
          v-for="(tick, index) in xTicks"
          :key="`xg-${index}`"
          :x1="tick.x"
          :x2="tick.x"
          :y1="PADDING.top"
          :y2="HEIGHT - PADDING.bottom"
          class="scatter__grid scatter__grid--v"
        />
        <line
          v-if="zeroY !== null"
          :x1="PADDING.left"
          :x2="WIDTH - PADDING.right"
          :y1="zeroY"
          :y2="zeroY"
          class="scatter__zero"
        />

        <text
          v-for="(tick, index) in yTicks"
          :key="`yt-${index}`"
          :x="PADDING.left - 10"
          :y="tick.y + 3"
          class="scatter__axis-text"
          text-anchor="end"
        >
          {{ tick.text }}
        </text>
        <text
          v-for="(tick, index) in xTicks"
          :key="`xt-${index}`"
          :x="tick.x"
          :y="HEIGHT - PADDING.bottom + 18"
          class="scatter__axis-text"
          text-anchor="middle"
        >
          {{ tick.text }}
        </text>

        <text :x="WIDTH - PADDING.right" :y="HEIGHT - 8" class="scatter__axis-title" text-anchor="end">
          年化波动率（风险）→
        </text>
        <text
          :x="PADDING.left - 46"
          :y="PADDING.top + plotHeight / 2"
          class="scatter__axis-title"
          text-anchor="middle"
          :transform="`rotate(-90 ${PADDING.left - 46} ${PADDING.top + plotHeight / 2})`"
        >
          年化收益率 →
        </text>

        <g v-for="point in points" :key="point.item.name">
          <title>
            {{ point.item.name }}｜{{ point.item.category }}｜年化收益
            {{ formatPercent(point.item.annual_return) }}｜年化波动
            {{ formatPercent(point.item.annual_volatility) }}｜夏普
            {{ point.item.sharpe === null ? '—' : point.item.sharpe.toFixed(2) }}
          </title>
          <circle
            :cx="point.x"
            :cy="point.y"
            :r="point.r"
            :fill="point.color"
            :fill-opacity="point.selected || point.hovered ? 1 : 0.72"
            :stroke="point.selected ? '#303133' : point.color"
            :stroke-width="point.selected ? 2 : 1"
            class="scatter__dot"
            @mouseenter="hoveredName = point.item.name"
            @mouseleave="hoveredName = ''"
            @click="emit('select', point.item.name)"
          />
        </g>

        <g v-for="point in points" :key="`l-${point.item.name}`">
          <text
            v-if="point.selected || point.hovered"
            :x="point.labelX"
            :y="point.labelY"
            class="scatter__point-label"
          >
            {{ point.item.name }}
          </text>
        </g>

        <text
          v-if="!items.length"
          :x="WIDTH / 2"
          :y="HEIGHT / 2"
          class="scatter__empty"
          text-anchor="middle"
        >
          暂无可统计的标的
        </text>
      </svg>

      <div v-if="hoveredPoint" class="scatter__tooltip" :style="tooltipStyle">
        <div class="scatter__tooltip-title">
          <i class="legend-dot" :style="{ background: hoveredPoint.color }"></i>
          {{ hoveredPoint.item.name }}
          <span class="scatter__tooltip-category">{{ hoveredPoint.item.category }}</span>
        </div>
        <div class="scatter__tooltip-row">
          年化收益
          <b :class="hoveredPoint.item.annual_return >= 0 ? 'is-up' : 'is-down'">
            {{ formatPercent(hoveredPoint.item.annual_return) }}
          </b>
        </div>
        <div class="scatter__tooltip-row">
          年化波动<b>{{ formatPercent(hoveredPoint.item.annual_volatility) }}</b>
        </div>
        <div class="scatter__tooltip-row">
          夏普比率<b>{{ hoveredPoint.item.sharpe === null ? '—' : hoveredPoint.item.sharpe.toFixed(2) }}</b>
        </div>
        <div class="scatter__tooltip-row">
          最大回撤<b class="is-down">{{ formatPercent(hoveredPoint.item.max_drawdown) }}</b>
        </div>
        <div class="scatter__tooltip-hint">
          {{ hoveredPoint.item.start_date }} ~ {{ hoveredPoint.item.end_date }} ·
          {{ hoveredPoint.item.sample_count }} 个样本
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scatter {
  width: 100%;
  overflow-x: auto;
}

.scatter__legend {
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

.legend-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.legend-count {
  color: #c0c4cc;
}

.scatter__canvas {
  position: relative;
  width: 960px;
}

.scatter__svg {
  display: block;
}

.scatter__grid {
  stroke: #ebeef5;
  stroke-width: 1;
}

.scatter__grid--v {
  stroke: #f2f4f8;
}

.scatter__zero {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 4 3;
}

.scatter__axis-text {
  font-size: 10px;
  fill: #909399;
}

.scatter__axis-title {
  font-size: 11px;
  fill: #a8abb2;
}

.scatter__dot {
  cursor: pointer;
  transition: fill-opacity 0.12s ease;
}

.scatter__point-label {
  font-size: 11px;
  fill: #303133;
  paint-order: stroke;
  stroke: #ffffff;
  stroke-width: 3;
  stroke-linejoin: round;
  pointer-events: none;
}

.scatter__empty {
  font-size: 13px;
  fill: #909399;
}

.scatter__tooltip {
  position: absolute;
  z-index: 2;
  min-width: 170px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  color: #606266;
  pointer-events: none;
  transform: translate(-50%, -100%);
}

.scatter__tooltip-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 5px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.scatter__tooltip-category {
  font-size: 11px;
  font-weight: 400;
  color: #a8abb2;
}

.scatter__tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  line-height: 1.7;
}

.scatter__tooltip-row b {
  font-weight: 600;
  color: #303133;
}

.scatter__tooltip-hint {
  margin-top: 4px;
  font-size: 11px;
  color: #c0c4cc;
}

.is-up {
  color: #f56c6c !important;
}

.is-down {
  color: #67c23a !important;
}
</style>
