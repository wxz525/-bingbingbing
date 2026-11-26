import csv
import html
import json
import logging
import os
import re
import sqlite3
import threading
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.news_tagger import tag_row

logger = logging.getLogger(__name__)

_BEIJING_TZ = timezone(timedelta(hours=8))
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TAG_PATTERN = re.compile(r"<[^>]+>")
_SPACE_PATTERN = re.compile(r"\s+")
_SUMMARY_NAME_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
_MAX_CONTENT_LENGTH = 50_000

_NEWS_SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    news_id TEXT PRIMARY KEY,
    trade_date TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT,
    stocks TEXT,
    content BLOB,
    topics TEXT,
    market_level TEXT,
    sentiment TEXT
);
CREATE INDEX IF NOT EXISTS idx_news_date ON news(trade_date);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _strip_html(raw: str) -> str:
    """把新闻正文 HTML 转成可读纯文本，避免前端再处理标签。"""
    text = html.unescape(_TAG_PATTERN.sub(" ", raw))
    return _SPACE_PATTERN.sub(" ", text).strip()


def _like_pattern(keyword: str) -> str:
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _parse_stocks(raw: str) -> list[str]:
    if not raw.strip():
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    codes = []
    for item in payload:
        if isinstance(item, dict):
            code = item.get("stocks_code")
            if isinstance(code, str) and code.strip():
                codes.append(code.strip())
    return codes


def _parse_row_date(row_date: str, timestamp: str) -> str | None:
    text = row_date.strip()
    if _DATE_PATTERN.fullmatch(text):
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            return None
    if timestamp.strip().isdigit():
        try:
            moment = datetime.fromtimestamp(int(timestamp.strip()), tz=_BEIJING_TZ)
        except (OverflowError, OSError, ValueError):
            return None
        return moment.date().isoformat()
    return None


