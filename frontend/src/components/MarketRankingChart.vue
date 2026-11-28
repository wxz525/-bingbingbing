<script setup lang="ts">
import { computed, ref } from 'vue'

import type { MarketRankingItem } from '@/types/market'

const props = defineProps<{
  items: MarketRankingItem[]
  selectedName?: string
}>()

const emit = defineEmits<{ select: [name: string] }>()

const WIDTH = 960
const ROW_HEIGHT = 30
const TOP = 8
const NAME_WIDTH = 156
const VALUE_WIDTH = 72
const plotWidth = WIDTH - NAME_WIDTH - VALUE_WIDTH

const hoveredName = ref('')

const height = computed(() => TOP * 2 + props.items.length * ROW_HEIGHT)

const domain = computed(() => {
  let min = 0
  let max = 0
  for (const item of props.items) {
    min = Math.min(min, item.return_rate)
    max = Math.max(max, item.return_rate)
  }
  const pad = (max - min) * 0.04 || 0.01
  return { min: min - pad, max: max + pad }
})

function xFor(value: number): number {
  const { min, max } = domain.value
  return NAME_WIDTH + ((value - min) / (max - min)) * plotWidth
}

const zeroX = computed(() => xFor(0))

const rows = computed(() =>
  props.items.map((item, index) => {
    const y = TOP + index * ROW_HEIGHT
    const endX = xFor(item.return_rate)
    const positive = item.return_rate >= 0
    return {
      item,
      index,
      y,
      barX: Math.min(zeroX.value, endX),
      barWidth: Math.max(1, Math.abs(endX - zeroX.value)),
      color: positive ? '#f56c6c' : '#67c23a',
      labelX: positive ? endX + 6 : endX - 6,
      labelAnchor: positive ? 'start' : 'end',
      nameX: 12,
      nameY: y + 13,
      categoryY: y + 25,
      text: `${positive ? '+' : ''}${(item.return_rate * 100).toFixed(2)}%`,
      selected: item.name === props.selectedName,
      hovered: item.name === hoveredName.value,
    }
  }),
)

function shortName(name: string): string {
  return name.length > 11 ? `${name.slice(0, 11)}…` : name
}
</script>

<template>
  <div class="ranking" data-testid="market-ranking-chart">
    <div v-if="!items.length" class="ranking__empty">当前区间没有可排行的标的</div>
    <div v-else class="ranking__canvas">
      <svg :width="WIDTH" :height="height" class="ranking__svg" role="img" aria-label="区间涨跌排行">
        <g v-for="row in rows" :key="row.item.name">
          <title>
            {{ row.item.name }}｜{{ row.item.category }}｜区间 {{ row.text }}｜{{ row.item.start_date }} ~
            {{ row.item.end_date }}
          </title>
          <rect
            :x="0"
            :y="row.y"
            :width="WIDTH"
            height="28"
            :class="[
              'ranking__row',
              row.selected ? 'ranking__row--selected' : '',
              row.hovered ? 'ranking__row--hover' : '',
            ]"
            @mouseenter="hoveredName = row.item.name"
            @mouseleave="hoveredName = ''"
            @click="emit('select', row.item.name)"
          />
          <text :x="row.nameX" :y="row.nameY" class="ranking__name" :class="{ 'ranking__name--active': row.selected }">
            {{ shortName(row.item.name) }}
          </text>
          <text :x="row.nameX" :y="row.categoryY" class="ranking__category">{{ row.item.category }}</text>
          <rect :x="row.barX" :y="row.y + 7" :width="row.barWidth" height="14" :fill="row.color" fill-opacity="0.85" />
          <text
            :x="row.labelX"
            :y="row.y + 18"
            :text-anchor="row.labelAnchor"
            class="ranking__value"
            :fill="row.color"
          >
            {{ row.text }}
          </text>
        </g>

        <line :x1="zeroX" :x2="zeroX" :y1="TOP" :y2="height - TOP" class="ranking__zero" />
      </svg>
    </div>
  </div>
</template>

<style scoped>
.ranking {
  width: 100%;
  overflow-x: auto;
}

.ranking__canvas {
  width: 960px;
}

.ranking__svg {
  display: block;
}

.ranking__row {
  fill: transparent;
  cursor: pointer;
}

.ranking__row--hover {
  fill: #f7f9fc;
}

.ranking__row--selected {
  fill: #ecf5ff;
}

.ranking__name {
  font-size: 12px;
  fill: #303133;
  pointer-events: none;
}

.ranking__name--active {
  font-weight: 600;
  fill: #409eff;
}

.ranking__category {
  font-size: 10px;
  fill: #c0c4cc;
  pointer-events: none;
}

.ranking__value {
  font-size: 11px;
  font-weight: 600;
  pointer-events: none;
}

.ranking__zero {
  stroke: #c0c4cc;
  stroke-width: 1;
  stroke-dasharray: 4 3;
  pointer-events: none;
}

.ranking__empty {
  padding: 24px 0;
  font-size: 13px;
  color: #909399;
  text-align: center;
}
</style>
