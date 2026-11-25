<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  getNews,
  getNewsMeta,
  getSummary,
  listNews,
  listSummaries,
} from '@/api/news'
import type {
  NewsDetail,
  NewsListItem,
  NewsMeta,
  SummaryDetail,
  SummaryListItem,
} from '@/types/news'
import { ApiRequestError } from '@/api/http'
import { isAbortError } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'

const NEWS_PAGE_SIZE = 20
const SUMMARY_PAGE_SIZE = 20
const POLL_INTERVAL = 5000

const activeSection = ref<'news' | 'summaries'>('news')

const newsMeta = ref<NewsMeta | null>(null)
const newsKeyword = ref('')
const newsRange = ref<[string, string] | null>(null)
const newsItems = ref<NewsListItem[]>([])
const newsTotal = ref(0)
const newsPage = ref(1)
const newsLoading = ref(false)
const newsError = ref('')
const selectedNewsId = ref('')
const newsDetail = ref<NewsDetail | null>(null)
const newsDetailLoading = ref(false)
const newsDetailError = ref('')

const summaryKeyword = ref('')
const summaryItems = ref<SummaryListItem[]>([])
const summaryTotal = ref(0)
const summaryPage = ref(1)
const summaryLoading = ref(false)
const summaryError = ref('')
const selectedSummaryName = ref('')
const summaryDetail = ref<SummaryDetail | null>(null)
const summaryDetailLoading = ref(false)
const summaryDetailError = ref('')

let newsController: AbortController | null = null
let summaryController: AbortController | null = null
let newsListRequestId = 0
let newsDetailRequestId = 0
let summaryListRequestId = 0
let summaryDetailRequestId = 0
let pollTimer: number | null = null

const isIndexing = computed(() => newsMeta.value?.status === 'building')
const indexMissing = computed(() => newsMeta.value?.status === 'missing')
const indexFailed = computed(() => newsMeta.value?.status === 'error')
const metaSummary = computed(() => {
  const meta = newsMeta.value
  if (!meta || !meta.total) {
    return ''
  }
  const range =
    meta.min_date && meta.max_date ? `${meta.min_date} ~ ${meta.max_date}` : '日期未知'
  return `共 ${meta.total.toLocaleString('zh-CN')} 条 · ${range} · ${meta.source_count} 个来源`
})
const summaryHtml = computed(() =>
  summaryDetail.value ? renderMarkdown(summaryDetail.value.content) : '',
)

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    return error.message
  }
  return fallback
}

function stopPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling(): void {
  if (pollTimer !== null) {
    return
  }
  pollTimer = window.setInterval(() => {
    void refreshWhileIndexing()
  }, POLL_INTERVAL)
}

async function refreshWhileIndexing(): Promise<void> {
  await loadNewsMeta()
  if (!isIndexing.value) {
    stopPolling()
  }
  await loadNews()
}

async function loadNewsMeta(): Promise<void> {
  try {
    const meta = await getNewsMeta()
    newsMeta.value = meta
    if (meta.status === 'building') {
      startPolling()
    } else {
      stopPolling()
    }
  } catch {
    // 元信息失败不阻塞列表展示，列表请求会给出具体错误。
  }
}

async function loadNews(): Promise<void> {
  newsLoading.value = true
  newsError.value = ''
  const requestId = ++newsListRequestId
  try {
    const response = await listNews({
      keyword: newsKeyword.value.trim() || undefined,
      start: newsRange.value?.[0],
      end: newsRange.value?.[1],
      page: newsPage.value,
      pageSize: NEWS_PAGE_SIZE,
    })
    if (requestId !== newsListRequestId) {
      return
    }
    newsItems.value = response.items
    newsTotal.value = response.total
  } catch (error) {
    if (isAbortError(error) || requestId !== newsListRequestId) {
      return
    }
    newsItems.value = []
    newsTotal.value = 0
    newsError.value = toErrorMessage(error, '新闻列表加载失败，请稍后重试')
  } finally {
    if (requestId === newsListRequestId) {
      newsLoading.value = false
    }
  }
}

