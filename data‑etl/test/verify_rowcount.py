"""入库校验：统计原始文件行数，对比数据库入库行数，检查是否丢数据。

输出两部分：
  1. 逐文件校验：原始行数（扫描） vs data_source.loaded_rows（登记入库行数）
  2. 表级校验：  目标表 count(*) vs 该表对应源文件行数合计
退出码：0 全部通过；1 存在差异。
"""
from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # data-etl

from config.config import DATA_DIR
from scripts.common.db import get_ch_client, get_mysql_conn
from scripts.common.logging_utils import get_logger

log = get_logger("verify")

# 无表头的 csv（不减表头行）
HEADERLESS = {"新闻/无标题.csv"}

# 源文件 -> 目标表映射（用于表级校验）
def target_tables(rel: str) -> list[str]:
    if rel == "目标资产价格变量/代码对照.csv":
        return ["dim_asset"]
    if rel.startswith("目标资产价格变量/"):
        return ["ods_market_price"]
    if rel == "指标集1_数据.xlsx":
        return ["ods_indicator"]
    if rel == "日历数据.xlsx":
        return ["ods_event_calendar"]
    if rel == "新闻/无标题.csv":
        return ["ods_news_cailianpress"]
    if rel == "科技.csv":
        return ["ods_twitter"]
    if rel == "公众号.xlsx":
        return ["ods_wechat_article"]
    if rel == "商品期货日成交额.xlsx":
        return ["ods_futures_turnover"]
    if rel == "全球资金信息摘要.zip":
        return ["report_index"]
    return []


# --------------------------------------------------------------------------- #
# 原始文件行数统计
# --------------------------------------------------------------------------- #
def _count_csv(path: Path) -> int:
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return sum(1 for _ in csv.reader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"无法解码 csv: {path}")


def _count_xlsx(path: Path) -> int:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True)
    total = 0
    for ws in wb.worksheets:
        total += max(ws.max_row - 1, 0)  # 减表头
    wb.close()
    return total


def _count_zip_md(path: Path) -> int:
    with zipfile.ZipFile(path, "r") as zf:
        return sum(1 for n in zf.namelist() if n.lower().endswith(".md"))


def scan_source_rows() -> dict[str, int]:
    expected: dict[str, int] = {}
    for p in sorted(DATA_DIR.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(DATA_DIR)).replace("\\", "/")
        suf = p.suffix.lower()
        try:
            if suf == ".csv":
                n = _count_csv(p)
                if rel not in HEADERLESS:
                    n = max(n - 1, 0)
                expected[rel] = n
            elif suf in (".xlsx", ".xls"):
                expected[rel] = _count_xlsx(p)
            elif suf == ".zip":
                expected[rel] = _count_zip_md(p)
        except Exception as e:
            log.warning(f"统计失败 {rel}: {e}")
            expected[rel] = -1
    return expected


# --------------------------------------------------------------------------- #
# 数据库行数
# --------------------------------------------------------------------------- #
MYSQL_TABLES = ["dim_asset", "dim_indicator", "report_index",
                "data_source", "etl_batch_log"]
CK_TABLES = [
    "ods_market_price", "ods_indicator", "ods_event_calendar",
    "ods_news_cailianpress", "ods_twitter", "ods_wechat_article",
    "ods_futures_turnover", "dwd_market_price_daily", "dwd_event_calendar",
    "dwd_news_unified", "dws_news_count_daily", "dws_market_asset_stats",
]


def db_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    with get_mysql_conn() as conn:
        with conn.cursor() as cur:
            for t in MYSQL_TABLES:
                cur.execute(f"SELECT COUNT(*) AS c FROM {t}")
                counts[t] = cur.fetchone()["c"]
    client = get_ch_client()
    for t in CK_TABLES:
        counts[t] = client.execute(f"SELECT count() FROM {t}")[0][0]
    return counts


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def main() -> int:
    log.info("扫描原始文件行数...")
    expected = scan_source_rows()
    log.info(f"共扫描到 {len(expected)} 个原始文件")

    # 读取 data_source 登记
    ds: dict[str, dict] = {}
    with get_mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT file_path, raw_rows, loaded_rows, target_table, status "
                "FROM data_source"
            )
            for r in cur.fetchall():
                ds[r["file_path"]] = r

    counts = db_counts()

    all_ok = True

    # 1. 逐文件校验
    print("\n=== 1. 逐文件校验：原始行数 vs 入库行数（data_source.loaded_rows） ===")
    for rel, raw in sorted(expected.items()):
        row = ds.get(rel)
        loaded = row["loaded_rows"] if row else 0
        if raw < 0:
            mark = "ERROR"
        elif loaded >= raw > 0:
            mark = "PASS"
        elif raw == 0:
            mark = "EMPTY"
        else:
            mark = "FAIL"
        if mark in ("FAIL", "ERROR"):
            all_ok = False
        status = row["status"] if row else "MISSING"
        print(f"  [{mark:5}] {rel}: raw={raw} loaded={loaded} (登记状态={status})")

    # 未登记的源文件
    missing = [rel for rel in expected if rel not in ds]
    if missing:
        all_ok = False
        print(f"\n[FAIL] 以下原始文件未在 data_source 登记（可能遗漏）：")
        for m in missing:
            print(f"   - {m}")

    # 2. 表级校验（仅 ODS / MySQL 维度表严格对比；DWD/DWS 展示 count）
    print("\n=== 2. 表级校验：目标表 count(*) vs 源文件行数合计 ===")
    table_sum: dict[str, int] = {}
    for rel, raw in expected.items():
        if raw < 0:
            continue
        for tt in target_tables(rel):
            table_sum[tt] = table_sum.get(tt, 0) + raw

    strict = {"ods_market_price", "ods_indicator", "ods_event_calendar",
              "ods_news_cailianpress", "ods_twitter", "ods_wechat_article",
              "ods_futures_turnover", "dim_asset", "report_index"}
    for tt in sorted(set(list(table_sum) + list(counts))):
        sm = table_sum.get(tt)
        actual = counts.get(tt)
        if tt in strict and sm is not None:
            if actual is not None and actual >= sm:
                mark = "PASS"
                extra = "（可能重复导入）" if actual > sm else ""
            else:
                mark = "FAIL"
                all_ok = False
                extra = ""
            print(f"  [{mark:5}] {tt}: expected_sum={sm} actual={actual}{extra}")
        else:
            print(f"  [INFO] {tt}: actual_count={actual}" +
                  (f" (源合计={sm}, DWD/DWS 仅展示)" if sm else ""))

    print(f"\n========== 校验结论：{'全部通过（无丢数据）' if all_ok else '存在差异，请检查'} ==========")
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 连接失败等运行时问题，给出可操作的提示
        log.error(f"校验中止：{type(e).__name__}: {e}")
        log.error(
            "请确认 MySQL / ClickHouse / MinIO 已启动，"
            "且项目根目录 .env 中的地址与账号密码与实际一致。"
        )
        sys.exit(2)
