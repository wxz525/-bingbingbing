import csv
from pathlib import Path

MAPPING_FILE_NAME = "代码对照.csv"


class MarketDataRepository:
    """从本地行情目录读取资产元数据与时间序列（只读，带内存缓存）。"""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._series_cache: dict[str, tuple[float, list[tuple[str, float]]]] = {}

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def list_assets(self) -> list[dict[str, object]]:
        mapping_path = self._data_dir / MAPPING_FILE_NAME
        if not mapping_path.exists():
            return []

        assets: list[dict[str, object]] = []
        with mapping_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                name = (row.get("名称") or "").strip()
                if not name or (row.get("状态") or "").strip() != "ok":
                    continue
                series_path = self._data_dir / f"{name}.csv"
                if not series_path.exists():
                    continue
                field = (row.get("字段") or "").strip() or "close"
                points = self._read_points(series_path, name)
                if not points:
                    continue
                assets.append(
                    {
                        "name": name,
                        "category": (row.get("大类") or "").strip() or "其他",
                        "wind_code": (row.get("Wind代码") or "").strip() or None,
                        "field": field,
                        "start_date": points[0][0],
                        "end_date": points[-1][0],
                        "row_count": len(points),
                    }
                )
        return assets

    def get_series(self, name: str) -> list[tuple[str, float]] | None:
        series_path = self._data_dir / f"{name}.csv"
        if not series_path.exists():
            return None
        return self._read_points(series_path, name)

    def _read_points(self, path: Path, cache_key: str) -> list[tuple[str, float]]:
        mtime = path.stat().st_mtime
        cached = self._series_cache.get(cache_key)
        if cached and cached[0] == mtime:
            return cached[1]

        raw: list[tuple[str, float]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if not header or len(header) < 2:
                return []
            for row in reader:
                if len(row) < 2:
                    continue
                date_text = row[0].strip()
                value_text = row[1].strip()
                if not date_text or not value_text:
                    continue
                try:
                    value = float(value_text)
                except ValueError:
                    continue
                raw.append((date_text, value))

        raw.sort(key=lambda item: item[0])
        self._series_cache[cache_key] = (mtime, raw)
        return raw
