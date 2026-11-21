"""Twitter 舆情 ETL：科技.csv（31 列） -> ClickHouse ods_twitter + dwd_news_unified。"""
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

log = get_logger("twitter")
TASK = "etl_twitter"
TARGETS = "ods_twitter,dwd_news_unified"
FILE_REL = "科技.csv"

INT_COLS = ["like_count", "reply_count", "retweet_count",
            "quote_count", "view_count", "bookmark_count"]

# 与 02_clickhouse_ddl.sql 中 ods_twitter 列顺序一致
ODS_COLS = [
    "id", "tweet_id", "twitter_user_id", "user_name", "author_display_name",
    "url", "text", "tweet_type", "source", "lang", "is_reply", "is_retweet",
    "is_quote", "conversation_id", "in_reply_to_tweet_id", "in_reply_to_user_id",
    "retweeted_tweet_raw", "quoted_tweet_raw", "created_at_twitter",
    "like_count", "reply_count", "retweet_count", "quote_count",
    "view_count", "bookmark_count", "origin", "history_job_id",
    "first_collected_at", "last_snapshot_at", "last_snapshot_job_id",
    "created_at", "updated_at", "publish_date", "source_file", "batch_id",
]
DWD_COLS = ["news_id", "source_type", "title", "content", "publish_date",
            "publish_ts", "stock_codes", "raw_url", "batch_id"]

EPOCH = date(1970, 1, 1)


def _to_int(v):
    try:
        s = str(v).strip()
        return int(s) if s.lstrip("-").isdigit() else None
    except Exception:
        return None


def run(batch_id: str | None = None) -> int:
    batch_id = batch_id or new_batch_id()
    start = datetime.now()
    log_batch(batch_id, TASK, target_table=TARGETS, status="running", start_time=start)

    path = DATA_DIR / FILE_REL
    rel = U.relpath_under_data(path)
    df = pd.read_csv(path, dtype=str, encoding="utf-8", on_bad_lines="warn")
    raw = len(df)
    # 统一列名（去空格）
    df.columns = [str(c).strip() for c in df.columns]

    client = get_ch_client()
    ods_rows, dwd_rows = [], []
    for r in df.itertuples(index=False):
        d = r._asdict()
        pdate = U.parse_date(d.get("created_at")) or EPOCH
        pdt = U.parse_datetime(d.get("created_at"))
        p_ts = int(pdt.timestamp()) if pdt else None
        ods_rows.append((
            U.clean_text(d.get("id")), U.clean_text(d.get("tweet_id")),
            U.clean_text(d.get("twitter_user_id")), U.clean_text(d.get("user_name")),
            U.clean_text(d.get("author_display_name")), U.clean_text(d.get("url")),
            U.clean_text(d.get("text")), U.clean_text(d.get("tweet_type")),
            U.clean_text(d.get("source")), U.clean_text(d.get("lang")),
            U.clean_text(d.get("is_reply")), U.clean_text(d.get("is_retweet")),
            U.clean_text(d.get("is_quote")), U.clean_text(d.get("conversation_id")),
            U.clean_text(d.get("in_reply_to_tweet_id")),
            U.clean_text(d.get("in_reply_to_user_id")),
            U.clean_text(d.get("retweeted_tweet_raw")),
            U.clean_text(d.get("quoted_tweet_raw")),
            U.clean_text(d.get("created_at_twitter")),
            _to_int(d.get("like_count")), _to_int(d.get("reply_count")),
            _to_int(d.get("retweet_count")), _to_int(d.get("quote_count")),
            _to_int(d.get("view_count")), _to_int(d.get("bookmark_count")),
            U.clean_text(d.get("origin")), U.clean_text(d.get("history_job_id")),
            U.clean_text(d.get("first_collected_at")),
            U.clean_text(d.get("last_snapshot_at")),
            U.clean_text(d.get("last_snapshot_job_id")),
            U.clean_text(d.get("created_at")), U.clean_text(d.get("updated_at")),
            pdate, rel, batch_id,
        ))
        text = U.clean_text(d.get("text"))
        dwd_rows.append((
            U.clean_text(d.get("tweet_id")) or U.clean_text(d.get("id")),
            "twitter", text[:200], text, pdate, p_ts, "",
            U.clean_text(d.get("url")), batch_id,
        ))

    if ods_rows:
        U.ch_insert_rows(client, "ods_twitter", ODS_COLS, ods_rows)
        U.ch_insert_rows(client, "dwd_news_unified", DWD_COLS, dwd_rows)
    loaded = len(ods_rows)

    upsert_data_source(
        "舆情", rel, path.name, "csv",
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
