<script setup lang="ts">
import { computed } from 'vue'

import type { FundBasicInfo } from '@/types/fundArchive'
import { displayText } from '@/utils/format'

const props = defineProps<{
  basicInfo: FundBasicInfo | null
}>()

const fields = computed(() => [
  { key: 'fund_code', label: '基金代码', value: displayText(props.basicInfo?.fund_code) },
  { key: 'fund_name', label: '基金名称', value: displayText(props.basicInfo?.fund_name) },
  { key: 'fund_type', label: '基金类型', value: displayText(props.basicInfo?.fund_type) },
  { key: 'manager_name', label: '基金管理人', value: displayText(props.basicInfo?.manager_name) },
  { key: 'custodian_name', label: '基金托管人', value: displayText(props.basicInfo?.custodian_name) },
  {
    key: 'establish_date',
    label: '成立日期',
    value: displayText(props.basicInfo?.establish_date),
  },
  { key: 'currency', label: '币种', value: displayText(props.basicInfo?.currency) },
  { key: 'fund_status', label: '基金状态', value: displayText(props.basicInfo?.fund_status) },
])
</script>

<template>
  <section class="panel" data-testid="basic-info-panel">
    <header class="panel__header">
      <h2 class="panel__title">基础信息</h2>
      <el-tag size="small" type="info" effect="plain">只读</el-tag>
    </header>
    <el-descriptions :column="3" border>
      <el-descriptions-item v-for="field in fields" :key="field.key" :label="field.label">
        <span :data-testid="`basic-${field.key}`">{{ field.value }}</span>
      </el-descriptions-item>
    </el-descriptions>
  </section>
</template>
