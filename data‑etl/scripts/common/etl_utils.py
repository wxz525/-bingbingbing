"""ETL 通用工具：路径、编码探测、日期/数值清洗、批量入库。"""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from config.config import CONFIG, DATA_DIR
from scripts.common.db import mysql_executemany  # noqa: F401  re-export，定义在 db.py
from scripts.common.logging_utils import get_logger

log = get_logger("etl_utils")


# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
def data_rel(rel: str) -> Path:
    """把 data 根下的相对路径转为绝对 Path。"""
    return DATA_DIR / rel


def relpath_under_data(path: Path) -> str:
    """返回相对 DATA_DIR 的路径字符串（正斜杠），用于 source_file / file_path 字段。"""
    return str(path.relative_to(DATA_DIR)).replace("\\", "/")


# --------------------------------------------------------------------------- #
# 读取（自动探测编码）
# --------------------------------------------------------------------------- #
def read_csv_auto(path: Path, **kwargs) -> pd.DataFrame:
    """读 csv，自动尝试 utf-8-sig / utf-8 / gbk。"""
    last_err: Optional[Exception] = None
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise RuntimeError(f"无法解码 csv: {path}，最后错误: {last_err}")


def read_excel_sheets(path: Path) -> dict[str, pd.DataFrame]:
    """读 xlsx 全部 sheet，返回 {sheet_name: df}。"""
    return pd.read_excel(path, sheet_name=None, engine="openpyxl")


# --------------------------------------------------------------------------- #
# 清洗
# --------------------------------------------------------------------------- #
def safe_float(v) -> Optional[float]:
    """容错转 float，空值/NaN/非数值返回 None。"""
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def parse_date(v) -> Optional[datetime.date]:
    """容错解析为 date，失败返回 None。"""
    if v is None or v == "":
        return None
    try:
        ts = pd.to_datetime(v, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.date()
    except Exception:
        return None


def parse_datetime(v) -> Optional[datetime]:
    if v is None or v == "":
        return None
    try:
        ts = pd.to_datetime(v, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


def clean_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v)


# --------------------------------------------------------------------------- #
# 批量入库
# --------------------------------------------------------------------------- #
def ch_insert_rows(client, table: str, columns: list[str],
                   rows: Iterable[tuple], batch_size: Optional[int] = None) -> int:
    """分批把 rows 写入 ClickHouse，返回插入行数。"""
    batch_size = batch_size or int(CONFIG["etl"].get("batch_size", 50000))
    inserted = 0
    buf: list[tuple] = []
    cols_sql = ",".join(columns)
    for r in rows:
        buf.append(r)
        if len(buf) >= batch_size:
            client.execute(f"INSERT INTO {table} ({cols_sql}) VALUES", buf)
            inserted += len(buf)
            buf = []
    if buf:
        client.execute(f"INSERT INTO {table} ({cols_sql}) VALUES", buf)
        inserted += len(buf)
    return inserted


# mysql_executemany 已移至 scripts.common.db，此处由顶部 import re-export
