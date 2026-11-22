<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  ApiRequestError,
  CONFLICT_MESSAGE,
  getFundArchive,
  listFundArchives,
  saveRedemptionRule,
} from '@/api/fundArchive'
import BasicInfoPanel from '@/components/BasicInfoPanel.vue'
import FundSearchBar from '@/components/FundSearchBar.vue'
import RedemptionRuleFormDialog from '@/components/RedemptionRuleFormDialog.vue'
import RedemptionRulePanel from '@/components/RedemptionRulePanel.vue'
import type {
  DetailErrorState,
  FundArchiveDetail,
  FundBasicInfo,
  RedemptionRule,
  RedemptionRulePayload,
  SaveErrorState,
} from '@/types/fundArchive'
import { isAbortError } from '@/utils/format'

const PAGE_SIZE = 20

const keyword = ref('')
const funds = ref<FundBasicInfo[]>([])
const listLoading = ref(false)
const listError = ref('')
const pagination = ref({ page: 1, pageSize: PAGE_SIZE, total: 0 })

const selectedFundCode = ref('')
const detail = ref<FundArchiveDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref<DetailErrorState | null>(null)

const dialogVisible = ref(false)
const editingRule = ref<RedemptionRule | null>(null)
const saving = ref(false)
const saveError = ref<SaveErrorState | null>(null)

let detailController: AbortController | null = null
let detailRequestId = 0

const hasDetailError = computed(() => detailError.value !== null)
const canRetryDetail = computed(
  () => detailError.value !== null && detailError.value.status !== 404,
)

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    return error.message
  }
  return fallback
}

async function loadFunds(): Promise<void> {
  listLoading.value = true
  listError.value = ''
  try {
    const response = await listFundArchives({
      keyword: keyword.value.trim() || undefined,
      page: pagination.value.page,
      pageSize: pagination.value.pageSize,
    })
    funds.value = response.items
    pagination.value.total = response.total
  } catch (error) {
    if (isAbortError(error)) {
      return
    }
    funds.value = []
    pagination.value.total = 0
    listError.value = toErrorMessage(error, '基金列表加载失败，请稍后重试')
  } finally {
    listLoading.value = false
  }
}

async function loadDetail(fundCode: string): Promise<void> {
  if (!fundCode) {
    return
  }

  // 主动取消上一个未完成的详情请求，旧响应永远不会覆盖当前基金数据。
  detailController?.abort()
  const controller = new AbortController()
  detailController = controller
  const requestId = ++detailRequestId

  detail.value = null
  detailError.value = null
  detailLoading.value = true

  try {
    const response = await getFundArchive(fundCode, controller.signal)
    if (requestId !== detailRequestId) {
      return
    }
    detail.value = response
  } catch (error) {
    if (isAbortError(error) || requestId !== detailRequestId) {
      return
    }
    detail.value = null
    detailError.value = {
      status: error instanceof ApiRequestError ? error.status : 0,
      message: toErrorMessage(error, '基金详情加载失败，请稍后重试'),
    }
  } finally {
    if (requestId === detailRequestId) {
      detailLoading.value = false
    }
  }
}

function handleKeywordUpdate(value: string): void {
  keyword.value = value
}

function handleSearch(): void {
  pagination.value.page = 1
  void loadFunds()
}

function handlePageChange(page: number): void {
  pagination.value.page = page
  void loadFunds()
}

function handleSelect(fundCode: string): void {
  dialogVisible.value = false
  saveError.value = null
  selectedFundCode.value = fundCode
  void loadDetail(fundCode)
}

function retryDetail(): void {
  if (selectedFundCode.value) {
    void loadDetail(selectedFundCode.value)
  }
}

function openEditDialog(): void {
  saveError.value = null
  editingRule.value = detail.value?.redemption_rule ?? null
  dialogVisible.value = true
}

async function handleSave(payload: RedemptionRulePayload): Promise<void> {
  if (saving.value || !selectedFundCode.value) {
    return
  }
  saving.value = true
  saveError.value = null
  try {
    const response = await saveRedemptionRule(selectedFundCode.value, payload)
    detail.value = response
    detailError.value = null
    dialogVisible.value = false
    ElMessage.success('申赎要素已保存')
  } catch (error) {
    // 失败时弹窗保持打开，表单内容原样保留，等待用户修正或刷新。
    if (error instanceof ApiRequestError) {
      saveError.value = {
        status: error.status,
        code: error.code,
        message: error.isConflict ? CONFLICT_MESSAGE : error.message,
        fieldErrors: error.fieldErrors,
      }
    } else {
      saveError.value = {
        status: 0,
        code: 'NETWORK_ERROR',
        message: '保存失败，请检查网络后重试',
        fieldErrors: {},
      }
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadFunds()
})

onBeforeUnmount(() => {
  detailController?.abort()
})
</script>

<template>
  <div class="fund-archive" data-testid="fund-archive-view">
    <FundSearchBar
      :keyword="keyword"
      :funds="funds"
      :selected-fund-code="selectedFundCode"
      :loading="listLoading"
      :page="pagination.page"
      :page-size="pagination.pageSize"
      :total="pagination.total"
      @update:keyword="handleKeywordUpdate"
      @search="handleSearch"
      @select="handleSelect"
      @page-change="handlePageChange"
    />

    <el-alert
      v-if="listError"
      class="fund-archive__alert"
      type="error"
      show-icon
      :closable="false"
      :title="listError"
      data-testid="list-error-alert"
    />

    <el-empty
      v-if="!selectedFundCode"
      class="fund-archive__empty"
      description="请先检索并选择基金"
    />

    <template v-else>
      <div v-if="hasDetailError" class="fund-archive__detail-error">
        <el-alert
          :title="detailError?.message"
          :type="detailError?.status === 404 ? 'warning' : 'error'"
          show-icon
          :closable="false"
          data-testid="detail-error-alert"
        />
        <el-button
          v-if="canRetryDetail"
          type="primary"
          plain
          size="small"
          data-testid="retry-button"
          @click="retryDetail"
        >
          重试
        </el-button>
      </div>

      <BasicInfoPanel :basic-info="detail?.basic_info ?? null" />

      <RedemptionRulePanel
        :rule="detail?.redemption_rule ?? null"
        :can-edit="Boolean(selectedFundCode) && !detailError"
        :loading="detailLoading"
        @edit="openEditDialog"
      />
    </template>

    <RedemptionRuleFormDialog
      v-model="dialogVisible"
      :fund-code="selectedFundCode"
      :rule="editingRule"
      :submitting="saving"
      :error="saveError"
      @submit="handleSave"
    />
  </div>
</template>

<style scoped>
.fund-archive {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fund-archive__alert {
  margin: 0;
}

.fund-archive__empty {
  padding: 48px 0;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}

.fund-archive__detail-error {
  display: flex;
  gap: 12px;
  align-items: center;
}

.fund-archive__detail-error :deep(.el-alert) {
  flex: 1;
}
</style>
