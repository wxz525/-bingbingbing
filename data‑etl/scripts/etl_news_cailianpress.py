"""财联社新闻 ETL：新闻/无标题.csv（无表头，11 列按位置命名） -> ClickHouse。

写入 ods_news_cailianpress + dwd_news_unified。
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from config.config import DATA_DIR
from scripts.common import etl_utils as U
from scripts.common.db import get_ch_client, log_batch, new_batch_id, upsert_data_source
from scripts.common.logging_utils import get_logger

log = get_logger("news_cailianpress")
TASK = "etl_news_cailianpress"
TARGETS = "ods_news_cailianpress,dwd_news_unified"
FILE_REL = "新闻/无标题.csv"

# 无表头，按位置命名（与探查结果一致）
COLS = ["news_id", "title", "content", "source", "extra_flag", "tags",
        "stock_codes", "publish_ts", "crawl_ts", "publish_date", "row_no"]

ODS_COLS = ["news_id", "title", "content", "source", "extra_flag", "tags",
            "stock_codes", "publish_ts", "crawl_ts", "publish_date", "row_no",
            "source_file", "batch_id"]
DWD_COLS = ["news_id", "source_type", "title", "content", "publish_date",
            "publish_ts", "stock_codes", "raw_url", "batch_id"]

EPOCH = date(1970, 1, 1)


def _to_int(v) -> int:
    try:
        s = str(v).strip()
        return int(s) if s.isdigit() else 0
    except Exception:
        return 0


def run(batch_id: str | None = None) -> int:
    batch_id = batch_id or new_batch_id()
    start = datetime.now()
    log_batch(batch_id, TASK, target_table=TARGETS, status="running", start_time=start)

    path = DATA_DIR / FILE_REL
    rel = U.relpath_under_data(path)
    df = pd.read_csv(path, header=None, names=COLS, dtype=str, encoding="utf-8",
                     on_bad_lines="warn")
    raw = len(df)

    client = get_ch_client()
    ods_rows, dwd_rows = [], []
    for r in df.itertuples(index=False):
        pdate = U.parse_date(r.publish_date) or EPOCH
        nid = _to_int(r.news_id)
        ods_rows.append((
            nid, U.clean_text(r.title), U.clean_text(r.content),
            U.clean_text(r.source), U.clean_text(r.extra_flag),
            U.clean_text(r.tags), U.clean_text(r.stock_codes),
            _to_int(r.publish_ts), _to_int(r.crawl_ts), pdate,
            _to_int(r.row_no), rel, batch_id,
        ))
        dwd_rows.append((
            str(nid), "cailianpress", U.clean_text(r.title),
            U.clean_text(r.content), pdate, _to_int(r.publish_ts) or None,
            U.clean_text(r.stock_codes), "", batch_id,
        ))

    if ods_rows:
        U.ch_insert_rows(client, "ods_news_cailianpress", ODS_COLS, ods_rows)
        U.ch_insert_rows(client, "dwd_news_unified", DWD_COLS, dwd_rows)
    loaded = len(ods_rows)

    upsert_data_source(
        "新闻", rel, path.name, "csv",
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
