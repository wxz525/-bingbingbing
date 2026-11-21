# Design: add-fund-archive

## 1. Context and Goals

基金档案是业务元数据模块，不承担行情、事件、舆情或研报正文查询。本设计复用项目既有存储边界：

| 存储 | 既有位置 | 本变更中的职责 |
| --- | --- | --- |
| MySQL | `gy_meta` | 新增基金基础信息、申赎规则版本与审计字段 |
| ClickHouse | `gy_dw` | 保持行情、事件、舆情等时序数据用途，不存申赎规则 |
| MinIO | `research-reports` | 保持研报文档用途，基金档案不直接读取正文 |

目标：整记录级 `MANUAL > ETL` 优先级、软删除历史、并发安全编辑、可解释的数据来源，以及前端统一 `--` 兜底。

## 2. Key Decisions

1. **独立基金主表**：新增 `fund_archive`，不强行复用通用行情资产表 `dim_asset`。
2. **整记录优先**：一条生效 MANUAL 规则完整覆盖 ETL 规则，避免逐字段拼接造成业务口径不一致。
3. **双来源单生效**：每只基金最多一条生效 MANUAL、一条生效 ETL；实际展示 MANUAL，缺失时展示 ETL。
4. **软删除而非更新覆盖**：编辑通过“归档旧生效记录 + 插入新记录”实现版本审计。
5. **后端统一判定**：前端不自行合并来源，不在浏览器中访问数据库或 MinIO。
6. **异常与空值分离**：后端保留真实错误码和 `null`，前端负责展示 `--`，不污染持久化数据。

## 3. MySQL Table Design

以下为 MySQL 8.0 增量 DDL 设计；实施时放入独立迁移脚本，不加入会清表现有数据的初始化 DDL。

### 3.1 `fund_archive`：基金基础信息

| 字段 | 类型 | 约束/含义 |
| --- | --- | --- |
| `fund_code` | VARCHAR(32) | 主键，基金业务代码 |
| `fund_name` | VARCHAR(128) | 非空，基金名称 |
| `fund_type` | VARCHAR(32) NULL | 股票型、债券型、混合型等 |
| `manager_name` | VARCHAR(128) NULL | 基金管理人 |
| `custodian_name` | VARCHAR(128) NULL | 基金托管人 |
| `establish_date` | DATE NULL | 成立日期 |
| `currency` | CHAR(3) NULL | ISO 4217，如 `CNY` |
| `fund_status` | VARCHAR(16) NULL | `NORMAL` / `SUSPENDED` / `TERMINATED` |
| `etl_source_file` | VARCHAR(512) NULL | 最近基础信息来源文件 |
| `etl_batch_id` | VARCHAR(64) NULL | 最近 ETL 批次 |
| `created_at` | DATETIME(3) | 创建时间 |
| `updated_at` | DATETIME(3) | 最近基础信息更新时间 |

> 备注：`fund_archive.updated_at` 仅代表基金基础信息更新时间。申赎规则版本迭代、人工编辑及 ETL 归档均 MUST NOT 修改该字段，避免将规则变更误解为基础信息变更。

### 3.2 `fund_redemption_rule`：申赎规则版本表

| 字段 | 类型 | 约束/含义 |
| --- | --- | --- |
| `rule_id` | BIGINT AUTO_INCREMENT | 主键 |
| `fund_code` | VARCHAR(32) | 外键至 `fund_archive` |
| `version_no` | INT UNSIGNED | 每只基金从 1 递增，与来源无关 |
| `purchase_status` | VARCHAR(16) NULL | `OPEN` / `CLOSED` / `SUSPENDED` |
| `redeem_status` | VARCHAR(16) NULL | `OPEN` / `CLOSED` / `SUSPENDED` |
| `min_purchase_amount` | DECIMAL(18,2) NULL | 最低申购金额，元，>= 0 |
| `min_additional_purchase_amount` | DECIMAL(18,2) NULL | 追加申购最低金额，元，>= 0 |
| `daily_purchase_limit` | DECIMAL(18,2) NULL | 单日申购上限，元，>= 0；NULL 表示未提供 |
| `min_redeem_shares` | DECIMAL(18,4) NULL | 最低赎回份额，>= 0 |
| `min_holding_shares` | DECIMAL(18,4) NULL | 最低持有份额，>= 0 |
| `purchase_fee_rate` | DECIMAL(10,6) NULL | 申购费率百分数，如 `0.150000` 表示 0.15%，0～100 |
| `redeem_fee_rate` | DECIMAL(10,6) NULL | 赎回费率百分数，口径同上 |
| `purchase_confirm_days` | SMALLINT UNSIGNED NULL | 申购确认天数 |
| `redeem_confirm_days` | SMALLINT UNSIGNED NULL | 赎回确认天数 |
| `redeem_arrival_days` | SMALLINT UNSIGNED NULL | 赎回到账天数 |
| `effective_date` | DATE NULL | 业务生效日期 |
| `remark` | VARCHAR(512) NULL | 备注 |
| `source_type` | VARCHAR(8) | `ETL` / `MANUAL` |
| `etl_batch_id` | VARCHAR(64) NULL | ETL 记录批次；人工记录为空 |
| `is_deleted` | TINYINT(1) | 0 生效、1 已归档；不是物理删除 |
| `active_fund_code` | VARCHAR(32) | 生成列：生效时为基金代码，归档时为 NULL |
| `created_by` | VARCHAR(64) | 创建操作人或 ETL 系统账号 |
| `created_at` | DATETIME(3) | 创建时间 |
| `deleted_by` | VARCHAR(64) NULL | 归档操作人或 ETL 系统账号 |
| `deleted_at` | DATETIME(3) NULL | 归档时间 |

