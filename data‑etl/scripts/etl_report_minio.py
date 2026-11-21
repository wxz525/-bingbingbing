"""研报 ETL：全球资金信息摘要.zip -> MinIO（正文） + MySQL report_index（索引）。

研报正文不入库：md 文件上传到 MinIO，数据库仅保存对象路径等索引信息。
"""
from __future__ import annotations

import hashlib
import io
import re
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config import CONFIG, DATA_DIR
from scripts.common import etl_utils as U
from scripts.common.db import get_minio_client, get_mysql_conn, log_batch, mysql_executemany, new_batch_id, upsert_data_source
from scripts.common.logging_utils import get_logger

log = get_logger("report_minio")
TASK = "etl_report_minio"
TARGET = "report_index"
FILE_REL = "全球资金信息摘要.zip"

# 文件名形如：2024-05-02-机构H-资金流看全球-2024年4月回顾.md
NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(机构[A-Z])-(.+)\.md$", re.IGNORECASE)

INDEX_SQL = (
    "INSERT INTO report_index "
    "(title, publish_date, institution, minio_bucket, minio_object_key, "
    " source_zip, source_file, file_size, file_md5, batch_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
    "ON DUPLICATE KEY UPDATE title=VALUES(title), publish_date=VALUES(publish_date), "
    "institution=VALUES(institution), file_size=VALUES(file_size), "
    "file_md5=VALUES(file_md5), batch_id=VALUES(batch_id)"
)


def run(batch_id: str | None = None) -> int:
    batch_id = batch_id or new_batch_id()
    start = datetime.now()
    log_batch(batch_id, TASK, target_table=TARGET, status="running", start_time=start)

    path = DATA_DIR / FILE_REL
    rel = U.relpath_under_data(path)
    cfg = CONFIG["minio"]
    bucket = cfg["bucket"]
    prefix = CONFIG["etl"].get("report_object_prefix", "reports")

    client = get_minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        log.info(f"created bucket: {bucket}")

    index_rows = []
    uploaded = 0
    with zipfile.ZipFile(path, "r") as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(".md")]
        for name in members:
            data = zf.read(name)
            file_size = len(data)
            file_md5 = hashlib.md5(data).hexdigest()
            # zip 内相对路径作为 object key（统一正斜杠）
            rel_in_zip = name.replace("\\", "/")
            object_key = f"{prefix}/{rel_in_zip}"
            client.put_object(bucket, object_key, io.BytesIO(data), file_size)
            uploaded += 1

            stem = Path(rel_in_zip).name
            m = NAME_RE.match(stem)
            if m:
                pub_date = U.parse_date(m.group(1))
                institution = m.group(2)
                title = m.group(3)
            else:
                pub_date, institution, title = None, None, Path(stem).stem

            index_rows.append((
                title, pub_date, institution, bucket, object_key,
                path.name, rel_in_zip, file_size, file_md5, batch_id,
            ))

    if index_rows:
        mysql_executemany(get_mysql_conn(), INDEX_SQL, index_rows)

    upsert_data_source(
        "研报", rel, path.name, "zip",
        raw_rows=len(index_rows), target_table=f"MinIO:{bucket}+report_index",
        status="loaded" if uploaded else "failed", loaded_rows=uploaded,
        remark=f"{uploaded} 个 md 文件上传 MinIO",
    )
    log_batch(batch_id, TASK, target_table=TARGET,
              raw_rows=len(index_rows), loaded_rows=uploaded,
              failed_rows=len(index_rows) - uploaded,
              status="success", start_time=start, end_time=datetime.now())
    log.info(f"[{TASK}] done md_files={len(index_rows)} uploaded={uploaded}")
    return uploaded


if __name__ == "__main__":
    run()
