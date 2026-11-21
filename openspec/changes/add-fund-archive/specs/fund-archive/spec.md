# Delta Spec: fund-archive

## ADDED Requirements

### Requirement: 基金档案页签与信息区块

系统 SHALL 提供「基金档案」Tab，并在基金详情中同时提供「基础信息」和「申赎要素」两个区块。基础信息至少包含基金代码、基金名称、基金类型、管理人、托管人、成立日期、币种和基金状态；申赎要素至少包含申购/赎回状态、金额与份额限制、申赎费率、确认/到账天数、生效日期及备注。

#### Scenario: AC-01 打开基金档案

- **Given** 基金 `000001` 已有基础信息和申赎要素
- **When** 用户进入「基金档案」Tab 并选择 `000001`
- **Then** 页面展示基础信息和申赎要素两个区块
- **And** 展示值与当前生效记录一致
- **And** 页面展示申赎要素来源 `MANUAL` 或 `ETL`、版本号及生效日期

#### Scenario: AC-02 无申赎要素的基金

- **Given** 基金 `000002` 仅有基础信息，没有任何申赎规则记录
- **When** 用户查询该基金档案
- **Then** 基础信息正常展示
- **And** 申赎要素各业务字段展示 `--`
- **And** 用户仍可进入新增首条人工规则的编辑流程

### Requirement: 人工数据优先于 ETL 数据

系统 SHALL 分别保留 `MANUAL` 与 `ETL` 来源的申赎规则，并按 `MANUAL > ETL` 选择唯一生效结果。ETL 重跑 SHALL NOT 修改、归档或删除人工记录。

#### Scenario: AC-03 人工值覆盖 ETL 值

- **Given** 基金 `000001` 存在生效 ETL 规则，申购起点为 1000 元
- **And** 存在生效 MANUAL 规则，申购起点为 100 元
- **When** 查询基金档案
- **Then** 申购起点展示 100 元
- **And** 来源展示 `MANUAL`
- **And** 其余字段全部取该条 MANUAL 规则，不与 ETL 记录逐字段拼接

#### Scenario: AC-04 无人工值及 ETL 重跑

- **Given** 基金 `000003` 只有 ETL 规则，没有 MANUAL 规则
- **When** ETL 产生新版规则并再次查询
- **Then** 页面展示最新生效 ETL 规则，来源为 `ETL`
- **When** 该基金已存在 MANUAL 规则后再次运行 ETL
- **Then** 页面仍展示 MANUAL 规则
- **And** ETL 仅更新其自身来源的记录，MANUAL 记录保持不变

### Requirement: 申赎要素编辑与软删除归档

用户 SHALL 能编辑申赎要素。保存时系统 MUST 在同一数据库事务内将当前生效记录软删除归档，并插入一条新的 `MANUAL` 生效记录；版本号按基金递增，历史记录 MUST NOT 被物理删除。

#### Scenario: AC-05 首次编辑 ETL 规则

- **Given** 基金 `000001` 当前仅有一条 `rule_id=10`、`version_no=1` 的生效 ETL 规则
- **When** 用户以 `expected_rule_id=10` 提交合法修改
- **Then** `rule_id=10` 的 `is_deleted` 变为 1
- **And** 被归档的 `rule_id=10` 记录的 `deleted_by`、`deleted_at` 必须被赋值，分别为当前操作人和本次事务归档时间，且均不得为 NULL
- **And** 插入 `source_type=MANUAL`、`version_no=2`、`is_deleted=0` 的新记录
- **And** 查询结果使用新人工记录

#### Scenario: AC-06 连续编辑保留完整历史

- **Given** 基金已有一版生效 MANUAL 规则及若干历史规则
- **When** 用户再次保存申赎要素
- **Then** 旧 MANUAL 生效记录被软删除，新 MANUAL 记录成为唯一生效人工记录
- **And** 该基金版本号连续递增
- **And** 所有历史字段值、来源、创建人、归档人和时间戳仍可查询

#### Scenario: AC-07 保存失败整体回滚

- **Given** 用户提交一次合法编辑，但插入新记录时数据库发生异常
- **When** 保存接口返回失败
- **Then** 旧记录仍保持原生效状态
- **And** 不产生新的半条记录
- **And** 页面保留用户已填写内容并提示保存失败

