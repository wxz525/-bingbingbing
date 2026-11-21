"""商品期货日成交额 ETL：商品期货日成交额.xlsx -> ClickHouse ods_futures_turnover。"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config import DATA_DIR
from scripts.common import etl_utils as U
from scripts.common.db import get_ch_client, log_batch, new_batch_id, upsert_data_source
from scripts.common.logging_utils import get_logger

log = get_logger("futures_turnover")
TASK = "etl_futures_turnover"
TARGET = "ods_futures_turnover"
FILE_REL = "商品期货日成交额.xlsx"

ODS_COLS = ["trade_date", "turnover", "source_file", "batch_id"]
EPOCH = date(1970, 1, 1)


def run(batch_id: str | None = None) -> int:
    batch_id = batch_id or new_batch_id()
    start = datetime.now()
    log_batch(batch_id, TASK, target_table=TARGET, status="running", start_time=start)

    path = DATA_DIR / FILE_REL
    rel = U.relpath_under_data(path)
    sheets = U.read_excel_sheets(path)
    df = next(iter(sheets.values()))
    raw = len(df)

    client = get_ch_client()
    rows = []
    for r in df.itertuples(index=False):
        vals = list(r)
        d = U.parse_date(vals[0]) or EPOCH
        v = U.safe_float(vals[1] if len(vals) > 1 else None)
        rows.append((d, v if v is not None else 0.0, rel, batch_id))

    if rows:
        U.ch_insert_rows(client, TARGET, ODS_COLS, rows)
    loaded = len(rows)

    upsert_data_source(
        "成交", rel, path.name, "xlsx",
        raw_rows=raw, target_table=TARGET,
        status="loaded" if loaded else "failed", loaded_rows=loaded,
    )
    log_batch(batch_id, TASK, target_table=TARGET,
              raw_rows=raw, loaded_rows=loaded, failed_rows=raw - loaded,
              status="success", start_time=start, end_time=datetime.now())
    log.info(f"[{TASK}] done raw={raw} loaded={loaded}")
    return loaded


if __name__ == "__main__":
    run()
