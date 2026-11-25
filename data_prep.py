from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "金融科技竞赛" / "上科大数据合集"
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def read_xlsx(path: Path):
    result = []
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        relroot = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in relroot}
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            ssroot = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(".//m:t", NS)) for si in ssroot.findall("m:si", NS)]
        for sh in wb.findall(".//m:sheet", NS):
            target = rels[sh.attrib["{" + NS["r"] + "}id"]].lstrip("/")
            member = target if target.startswith("xl/") else "xl/" + target
            root = ET.fromstring(z.read(member))
            rows = root.findall(".//m:sheetData/m:row", NS)
            if not rows:
                continue
            parsed = []
            for row in rows:
                vals = {}
                for c in row.findall("m:c", NS):
                    ref = c.attrib.get("r", "")
                    col = re.match(r"[A-Z]+", ref).group(0) if ref else "?"
                    v = c.find("m:v", NS)
                    val = "" if v is None else v.text or ""
                    if c.attrib.get("t") == "s" and val:
                        val = shared[int(val)]
                    elif c.attrib.get("t") == "inlineStr":
                        val = "".join(t.text or "" for t in c.findall(".//m:t", NS))
                    vals[col] = val
                parsed.append(vals)
            result.append({"sheet": sh.attrib["name"], "rows": parsed})
    return result


def excel_date(value):
    try:
        if re.fullmatch(r"\d+(\.\d+)?", str(value)):
            return (dt.datetime(1899, 12, 30) + dt.timedelta(days=float(value))).date().isoformat()
        return dt.datetime.fromisoformat(str(value).replace("Z", "")).date().isoformat()
    except Exception:
        return None


def csv_summary(path: Path, has_header=True):
    enc = "utf-8-sig"
    try:
        with path.open("r", encoding=enc, newline="") as f:
            reader = csv.reader(f)
            first = next(reader, [])
            header = first if has_header else [f"column_{i+1}" for i in range(len(first))]
    except UnicodeDecodeError:
        enc = "gb18030"
        with path.open("r", encoding=enc, newline="") as f:
            first = next(csv.reader(f), [])
            header = first if has_header else [f"column_{i+1}" for i in range(len(first))]
    date_col = next((i for i, x in enumerate(header) if x.lower() in {"date", "日期", "datetime", "time", "时间"}), None)
    close_col = next((i for i, x in enumerate(header) if x.lower() in {"close", "收盘", "收盘价", "value", "价格"}), None)
    n = bad_rows = 0
    dmin = dmax = None
    dates = set()
    duplicate_dates = 0
    missing = Counter()
    sample = []
    with path.open("r", encoding=enc, newline="") as f:
        reader = csv.reader(f)
        if has_header:
            next(reader, None)
        else:
            first = next(reader, None)
            if first is not None:
                n += 1
                sample.append(first[:min(10, len(first))])
                if len(first) != len(header):
                    bad_rows += 1
                for i, name in enumerate(header):
                    if i >= len(first) or not first[i].strip():
                        missing[name] += 1
        for row in reader:
            n += 1
            if len(sample) < 2:
                sample.append(row[:min(10, len(row))])
            if len(row) != len(header):
                bad_rows += 1
            for i, name in enumerate(header):
                if i >= len(row) or not row[i].strip():
                    missing[name] += 1
            if date_col is not None and date_col < len(row):
                d = excel_date(row[date_col])
                if d:
                    if d in dates:
                        duplicate_dates += 1
                    dates.add(d)
                    dmin = min(dmin, d) if dmin else d
                    dmax = max(dmax, d) if dmax else d
    return {"file": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "encoding": enc,
            "rows": n, "columns": header, "date_min": dmin, "date_max": dmax,
            "duplicate_dates": duplicate_dates, "malformed_rows": bad_rows,
            "missing_counts": dict(missing), "sample_rows": sample}