### Requirement: 编辑校验与并发保护

系统 SHALL 在服务端校验基金存在性、字段类型、必填项、数值范围、日期和操作人，并使用客户端提交的当前记录标识与版本号检测并发冲突。校验规则 SHALL 与 [design.md](../../design.md) 一致。

#### Scenario: AC-08 拒绝非法申赎要素

- **Given** 用户将申购起点填写为负数，或将申购状态填写为未定义值
- **When** 提交保存
- **Then** 接口返回 HTTP 400 和明确的字段错误
- **And** 数据库无任何变更

#### Scenario: AC-09 防止并发覆盖

- **Given** 两个用户都基于 `rule_id=20、version_no=3` 打开编辑页
- **When** 第一个用户保存成功后，第二个用户仍提交旧版本
- **Then** 第二次请求返回 HTTP 409
- **And** 第二次请求不归档或插入任何记录
- **And** 页面提示数据已更新并允许用户刷新后重新编辑

### Requirement: 空值与查询异常兜底

前端 SHALL 将接口成功响应中的 `null`、空字符串以及查询请求异常所涉及的字段展示为 `--`。前端 SHALL NOT 将数值 `0`、布尔 `false` 当作空值，也 SHALL NOT 将查询异常伪装为成功响应。

#### Scenario: AC-10 成功响应中的空值与零值

- **Given** 查询成功，托管人为 `null`、备注为空字符串、最低赎回份额为 `0`
- **When** 页面渲染
- **Then** 托管人和备注展示 `--`
- **And** 最低赎回份额展示 `0`

#### Scenario: AC-11 查询接口异常

- **Given** 基金详情接口超时或返回 HTTP 500
- **When** 页面捕获查询异常
- **Then** 页面保留基金档案 Tab 和两个信息区块的结构
- **And** 无法取得的字段展示 `--`
- **And** 页面提供明确的加载失败提示及重试入口
- **And** 不展示上次其他基金的数据

### Requirement: 数据存储边界与访问路径

基金基础信息和申赎规则 SHALL 存储于 MySQL `gy_meta`；行情、事件、舆情时序数据 SHALL 存储于 ClickHouse `gy_dw`；研报文档 SHALL 存储于 MinIO `research-reports`，MySQL 仅保存其对象索引。前端 SHALL 仅通过后端 API 获取数据。

#### Scenario: AC-12 基金档案不串用存储

- **Given** 用户查询或保存基金档案
- **When** 后端处理请求
- **Then** 基础信息与申赎规则仅读写 MySQL
- **And** 不把申赎规则写入 ClickHouse 或 MinIO
- **And** 不在基金档案查询关键路径中查询研报正文、行情、事件或舆情

#### Scenario: AC-13 存储访问受控

- **Given** 对前端交付物和后端实现进行审查
- **When** 检查数据库及对象存储访问方式
- **Then** 前端不包含 MySQL、ClickHouse、MinIO 连接信息或凭据
- **And** ClickHouse 与 MinIO 的既有用途和连接配置不因本变更而改变

### Requirement: 首次新增人工申赎规则

系统 SHALL 支持已存在基金在完全没有申赎规则记录时直接创建首条 MANUAL 规则。首次新增 MUST NOT 归档任何记录，并 MUST 从版本 1 开始建立人工生效记录。

#### Scenario: AC-14 无申赎记录首次新增 MANUAL 规则

- **Given** 基金 `000004` 已存在于 `fund_archive`，且没有任何申赎规则记录
- **And** 用户已填写合法、完整的申赎要素
- **When** 用户以 `expected_rule_id=null`、`expected_version_no=0` 提交保存
- **Then** 系统不归档或软删除任何旧记录
- **And** 插入 `source_type=MANUAL`、`version_no=1`、`is_deleted=0` 的新记录
- **And** 新记录的 `created_by`、`created_at` 分别赋值为当前操作人和创建时间，`deleted_by`、`deleted_at` 均为 NULL
- **And** 保存后查询返回该 MANUAL 规则，页面展示来源 `MANUAL` 和版本号 1
- **And** `fund_archive.updated_at` 保持原值，不因本次申赎规则新增而变化