约束：

- `UNIQUE (fund_code, version_no)` 保证版本单调且不可重复。
- `UNIQUE (active_fund_code, source_type)` 保证每来源最多一条生效记录；MySQL 唯一索引允许多个 NULL，因此可保留多条归档记录。
- `CHECK` 约束限制来源、状态、非负金额/份额和 0～100 费率；服务端仍需给出可读校验错误。
- 普通索引 `(fund_code, is_deleted, version_no)` 支持详情和历史排查。
- 外键 `fk_rule_fund` 禁止为不存在的基金写入规则，并显式设置 `ON DELETE RESTRICT`；存在申赎规则时禁止删除基金主记录。本模块禁止物理删除 `fund_archive` 中的基金，不提供相关接口或任务，避免依赖隐性外键默认行为。

### 3.3 Reference DDL

```sql
CREATE TABLE fund_archive (
  fund_code VARCHAR(32) NOT NULL,
  fund_name VARCHAR(128) NOT NULL,
  fund_type VARCHAR(32) NULL,
  manager_name VARCHAR(128) NULL,
  custodian_name VARCHAR(128) NULL,
  establish_date DATE NULL,
  currency CHAR(3) NULL,
  fund_status VARCHAR(16) NULL,
  etl_source_file VARCHAR(512) NULL,
  etl_batch_id VARCHAR(64) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (fund_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金基础信息';

CREATE TABLE fund_redemption_rule (
  rule_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  fund_code VARCHAR(32) NOT NULL,
  version_no INT UNSIGNED NOT NULL,
  purchase_status VARCHAR(16) NULL,
  redeem_status VARCHAR(16) NULL,
  min_purchase_amount DECIMAL(18,2) NULL,
  min_additional_purchase_amount DECIMAL(18,2) NULL,
  daily_purchase_limit DECIMAL(18,2) NULL,
  min_redeem_shares DECIMAL(18,4) NULL,
  min_holding_shares DECIMAL(18,4) NULL,
  purchase_fee_rate DECIMAL(10,6) NULL,
  redeem_fee_rate DECIMAL(10,6) NULL,
  purchase_confirm_days SMALLINT UNSIGNED NULL,
  redeem_confirm_days SMALLINT UNSIGNED NULL,
  redeem_arrival_days SMALLINT UNSIGNED NULL,
  effective_date DATE NULL,
  remark VARCHAR(512) NULL,
  source_type VARCHAR(8) NOT NULL,
  etl_batch_id VARCHAR(64) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  active_fund_code VARCHAR(32)
    GENERATED ALWAYS AS (IF(is_deleted = 0, fund_code, NULL)) STORED,
  created_by VARCHAR(64) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  deleted_by VARCHAR(64) NULL,
  deleted_at DATETIME(3) NULL,
  PRIMARY KEY (rule_id),
  UNIQUE KEY uk_fund_version (fund_code, version_no),
  UNIQUE KEY uk_active_source (active_fund_code, source_type),
  KEY idx_fund_history (fund_code, is_deleted, version_no),
  CONSTRAINT fk_rule_fund FOREIGN KEY (fund_code)
    REFERENCES fund_archive (fund_code) ON DELETE RESTRICT,
  CONSTRAINT chk_rule_source CHECK (source_type IN ('ETL', 'MANUAL')),
  CONSTRAINT chk_purchase_status CHECK (
    purchase_status IS NULL OR purchase_status IN ('OPEN', 'CLOSED', 'SUSPENDED')
  ),
  CONSTRAINT chk_redeem_status CHECK (
    redeem_status IS NULL OR redeem_status IN ('OPEN', 'CLOSED', 'SUSPENDED')
  ),
  CONSTRAINT chk_rule_amount CHECK (
    (min_purchase_amount IS NULL OR min_purchase_amount >= 0)
    AND (min_additional_purchase_amount IS NULL OR min_additional_purchase_amount >= 0)
    AND (daily_purchase_limit IS NULL OR daily_purchase_limit >= 0)
    AND (min_redeem_shares IS NULL OR min_redeem_shares >= 0)
    AND (min_holding_shares IS NULL OR min_holding_shares >= 0)
  ),
  CONSTRAINT chk_rule_fee CHECK (
    (purchase_fee_rate IS NULL OR purchase_fee_rate BETWEEN 0 AND 100)
    AND (redeem_fee_rate IS NULL OR redeem_fee_rate BETWEEN 0 AND 100)
  ),
  CONSTRAINT chk_rule_delete CHECK (
    (is_deleted = 0 AND deleted_at IS NULL AND deleted_by IS NULL)
    OR (is_deleted = 1 AND deleted_at IS NOT NULL AND deleted_by IS NOT NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金申赎规则版本';
```