def main():
    report = {"root": str(ROOT), "files": [], "workbooks": [], "notes": []}
    files = [p for p in ROOT.rglob("*") if p.is_file()]
    for p in files:
        report["files"].append({"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "suffix": p.suffix.lower()})
    # Daily asset price files and the large news CSV are streamed row by row.
    mapping_files = {"代码对照.csv"}
    for p in sorted((ROOT / "目标资产价格变量").glob("*.csv")):
        if p.name in mapping_files:
            report.setdefault("mapping_csv", []).append(csv_summary(p))
        else:
            report.setdefault("asset_csv", []).append(csv_summary(p))
    for p in sorted(ROOT.glob("*.csv")):
        report.setdefault("root_csv", []).append(csv_summary(p))
    news = list((ROOT / "新闻").glob("*.csv"))
    for p in news:
        report.setdefault("news_csv", []).append(csv_summary(p, has_header=False))
    for p in sorted(ROOT.glob("*.xlsx")):
        workbook = {"file": p.name, "bytes": p.stat().st_size, "sheets": []}
        for sheet in read_xlsx(p):
            rows = sheet["rows"]
            cols = sorted({c for row in rows for c in row}, key=lambda c: (len(c), c))
            header_row = rows[0]
            headers = [header_row.get(c, "") for c in cols]
            data = rows[1:]
            date_index = next((i for i, h in enumerate(headers) if str(h).lower() in {"date", "日期", "occurdate"}), 0 if p.name.startswith("指标集") or "成交额" in p.name else None)
            date_values = [excel_date(row.get(cols[date_index], "")) for row in data] if date_index is not None and cols else []
            date_values = [x for x in date_values if x]
            miss = {headers[i] or f"column_{cols[i]}": sum(not row.get(cols[i], "").strip() for row in data) for i in range(len(cols))}
            sheet_info = {"name": sheet["sheet"], "rows_including_header": len(rows), "columns": headers,
                          "date_min": min(date_values) if date_values else None, "date_max": max(date_values) if date_values else None,
                          "missing_counts": miss, "sample_rows": [[row.get(c, "") for c in cols] for row in rows[1:3]]}
            workbook["sheets"].append(sheet_info)
        report["workbooks"].append(workbook)
    md = ["# 金融科技竞赛数据集盘点", "", f"数据目录：`{ROOT}`", "", f"文件总数：{len(files)}"]
    extcounts = Counter((Path(x["path"]).suffix.lower() or "[无扩展名]") for x in report["files"])
    md.append("文件类型：" + "、".join(f"{k} {v} 个" for k, v in sorted(extcounts.items())))
    md += ["", "## 行情 CSV（目标资产价格变量）", "", "| 文件 | 行数 | 日期范围 | 重复日期 | 缺失/异常行 | 字段 |", "|---|---:|---|---:|---:|---|"]
    for x in report.get("asset_csv", []):
        md.append(f"| {Path(x['file']).name} | {x['rows']} | {x['date_min']} 至 {x['date_max']} | {x['duplicate_dates']} | {x['malformed_rows']} | {', '.join(x['columns'])} |")
    md += ["", "## 工作簿概览", ""]
    for w in report["workbooks"]:
        md += [f"### {w['file']}", ""]
        for s in w["sheets"]:
            md.append(f"- `{s['name']}`：{s['rows_including_header']-1} 行数据；字段：{', '.join(s['columns']) or '无表头'}；日期范围：{s['date_min']} 至 {s['date_max']}。")
        md.append("")
    md += ["## 大型/根目录 CSV", ""]
    for x in report.get("root_csv", []) + report.get("news_csv", []):
        md.append(f"- `{x['file']}`：{x['rows']} 行，字段 `{', '.join(x['columns'])}`，日期范围 {x['date_min']} 至 {x['date_max']}；格式异常行 {x['malformed_rows']}。")
    md += ["", "## 与仓库现有 data-etl 的关系", "",
           "仓库已有 `data-etl/docs/数据字典.md`、各数据源 ETL、分层建表 SQL、`run_all.py` 与 `test/verify_rowcount.py`。本报告只记录本地数据副本的实测盘点，不重复定义数据模型，也不替代已有字典和入库校验。",
           "", "## 发现与需核实项", "",
           "- 目标资产目录包含 39 个行情 CSV 和 1 个 `代码对照.csv`；对照文件用于资产维度，不作为行情序列。",
           "- 仓库字典记载行情总量为 314,318 行；本报告逐文件统计可与该基准对照。",
           "- 新闻 CSV 无表头。扫描时按 11 个位置列处理，行数包含首行，避免此前少算一行。仓库字典基准为 900,704 行。",
           "- X01–X31 含义待业务方补充，这一点已在仓库字典中说明；本报告不推测其具体因子名称。",
           "- 新闻数据量大，脚本逐行读取；其他原始数据仍由项目已有 ETL 负责清洗和入库。", ""]
    (OUT / "数据集盘点报告.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / "数据集盘点明细.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"扫描文件 {len(files)} 个；行情 CSV {len(report.get('asset_csv', []))} 个；工作簿 {len(report['workbooks'])} 个")
    print(f"报告：{OUT / '数据集盘点报告.md'}")


if __name__ == "__main__":
    main()
