"""数据库 / 对象存储连接工厂与 ETL 元信息写入工具。

设计要点（来自历史经验）：
1. 所有连接显式设置 connect/read/write 超时，避免网络不可达时脚本长时间挂起。
2. 建库建表先于写入：调用方应先执行 sql/ 下的 DDL，再运行 ETL。
3. 密码来自 config.config（环境变量优先），本模块不出现任何明文密码。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import pymysql
from clickhouse_driver import Client
from minio import Minio

from config.config import CONFIG


# --------------------------------------------------------------------------- #
# 连接工厂
# --------------------------------------------------------------------------- #
def get_mysql_conn(database: Optional[str] = None):
    """返回 MySQL 连接（DictCursor，autocommit）。"""
    cfg = CONFIG["mysql"]
    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg["port"]),
        user=cfg["user"],
        password=cfg["password"],
        database=database or cfg["database"],
        charset=cfg.get("charset", "utf8mb4"),
        connect_timeout=int(cfg.get("connect_timeout", 10)),
        read_timeout=int(cfg.get("read_timeout", 60)),
        write_timeout=int(cfg.get("write_timeout", 60)),
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_ch_client():
    """返回 ClickHouse native 客户端。"""
    cfg = CONFIG["clickhouse"]
    return Client(
        host=cfg["host"],
        port=int(cfg["port"]),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        connect_timeout=int(cfg.get("connect_timeout", 10)),
        send_receive_timeout=int(cfg.get("send_receive_timeout", 600)),
        settings={"use_numpy": False},
    )


def get_minio_client() -> Minio:
    cfg = CONFIG["minio"]
    return Minio(
        cfg["endpoint"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
        secure=bool(cfg.get("secure", False)),
    )


# --------------------------------------------------------------------------- #
# 批次号
# --------------------------------------------------------------------------- #
def new_batch_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]


# --------------------------------------------------------------------------- #
# ETL 批次日志（写入 MySQL 元数据库 etl_batch_log）
# --------------------------------------------------------------------------- #
def log_batch(
    batch_id: str,
    task_name: str,
    source_file: str = "",
    target_table: str = "",
    raw_rows: int = 0,
    loaded_rows: int = 0,
    failed_rows: int = 0,
    status: str = "running",
    message: str = "",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> None:
    sql = (
        "INSERT INTO etl_batch_log "
        "(batch_id, task_name, source_file, target_table, raw_rows, loaded_rows, "
        " failed_rows, status, message, start_time, end_time) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    with get_mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    batch_id, task_name, source_file, target_table,
                    raw_rows, loaded_rows, failed_rows, status, message,
                    start_time, end_time,
                ),
            )


# --------------------------------------------------------------------------- #
# 数据源清单登记（写入 MySQL data_source，用于校验是否遗漏原始文件）
# --------------------------------------------------------------------------- #
def upsert_data_source(
    category: str,
    file_path: str,
    file_name: str,
    file_type: str,
    raw_rows: Optional[int] = None,
    target_table: str = "",
    status: str = "pending",
    loaded_rows: int = 0,
    remark: str = "",
) -> None:
    sql = (
        "INSERT INTO data_source "
        "(category, file_path, file_name, file_type, raw_rows, loaded_rows, "
        " target_table, status, last_load_time, remark) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s) "
        "ON DUPLICATE KEY UPDATE "
        "category=VALUES(category), file_name=VALUES(file_name), file_type=VALUES(file_type), "
        "raw_rows=COALESCE(VALUES(raw_rows), raw_rows), "
        "loaded_rows=VALUES(loaded_rows), target_table=VALUES(target_table), "
        "status=VALUES(status), last_load_time=NOW(), remark=VALUES(remark)"
    )
    with get_mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    category, file_path, file_name, file_type,
                    raw_rows, loaded_rows, target_table, status, remark,
                ),
            )


# --------------------------------------------------------------------------- #
# 批量写入
# --------------------------------------------------------------------------- #
def mysql_executemany(conn, sql: str, rows: list[tuple]) -> int:
    """对 MySQL 执行 executemany，返回写入行数（空列表直接返回 0）。"""
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)
