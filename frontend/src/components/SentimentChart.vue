<script setup lang="ts">
import { computed } from 'vue'
import type { SentimentPoint, SentimentSummaryPoint } from '@/types/news'

const props = defineProps<{
  points: SentimentPoint[]
  summaries: SentimentSummaryPoint[]
}>()

const WIDTH = 960
const HEIGHT = 340
const PADDING = { left: 62, right: 18, top: 18, bottom: 30 }
const plotWidth = WIDTH - PADDING.left - PADDING.right
const plotHeight = HEIGHT - PADDING.top - PADDING.bottom

const MA_PERIOD = 7

// 情绪强度固定映射到 [-1, 1]，0 为中线
function yFor(value: number): number {
  return PADDING.top + ((1 - Math.max(-1, Math.min(1, value))) / 2) * plotHeight
}

const bandWidth = computed(() =>
  props.points.length > 0 ? plotWidth / props.points.length : plotWidth,
)

const zeroY = computed(() => yFor(0))

const bars = computed(() =>
  props.points.map((point, index) => {
    const x = PADDING.left + index * bandWidth.value
    const scoreY = yFor(point.score)
    return {
      x: x + 0.5,
      width: Math.max(1, bandWidth.value - 1),
      y: Math.min(zeroY.value, scoreY),
      height: Math.abs(zeroY.value - scoreY),
      fill: point.score > 0 ? '#67C23A' : point.score < 0 ? '#F56C6C' : '#C0C4CC',
      opacity: point.score === 0 ? 0.25 : 0.8,
      title: `${point.date}｜利好 ${point.bullish} · 利空 ${point.bearish} · 中性 ${point.neutral}（共 ${point.total} 条）`,
    }
  }),
)

function movingAverage(): (number | null)[] {
  const list = props.points.map((point) => point.score)
  const result: (number | null)[] = new Array(list.length).fill(null)
  let sum = 0
  for (let index = 0; index < list.length; index += 1) {
    sum += list[index]
    if (index >= MA_PERIOD) {
      sum -= list[index - MA_PERIOD]
    }
    if (index >= MA_PERIOD - 1) {
      result[index] = sum / MA_PERIOD
    }
  }
  return result
}

const maPath = computed(() => {
  const series = movingAverage()
  const parts: string[] = []
  series.forEach((value, index) => {
    if (value === null) {
      return
    }
    const x = PADDING.left + index * bandWidth.value + bandWidth.value / 2
    parts.push(`${parts.length === 0 ? 'M' : 'L'}${x.toFixed(1)},${yFor(value).toFixed(1)}`)
  })
  return parts.join(' ')
})

// 机构摘要观点：就近吸附到时间桶，标记在柱值附近
const markers = computed(() => {
  const pts = props.points
  if (!pts.length) {
    return []
  }
  return props.summaries
    .map((summary, index) => {
      const target = summary.date ? new Date(summary.date).getTime() : Number.NaN
      if (Number.isNaN(target)) {
        return null
      }
      let best = 0
      let bestDiff = Number.POSITIVE_INFINITY
      for (let i = 0; i < pts.length; i += 1) {
        const diff = Math.abs(new Date(pts[i].date).getTime() - target)
        if (diff < bestDiff) {
          bestDiff = diff
          best = i
        }
      }
      const bucketScore = pts[best].score
      const cx = PADDING.left + best * bandWidth.value + bandWidth.value / 2 + ((index % 3) - 1) * 5
      const cy = yFor(bucketScore) + (bucketScore >= 0 ? -12 : 12)
      const sentiment = summary.sentiment ?? 'neutral'
      const color = sentiment === 'bullish' ? '#67C23A' : sentiment === 'bearish' ? '#F56C6C' : '#909399'
      const label =
        sentiment === 'bullish' ? '利好' : sentiment === 'bearish' ? '利空' : '中性'
      const title = `${summary.date ?? ''} ${summary.institution ?? ''}｜机构观点：${label}｜${summary.title}`
      return { cx, cy, sentiment, color, title, hasShape: true }
    })
    .filter((marker): marker is NonNullable<typeof marker> => marker !== null)
})

function markerPoints(cx: number, cy: number, sentiment: string): string {
  if (sentiment === 'bullish') {
    return `${cx},${cy - 5} ${cx - 5},${cy + 4} ${cx + 5},${cy + 4}`
  }
  if (sentiment === 'bearish') {
    return `${cx},${cy + 5} ${cx - 5},${cy - 4} ${cx + 5},${cy - 4}`
  }
  return ''
}

