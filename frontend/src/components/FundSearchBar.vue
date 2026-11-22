<script setup lang="ts">
import type { FundBasicInfo } from '@/types/fundArchive'
import { displayText } from '@/utils/format'

const props = defineProps<{
  keyword: string
  funds: FundBasicInfo[]
  selectedFundCode: string
  loading: boolean
  page: number
  pageSize: number
  total: number
}>()

const emit = defineEmits<{
  (event: 'update:keyword', value: string): void
  (event: 'search'): void
  (event: 'select', fundCode: string): void
  (event: 'page-change', page: number): void
}>()

function optionLabel(fund: FundBasicInfo): string {
  return `${displayText(fund.fund_code)} ${displayText(fund.fund_name)}`
}

function handleKeywordUpdate(value: string): void {
  emit('update:keyword', value)
}

function handleSelect(value: string): void {
  if (value) {
    emit('select', value)
  }
}

function handlePageUpdate(page: number): void {
  emit('page-change', page)
}
</script>

<template>
  <section class="panel search-panel" data-testid="fund-search-panel">
    <div class="search-panel__row">
      <el-input
        class="search-panel__keyword"
        :model-value="props.keyword"
        placeholder="输入基金代码或名称"
        clearable
        data-testid="keyword-input"
        @update:model-value="handleKeywordUpdate"
        @keyup.enter="emit('search')"
      />
      <el-button type="primary" :loading="props.loading" data-testid="search-button" @click="emit('search')">
        检索
      </el-button>
      <el-select
        class="search-panel__select"
        :model-value="props.selectedFundCode"
        filterable
        placeholder="请选择基金"
        data-testid="fund-select"
        @update:model-value="handleSelect"
      >
        <el-option
          v-for="fund in props.funds"
          :key="fund.fund_code"
          :label="optionLabel(fund)"
          :value="fund.fund_code"
        />
      </el-select>
    </div>
    <div v-if="props.total > props.pageSize" class="search-panel__pager">
      <el-pagination
        small
        layout="total, prev, pager, next"
        :total="props.total"
        :page-size="props.pageSize"
        :current-page="props.page"
        @current-change="handlePageUpdate"
      />
    </div>
  </section>
</template>

<style scoped>
.search-panel__row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.search-panel__keyword {
  width: 280px;
}

.search-panel__select {
  width: 320px;
}

.search-panel__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
