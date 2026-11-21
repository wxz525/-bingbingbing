-- =============================================================================
-- 国元证券 TRAE 金科竞赛 - ClickHouse 分层 DDL
-- 数据库：gy_dw
-- 分层：
--   ODS  贴源层  - 保留原始字段 + 批次号 + 入库时间，一个数据源一张表
--   DWD  明细层  - 清洗标准化、类型规整、去重后的明细
--   DWS  汇总层  - 面向看板的轻度聚合
-- 研报正文不入库（存 MinIO），研报元数据索引入 MySQL gy_meta.report_index。
-- 执行：先执行本文件建库建表，再运行 ETL；ETL 完成后由 run_all.py 刷新 DWS。
-- =============================================================================

CREATE DATABASE IF NOT EXISTS gy_dw;

-- =============================================================================
-- ODS 贴源层
-- =============================================================================

-- 1. 行情价格（合并 目标资产价格变量/ 下 39 个 csv：date + close/yield）
DROP TABLE IF EXISTS ods_market_price;
CREATE TABLE ods_market_price (
    asset_code  LowCardinality(String) COMMENT '资产代码（取文件名/代码对照）',
    asset_name  String,
    category    LowCardinality(String) COMMENT '大类',
    field_type  LowCardinality(String) COMMENT 'close / yield',
    trade_date  Date,
    value       Nullable(Float64),
    source_file String,
    batch_id    String,
    load_time   DateTime DEFAULT now()
) ENGINE = MergeTree
PARTITION BY toYYYYMM(trade_date)
ORDER BY (asset_code, trade_date)
COMMENT '行情价格 ODS（39 个资产时序合并）';

-- 2. 衍生指标（指标集1_数据.xlsx 31 个 sheet，宽表转长表：sheet+seq+date+value）
DROP TABLE IF EXISTS ods_indicator;
CREATE TABLE ods_indicator (
    indicator_code LowCardinality(String) COMMENT '如 X01_序列1',
    sheet_code     LowCardinality(String) COMMENT 'X01..X31',
    seq_name       LowCardinality(String) COMMENT '序列1..序列N',
    trade_date     Date,
    value          Nullable(Float64),
    source_file    String,
    batch_id       String,
    load_time      DateTime DEFAULT now()
) ENGINE = MergeTree
PARTITION BY toYYYYMM(trade_date)
ORDER BY (sheet_code, seq_name, trade_date)
COMMENT '衍生指标 ODS（长表）';

-- 3. 事件日历（日历数据.xlsx）
DROP TABLE IF EXISTS ods_event_calendar;
CREATE TABLE ods_event_calendar (
    indicator_name    String,
    occur_date        Date,
    occur_time        String,
    home_country      LowCardinality(String),
    indicator_former  Nullable(Float64),
    indicator_forecast Nullable(Float64),
    indicator_fact    Nullable(Float64),
    source_file       String,
    batch_id          String,
    load_time         DateTime DEFAULT now()
) ENGINE = MergeTree
PARTITION BY toYYYYMM(occur_date)
ORDER BY (occur_date, home_country, indicator_name)
COMMENT '全球经济事件日历 ODS';

-- 4. 财联社新闻（新闻/无标题.csv，无表头，11 列按位置命名）
DROP TABLE IF EXISTS ods_news_cailianpress;
CREATE TABLE ods_news_cailianpress (
    news_id     UInt64,
    title       String,
    content     String,
    source      LowCardinality(String),
    extra_flag  String   COMMENT '原始第 5 列（疑似分类标记）',
    tags        String   COMMENT '原始第 6 列',
    stock_codes String   COMMENT '原始第 7 列（JSON 字符串，关联股票）',
    publish_ts  UInt64   COMMENT '发布时间 unix 时间戳',
    crawl_ts    UInt64   COMMENT '采集时间 unix 时间戳',
    publish_date Date,
    row_no      UInt32   COMMENT '原始第 11 列（行序号）',
    source_file String,
    batch_id    String,
    load_time   DateTime DEFAULT now()
) ENGINE = MergeTree
PARTITION BY toYYYYMM(publish_date)
ORDER BY (publish_date, news_id)
COMMENT '财联社新闻 ODS';

-- 5. Twitter 舆情（科技.csv，31 列原始字段 + 派生 publish_date）
DROP TABLE IF EXISTS ods_twitter;
CREATE TABLE ods_twitter (
    id                    String,
    tweet_id              String,
    twitter_user_id       String,
    user_name             String,
    author_display_name   String,
    url                   String,
    text                  String,
    tweet_type            String,
    source                String,
    lang                  String,
    is_reply              String,
    is_retweet            String,
    is_quote              String,
    conversation_id       String,
    in_reply_to_tweet_id  String,
    in_reply_to_user_id   String,
    retweeted_tweet_raw   String,
    quoted_tweet_raw      String,
    created_at_twitter    String,
    like_count            Nullable(Int64),
    reply_count           Nullable(Int64),
    retweet_count         Nullable(Int64),
    quote_count           Nullable(Int64),
    view_count            Nullable(Int64),
    bookmark_count        Nullable(Int64),
    origin                String,
    history_job_id        String,
    first_collected_at    String,
    last_snapshot_at      String,
    last_snapshot_job_id  String,
    created_at            String,
    updated_at            String,
    publish_date          Date     COMMENT '由 created_at 解析（失败置 1970-01-01）',
    source_file           String,
    batch_id              String,
    load_time             DateTime DEFAULT now()
) ENGINE = MergeTree
PARTITION BY toYYYYMM(publish_date)
ORDER BY (publish_date, tweet_id)
COMMENT 'Twitter 舆情 ODS（科技.csv）';