const xLabels = computed(() => {
  const count = props.points.length
  if (!count) {
    return []
  }
  const slots = Math.min(7, count)
  const result: { x: number; text: string }[] = []
  for (let i = 0; i < slots; i += 1) {
    const index = Math.round((i * (count - 1)) / (slots - 1 || 1))
    const x = PADDING.left + index * bandWidth.value + bandWidth.value / 2
    result.push({ x, text: props.points[index].date })
  }
  return result
})

const yLabels = [-1, -0.5, 0, 0.5, 1]
</script>

<template>
  <div class="sentiment-chart" data-testid="sentiment-chart">
    <div class="sentiment-chart__legend">
      <span class="legend-item"><i class="legend-swatch legend-swatch--bar"></i>新闻情绪强度</span>
      <span class="legend-item"><i class="legend-swatch legend-swatch--ma"></i>7 期均值</span>
      <span class="legend-item">
        <svg width="14" height="14" viewBox="0 0 14 14">
          <polygon points="7,2 2,11 12,11" fill="#67C23A" />
        </svg>
        机构观点（利涨/利跌/中性）
      </span>
    </div>
    <svg :width="WIDTH" :height="HEIGHT" class="sentiment-chart__svg" role="img" aria-label="主题情绪指数走势">
      <g v-for="(label, index) in yLabels" :key="`y-${index}`">
        <line
          v-if="label !== 0"
          :x1="PADDING.left"
          :x2="WIDTH - PADDING.right"
          :y1="yFor(label)"
          :y2="yFor(label)"
          class="sentiment-chart__grid"
        />
        <text :x="PADDING.left - 8" :y="yFor(label) + 3" class="sentiment-chart__axis-text" text-anchor="end">
          {{ label }}
        </text>
      </g>
      <line
        :x1="PADDING.left"
        :x2="WIDTH - PADDING.right"
        :y1="zeroY"
        :y2="zeroY"
        class="sentiment-chart__zero"
      />
      <g v-for="(bar, index) in bars" :key="`b-${index}`">
        <title>{{ bar.title }}</title>
        <rect :x="bar.x" :y="bar.y" :width="bar.width" :height="bar.height" :fill="bar.fill" :fill-opacity="bar.opacity" />
      </g>
      <path v-if="maPath" :d="maPath" class="sentiment-chart__ma" />
      <g v-for="(marker, index) in markers" :key="`m-${index}`">
        <title>{{ marker.title }}</title>
        <polygon
          v-if="marker.sentiment !== 'neutral'"
          :points="markerPoints(marker.cx, marker.cy, marker.sentiment)"
          :fill="marker.color"
          fill-opacity="0.95"
        />
        <circle v-else :cx="marker.cx" :cy="marker.cy" r="4" :fill="marker.color" fill-opacity="0.9" />
      </g>
      <g v-for="(label, index) in xLabels" :key="`x-${index}`">
        <text :x="label.x" :y="HEIGHT - 10" class="sentiment-chart__axis-text" text-anchor="middle">
          {{ label.text }}
        </text>
      </g>
      <text v-if="!points.length" :x="WIDTH / 2" :y="HEIGHT / 2" class="sentiment-chart__empty" text-anchor="middle">
        暂无该主题的情绪数据
      </text>
    </svg>
  </div>
</template>

<style scoped>
.sentiment-chart {
  width: 100%;
  overflow-x: auto;
}

.sentiment-chart__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 8px;
  font-size: 12px;
  color: #606266;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.legend-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.legend-swatch--bar {
  background: linear-gradient(180deg, #67c23a 50%, #f56c6c 50%);
  opacity: 0.8;
}

.legend-swatch--ma {
  background: #409eff;
  height: 2px;
  border-radius: 1px;
}

.sentiment-chart__svg {
  display: block;
}

.sentiment-chart__grid {
  stroke: #ebeef5;
  stroke-width: 1;
}

.sentiment-chart__zero {
  stroke: #909399;
  stroke-width: 1;
  stroke-dasharray: 4 3;
}

.sentiment-chart__ma {
  fill: none;
  stroke: #409eff;
  stroke-width: 2;
}

.sentiment-chart__axis-text {
  font-size: 10px;
  fill: #909399;
}

.sentiment-chart__empty {
  font-size: 13px;
  fill: #909399;
}
</style>
