"""衍生指标 ETL：指标集1_数据.xlsx（31 个 sheet，宽表转长表） -> ClickHouse ods_indicator。

同时把每个 sheet/序列的元数据写入 MySQL dim_indicator。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from config.config import DATA_DIR
from scripts.common import etl_utils as U
from scripts.common.db import get_ch_client, get_mysql_conn, log_batch, mysql_executemany, new_batch_id, upsert_data_source
from scripts.common.logging_utils import get_logger

log = get_logger("indicator")
TASK = "etl_indicator"
TARGET = "ods_indicator"
FILE_REL = "指标集1_数据.xlsx"

ODS_COLS = ["indicator_code", "sheet_code", "seq_name", "trade_date",
            "value", "source_file", "batch_id"]

DIM_SQL = (
    "INSERT INTO dim_indicator "
    "(source_file, sheet_code, seq_name, start_date, end_date, row_count, remark, batch_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
    "ON DUPLICATE KEY UPDATE start_date=VALUES(start_date), end_date=VALUES(end_date), "
    "row_count=VALUES(row_count), remark=VALUES(remark), batch_id=VALUES(batch_id)"
)


def run(batch_id: str | None = None) -> int:
    batch_id = batch_id or new_batch_id()
    start = datetime.now()
    log_batch(batch_id, TASK, target_table=TARGET, status="running", start_time=start)

    path = DATA_DIR / FILE_REL
    rel = U.relpath_under_data(path)
    sheets = U.read_excel_sheets(path)
    client = get_ch_client()

    total_raw = total_loaded = 0
    dim_rows = []
    for sheet_name, df in sheets.items():
        if df.empty or "日期" not in df.columns:
            log.warning(f"  skip sheet {sheet_name}: no 日期 column")
            continue
        data_cols = [c for c in df.columns if c != "日期"]
        for col in data_cols:
            sub = df[["日期", col]].copy()
            sub = sub.dropna(subset=["日期"])
            raw = len(sub)
            dates = sub["日期"].apply(U.parse_date)
            vals = sub[col].apply(U.safe_float)
            valid = dates.notna()
            rows = [
                (f"{sheet_name}_{col}", sheet_name, str(col), d, v, rel, batch_id)
                for d, v in zip(dates[valid], vals[valid])
            ]
            if rows:
                U.ch_insert_rows(client, "ods_indicator", ODS_COLS, rows)
            total_raw += raw
            total_loaded += len(rows)
            # 元数据
            dseries = pd.to_datetime(sub["日期"], errors="coerce").dropna()
            dim_rows.append((
                rel, sheet_name, str(col),
                dseries.min().date() if len(dseries) else None,
                dseries.max().date() if len(dseries) else None,
                raw, "宽表转长表，序列业务口径待补充", batch_id,
            ))
            log.info(f"  {sheet_name}/{col}: raw={raw} loaded={len(rows)}")

    if dim_rows:
        mysql_executemany(get_mysql_conn(), DIM_SQL, dim_rows)

    upsert_data_source(
        "指标", rel, path.name, "xlsx",
        raw_rows=total_raw, target_table=TARGET,
        status="loaded" if total_loaded else "failed", loaded_rows=total_loaded,
    )
    log_batch(batch_id, TASK, target_table=TARGET,
              raw_rows=total_raw, loaded_rows=total_loaded,
              failed_rows=total_raw - total_loaded,
              status="success", start_time=start, end_time=datetime.now())
    log.info(f"[{TASK}] done raw={total_raw} loaded={total_loaded}")
    return total_loaded


if __name__ == "__main__":
    run()
