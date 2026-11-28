import math
from datetime import date, timedelta

from app.errors import MarketAssetNotFound
from app.market_repository import MarketDataRepository
from app.schemas import (
    MarketAssetInfo,
    MarketAssetListResponse,
    MarketCompareResponse,
    MarketCompareSeries,
    MarketRankingItem,
    MarketRankingResponse,
    MarketSeriesResponse,
)

MAX_COMPARE_SERIES = 5
MAX_COMPARE_DATES = 1200
MIN_WINDOW_POINTS = 20


class MarketService:
    def __init__(self, repository: MarketDataRepository) -> None:
        self._repository = repository

    def list_assets(self) -> MarketAssetListResponse:
        items = [
            MarketAssetInfo(
                name=str(asset["name"]),
                category=str(asset["category"]),
                wind_code=asset["wind_code"],  # type: ignore[arg-type]
                field=str(asset["field"]),
                start_date=date.fromisoformat(str(asset["start_date"])),
                end_date=date.fromisoformat(str(asset["end_date"])),
                row_count=int(asset["row_count"]),  # type: ignore[arg-type]
            )
            for asset in self._repository.list_assets()
        ]
        return MarketAssetListResponse(items=items)

    def get_series(self, name: str) -> MarketSeriesResponse:
        asset = next(
            (item for item in self._repository.list_assets() if item["name"] == name),
            None,
        )
        if asset is None:
            raise MarketAssetNotFound()
        points = self._repository.get_series(name) or []
        return MarketSeriesResponse(
            name=name,
            category=str(asset["category"]),
            wind_code=asset["wind_code"],  # type: ignore[arg-type]
            field=str(asset["field"]),
            start_date=date.fromisoformat(str(asset["start_date"])),
            end_date=date.fromisoformat(str(asset["end_date"])),
            points=points,
        )

    def _price_assets(self) -> list[dict[str, object]]:
        return [
            asset for asset in self._repository.list_assets() if str(asset["field"]) != "yield"
        ]

    def _window(self, days: int | None) -> tuple[date | None, date | None]:
        """全局数据截止日与区间起点，保证对比与排行使用同一时间窗口。"""
        assets = self._price_assets()
        if not assets:
            return None, None
        latest = max(date.fromisoformat(str(asset["end_date"])) for asset in assets)
        cutoff = latest - timedelta(days=days) if days is not None else None
        return latest, cutoff

    def _window_points(
        self,
        points: list[tuple[str, float]],
        cutoff: date | None,
    ) -> list[tuple[str, float]]:
        if cutoff is None:
            return points
        return [point for point in points if date.fromisoformat(point[0]) >= cutoff]

    def get_compare(self, names: list[str], days: int | None = None) -> MarketCompareResponse:
        """多标的归一化对比：统一到共同起点 = 100，按并集日期前值填充对齐。"""
        assets = {str(asset["name"]): asset for asset in self._repository.list_assets()}
        latest, cutoff = self._window(days)

        selected: list[tuple[str, dict[str, object], list[tuple[str, float]]]] = []
        for name in names[:MAX_COMPARE_SERIES]:
            asset = assets.get(name)
            if asset is None or str(asset["field"]) == "yield":
                continue
            points = self._repository.get_series(name) or []
            window = self._window_points(points, cutoff)
            if len(window) < 2:
                continue
            selected.append((name, asset, window))
        if not selected:
            raise MarketAssetNotFound()

        # 共同起点取各标的在窗口内第一个交易日的最大值，保证所有标的都有基准价。
        common_start = max(date.fromisoformat(window[0][0]) for _, _, window in selected)

        union: set[str] = set()
        for _, _, window in selected:
            for date_text, _ in window:
                if date.fromisoformat(date_text) >= common_start:
                    union.add(date_text)
        date_list = sorted(union)
        if len(date_list) > MAX_COMPARE_DATES:
            step = math.ceil(len(date_list) / MAX_COMPARE_DATES)
            trimmed = date_list[::step]
            if trimmed[-1] != date_list[-1]:
                trimmed.append(date_list[-1])
            date_list = trimmed

        items: list[MarketCompareSeries] = []
        for name, asset, window in selected:
            base = next(
                (
                    value
                    for date_text, value in reversed(window)
                    if date.fromisoformat(date_text) <= common_start
                ),
                None,
            )
            if base is None or base <= 0:
                continue

            values: list[float | None] = []
            pointer = 0
            last_value: float | None = None
            for date_text in date_list:
                while pointer < len(window) and window[pointer][0] <= date_text:
                    last_value = window[pointer][1]
                    pointer += 1
                values.append(None if last_value is None else last_value / base * 100)

            latest_value = next((value for value in reversed(values) if value is not None), None)
            if latest_value is None:
                continue
            items.append(
                MarketCompareSeries(
                    name=name,
                    category=str(asset["category"]),
                    base_date=common_start,
                    base_value=base,
                    latest_value=latest_value,
                    total_return=latest_value / 100 - 1,
                    values=values,
                )
            )

        items.sort(key=lambda item: item.total_return, reverse=True)
        return MarketCompareResponse(
            days=days,
            start_date=common_start,
            end_date=latest,
            dates=date_list,
            items=items,
        )

    def get_ranking(self, days: int | None = None) -> MarketRankingResponse:
        """区间涨跌排行：按窗口内首末收盘价计算涨跌幅，收益率类标的剔除。"""
        latest, cutoff = self._window(days)
        items: list[MarketRankingItem] = []
        for asset in self._price_assets():
            name = str(asset["name"])
            points = self._repository.get_series(name) or []
            window = self._window_points(points, cutoff)
            if len(window) < MIN_WINDOW_POINTS:
                continue
            start_value = window[0][1]
            end_value = window[-1][1]
            if start_value <= 0:
                continue
            items.append(
                MarketRankingItem(
                    name=name,
                    category=str(asset["category"]),
                    start_date=date.fromisoformat(window[0][0]),
                    end_date=date.fromisoformat(window[-1][0]),
                    start_value=start_value,
                    end_value=end_value,
                    return_rate=end_value / start_value - 1,
                    sample_count=len(window),
                )
            )
        items.sort(key=lambda item: item.return_rate, reverse=True)
        start_date = min((item.start_date for item in items), default=None)
        return MarketRankingResponse(
            days=days,
            start_date=start_date,
            end_date=latest,
            items=items,
        )