function searchNews(): void {
  newsPage.value = 1
  newsController?.abort()
  selectedNewsId.value = ''
  newsDetail.value = null
  newsDetailError.value = ''
  void loadNews()
}

function resetNews(): void {
  newsKeyword.value = ''
  newsRange.value = null
  searchNews()
}

function changeNewsPage(page: number): void {
  newsPage.value = page
  void loadNews()
}

async function selectNews(item: NewsListItem): Promise<void> {
  selectedNewsId.value = item.id
  newsController?.abort()
  const controller = new AbortController()
  newsController = controller
  const requestId = ++newsDetailRequestId
  newsDetail.value = null
  newsDetailError.value = ''
  newsDetailLoading.value = true
  try {
    const response = await getNews(item.id, controller.signal)
    if (requestId !== newsDetailRequestId) {
      return
    }
    newsDetail.value = response
  } catch (error) {
    if (isAbortError(error) || requestId !== newsDetailRequestId) {
      return
    }
    newsDetailError.value = toErrorMessage(error, '新闻正文加载失败，请稍后重试')
  } finally {
    if (requestId === newsDetailRequestId) {
      newsDetailLoading.value = false
    }
  }
}

async function loadSummaries(): Promise<void> {
  summaryLoading.value = true
  summaryError.value = ''
  const requestId = ++summaryListRequestId
  try {
    const response = await listSummaries({
      keyword: summaryKeyword.value.trim() || undefined,
      page: summaryPage.value,
      pageSize: SUMMARY_PAGE_SIZE,
    })
    if (requestId !== summaryListRequestId) {
      return
    }
    summaryItems.value = response.items
    summaryTotal.value = response.total
  } catch (error) {
    if (isAbortError(error) || requestId !== summaryListRequestId) {
      return
    }
    summaryItems.value = []
    summaryTotal.value = 0
    summaryError.value = toErrorMessage(error, '资金流摘要加载失败，请稍后重试')
  } finally {
    if (requestId === summaryListRequestId) {
      summaryLoading.value = false
    }
  }
}

function searchSummaries(): void {
  summaryPage.value = 1
  summaryController?.abort()
  selectedSummaryName.value = ''
  summaryDetail.value = null
  summaryDetailError.value = ''
  void loadSummaries()
}

function resetSummaries(): void {
  summaryKeyword.value = ''
  searchSummaries()
}

function changeSummaryPage(page: number): void {
  summaryPage.value = page
  void loadSummaries()
}

async function selectSummary(item: SummaryListItem): Promise<void> {
  selectedSummaryName.value = item.name
  summaryController?.abort()
  const controller = new AbortController()
  summaryController = controller
  const requestId = ++summaryDetailRequestId
  summaryDetail.value = null
  summaryDetailError.value = ''
  summaryDetailLoading.value = true
  try {
    const response = await getSummary(item.name, controller.signal)
    if (requestId !== summaryDetailRequestId) {
      return
    }
    summaryDetail.value = response
  } catch (error) {
    if (isAbortError(error) || requestId !== summaryDetailRequestId) {
      return
    }
    summaryDetailError.value = toErrorMessage(error, '摘要内容加载失败，请稍后重试')
  } finally {
    if (requestId === summaryDetailRequestId) {
      summaryDetailLoading.value = false
    }
  }
}

onMounted(() => {
  void loadNewsMeta()
  void loadNews()
  void loadSummaries()
})

onBeforeUnmount(() => {
  stopPolling()
  newsController?.abort()
  summaryController?.abort()
})
</script>

