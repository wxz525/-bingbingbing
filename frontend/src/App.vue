<script setup lang="ts">
import { ref } from 'vue'

import MarketDashboardView from '@/views/MarketDashboardView.vue'
import NewsCenterView from '@/views/NewsCenterView.vue'
import RelationshipResearchView from '@/views/RelationshipResearchView.vue'

const activeTab = ref('market')
const researchKey = ref<string | null>(null)

function openResearch(key: string): void {
  researchKey.value = key
  activeTab.value = 'research'
}
</script>

<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <h1 class="app-shell__title">SYNAPSE 市场联觉</h1>
      <span class="app-shell__subtitle">行情看板 · 关联研究 · 资讯中心</span>
    </header>

    <el-tabs v-model="activeTab" class="app-shell__tabs">
      <el-tab-pane label="行情看板" name="market">
        <MarketDashboardView @open-research="openResearch" />
      </el-tab-pane>
      <el-tab-pane label="关联研究" name="research">
        <RelationshipResearchView :initial-key="researchKey" />
      </el-tab-pane>
      <el-tab-pane label="资讯中心" name="news-center">
        <NewsCenterView />
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