## 4. Query and Priority

详情查询按以下顺序执行：

1. 根据 `fund_code` 读取 `fund_archive`，不存在返回 404。
2. 查询生效 MANUAL 规则；存在则整条返回。
3. 否则查询生效 ETL 规则；存在则整条返回。
4. 两者均无则 `redemption_rule` 为 `null`，页面申赎字段展示 `--`。

可用一条 SQL 取候选记录，后端按优先级取第一条：

```sql
SELECT *
FROM fund_redemption_rule
WHERE fund_code = ? AND is_deleted = 0
  AND source_type IN ('MANUAL', 'ETL')
ORDER BY CASE source_type WHEN 'MANUAL' THEN 1 ELSE 2 END
LIMIT 1;
```

数据库约束确保每个来源最多一条候选记录。禁止将 MANUAL 和 ETL 的字段逐列 `COALESCE` 拼成一条记录。

## 5. API Design

统一前缀：`/api/v1`。时间使用 ISO 8601；金额、份额和费率在 JSON 中使用十进制字符串，避免浮点精度损失；未提供字段为 `null`。

### 5.1 基金档案分页列表

`GET /api/v1/fund-archives?keyword=&page=1&page_size=20`

- `keyword` 可选，匹配基金代码或名称；`page >= 1`，`1 <= page_size <= 100`。
- 返回 `items`、`page`、`page_size`、`total`；列表项仅含基础信息摘要。
- 参数错误返回 400，存储查询失败返回 500。

### 5.2 基金档案详情

`GET /api/v1/fund-archives/{fundCode}`

```json
{
  "basic_info": {
    "fund_code": "000001",
    "fund_name": "示例基金",
    "fund_type": "混合型",
    "manager_name": "示例基金管理有限公司",
    "custodian_name": null,
    "establish_date": "2020-01-02",
    "currency": "CNY",
    "fund_status": "NORMAL"
  },
  "redemption_rule": {
    "rule_id": 12,
    "version_no": 2,
    "source_type": "MANUAL",
    "purchase_status": "OPEN",
    "redeem_status": "OPEN",
    "min_purchase_amount": "100.00",
    "min_additional_purchase_amount": "100.00",
    "daily_purchase_limit": null,
    "min_redeem_shares": "1.0000",
    "min_holding_shares": "0.0000",
    "purchase_fee_rate": "0.150000",
    "redeem_fee_rate": "0.500000",
    "purchase_confirm_days": 1,
    "redeem_confirm_days": 1,
    "redeem_arrival_days": 2,
    "effective_date": "2026-11-21",
    "remark": null
  }
}
```

- 基金不存在返回 404；规则不存在时 `redemption_rule=null`，不是查询异常。
- 响应不返回已归档记录；本期历史仅通过数据库审计查询。

### 5.3 保存申赎要素

`PUT /api/v1/fund-archives/{fundCode}/redemption-rule`

请求采用完整规则替换语义：

```json
{
  "expected_rule_id": 10,
  "expected_version_no": 1,
  "purchase_status": "OPEN",
  "redeem_status": "OPEN",
  "min_purchase_amount": "100.00",
  "min_additional_purchase_amount": "100.00",
  "daily_purchase_limit": null,
  "min_redeem_shares": "1.0000",
  "min_holding_shares": "0.0000",
  "purchase_fee_rate": "0.150000",
  "redeem_fee_rate": "0.500000",
  "purchase_confirm_days": 1,
  "redeem_confirm_days": 1,
  "redeem_arrival_days": 2,
  "effective_date": "2026-11-21",
  "remark": "人工维护"
}
```