class NewsIndexRepository:
    """把新闻 CSV 建成 SQLite 索引，并提供分页检索。

    首次启动（或源文件更新后）会在后台线程重建索引，
    期间查询接口返回空列表并携带构建状态，不影响其他页面。
    """

    def __init__(self, csv_path: Path, db_path: Path) -> None:
        self._csv_path = Path(csv_path)
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._status = "idle"
        self._indexed_rows = 0
        self._error: str | None = None

        meta = self._read_meta()
        if meta and meta.get("source_mtime") == self._source_mtime_text():
            self._status = "ready"
            self._indexed_rows = int(meta.get("row_count") or 0)
        elif not self._csv_path.exists():
            self._status = "missing"

    @property
    def csv_path(self) -> Path:
        return self._csv_path

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _source_mtime_text(self) -> str:
        try:
            return str(self._csv_path.stat().st_mtime_ns)
        except OSError:
            return ""

    def _read_meta(self) -> dict[str, str] | None:
        if not self._db_path.exists():
            return None
        try:
            with sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True) as connection:
                rows = connection.execute("SELECT key, value FROM meta").fetchall()
        except sqlite3.Error:
            return None
        return {str(key): str(value) for key, value in rows}

    def start_background_build(self) -> None:
        with self._lock:
            if self._status == "ready" and not self._is_stale():
                return
            if self._thread is not None and self._thread.is_alive():
                return
            if not self._csv_path.exists():
                self._status = "missing"
                return
            self._status = "building"
            self._error = None
            self._thread = threading.Thread(target=self._build, name="news-index-builder", daemon=True)
            self._thread.start()

    def _is_stale(self) -> bool:
        meta = self._read_meta()
        return not meta or meta.get("source_mtime") != self._source_mtime_text()

    def _build(self) -> None:
        temp_path = self._db_path.with_name(f"{self._db_path.name}.building-{os.getpid()}")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        processed = 0
        try:
            if temp_path.exists():
                temp_path.unlink()
            csv.field_size_limit(10 * 1024 * 1024)
            connection = sqlite3.connect(temp_path)
            try:
                connection.executescript(_NEWS_SCHEMA)
                connection.execute("PRAGMA journal_mode=OFF")
                connection.execute("PRAGMA synchronous=OFF")
                batch: list[tuple[str, str, str, str, str, bytes | None, str, str, str]] = []
                with self._csv_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
                    for row in csv.reader(handle):
                        if len(row) < 10:
                            continue
                        news_id = row[0].strip()
                        title = row[1].strip()
                        trade_date = _parse_row_date(row[9], row[7])
                        if not news_id or not trade_date:
                            continue
                        content_text = _strip_html(row[2])[:_MAX_CONTENT_LENGTH]
                        topics, market_level, sentiment = tag_row(
                            title or "", row[3].strip(), content_text
                        )
                        batch.append(
                            (
                                news_id,
                                trade_date,
                                title or "（无标题）",
                                row[3].strip(),
                                json.dumps(_parse_stocks(row[6]), ensure_ascii=False),
                                zlib.compress(content_text.encode("utf-8"), 6) if content_text else None,
                                topics,
                                market_level,
                                sentiment,
                            )
                        )
                        if len(batch) >= 2000:
                            connection.executemany(
                                "INSERT OR IGNORE INTO news "
                                "(news_id, trade_date, title, source, stocks, content, "
                                "topics, market_level, sentiment) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                batch,
                            )
                            processed += len(batch)
                            batch.clear()
                            with self._lock:
                                self._indexed_rows = processed
                if batch:
                    connection.executemany(
                        "INSERT OR IGNORE INTO news "
                        "(news_id, trade_date, title, source, stocks, content, "
                        "topics, market_level, sentiment) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        batch,
                    )
                    processed += len(batch)
                connection.executemany(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    [
                        ("source_mtime", self._source_mtime_text()),
                        ("row_count", str(processed)),
                        ("built_at", datetime.now(_BEIJING_TZ).isoformat(timespec="seconds")),
                    ],
                )
                connection.commit()
            finally:
                connection.close()

            os.replace(temp_path, self._db_path)
            with self._lock:
                self._indexed_rows = processed
                self._status = "ready"
            logger.info("新闻索引构建完成，共 %s 条", processed)
        except Exception as exc:  # noqa: BLE001 - 后台线程需兜底记录，避免静默失败
            logger.exception("新闻索引构建失败", exc_info=exc)
            with self._lock:
                self._status = "error"
                self._error = str(exc)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self._status,
                "indexed_rows": self._indexed_rows,
                "error": self._error,
            }

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)

    def is_ready(self) -> bool:
        with self._lock:
            return self._status == "ready"

    def list_news(
        self,
        keyword: str | None,
        start_date: str | None,
        end_date: str | None,
        topics: list[str],
        level: str | None,
        sentiment: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        if not self._db_path.exists():
            return [], 0
        conditions: list[str] = []
        params: list[Any] = []
        if keyword:
            pattern = _like_pattern(keyword)
            conditions.append("(title LIKE ? ESCAPE '\\' OR IFNULL(source, '') LIKE ? ESCAPE '\\')")
            params.extend([pattern, pattern])
        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)
        if topics:
            topic_terms = [f"IFNULL(topics, '') LIKE ?" for _ in topics]
            conditions.append(f"({' OR '.join(topic_terms)})")
            params.extend(f"%{t}%" for t in topics)
        if level:
            conditions.append("market_level = ?")
            params.append(level)
        if sentiment:
            conditions.append("sentiment = ?")
            params.append(sentiment)
        where_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM news{where_sql}", params
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT news_id, trade_date, title, source, stocks, topics, market_level, sentiment "
                f"FROM news{where_sql} ORDER BY trade_date DESC, rowid DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()

        items = [
            {
                "id": row[0],
                "date": row[1],
                "title": row[2],
                "source": row[3] or None,
                "stocks": json.loads(row[4] or "[]"),
                "topics": [t for t in (row[5] or "").split(",") if t],
                "market_level": row[6] or None,
                "sentiment": row[7] or None,
            }
            for row in rows
        ]
        return items, int(total)

    def get_news(self, news_id: str) -> dict[str, Any] | None:
        if not self._db_path.exists():
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT news_id, trade_date, title, source, stocks, content, "
                "topics, market_level, sentiment FROM news "
                "WHERE news_id = ?",
                (news_id,),
            ).fetchone()
        if row is None:
            return None
        content = ""
        if row[5]:
            try:
                content = zlib.decompress(row[5]).decode("utf-8", errors="replace")
            except zlib.error:
                content = bytes(row[5]).decode("utf-8", errors="replace")
        return {
            "id": row[0],
            "date": row[1],
            "title": row[2],
            "source": row[3] or None,
            "stocks": json.loads(row[4] or "[]"),
            "content": content,
            "topics": [t for t in (row[6] or "").split(",") if t],
            "market_level": row[7] or None,
            "sentiment": row[8] or None,
        }

    def meta(self) -> dict[str, Any]:
        snapshot = self.status_snapshot()
        meta = {
            "total": 0,
            "min_date": None,
            "max_date": None,
            "source_count": 0,
            "status": snapshot["status"],
            "indexed_rows": snapshot["indexed_rows"],
            "cache_ready": self._db_path.exists(),
        }
        if not self._db_path.exists():
            return meta
        with self._connect() as connection:
            total, min_date, max_date = connection.execute(
                "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM news"
            ).fetchone()
            source_count = connection.execute(
                "SELECT COUNT(DISTINCT source) FROM news WHERE IFNULL(source, '') != ''"
            ).fetchone()[0]
        meta.update(
            total=int(total),
            min_date=min_date,
            max_date=max_date,
            source_count=int(source_count),
        )
        return meta


