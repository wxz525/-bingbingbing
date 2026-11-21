"""资产元数据 ETL：目标资产价格变量/代码对照.csv -> MySQL dim_asset。"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config import DATA_DIR
from scripts.common import etl_utils as U
from scripts.common.db import get_mysql_conn, log_batch, mysql_executemany, new_batch_id, upsert_data_source
from scripts.common.logging_utils import get_logger

log = get_logger("dim_asset")
TASK = "etl_dim_asset"
TARGET = "dim_asset"
FILE_REL = "目标资产价格变量/代码对照.csv"

SQL = (
    "INSERT INTO dim_asset "
    "(category, name, wind_code, field_type, trade_calendar, start_date, "
    " end_date, row_count, status, remark, source_file, batch_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
    "ON DUPLICATE KEY UPDATE category=VALUES(category), wind_code=VALUES(wind_code), "
    "field_type=VALUES(field_type), trade_calendar=VALUES(trade_calendar), "
    "start_date=VALUES(start_date), end_date=VALUES(end_date), row_count=VALUES(row_count), "
    "status=VALUES(status), remark=VALUES(remark), source_file=VALUES(source_file), "
    "batch_id=VALUES(batch_id)"
)


def run(batch_id: str | None = None) -> int:
    batch_id = batch_id or new_batch_id()
    start = datetime.now()
    log_batch(batch_id, TASK, target_table=TARGET, status="running", start_time=start)

    path = DATA_DIR / FILE_REL
    rel = U.relpath_under_data(path)
    df = U.read_csv_auto(path)
    raw = len(df)

    rows = []
    for _, r in df.iterrows():
        rows.append((
            U.clean_text(r.get("大类")),
            U.clean_text(r.get("名称")),
            U.clean_text(r.get("Wind代码")) or None,
            U.clean_text(r.get("字段")) or None,
            U.clean_text(r.get("交易日历")) or None,
            U.parse_date(r.get("起始")),
            U.parse_date(r.get("结束")),
            int(r.get("条数")) if str(r.get("条数")).isdigit() else None,
            U.clean_text(r.get("状态")) or None,
            U.clean_text(r.get("备注")) or None,
            rel, batch_id,
        ))

    if rows:
        mysql_executemany(get_mysql_conn(), SQL, rows)
    loaded = len(rows)

    upsert_data_source(
        "行情", rel, path.name, "csv",
        raw_rows=raw, target_table=TARGET,
        status="loaded" if loaded else "failed", loaded_rows=loaded,
        remark="资产元数据，入 MySQL dim_asset",
    )
    log_batch(batch_id, TASK, target_table=TARGET,
              raw_rows=raw, loaded_rows=loaded, failed_rows=raw - loaded,
              status="success", start_time=start, end_time=datetime.now())
    log.info(f"[{TASK}] done raw={raw} loaded={loaded}")
    return loaded


if __name__ == "__main__":
    run()