-- 6. 公众号文章（公众号.xlsx）
DROP TABLE IF EXISTS ods_wechat_article;
CREATE TABLE ods_wechat_article (
    publish_date  Date,
    url           String,
    title         String,
    related_party String   COMMENT '相关方',
    source_file   String,
    batch_id      String,
    load_time     DateTime DEFAULT now()
) ENGINE = MergeTree
PARTITION BY toYYYYMM(publish_date)
ORDER BY (publish_date, title)
COMMENT '公众号文章 ODS';

-- 7. 商品期货日成交额（商品期货日成交额.xlsx）
DROP TABLE IF EXISTS ods_futures_turnover;
CREATE TABLE ods_futures_turnover (
    trade_date  Date,
    turnover    Float64  COMMENT '成交额（万亿元）',
    source_file String,
    batch_id    String,
    load_time   DateTime DEFAULT now()
) ENGINE = MergeTree
PARTITION BY toYYYYMM(trade_date)
ORDER BY trade_date
COMMENT '商品期货日成交额 ODS';

-- =============================================================================
-- DWD 明细层（清洗标准化）
-- =============================================================================

-- 行情清洗：ReplacingMergeTree 按 (asset_code, trade_date) 去重，value 非空
DROP TABLE IF EXISTS dwd_market_price_daily;
CREATE TABLE dwd_market_price_daily (
    asset_code  LowCardinality(String),
    asset_name  String,
    category    LowCardinality(String),
    field_type  LowCardinality(String),
    trade_date  Date,
    value       Nullable(Float64),
    source_file String,
    batch_id    String,
    load_time   DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(load_time)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (asset_code, trade_date)
COMMENT '行情价格 DWD（去重清洗）';

-- 事件日历清洗
DROP TABLE IF EXISTS dwd_event_calendar;
CREATE TABLE dwd_event_calendar (
    indicator_name    String,
    occur_date        Date,
    occur_time        String,
    home_country      LowCardinality(String),
    indicator_former  Nullable(Float64),
    indicator_forecast Nullable(Float64),
    indicator_fact    Nullable(Float64),
    batch_id          String,
    load_time         DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(load_time)
PARTITION BY toYYYYMM(occur_date)
ORDER BY (occur_date, home_country, indicator_name)
COMMENT '事件日历 DWD';

-- 统一新闻明细（合并财联社 / Twitter / 公众号）
DROP TABLE IF EXISTS dwd_news_unified;
CREATE TABLE dwd_news_unified (
    news_id      String,
    source_type  LowCardinality(String) COMMENT 'cailianpress / twitter / wechat',
    title        String,
    content      String,
    publish_date Date,
    publish_ts   Nullable(UInt64),
    stock_codes  String,
    raw_url      String,
    batch_id     String,
    load_time    DateTime DEFAULT now()
) ENGINE = MergeTree
PARTITION BY toYYYYMM(publish_date)
ORDER BY (source_type, publish_date, news_id)
COMMENT '统一新闻明细 DWD（多源合并）';

-- =============================================================================
-- DWS 汇总层（由 run_all.py 在 ETL 后执行 INSERT SELECT 刷新）
-- =============================================================================

-- 每日各来源新闻量
DROP TABLE IF EXISTS dws_news_count_daily;
CREATE TABLE dws_news_count_daily (
    publish_date Date,
    source_type  LowCardinality(String),
    news_cnt     UInt64
) ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(publish_date)
ORDER BY (publish_date, source_type)
COMMENT '每日各来源新闻量 DWS';

-- 每个资产的行情统计（起止日期、条数、最新值）
DROP TABLE IF EXISTS dws_market_asset_stats;
CREATE TABLE dws_market_asset_stats (
    asset_code LowCardinality(String),
    asset_name String,
    category   LowCardinality(String),
    field_type LowCardinality(String),
    min_date   Date,
    max_date   Date,
    row_cnt    UInt64,
    last_value Nullable(Float64)
) ENGINE = MergeTree
ORDER BY asset_code
COMMENT '资产行情统计 DWS';

-- =============================================================================
-- DWS 刷新语句（幂等：先清空再聚合写入）—— 由 run_all.py 调用
-- =============================================================================
-- TRUNCATE TABLE dws_news_count_daily;
-- INSERT INTO dws_news_count_daily
-- SELECT publish_date, source_type, count() AS news_cnt
-- FROM dwd_news_unified GROUP BY publish_date, source_type;
--
-- TRUNCATE TABLE dws_market_asset_stats;
-- INSERT INTO dws_market_asset_stats
-- SELECT asset_code, any(asset_name), any(category), any(field_type),
--        min(trade_date), max(trade_date), count(),
--        argMax(value, trade_date)
-- FROM dwd_market_price_daily GROUP BY asset_code;