<template>
  <div class="news-center" data-testid="news-center-view">
    <el-tabs v-model="activeSection" class="news-center__tabs">
      <el-tab-pane label="新闻资讯" name="news">
        <div class="news-toolbar">
          <el-input
            v-model="newsKeyword"
            class="news-toolbar__search"
            placeholder="搜索新闻标题或来源"
            clearable
            @keyup.enter="searchNews"
          />
          <el-date-picker
            v-model="newsRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            class="news-toolbar__range"
          />
          <el-button type="primary" @click="searchNews">查询</el-button>
          <el-button @click="resetNews">重置</el-button>
          <span v-if="metaSummary && !isIndexing" class="news-toolbar__stats">{{ metaSummary }}</span>
        </div>

        <el-alert
          v-if="indexMissing"
          class="news-center__alert"
          type="warning"
          :closable="false"
          show-icon
          title="未找到新闻数据文件（data/新闻/无标题.csv），请确认数据目录后重启后端"
        />
        <el-alert
          v-else-if="indexFailed"
          class="news-center__alert"
          type="error"
          :closable="false"
          show-icon
          title="新闻索引构建失败，请查看后端日志后重启服务"
        />
        <el-alert
          v-else-if="isIndexing"
          class="news-center__alert"
          type="info"
          :closable="false"
          show-icon
          :title="`新闻索引正在后台构建，已处理 ${(newsMeta?.indexed_rows ?? 0).toLocaleString('zh-CN')} 条；构建完成后可检索全部新闻`"
        />
        <el-alert
          v-if="newsError"
          class="news-center__alert"
          type="error"
          :closable="false"
          show-icon
          :title="newsError"
        />

        <div class="news-body">
          <section class="news-list" v-loading="newsLoading">
            <button
              v-for="item in newsItems"
              :key="item.id"
              type="button"
              class="news-item"
              :class="{ 'news-item--active': item.id === selectedNewsId }"
              @click="selectNews(item)"
            >
              <span class="news-item__title">{{ item.title }}</span>
              <span class="news-item__meta">
                <span>{{ item.date ?? '日期未知' }}</span>
                <span v-if="item.source">{{ item.source }}</span>
                <span v-if="item.stocks.length" class="news-item__stocks">
                  {{ item.stocks.length }} 只个股
                </span>
              </span>
            </button>

            <el-empty
              v-if="!newsItems.length && !newsLoading"
              :description="isIndexing ? '索引构建中，暂无数据' : '没有匹配的新闻'"
              :image-size="80"
            />

            <el-pagination
              v-if="newsTotal > NEWS_PAGE_SIZE"
              class="news-list__pagination"
              layout="prev, pager, next"
              small
              :total="newsTotal"
              :page-size="NEWS_PAGE_SIZE"
              :current-page="newsPage"
              @current-change="changeNewsPage"
            />
          </section>

          <section class="news-detail" v-loading="newsDetailLoading">
            <el-alert
              v-if="newsDetailError"
              type="error"
              :closable="false"
              show-icon
              :title="newsDetailError"
            />
            <template v-else-if="newsDetail">
              <h2 class="news-detail__title">{{ newsDetail.title }}</h2>
              <div class="news-detail__meta">
                <span>{{ newsDetail.date ?? '日期未知' }}</span>
                <span v-if="newsDetail.source">来源：{{ newsDetail.source }}</span>
              </div>
              <div v-if="newsDetail.stocks.length" class="news-detail__stocks">
                <el-tag
                  v-for="code in newsDetail.stocks"
                  :key="code"
                  size="small"
                  type="info"
                  effect="plain"
                >
                  {{ code }}
                </el-tag>
              </div>
              <div class="news-detail__content">{{ newsDetail.content }}</div>
            </template>
            <el-empty v-else description="选择左侧新闻查看正文" :image-size="100" />
          </section>
        </div>
      </el-tab-pane>

      <el-tab-pane label="资金流摘要" name="summaries">
        <div class="news-toolbar">
          <el-input
            v-model="summaryKeyword"
            class="news-toolbar__search"
            placeholder="搜索摘要标题或机构"
            clearable
            @keyup.enter="searchSummaries"
          />
          <el-button type="primary" @click="searchSummaries">查询</el-button>
          <el-button @click="resetSummaries">重置</el-button>
          <span class="news-toolbar__stats">共 {{ summaryTotal }} 篇摘要</span>
        </div>

        <el-alert
          v-if="summaryError"
          class="news-center__alert"
          type="error"
          :closable="false"
          show-icon
          :title="summaryError"
        />

        <div class="news-body">
          <section class="news-list" v-loading="summaryLoading">
            <button
              v-for="item in summaryItems"
              :key="item.name"
              type="button"
              class="news-item"
              :class="{ 'news-item--active': item.name === selectedSummaryName }"
              @click="selectSummary(item)"
            >
              <span class="news-item__title">{{ item.title }}</span>
              <span class="news-item__meta">
                <span>{{ item.date ?? '日期未知' }}</span>
                <span v-if="item.institution">{{ item.institution }}</span>
              </span>
            </button>

            <el-empty
              v-if="!summaryItems.length && !summaryLoading"
              description="没有匹配的资金流摘要"
              :image-size="80"
            />

            <el-pagination
              v-if="summaryTotal > SUMMARY_PAGE_SIZE"
              class="news-list__pagination"
              layout="prev, pager, next"
              small
              :total="summaryTotal"
              :page-size="SUMMARY_PAGE_SIZE"
              :current-page="summaryPage"
              @current-change="changeSummaryPage"
            />
          </section>

          <section class="news-detail" v-loading="summaryDetailLoading">
            <el-alert
              v-if="summaryDetailError"
              type="error"
              :closable="false"
              show-icon
              :title="summaryDetailError"
            />
            <template v-else-if="summaryDetail">
              <h2 class="news-detail__title">{{ summaryDetail.title }}</h2>
              <div class="news-detail__meta">
                <span>{{ summaryDetail.date ?? '日期未知' }}</span>
                <span v-if="summaryDetail.institution">
                  机构：{{ summaryDetail.institution }}
                </span>
              </div>
              <div class="news-detail__markdown" v-html="summaryHtml"></div>
            </template>
            <el-empty v-else description="选择左侧摘要查看内容" :image-size="100" />
          </section>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.news-center {
  display: flex;
  flex-direction: column;
}

