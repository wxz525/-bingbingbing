-- =============================================================================
-- 国元证券 TRAE 金科竞赛 - MySQL 元数据层 DDL
-- 数据库：gy_meta  用途：保存元数据、研报索引、数据源清单、ETL 批次日志
-- 研报正文不入库，仅在 report_index 保存 MinIO 对象路径索引。
-- 执行顺序：先建库建表，再运行 scripts/ 下的 ETL。
-- =============================================================================

CREATE DATABASE IF NOT EXISTS gy_meta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gy_meta;

-- -----------------------------------------------------------------------------
-- 1. 资产维度表（来源：目标资产价格变量/代码对照.csv）
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_asset;
CREATE TABLE dim_asset (
  asset_id       BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  category       VARCHAR(32)  NOT NULL COMMENT '大类：中国权益/全球权益/大宗商品/外汇/全球债券/另类',
  name           VARCHAR(64)  NOT NULL COMMENT '资产名称',
  wind_code      VARCHAR(32)           DEFAULT NULL COMMENT 'Wind 代码',
  field_type     VARCHAR(16)           DEFAULT NULL COMMENT '字段类型：close / yield',
  trade_calendar VARCHAR(128)          DEFAULT NULL COMMENT '交易日历描述',
  start_date     DATE                  DEFAULT NULL COMMENT '数据起始日期',
  end_date       DATE                  DEFAULT NULL COMMENT '数据结束日期',
  row_count      INT                   DEFAULT NULL COMMENT '原始数据条数',
  status         VARCHAR(16)           DEFAULT NULL COMMENT 'ok / 缺失',
  remark         VARCHAR(512)          DEFAULT NULL COMMENT '备注（业务口径）',
  source_file    VARCHAR(255)          DEFAULT NULL COMMENT '源 csv 相对路径',
  batch_id       VARCHAR(64)           DEFAULT NULL COMMENT 'ETL 批次号',
  created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (asset_id),
  UNIQUE KEY uk_name (name),
  KEY idx_category (category)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='资产维度（行情/指标目标资产）';

-- -----------------------------------------------------------------------------
-- 2. 指标维度表（来源：指标集1_数据.xlsx 的 31 个 sheet）
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_indicator;
CREATE TABLE dim_indicator (
  indicator_id BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  source_file  VARCHAR(255)          DEFAULT NULL COMMENT '源 xlsx 相对路径',
  sheet_code   VARCHAR(16)  NOT NULL COMMENT 'sheet 编号：X01..X31',
  seq_name     VARCHAR(16)  NOT NULL COMMENT '序列名：序列1..序列N',
  start_date   DATE                  DEFAULT NULL,
  end_date     DATE                  DEFAULT NULL,
  row_count    INT                   DEFAULT NULL,
  remark       VARCHAR(512)          DEFAULT NULL COMMENT '指标业务口径（待业务方补充）',
  batch_id     VARCHAR(64)           DEFAULT NULL,
  created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (indicator_id),
  UNIQUE KEY uk_sheet_seq (sheet_code, seq_name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='衍生指标维度（指标集 sheet 元数据）';

-- -----------------------------------------------------------------------------
-- 3. 研报索引表（来源：全球资金信息摘要.zip 解压后的 md 文件；正文存 MinIO）
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS report_index;
CREATE TABLE report_index (
  report_id        BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  title            VARCHAR(512) NOT NULL COMMENT '研报标题（取自文件名）',
  publish_date     DATE                  DEFAULT NULL COMMENT '发布日期（从文件名解析）',
  institution      VARCHAR(32)           DEFAULT NULL COMMENT '机构标识：机构A/B/C/E/H 等（从文件名解析）',
  minio_bucket     VARCHAR(64)  NOT NULL COMMENT 'MinIO bucket',
  minio_object_key VARCHAR(512) NOT NULL COMMENT 'MinIO 对象路径（研报正文索引）',
  source_zip       VARCHAR(128)          DEFAULT NULL COMMENT '来源压缩包名',
  source_file      VARCHAR(512)          DEFAULT NULL COMMENT 'zip 内相对路径',
  file_size        BIGINT                DEFAULT NULL COMMENT '文件字节数',
  file_md5         VARCHAR(32)           DEFAULT NULL COMMENT '文件 md5',
  batch_id         VARCHAR(64)           DEFAULT NULL,
  created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (report_id),
  UNIQUE KEY uk_object (minio_bucket, minio_object_key),
  KEY idx_publish_date (publish_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='研报索引（正文存 MinIO，库内只存路径）';

-- -----------------------------------------------------------------------------
-- 4. 数据源清单（记录每一个原始文件，用于校验不遗漏）
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS data_source;
CREATE TABLE data_source (
  source_id      BIGINT       NOT NULL AUTO_INCREMENT,
  category       VARCHAR(32)           DEFAULT NULL COMMENT '分类：行情/指标/日历/新闻/舆情/研报/成交',
  file_path      VARCHAR(512) NOT NULL COMMENT '相对 data 根的路径（唯一）',
  file_name      VARCHAR(255)          DEFAULT NULL,
  file_type      VARCHAR(8)            DEFAULT NULL COMMENT 'csv / xlsx / zip',
  raw_rows       INT                   DEFAULT NULL COMMENT '原始数据行数（去表头）',
  loaded_rows    INT          NOT NULL DEFAULT 0 COMMENT '已入库行数',
  target_table   VARCHAR(128)          DEFAULT NULL COMMENT '入库目标表',
  status         VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending / loaded / failed',
  last_load_time DATETIME              DEFAULT NULL,
  remark         VARCHAR(512)          DEFAULT NULL,
  PRIMARY KEY (source_id),
  UNIQUE KEY uk_path (file_path)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='原始数据源清单';

-- -----------------------------------------------------------------------------
-- 5. ETL 批次日志
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS etl_batch_log;
CREATE TABLE etl_batch_log (
  log_id       BIGINT        NOT NULL AUTO_INCREMENT,
  batch_id     VARCHAR(64)   NOT NULL COMMENT '批次号',
  task_name    VARCHAR(64)   NOT NULL COMMENT '任务名',
  source_file  VARCHAR(512)           DEFAULT NULL,
  target_table VARCHAR(128)           DEFAULT NULL,
  raw_rows     INT                    DEFAULT 0,
  loaded_rows  INT                    DEFAULT 0,
  failed_rows  INT                    DEFAULT 0,
  status       VARCHAR(16)            DEFAULT NULL COMMENT 'running / success / failed',
  start_time   DATETIME               DEFAULT NULL,
  end_time     DATETIME               DEFAULT NULL,
  message      VARCHAR(2000)          DEFAULT NULL,
  created_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id),
  KEY idx_batch (batch_id),
  KEY idx_task (task_name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT ='ETL 批次执行日志';
