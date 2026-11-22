<script setup lang="ts">
import { computed } from 'vue'

import { REDEMPTION_DISPLAY_FIELDS } from '@/constants/redemption'
import type { RedemptionRule } from '@/types/fundArchive'
import { displayStatus, displayText } from '@/utils/format'

const props = defineProps<{
  rule: RedemptionRule | null
  canEdit: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  (event: 'edit'): void
}>()

const sourceTagType = computed(() => (props.rule?.source_type === 'MANUAL' ? 'success' : 'info'))
const editLabel = computed(() => (props.rule ? '编辑申赎要素' : '新增申赎要素'))

const displayItems = computed(() =>
  REDEMPTION_DISPLAY_FIELDS.map((field) => ({
    ...field,
    value:
      field.kind === 'status'
        ? displayStatus(props.rule?.[field.key])
        : displayText(props.rule?.[field.key]),
  })),
)
</script>

<template>
  <section class="panel" data-testid="redemption-rule-panel">
    <header class="panel__header">
      <h2 class="panel__title">申赎要素</h2>
      <el-button
        type="primary"
        plain
        size="small"
        :disabled="!props.canEdit || props.loading"
        data-testid="edit-rule-button"
        @click="emit('edit')"
      >
        {{ editLabel }}
      </el-button>
    </header>

    <div class="rule-meta">
      <div class="rule-meta__item">
        <span class="rule-meta__label">数据来源</span>
        <el-tag :type="sourceTagType" size="small" data-testid="rule-source">
          {{ displayText(props.rule?.source_type) }}
        </el-tag>
      </div>
      <div class="rule-meta__item">
        <span class="rule-meta__label">版本号</span>
        <span class="rule-meta__value" data-testid="rule-version">
          {{ displayText(props.rule?.version_no) }}
        </span>
      </div>
      <div class="rule-meta__item">
        <span class="rule-meta__label">生效日期</span>
        <span class="rule-meta__value" data-testid="rule-effective-date">
          {{ displayText(props.rule?.effective_date) }}
        </span>
      </div>
    </div>

    <div class="rule-grid">
      <div v-for="item in displayItems" :key="item.key" class="rule-grid__cell">
        <span class="rule-grid__label">{{ item.label }}</span>
        <span class="rule-grid__value" :data-testid="`rule-${item.key}`">{{ item.value }}</span>
      </div>
      <div class="rule-grid__cell rule-grid__cell--wide">
        <span class="rule-grid__label">备注</span>
        <span class="rule-grid__value" data-testid="rule-remark">
          {{ displayText(props.rule?.remark) }}
        </span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.rule-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 28px;
  padding: 12px 16px;
  margin-bottom: 16px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.rule-meta__item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rule-meta__label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.rule-meta__value {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.rule-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  overflow: hidden;
  background: var(--el-border-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}

.rule-grid__cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  background: var(--el-bg-color);
}

.rule-grid__cell--wide {
  grid-column: 1 / -1;
}

.rule-grid__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.rule-grid__value {
  font-size: 14px;
  color: var(--el-text-color-primary);
  word-break: break-all;
}

@media (max-width: 900px) {
  .rule-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