.news-center__tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.news-center__alert {
  margin-bottom: 12px;
}

.news-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.news-toolbar__search {
  width: 240px;
}

.news-toolbar__range {
  max-width: 260px;
}

.news-toolbar__stats {
  font-size: 12px;
  color: #909399;
}

.news-body {
  display: flex;
  gap: 16px;
  align-items: stretch;
  min-height: 560px;
}

.news-list {
  flex: 0 0 380px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 680px;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.news-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.news-item:hover {
  background: #f5f7fa;
}

.news-item--active {
  background: #ecf5ff;
}

.news-item__title {
  font-size: 14px;
  line-height: 1.5;
  color: #303133;
}

.news-item--active .news-item__title {
  color: #409eff;
  font-weight: 600;
}

.news-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #909399;
}

.news-item__stocks {
  color: #b1b3b8;
}

.news-list__pagination {
  justify-content: center;
  margin-top: 8px;
}

.news-detail {
  flex: 1;
  min-width: 0;
  max-height: 680px;
  overflow-y: auto;
  padding: 24px 28px;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.news-detail__title {
  margin: 0 0 12px;
  font-size: 20px;
  line-height: 1.4;
  color: #303133;
}

.news-detail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #909399;
}

.news-detail__stocks {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}

.news-detail__content {
  font-size: 14px;
  line-height: 1.9;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

.news-detail__markdown {
  font-size: 14px;
  line-height: 1.9;
  color: #303133;
  word-break: break-word;
}

.news-detail__markdown :deep(h3),
.news-detail__markdown :deep(h4) {
  margin: 18px 0 8px;
  font-size: 15px;
  color: #303133;
}

.news-detail__markdown :deep(p) {
  margin: 8px 0;
}

.news-detail__markdown :deep(ul),
.news-detail__markdown :deep(ol) {
  margin: 8px 0;
  padding-left: 22px;
}

.news-detail__markdown :deep(li) {
  margin: 4px 0;
}
</style>
