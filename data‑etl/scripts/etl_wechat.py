"""公众号文章 ETL：公众号.xlsx -> ClickHouse ods_wechat_article + dwd_news_unified。"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config import DATA_DIR
from scripts.common import etl_utils as U
from scripts.common.db import get_ch_client, log_batch, new_batch_id, upsert_data_source
from scripts.common.logging_utils import get_logger

log = get_logger("wechat")
TASK = "etl_wechat"
TARGETS = "ods_wechat_article,dwd_news_unified"
FILE_REL = "公众号.xlsx"

ODS_COLS = ["publish_date", "url", "title", "related_party",
            "source_file", "batch_id"]
DWD_COLS = ["news_id", "source_type", "title", "content", "publish_date",
            "publish_ts", "stock_codes", "raw_url", "batch_id"]

EPOCH = date(1970, 1, 1)


def run(batch_id: str | None = None) -> int:
    batch_id = batch_id or new_batch_id()
    start = datetime.now()
    log_batch(batch_id, TASK, target_table=TARGETS, status="running", start_time=start)

    path = DATA_DIR / FILE_REL
    rel = U.relpath_under_data(path)
    sheets = U.read_excel_sheets(path)
    df = next(iter(sheets.values()))
    raw = len(df)
    cols = list(df.columns)

    client = get_ch_client()
    ods_rows, dwd_rows = [], []
    for i, r in enumerate(df.itertuples(index=False)):
        vals = list(r)
        pub_date = U.parse_date(vals[0]) or EPOCH
        url = U.clean_text(vals[1] if len(vals) > 1 else "")
        title = U.clean_text(vals[2] if len(vals) > 2 else "")
        related = U.clean_text(vals[3] if len(vals) > 3 else "")
        ods_rows.append((pub_date, url, title, related, rel, batch_id))
        dwd_rows.append((
            f"wechat_{i}", "wechat", title, "", pub_date, None, "", url, batch_id,
        ))

    if ods_rows:
        U.ch_insert_rows(client, "ods_wechat_article", ODS_COLS, ods_rows)
        U.ch_insert_rows(client, "dwd_news_unified", DWD_COLS, dwd_rows)
    loaded = len(ods_rows)

    upsert_data_source(
        "舆情", rel, path.name, "xlsx",
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
