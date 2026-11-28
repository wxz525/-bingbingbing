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
  --syn-page: #080d24;
  --syn-surface: #142139;
  --syn-surface-2: #192b43;
  --syn-brand: #169ed4;
  --syn-highlight: #47c3e8;
  --syn-accent: #8978e2;
  --syn-text: #f0f5ff;
  --syn-text-2: #94aec6;
  --syn-line: #30435d;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px 22px 28px;
  border-radius: 8px;
  background: var(--syn-page);
  color: var(--syn-text);
}

.research-view__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(48, 67, 93, 0.7);
}

.research-view__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}

.research-view__title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--syn-text);
}

.research-view__english {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--syn-text-2);
}

.research-view__subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--syn-text-2);
}

.research-view__range {
  display: inline-flex;
  padding: 2px;
  border: 1px solid var(--syn-line);
  border-radius: 5px;
  background: #0c1330;
}

.range-button {
  padding: 5px 12px;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: var(--syn-text-2);
  font-size: 12px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.range-button:hover {
  color: var(--syn-text);
}

.range-button--active {
  background: rgba(22, 158, 212, 0.22);
  color: var(--syn-highlight);
}

.research-view__plan {
  margin: 0;
  font-size: 11px;
  line-height: 1.6;
  color: rgba(148, 174, 198, 0.7);
}

@media (max-width: 720px) {
  .research-view {
    padding: 16px 14px 22px;
  }
}
</style>
