"""行情价格 ETL：目标资产价格变量/*.csv -> ClickHouse ods_market_price / dwd_market_price_daily。

覆盖文件：目标资产价格变量/ 下 39 个价格时序 csv + 代码对照.csv（元数据）。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # data-etl

from config.config import DATA_DIR
from scripts.common import etl_utils as U
from scripts.common.db import get_ch_client, log_batch, new_batch_id, upsert_data_source
from scripts.common.logging_utils import get_logger

log = get_logger("market_price")
TASK = "etl_market_price"
TARGETS = "ods_market_price,dwd_market_price_daily"
DATA_SUBDIR = "目标资产价格变量"
META_FILE = "代码对照.csv"

ODS_COLS = ["asset_code", "asset_name", "category", "field_type",
            "trade_date", "value", "source_file", "batch_id"]


def run(batch_id: str | None = None) -> int:
    batch_id = batch_id or new_batch_id()
    start = datetime.now()
    log_batch(batch_id, TASK, target_table=TARGETS, status="running", start_time=start)

    base = DATA_DIR / DATA_SUBDIR
    meta_df = U.read_csv_auto(base / META_FILE)
    name_map = {str(r["名称"]).strip(): r for _, r in meta_df.iterrows()}

    price_files = sorted(p for p in base.glob("*.csv") if p.name != META_FILE)
    client = get_ch_client()

    total_raw = total_loaded = 0
    for f in price_files:
        rel = U.relpath_under_data(f)
        df = U.read_csv_auto(f)
        raw = len(df)
        val_col = df.columns[1] if len(df.columns) > 1 else None

        name = f.stem
        meta_row = name_map.get(name, {})
        category = str(meta_row.get("大类", "")).strip() or "未分类"
        field_type = str(meta_row.get("字段", "")).strip() or (val_col or "value")
        wind_code = str(meta_row.get("Wind代码", "")).strip() or name

        rows = []
        for _, r in df.iterrows():
            d = U.parse_date(r.get("date"))
            v = U.safe_float(r.get(val_col)) if val_col else None
            if d is None:
                continue
            rows.append((wind_code, name, category, field_type, d, v, rel, batch_id))

        if rows:
            U.ch_insert_rows(client, "ods_market_price", ODS_COLS, rows)
            U.ch_insert_rows(client, "dwd_market_price_daily", ODS_COLS, rows)
        loaded = len(rows)
        total_raw += raw
        total_loaded += loaded
        upsert_data_source(
            "行情", rel, f.name, "csv",
            raw_rows=raw, target_table=TARGETS,
            status="loaded" if loaded else "failed", loaded_rows=loaded,
        )
        log.info(f"  {f.name}: raw={raw} loaded={loaded}")

    # 元数据文件登记（实际入 dim_asset 由 etl_dim_asset 完成）
    rel_meta = U.relpath_under_data(base / META_FILE)
    upsert_data_source(
        "行情", rel_meta, META_FILE, "csv",
        raw_rows=len(meta_df), target_table="dim_asset(MySQL)",
        status="loaded", loaded_rows=len(meta_df),
    )

    log_batch(batch_id, TASK, target_table=TARGETS,
              raw_rows=total_raw, loaded_rows=total_loaded,
              failed_rows=total_raw - total_loaded,
              status="success", start_time=start, end_time=datetime.now())
    log.info(f"[{TASK}] done raw={total_raw} loaded={total_loaded}")
    return total_loaded


if __name__ == "__main__":
    run()
