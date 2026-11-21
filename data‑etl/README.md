# data-etl — 国元证券 TRAE 金科竞赛数据入库模块

将 `./data` 下的原始竞赛数据清洗转换，分层入库到 **MySQL（元数据）**、**ClickHouse（时序明细）**、**MinIO（研报正文）**。

## 分工约定

| 角色 | 机器 | 职责 |
| --- | --- | --- |
| 开发 | 任意（无需 Docker） | 编写 SQL / ETL 脚本 / 校验脚本 / 数据字典，本地做**静态校验**（`py_compile`、`import`），不执行真实入库 |
| 部署执行 | 具备 Docker 的机器 | 拉取代码 → 配置 `.env` → `docker compose up -d` → 放置 `./data` → 运行 ETL → 运行校验 |

> 原始数据 `./data` **不提交仓库**，由执行方自行放置到项目根目录。

## 目录结构

```
data-etl/
├── config/
│   ├── config.yaml        # 非敏感默认值（host/port/库名），密码留空
│   └── config.py          # 配置加载：.env > 环境变量 > config.yaml；路径基于 __file__，不依赖 cwd
├── sql/
│   ├── 01_mysql_ddl.sql   # MySQL 元数据层建表（dim_asset / dim_indicator / report_index / data_source / etl_batch_log）
│   └── 02_clickhouse_ddl.sql  # ClickHouse 分层建表（ODS / DWD / DWS）
├── scripts/
│   ├── common/            # 公共模块：db 连接工厂、etl_utils、日志
│   ├── etl_dim_asset.py          # 代码对照.csv -> MySQL dim_asset
│   ├── etl_market_price.py       # 39 个行情 csv -> ods_market_price / dwd
│   ├── etl_indicator.py          # 指标集 xlsx -> ods_indicator + dim_indicator
│   ├── etl_event_calendar.py     # 日历 xlsx -> ods/dwd_event_calendar
│   ├── etl_news_cailianpress.py  # 新闻/无标题.csv -> ods + dwd_news_unified
│   ├── etl_twitter.py            # 科技.csv -> ods_twitter + dwd_news_unified
│   ├── etl_wechat.py             # 公众号.xlsx -> ods_wechat_article + dwd
│   ├── etl_futures_turnover.py   # 商品期货日成交额 -> ods_futures_turnover
│   ├── etl_report_minio.py       # 研报 zip -> MinIO + MySQL report_index
│   └── run_all.py                # 一键编排：顺序执行全部 ETL + 刷新 DWS
├── docs/
│   └── 数据字典.md        # 全部原始文件 + 17 张表的来源/字段/业务口径 + 预期行数
├── test/
│   └── verify_rowcount.py # 入库校验：原始行数 vs DB 入库行数
└── requirements.txt
```

## 快速开始（执行机）

```bash
# 0. 依赖
pip install -r data-etl/requirements.txt

# 1. 配置账号密码（.env 已在 .gitignore 中忽略，不会提交）
cp .env.example .env
#    编辑 .env，至少修改 MYSQL_PASSWORD / CLICKHOUSE_PASSWORD / MINIO_SECRET_KEY

# 2. 放置原始数据（不提交仓库）
#    确保项目根目录存在 ./data，内含 目标资产价格变量/、指标集1_数据.xlsx、新闻/ 等

# 3. 启动中间件（首次启动自动执行 data-etl/sql 下的建库建表脚本）
docker compose -f docker‑compose/docker-compose.yml --env-file .env up -d
docker compose -f docker‑compose/docker-compose.yml ps    # 等待 mysql/clickhouse 变为 healthy

# 4. 执行 ETL（任意目录均可，脚本基于 __file__ 定位 ../data）
python data-etl/scripts/run_all.py

# 5. 核对行数（存在丢数据时退出码为 1）
python data-etl/test/verify_rowcount.py
```

## 配置说明

优先级：**进程环境变量 > 项目根 `.env` > `config/config.yaml`**。

`.env.example` 提供了全部可配置项（MySQL / ClickHouse / MinIO 的 host、port、user、库名、密码）。
只改密码时也可不建 `.env`，直接注入环境变量：

```bash
# Windows PowerShell
$env:MYSQL_PASSWORD="..."; $env:CLICKHOUSE_PASSWORD="..."; $env:MINIO_SECRET_KEY="..."
```

端口约定（见 [docker-compose.yml](../docker‑compose/docker-compose.yml)）：

| 服务 | 宿主机端口 | 说明 |
| --- | --- | --- |
| MySQL | 3306 | |
| ClickHouse | 8123 / 9000 | 9000 为 native 协议，`clickhouse-driver` 使用 |
| MinIO | 9002 / 9003 | 9002 为 S3 API，9003 为控制台（避免与 ClickHouse 9000 冲突） |

## 手动建表（不使用 docker compose 时）

```bash
mysql -h 127.0.0.1 -u root -p < data-etl/sql/01_mysql_ddl.sql
clickhouse-client --multiquery < data-etl/sql/02_clickhouse_ddl.sql
```

> DDL 使用 `DROP TABLE IF EXISTS`，属于**重建式**初始化：重复执行会清空已有数据。
> 容器自动初始化只在数据卷为空时触发一次；需重置时执行 `docker compose ... down -v` 再 `up -d`。

## 运行

```bash
# 一键执行全部 ETL
python data-etl/scripts/run_all.py

# 或单独执行某个任务
python data-etl/scripts/etl_market_price.py
```

`run_all.py` 用同一批次号顺序执行 9 个任务，最后刷新 ClickHouse DWS 汇总层；单个任务失败不中断整体，失败原因写入 `etl_batch_log`。

## 入库校验

```bash
python data-etl/test/verify_rowcount.py
```

输出逐文件（原始行数 vs 入库行数）与表级（`count(*)` vs 源合计）对比。

## 约定

- 全部使用相对路径：脚本通过 `Path(__file__)` 定位 `../data`，不依赖运行时工作目录，也不出现本机绝对路径。
- 研报正文不入库：md 文件上传 MinIO（bucket `research-reports`，脚本自动创建），MySQL `report_index` 仅保存对象路径索引。
- 敏感信息只放 `.env`：`config.yaml` 中密码字段保持空串，仓库内不含任何明文密码。
- 原始数据不提交 git：`data/`、`.env` 已在 `.gitignore` 忽略，只提交代码、SQL、文档。
