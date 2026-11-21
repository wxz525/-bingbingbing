"""事件日历 ETL：日历数据.xlsx -> ClickHouse ods_event_calendar / dwd_event_calendar。"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from config.config import DATA_DIR
from scripts.common import etl_utils as U
from scripts.common.db import get_ch_client, log_batch, new_batch_id, upsert_data_source
from scripts.common.logging_utils import get_logger

log = get_logger("event_calendar")
TASK = "etl_event_calendar"
TARGETS = "ods_event_calendar,dwd_event_calendar"
FILE_REL = "日历数据.xlsx"

ODS_COLS = ["indicator_name", "occur_date", "occur_time", "home_country",
            "indicator_former", "indicator_forecast", "indicator_fact",
            "source_file", "batch_id"]
DWD_COLS = ["indicator_name", "occur_date", "occur_time", "home_country",
            "indicator_former", "indicator_forecast", "indicator_fact",
            "batch_id"]


def run(batch_id: str | None = None) -> int:
    batch_id = batch_id or new_batch_id()
    start = datetime.now()
    log_batch(batch_id, TASK, target_table=TARGETS, status="running", start_time=start)

    path = DATA_DIR / FILE_REL
    rel = U.relpath_under_data(path)
    df = U.read_excel_sheets(path)
    # 默认取第一个 sheet
    sheet_name = next(iter(df))
    df = df[sheet_name]
    raw = len(df)

    client = get_ch_client()
    rows_ods, rows_dwd = [], []
    for _, r in df.iterrows():
        d = U.parse_date(r.get("OccurDate"))
        if d is None:
            continue
        ods = (
            U.clean_text(r.get("IndicatorName")), d, U.clean_text(r.get("OccurTime")),
            U.clean_text(r.get("HomeCountry")),
            U.safe_float(r.get("IndicatorFormer")),
            U.safe_float(r.get("IndicatorForecast")),
            U.safe_float(r.get("IndicatorFact")),
            rel, batch_id,
        )
        rows_ods.append(ods)
        rows_dwd.append(ods[:7] + (batch_id,))

    if rows_ods:
        U.ch_insert_rows(client, "ods_event_calendar", ODS_COLS, rows_ods)
        U.ch_insert_rows(client, "dwd_event_calendar", DWD_COLS, rows_dwd)
    loaded = len(rows_ods)

    upsert_data_source(
        "日历", rel, path.name, "xlsx",
        raw_rows=raw, target_table=TARGETS,
        status="loaded" if loaded else "failed", loaded_rows=loaded,
    )
    log_batch(batch_id, TASK, target_table=TARGETS,
              raw_rows=raw, loaded_rows=loaded, failed_rows=raw - loaded,
              status="success", start_time=start, end_time=datetime.now())
    log.info(f"[{TASK}] done raw={raw} loaded={loaded}")
    return loaded


if __name__ == "__main__":
    run()
