<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  getNews,
  getNewsMeta,
  getSentimentOverview,
  getSentimentSeries,
  getSummary,
  listNews,
  listSummaries,
} from '@/api/news'
import type {
  NewsDetail,
  NewsListItem,
  NewsMeta,
  SentimentOverviewResponse,
  SentimentSeriesResponse,
  SummaryDetail,
  SummaryListItem,
} from '@/types/news'
import { ApiRequestError } from '@/api/http'
import { isAbortError } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'
import SentimentChart from '@/components/SentimentChart.vue'

const NEWS_PAGE_SIZE = 20
const SUMMARY_PAGE_SIZE = 20
const POLL_INTERVAL = 5000

const TOPIC_OPTIONS = [
  { value: 'macro', label: '宏观政策' },
  { value: 'tech', label: '科技/半导体' },
  { value: 'pharma', label: '医药/医疗' },
  { value: 'energy', label: '能源/资源' },
  { value: 'finance', label: '金融/资本市场' },
  { value: 'consumer', label: '消费/白酒' },
  { value: 'infrastructure', label: '基建/周期' },
  { value: 'event', label: '事件/地缘' },
  { value: 'capital_flow', label: '资金面情报' },
]
const LEVEL_OPTIONS = [
  { value: 'macro', label: '宏观市场' },
  { value: 'sector', label: '细分市场/行业' },
  { value: 'single', label: '个股/公司' },
]
const SENTIMENT_OPTIONS = [
  { value: 'bullish', label: '利好' },
  { value: 'neutral', label: '中性' },
  { value: 'bearish', label: '利空' },
]
const TOPIC_LABEL: Record<string, string> = Object.fromEntries(
  TOPIC_OPTIONS.map((o) => [o.value, o.label]),
)
const LEVEL_LABEL: Record<string, string> = Object.fromEntries(
  LEVEL_OPTIONS.map((o) => [o.value, o.label]),
)
const SENTIMENT_TYPE: Record<string, 'success' | 'info' | 'danger'> = {
  bullish: 'danger',
  neutral: 'info',
  bearish: 'success',
}

const activeSection = ref<'news' | 'summaries'>('news')

const newsMeta = ref<NewsMeta | null>(null)
const newsKeyword = ref('')
const newsRange = ref<[string, string] | null>(null)
const newsTopic = ref<string>('')
const newsLevel = ref<string>('')
const newsSentiment = ref<string>('')
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
const summaryTopic = ref<string>('')
const summaryLevel = ref<string>('')
const summarySentiment = ref<string>('')
const summaryItems = ref<SummaryListItem[]>([])
const summaryTotal = ref(0)
const summaryPage = ref(1)
const summaryLoading = ref(false)
const summaryError = ref('')
const selectedSummaryName = ref('')
const summaryDetail = ref<SummaryDetail | null>(null)
const summaryDetailLoading = ref(false)
const summaryDetailError = ref('')
const relatedNews = ref<NewsListItem[]>([])
const relatedNewsLoading = ref(false)

const sentimentOverview = ref<SentimentOverviewResponse | null>(null)
const sentimentOverviewLoading = ref(false)
const sentimentSeries = ref<SentimentSeriesResponse | null>(null)
const sentimentTopic = ref('tech')
const sentimentBucket = ref<'day' | 'week'>('week')
const sentimentRange = ref<[string, string] | null>(null)
const sentimentLoading = ref(false)
const sentimentError = ref('')

let newsController: AbortController | null = null
let summaryController: AbortController | null = null
let sentimentController: AbortController | null = null
let newsListRequestId = 0
let newsDetailRequestId = 0
let summaryListRequestId = 0
let summaryDetailRequestId = 0
let sentimentRequestId = 0
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
      topics: newsTopic.value ? [newsTopic.value] : undefined,
      level: newsLevel.value || undefined,
      sentiment: newsSentiment.value || undefined,
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
  newsTopic.value = ''
  newsLevel.value = ''
  newsSentiment.value = ''
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
      topic: summaryTopic.value || undefined,
      level: summaryLevel.value || undefined,
      sentiment: summarySentiment.value || undefined,
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
  summaryTopic.value = ''
  summaryLevel.value = ''
  summarySentiment.value = ''
  searchSummaries()
}