- 已有当前规则时，`expected_rule_id` 和 `expected_version_no` 必须等于详情返回值。
- 首次创建时两者分别为 `null` 和 `0`。
- 操作人从登录态获取，忽略并拒绝请求体中的 `created_by`、`source_type`、`is_deleted` 等受控字段。
- 成功返回 200 及最新详情；字段错误 400；基金不存在 404；版本冲突 409；数据库异常 500。
- 错误响应结构：`{"code":"VERSION_CONFLICT","message":"申赎要素已更新，请刷新后重试","field_errors":{}}`。

### 5.4 Server-side Validation

| 字段 | 规则 |
| --- | --- |
| 金额、份额 | 可空；非空时必须是合法十进制且 >= 0，小数位不得超过表定义 |
| 费率 | 可空；非空时 0～100，最多 6 位小数 |
| 天数 | 可空；非空时为 0～32767 的整数 |
| 申购/赎回状态 | 可空；非空时仅允许 `OPEN`、`CLOSED`、`SUSPENDED` |
| 生效日期 | 可空；非空时必须是合法 `YYYY-MM-DD` |
| 备注 | 可空；去除首尾空白后最长 512 字符，空串归一为 NULL |
| 基金代码 | 路径必填，去除首尾空白后匹配已存在基金 |

## 6. Edit Transaction and Concurrency

保存事务 MUST 按以下顺序执行：

1. 开启事务，`SELECT fund_code FROM fund_archive WHERE fund_code=? FOR UPDATE` 锁定基金主记录；不存在则回滚并返回 404。该锁串行化同基金编辑与 ETL 规则写入。
2. 按第 4 节逻辑取得当前生效规则，核对 `expected_rule_id` 和 `expected_version_no`；不一致则回滚并返回 409。
3. 若存在当前生效记录，仅更新该记录的 `is_deleted=1`、`deleted_at`、`deleted_by`。若当前为 ETL，归档的是当前生效 ETL 记录；若当前为 MANUAL，归档旧人工版本。
4. 计算 `version_no = 当前基金最大 version_no + 1`（无记录时为 1），插入 `source_type=MANUAL`、`is_deleted=0` 的完整新记录，操作人来自登录态。
5. 提交事务后返回最新详情。任一步失败均回滚；唯一键冲突映射为 409，不能返回模糊成功。

ETL 写入同一基金时也先锁基金主记录：归档旧生效 ETL、插入新 ETL，使用新的基金级版本号，但绝不更新或归档 MANUAL。ETL 归档旧 ETL 记录时，MUST 在同一事务内设置 `is_deleted=1`，并将 `deleted_by` 填充为明确的 ETL 系统账号、`deleted_at` 填充为本次事务归档时间，两个审计字段均不得为 NULL。若人工编辑曾归档旧 ETL，后续 ETL 可插入新 ETL；因 MANUAL 优先，页面仍显示人工规则。

## 7. Frontend Behavior

- 「基金档案」Tab 包含基金选择/检索区、基础信息区块、申赎要素区块；申赎区块提供查看与编辑状态。
- 编辑表单展示数据类型和费率单位；保存按钮在请求中禁用，避免重复提交。
- 保存成功后以响应刷新当前版本；409 时提示刷新，不自动覆盖服务端新数据。
- 每次查询使用请求序号或取消机制，只接收当前基金最新请求结果，防止快速切换时串数据。
- 展示函数仅将 `null`、`undefined`、去除空白后的空字符串格式化为 `--`；`0` 和 `false` 正常展示。
- 查询失败时清空旧基金数据、保留区块、显示 `--`、错误提示和重试按钮；保存失败保留表单值。

## 8. ETL Contract

- 基金主数据 ETL 对 `fund_archive` 做幂等 upsert，记录来源文件和批次；不把未知值写成字符串 `--`。
- 申赎 ETL 仅生成 `source_type=ETL` 的版本，不更新人工行；同一批次重复执行需以“源文件 + 基金代码 + 内容哈希/批次幂等键”避免重复生成相同版本。
- 本变更不要求改造行情、事件、舆情、研报 ETL，也不改变 ClickHouse 或 MinIO 既有 DDL/对象布局。

## 9. Testability and Observability

- 后端记录基金代码、旧/新 `rule_id`、版本、来源、操作人和结果，不记录数据库或 MinIO 凭据。
- 集成测试必须使用真实 MySQL 约束验证软删除、唯一生效、回滚与并发冲突，不能只依赖 mock。
- 前端测试覆盖空值、零值、异常、旧响应覆盖、新提交冲突；ETL 测试覆盖“人工记录不被覆盖”。
