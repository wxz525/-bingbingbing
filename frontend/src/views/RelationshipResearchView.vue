<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import RatioSpreadPanel from '@/components/RatioSpreadPanel.vue'

type RangeKey = '1m' | '3m' | '1y' | '3y' | 'all'

const RANGE_OPTIONS: { label: string; value: RangeKey; days: number | null }[] = [
  { label: '近1月', value: '1m', days: 31 },
  { label: '近3月', value: '3m', days: 92 },
  { label: '近1年', value: '1y', days: 366 },
  { label: '近3年', value: '3y', days: 1096 },
  { label: '全部', value: 'all', days: null },
]

const props = withDefaults(
  defineProps<{
    /** 从行情看板跳转时带入的指标 key */
    initialKey?: string | null
  }>(),
  { initialKey: null },
)

const activeKey = ref(props.initialKey ?? 'gold_silver')
const range = ref<RangeKey>('1y')

const days = computed(() => RANGE_OPTIONS.find((item) => item.value === range.value)?.days ?? null)
const rangeLabel = computed(
  () => RANGE_OPTIONS.find((item) => item.value === range.value)?.label ?? '',
)

watch(
  () => props.initialKey,
  (key) => {
    if (key) {
      activeKey.value = key
    }
  },
)
</script>

<template>
  <div class="research-view">
    <header class="research-view__head">
      <div class="research-view__titles">
        <div class="research-view__title-row">
          <h2 class="research-view__title">比值与利差</h2>
          <span class="research-view__english">Ratios &amp; Spreads</span>
        </div>
        <p class="research-view__subtitle">研究不同资产的相对强弱、利率差异与历史变化。</p>
      </div>

      <div class="research-view__range" role="group" aria-label="时间区间">
        <button
          v-for="option in RANGE_OPTIONS"
          :key="option.value"
          type="button"
          class="range-button"
          :class="{ 'range-button--active': range === option.value }"
          @click="range = option.value"
        >
          {{ option.label }}
        </button>
      </div>
    </header>

    <p class="research-view__plan">
      关联研究栏目规划：相关性分析 · 多资产对比 · 比值与利差 · 市场情境研究。当前版本完整实现「比值与利差」，其余栏目待后续版本提供。
    </p>

    <RatioSpreadPanel v-model:active-key="activeKey" :days="days" :range-label="rangeLabel" />
  </div>
</template>

<style scoped>
.research-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.research-view__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.research-view__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}

.research-view__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.research-view__english {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #909399;
}

.research-view__subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #909399;
}

.research-view__range {
  display: inline-flex;
}

.range-button {
  padding: 5px 12px;
  border: 1px solid #dcdfe6;
  background: #ffffff;
  color: #606266;
  font-size: 12px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.range-button + .range-button {
  margin-left: -1px;
}

.range-button:first-child {
  border-radius: 4px 0 0 4px;
}

.range-button:last-child {
  border-radius: 0 4px 4px 0;
}

.range-button:hover {
  color: #409eff;
}

.range-button--active {
  position: relative;
  z-index: 1;
  border-color: #409eff;
  background: #ecf5ff;
  color: #409eff;
}

.research-view__plan {
  margin: 0;
  padding: 0 4px;
  font-size: 11px;
  line-height: 1.6;
  color: #909399;
}

@media (max-width: 720px) {
  .research-view__head {
    padding: 14px;
  }
}

</style>