function changeSummaryPage(page: number): void {
  summaryPage.value = page
  void loadSummaries()
}

async function selectSummary(item: SummaryListItem): Promise<void> {
  selectedSummaryName.value = item.name
  summaryController?.abort()
  relatedNews.value = []
  relatedNewsLoading.value = false
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
    void loadRelatedNews(response)
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

async function loadRelatedNews(summary: SummaryDetail): Promise<void> {
  if (!summary.topics.length && !summary.date) {
    return
  }
  relatedNewsLoading.value = true
  try {
    let start: string | undefined
    let end: string | undefined
    if (summary.date) {
      const d = new Date(summary.date)
      const fmt = (dt: Date) => {
        const y = dt.getFullYear()
        const m = String(dt.getMonth() + 1).padStart(2, '0')
        const day = String(dt.getDate()).padStart(2, '0')
        return `${y}-${m}-${day}`
      }
      const before = new Date(d.getTime() - 7 * 86400000)
      const after = new Date(d.getTime() + 7 * 86400000)
      start = fmt(before)
      end = fmt(after)
    }
    // 取前 3 个 topic，过滤掉 capital_flow（太泛）避免匹配过多噪音
    const topicFiltered = summary.topics.filter((t) => t !== 'capital_flow').slice(0, 3)
    if (!topicFiltered.length) {
      return
    }
    const response = await listNews({
      topics: topicFiltered,
      start,
      end,
      pageSize: 10,
    })
    relatedNews.value = response.items
  } catch (error) {
    if (isAbortError(error)) {
      return
    }
    relatedNews.value = []
  } finally {
    relatedNewsLoading.value = false
  }
}

async function loadSentimentOverview(): Promise<void> {
  sentimentOverviewLoading.value = true
  try {
    sentimentOverview.value = await getSentimentOverview()
  } catch (error) {
    if (isAbortError(error)) {
      return
    }
    sentimentOverview.value = null
  } finally {
    sentimentOverviewLoading.value = false
  }
}

async function loadSentimentSeries(): Promise<void> {
  sentimentLoading.value = true
  sentimentError.value = ''
  const requestId = ++sentimentRequestId
  sentimentController?.abort()
  const controller = new AbortController()
  sentimentController = controller
  try {
    const response = await getSentimentSeries(
      {
        topic: sentimentTopic.value,
        start: sentimentRange.value?.[0],
        end: sentimentRange.value?.[1],
        bucket: sentimentBucket.value,
      },
      controller.signal,
    )
    if (requestId !== sentimentRequestId) {
      return
    }
    sentimentSeries.value = response
  } catch (error) {
    if (isAbortError(error) || requestId !== sentimentRequestId) {
      return
    }
    sentimentSeries.value = null
    sentimentError.value = toErrorMessage(error, '情绪指数加载失败，请稍后重试')
  } finally {
    if (requestId === sentimentRequestId) {
      sentimentLoading.value = false
    }
  }
}

function reloadSentimentSeries(): void {
  void loadSentimentSeries()
}

function formatCount(value: number): string {
  if (value >= 10000) {
    return `${(value / 10000).toFixed(1)} 万`
  }
  return String(value)
}

function share(part: number, total: number): string {
  if (!total) {
    return '0%'
  }
  return `${((part / total) * 100).toFixed(2)}%`
}

function shareText(part: number, total: number): string {
  if (!total) {
    return '0%'
  }
  return `${((part / total) * 100).toFixed(1)}%`
}

onMounted(() => {
  void loadNewsMeta()
  void loadNews()
  void loadSummaries()
  void loadSentimentOverview()
  void loadSentimentSeries()
})

onBeforeUnmount(() => {
  stopPolling()
  newsController?.abort()
  summaryController?.abort()
  sentimentController?.abort()
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
          <el-select
            v-model="newsTopic"
            placeholder="全部主题"
            clearable
            class="news-toolbar__filter"
            @change="searchNews"
          >
            <el-option
              v-for="opt in TOPIC_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
          <el-select
            v-model="newsLevel"
            placeholder="全部层级"
            clearable
            class="news-toolbar__filter"
            @change="searchNews"
          >
            <el-option
              v-for="opt in LEVEL_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
          <el-select
            v-model="newsSentiment"
            placeholder="全部情绪"
            clearable
            class="news-toolbar__filter"
            @change="searchNews"
          >
            <el-option
              v-for="opt in SENTIMENT_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
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
              <span v-if="item.sentiment || item.topics.length" class="news-item__tags">
                <el-tag
                  v-if="item.sentiment && SENTIMENT_TYPE[item.sentiment]"
                  :type="SENTIMENT_TYPE[item.sentiment]"
                  size="small"
                  effect="light"
                  round
                >
                  {{ SENTIMENT_OPTIONS.find((o) => o.value === item.sentiment)?.label ?? item.sentiment }}
                </el-tag>
                <el-tag
                  v-for="topic in item.topics"
                  :key="topic"
                  size="small"
                  effect="plain"
                  round
                >
                  {{ TOPIC_LABEL[topic] ?? topic }}
                </el-tag>
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
                <span v-if="newsDetail.market_level">层级：{{ LEVEL_LABEL[newsDetail.market_level] ?? newsDetail.market_level }}</span>
              </div>
              <div v-if="newsDetail.sentiment || newsDetail.topics.length" class="news-detail__tags">
                <el-tag
                  v-if="newsDetail.sentiment && SENTIMENT_TYPE[newsDetail.sentiment]"
                  :type="SENTIMENT_TYPE[newsDetail.sentiment]"
                  effect="light"
                  round
                >
                  {{ SENTIMENT_OPTIONS.find((o) => o.value === newsDetail!.sentiment)?.label ?? newsDetail!.sentiment }}
                </el-tag>
                <el-tag
                  v-for="topic in newsDetail.topics"
                  :key="topic"
                  effect="plain"
                  round
                >
                  {{ TOPIC_LABEL[topic] ?? topic }}
                </el-tag>
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
          <el-select
            v-model="summaryTopic"
            placeholder="全部主题"
            clearable
            class="news-toolbar__filter"
            @change="searchSummaries"
          >
            <el-option
              v-for="opt in TOPIC_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
          <el-select
            v-model="summaryLevel"
            placeholder="全部层级"
            clearable
            class="news-toolbar__filter"
            @change="searchSummaries"
          >
            <el-option
              v-for="opt in LEVEL_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
          <el-select
            v-model="summarySentiment"
            placeholder="全部情绪"
            clearable
            class="news-toolbar__filter"
            @change="searchSummaries"
          >
            <el-option
              v-for="opt in SENTIMENT_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
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
              <span v-if="item.sentiment || item.topics.length" class="news-item__tags">
                <el-tag
                  v-if="item.sentiment && SENTIMENT_TYPE[item.sentiment]"
                  :type="SENTIMENT_TYPE[item.sentiment]"
                  size="small"
                  effect="light"
                  round
                >
                  {{ SENTIMENT_OPTIONS.find((o) => o.value === item.sentiment)?.label ?? item.sentiment }}
                </el-tag>
                <el-tag
                  v-for="topic in item.topics"
                  :key="topic"
                  size="small"
                  effect="plain"
                  round
                >
                  {{ TOPIC_LABEL[topic] ?? topic }}
                </el-tag>
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
                <span v-if="summaryDetail.market_level">层级：{{ LEVEL_LABEL[summaryDetail.market_level] ?? summaryDetail.market_level }}</span>
              </div>
              <div v-if="summaryDetail.sentiment || summaryDetail.topics.length" class="news-detail__tags">
                <el-tag
                  v-if="summaryDetail.sentiment && SENTIMENT_TYPE[summaryDetail.sentiment]"
                  :type="SENTIMENT_TYPE[summaryDetail.sentiment]"
                  effect="light"
                  round
                >
                  {{ SENTIMENT_OPTIONS.find((o) => o.value === summaryDetail!.sentiment)?.label ?? summaryDetail!.sentiment }}
                </el-tag>
                <el-tag
                  v-for="topic in summaryDetail.topics"
                  :key="topic"
                  effect="plain"
                  round
                >
                  {{ TOPIC_LABEL[topic] ?? topic }}
                </el-tag>
              </div>
              <div class="news-detail__markdown" v-html="summaryHtml"></div>

              <div class="related-news" v-loading="relatedNewsLoading">
                <div class="related-news__title">相关新闻（{{ relatedNews.length }} 条）</div>
                <el-empty
                  v-if="!relatedNewsLoading && !relatedNews.length"
                  description="近 7 天内未找到主题匹配的新闻"
                  :image-size="60"
                />
                <ul v-else-if="relatedNews.length" class="related-news__list">
                  <li
                    v-for="item in relatedNews"
                    :key="item.id"
                    class="related-news__item"
                    @click="activeSection = 'news'; newsKeyword = ''; newsTopic = ''; newsLevel = ''; newsSentiment = ''; newsPage = 1; newsRange = null; newsItems = []; loadNews(); void selectNews(item)"
                  >
                    <span class="related-news__meta">
                      {{ item.date ?? '' }}
                      <el-tag
                        v-if="item.sentiment && SENTIMENT_TYPE[item.sentiment]"
                        :type="SENTIMENT_TYPE[item.sentiment]"
                        size="small"
                        effect="light"
                        round
                        style="margin-left: 4px"
                      >
                        {{ SENTIMENT_OPTIONS.find((o) => o.value === item.sentiment)?.label ?? item.sentiment }}
                      </el-tag>
                    </span>
                    <span class="related-news__title-text">{{ item.title }}</span>
                  </li>
                </ul>
              </div>
            </template>
            <el-empty v-else description="选择左侧摘要查看内容" :image-size="100" />
          </section>
        </div>
      </el-tab-pane>

      <el-tab-pane label="情绪指数" name="sentiment">
        <div class="news-toolbar">
          <el-select
            v-model="sentimentTopic"
            class="news-toolbar__filter"
            @change="reloadSentimentSeries"
          >
            <el-option
              v-for="opt in TOPIC_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
          <el-date-picker
            v-model="sentimentRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            class="news-toolbar__range"
            :clearable="true"
            @change="reloadSentimentSeries"
          />
          <el-radio-group v-model="sentimentBucket" size="default" @change="reloadSentimentSeries">
            <el-radio-button value="week">按周</el-radio-button>
            <el-radio-button value="day">按日</el-radio-button>
          </el-radio-group>
          <span v-if="sentimentSeries" class="news-toolbar__stats">
            共 {{ sentimentSeries.points.length }} 个周期 · {{ sentimentSeries.summaries.length }} 条机构观点
          </span>
        </div>

        <el-alert
          v-if="sentimentError"
          class="news-center__alert"
          type="error"
          :closable="false"
          show-icon
          :title="sentimentError"
        />

        <div class="sentiment-topics" v-loading="sentimentOverviewLoading">
          <button
            v-for="topic in sentimentOverview?.topics ?? []"
            :key="topic.topic"
            type="button"
            class="sentiment-card"
            :class="{ 'sentiment-card--active': topic.topic === sentimentTopic }"
            @click="sentimentTopic = topic.topic; reloadSentimentSeries()"
          >
            <span class="sentiment-card__label">{{ TOPIC_LABEL[topic.topic] ?? topic.topic }}</span>
            <span class="sentiment-card__stack" aria-hidden="true">
              <i
                class="sentiment-card__stack-seg sentiment-card__stack-seg--bull"
                :style="{ width: share(topic.news_bullish, topic.news_total) }"
              ></i>
              <i
                class="sentiment-card__stack-seg sentiment-card__stack-seg--neutral"
                :style="{ width: share(topic.news_neutral, topic.news_total) }"
              ></i>
              <i
                class="sentiment-card__stack-seg sentiment-card__stack-seg--bear"
                :style="{ width: share(topic.news_bearish, topic.news_total) }"
              ></i>
            </span>
            <span class="sentiment-card__legend">
              <span class="sentiment-card__legend-item">
                <i class="sentiment-card__dot sentiment-card__dot--bull"></i>
                利好 {{ formatCount(topic.news_bullish) }}（{{ shareText(topic.news_bullish, topic.news_total) }}）
              </span>
              <span class="sentiment-card__legend-item">
                <i class="sentiment-card__dot sentiment-card__dot--neutral"></i>
                中性 {{ formatCount(topic.news_neutral) }}（{{ shareText(topic.news_neutral, topic.news_total) }}）
              </span>
              <span class="sentiment-card__legend-item">
                <i class="sentiment-card__dot sentiment-card__dot--bear"></i>
                利空 {{ formatCount(topic.news_bearish) }}（{{ shareText(topic.news_bearish, topic.news_total) }}）
              </span>
            </span>
            <span class="sentiment-card__meta">
              新闻共 {{ formatCount(topic.news_total) }} 条
            </span>
            <span class="sentiment-card__meta sentiment-card__meta--summary">
              机构摘要 {{ formatCount(topic.summary_total) }} 篇 · 利好 {{ formatCount(topic.summary_bullish) }} / 利空 {{ formatCount(topic.summary_bearish) }}
            </span>
          </button>
          <el-empty
            v-if="!sentimentOverviewLoading && !(sentimentOverview?.topics?.length)"
            description="暂无主题情绪概览"
            :image-size="60"
          />
        </div>

        <div class="sentiment-chart-wrap" v-loading="sentimentLoading">
          <SentimentChart
            :points="sentimentSeries?.points ?? []"
            :summaries="sentimentSeries?.summaries ?? []"
          />
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

.news-toolbar__filter {
  width: 130px;
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

.news-item__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
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

.news-detail__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
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

.related-news {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px dashed #dcdfe6;
}

.related-news__title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.related-news__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.related-news__item {
  cursor: pointer;
  padding: 10px 12px;
  border-radius: 6px;
  transition: background-color 0.15s;
}

.related-news__item:hover {
  background-color: #f5f7fa;
}

.related-news__meta {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 3px;
}

.related-news__title-text {
  font-size: 13px;
  color: #303133;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.sentiment-topics {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
  gap: 12px;
  margin: 14px 0 18px;
}

.sentiment-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: left;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.sentiment-card:hover {
  border-color: #c6e2ff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.sentiment-card--active {
  border-color: #409eff;
  box-shadow: 0 0 0 1px #409eff inset;
}

.sentiment-card__label {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.sentiment-card__stack {
  display: flex;
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  background: #f0f2f5;
}

.sentiment-card__stack-seg {
  display: block;
  height: 100%;
  transition: width 0.3s ease;
}

.sentiment-card__stack-seg--bull {
  background: #f56c6c;
}

.sentiment-card__stack-seg--neutral {
  background: #c8cdd4;
}

.sentiment-card__stack-seg--bear {
  background: #67c23a;
}

.sentiment-card__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 11px;
  color: #606266;
  line-height: 1.5;
}

.sentiment-card__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  white-space: nowrap;
}

.sentiment-card__dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.sentiment-card__dot--bull {
  background: #f56c6c;
}

.sentiment-card__dot--neutral {
  background: #c8cdd4;
}

.sentiment-card__dot--bear {
  background: #67c23a;
}

.sentiment-card__meta {
  font-size: 12px;
  color: #606266;
}

.sentiment-card__meta--summary {
  color: #909399;
}

.sentiment-chart-wrap {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px;
}
</style>