class SummaryRepository:
    """读取本地 Markdown 资金流摘要，列表索引带目录签名缓存，标签从 summaries_tags.json 加载。"""

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)
        self._items: list[dict[str, Any]] | None = None
        self._signature: tuple[int, int, int] | None = None

    def _load_tags(self) -> dict[str, dict[str, Any]]:
        tag_file = self._directory / "summaries_tags.json"
        if not tag_file.exists():
            return {}
        try:
            return json.loads(tag_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _load(self) -> list[dict[str, Any]]:
        if not self._directory.exists():
            self._items = []
            self._signature = None
            return self._items
        try:
            stat = self._directory.stat()
        except OSError:
            return self._items or []
        md_count = len(list(self._directory.glob("*.md")))
        tag_mtime = 0
        tag_file = self._directory / "summaries_tags.json"
        if tag_file.exists():
            try:
                tag_mtime = tag_file.stat().st_mtime_ns
            except OSError:
                pass
        signature = (stat.st_mtime_ns, md_count, tag_mtime)
        if self._items is not None and signature == self._signature:
            return self._items

        tags = self._load_tags()
        items: list[dict[str, Any]] = []
        for path in self._directory.glob("*.md"):
            match = _SUMMARY_NAME_PATTERN.match(path.stem)
            if match:
                date_text, rest = match.group(1), match.group(2)
            else:
                date_text, rest = None, path.stem
            parts = rest.split("-", 1)
            if len(parts) == 2:
                institution, title = parts[0], parts[1]
            else:
                institution, title = None, rest
            tag = tags.get(path.name, {})
            items.append(
                {
                    "name": path.name,
                    "date": date_text,
                    "institution": institution,
                    "title": title,
                    "topics": list(tag.get("topics", [])),
                    "market_level": tag.get("market_level"),
                    "sentiment": tag.get("sentiment"),
                }
            )
        items.sort(key=lambda item: (item["date"] or "", item["name"]), reverse=True)
        self._items = items
        self._signature = signature
        return items

    def list_summaries(
        self,
        keyword: str | None,
        topic: str | None,
        level: str | None,
        sentiment: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        items = self._load()
        if keyword:
            text = keyword.lower()
            items = [
                item
                for item in items
                if text in item["title"].lower()
                or text in (item["institution"] or "").lower()
            ]
        if topic:
            items = [item for item in items if topic in item.get("topics", [])]
        if level:
            items = [item for item in items if item.get("market_level") == level]
        if sentiment:
            items = [item for item in items if item.get("sentiment") == sentiment]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def get_summary(self, name: str) -> dict[str, Any] | None:
        item = next((entry for entry in self._load() if entry["name"] == name), None)
        if item is None:
            return None
        path = self._directory / name
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        return {**item, "content": content}
