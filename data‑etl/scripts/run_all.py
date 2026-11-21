"""一键编排：按依赖顺序执行全部 ETL，完成后刷新 ClickHouse DWS 汇总层。

用法（在项目根或任意目录）：
    python data-etl/scripts/run_all.py

前置：
    1. 已执行 sql/01_mysql_ddl.sql 与 sql/02_clickhouse_ddl.sql 建表；
    2. 已设置环境变量 MYSQL_PASSWORD / CLICKHOUSE_PASSWORD / MINIO_SECRET_KEY；
    3. pip install -r data-etl/requirements.txt。
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # data-etl

from scripts.common.db import get_ch_client, log_batch, new_batch_id
from scripts.common.logging_utils import get_logger

import scripts.etl_dim_asset as m_dim
import scripts.etl_market_price as m_price
import scripts.etl_indicator as m_indicator
import scripts.etl_event_calendar as m_event
import scripts.etl_news_cailianpress as m_news
import scripts.etl_twitter as m_twitter
import scripts.etl_wechat as m_wechat
import scripts.etl_futures_turnover as m_futures
import scripts.etl_report_minio as m_report

log = get_logger("run_all")

# 执行顺序：先元数据，再事实数据，最后文件入库
TASKS = [
    ("etl_dim_asset", m_dim, "dim_asset(MySQL)"),
    ("etl_market_price", m_price, "ods_market_price,dwd_market_price_daily"),
    ("etl_indicator", m_indicator, "ods_indicator,dim_indicator(MySQL)"),
    ("etl_event_calendar", m_event, "ods_event_calendar,dwd_event_calendar"),
    ("etl_news_cailianpress", m_news, "ods_news_cailianpress,dwd_news_unified"),
    ("etl_twitter", m_twitter, "ods_twitter,dwd_news_unified"),
    ("etl_wechat", m_wechat, "ods_wechat_article,dwd_news_unified"),
    ("etl_futures_turnover", m_futures, "ods_futures_turnover"),
    ("etl_report_minio", m_report, "MinIO+report_index"),
]


def refresh_dws() -> None:
    """ETL 完成后刷新 DWS 汇总层（幂等：TRUNCATE + INSERT SELECT）。"""
    client = get_ch_client()
    client.execute("TRUNCATE TABLE dws_news_count_daily")
    client.execute(
        "INSERT INTO dws_news_count_daily "
        "SELECT publish_date, source_type, count() AS news_cnt "
        "FROM dwd_news_unified GROUP BY publish_date, source_type"
    )
    client.execute("TRUNCATE TABLE dws_market_asset_stats")
    client.execute(
        "INSERT INTO dws_market_asset_stats "
        "SELECT asset_code, any(asset_name), any(category), any(field_type), "
        "min(trade_date), max(trade_date), count(), argMax(value, trade_date) "
        "FROM dwd_market_price_daily GROUP BY asset_code"
    )
    log.info("DWS 汇总层刷新完成")


def main() -> None:
    batch_id = new_batch_id()
    log.info(f"===== run_all 启动 batch={batch_id} =====")
    results = []
    for name, mod, target in TASKS:
        try:
            n = mod.run(batch_id=batch_id)
            results.append((name, "success", n))
        except Exception as e:  # 单个任务失败不中断整体
            msg = str(e)[:1000]
            log.error(f"{name} 失败: {e}\n{traceback.format_exc()}")
            log_batch(batch_id, name, target_table=target, status="failed",
                      message=msg, start_time=datetime.now(), end_time=datetime.now())
            results.append((name, "failed", 0))

    try:
        refresh_dws()
    except Exception as e:
        log.error(f"刷新 DWS 失败: {e}")

    log.info("===== run_all 汇总 =====")
    ok = sum(1 for _, s, _ in results if s == "success")
    for name, status, n in results:
        log.info(f"  {name}: {status} (loaded={n})")
    log.info(f"成功 {ok}/{len(results)} 个任务，批次 {batch_id}")


if __name__ == "__main__":
    main()
