<script setup lang="ts">
import { ref } from 'vue'

import FundArchiveView from '@/views/FundArchiveView.vue'

const activeTab = ref('fund-archive')
</script>

<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <h1 class="app-shell__title">基金数据平台</h1>
      <span class="app-shell__subtitle">基金档案 · 基础信息与申赎要素</span>
    </header>

    <el-tabs v-model="activeTab" class="app-shell__tabs">
      <el-tab-pane label="基金档案" name="fund-archive">
        <FundArchiveView />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  padding: 24px 32px 48px;
  background: #f5f7fa;
}

.app-shell__header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}

.app-shell__title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.app-shell__subtitle {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.app-shell__tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}
</style>
