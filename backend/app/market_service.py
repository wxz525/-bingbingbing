import math
from datetime import date, timedelta

from app.errors import MarketAssetNotFound
from app.market_repository import MarketDataRepository
from app.schemas import (
    MarketAssetInfo,
    MarketAssetListResponse,
    MarketCompareResponse,
    MarketCompareSeries,
    MarketIndicatorListResponse,
    MarketIndicatorResponse,
    MarketIndicatorSummary,
    MarketRankingItem,
    MarketRankingResponse,
    MarketSeriesResponse,
)

MAX_COMPARE_SERIES = 5
MAX_COMPARE_DATES = 1200
MIN_WINDOW_POINTS = 20

# 由现有序列实时折算的比值 / 利差指标，不引入外部数据。
INDICATOR_DEFINITIONS: list[dict[str, str]] = [
    {
        "key": "gold_silver",
        "name": "金银比",
        "kind": "ratio",
        "unit": "倍",
        "numerator": "COMEX黄金期货",
        "denominator": "COMEX白银期货",
        "description": "黄金 / 白银，数值抬升通常意味着避险需求强于工业需求",
    },
    {
        "key": "gold_copper",
        "name": "金铜比",
        "kind": "ratio",
        "unit": "倍",
        "numerator": "COMEX黄金期货",
        "denominator": "COMEX铜期货",
        "description": "黄金 / 铜，上行代表避险需求走强或增长预期走弱",
    },
    {
        "key": "csi300_csi500",
        "name": "沪深300 / 中证500",
        "kind": "ratio",
        "unit": "倍",
        "numerator": "沪深300",
        "denominator": "中证500",
        "description": "大盘 / 中盘风格比，上行代表资金偏向大盘蓝筹",
    },
    {
        "key": "chinext_csi300",
        "name": "创业板指 / 沪深300",
        "kind": "ratio",
        "unit": "倍",
        "numerator": "创业板指",
        "denominator": "沪深300",
        "description": "成长 / 价值风格比，上行代表成长风格占优",
    },
    {
        "key": "hsi_csi300",
        "name": "恒生指数 / 沪深300",
        "kind": "ratio",
        "unit": "倍",
        "numerator": "恒生指数",
        "denominator": "沪深300",
        "description": "港 / A 股相对强弱，港股走强时抬升",
    },
    {
        "key": "spx_csi300",
        "name": "标普500 / 沪深300",
        "kind": "ratio",
        "unit": "倍",
        "numerator": "标普500",
        "denominator": "沪深300",
        "description": "中美权益相对强弱，未做汇率调整，仅看趋势",
    },
    {
        "key": "nasdaq_spx",
        "name": "纳指100 / 标普500",
        "kind": "ratio",
        "unit": "倍",
        "numerator": "纳斯达克100",
        "denominator": "标普500",
        "description": "科技 / 大盘比，上行代表科技板块领涨",
    },
    {
        "key": "cn_us_10y",
        "name": "中美10年国债利差",
        "kind": "spread",
        "unit": "pp",
        "numerator": "中国10年国债收益率",
        "denominator": "美国10年期国债收益率",
        "description": "中国10Y − 美国10Y，单位为百分点",
    },
    {
        "key": "cn_term_10y_1y",
        "name": "中国期限利差 10Y−1Y",
        "kind": "spread",
        "unit": "pp",
        "numerator": "中国10年国债收益率",
        "denominator": "中国1年国债收益率",
        "description": "曲线陡峭度，倒挂时转负",
    },
    {
        "key": "cn_term_30y_10y",
        "name": "中国期限利差 30Y−10Y",
        "kind": "spread",
        "unit": "pp",
        "numerator": "中国30年国债收益率",
        "denominator": "中国10年国债收益率",
        "description": "超长端相对 10 年的期限溢价",
    },
    {
        "key": "cn_de_10y",
        "name": "中德10年国债利差",
        "kind": "spread",
        "unit": "pp",
        "numerator": "中国10年国债收益率",
        "denominator": "德国10年期国债收益率",
        "description": "中国10Y − 德国10Y，单位为百分点",
    },
    {
        "key": "us_de_10y",
        "name": "美德10年国债利差",
        "kind": "spread",
        "unit": "pp",
        "numerator": "美国10年期国债收益率",
        "denominator": "德国10年期国债收益率",
        "description": "美国10Y − 德国10Y，单位为百分点",
    },
]

INDICATOR_MAP = {item["key"]: item for item in INDICATOR_DEFINITIONS}


class MarketService:
    def __init__(self, repository: MarketDataRepository) -> None:
        self._repository = repository
        self._indicator_cache: dict[str, list[tuple[str, float]]] = {}

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

    def _indicator_full(self, key: str) -> list[tuple[str, float]]:
        """按分子/分母序列折算比值或利差，日期取并集并前值填充。"""
        cached = self._indicator_cache.get(key)
        if cached is not None:
            return cached
        definition = INDICATOR_MAP.get(key)
        if definition is None:
            raise MarketAssetNotFound()

        numerator = self._repository.get_series(definition["numerator"]) or []
        denominator = self._repository.get_series(definition["denominator"]) or []
        if not numerator or not denominator:
            self._indicator_cache[key] = []
            return []

        numerator_map = dict(numerator)
        denominator_map = dict(denominator)
        is_ratio = definition["kind"] == "ratio"

        result: list[tuple[str, float]] = []
        last_numerator: float | None = None
        last_denominator: float | None = None
        for date_text in sorted(set(numerator_map) | set(denominator_map)):
            if date_text in numerator_map:
                last_numerator = numerator_map[date_text]
            if date_text in denominator_map:
                last_denominator = denominator_map[date_text]
            if last_numerator is None or last_denominator is None:
                continue
            if is_ratio:
                if last_denominator == 0:
                    continue
                result.append((date_text, last_numerator / last_denominator))
            else:
                result.append((date_text, last_numerator - last_denominator))

        self._indicator_cache[key] = result
        return result

    def _clip(self, points: list[tuple[str, float]], days: int | None) -> list[tuple[str, float]]:
        if days is None or not points:
            return points
        latest = date.fromisoformat(points[-1][0])
        cutoff = latest - timedelta(days=days)
        return [point for point in points if date.fromisoformat(point[0]) >= cutoff]

    def list_indicators(self, days: int | None = None) -> MarketIndicatorListResponse:
        items: list[MarketIndicatorSummary] = []
        for definition in INDICATOR_DEFINITIONS:
            points = self._clip(self._indicator_full(definition["key"]), days)
            if len(points) < 2:
                continue
            latest = points[-1][1]
            start_value = points[0][1]
            change = latest - start_value
            items.append(
                MarketIndicatorSummary(
                    key=definition["key"],
                    name=definition["name"],
                    kind=definition["kind"],
                    unit=definition["unit"],
                    description=definition["description"],
                    latest=latest,
                    latest_date=date.fromisoformat(points[-1][0]),
                    change=change,
                    change_pct=(change / abs(start_value)) if start_value else None,
                    point_count=len(points),
                )
            )
        return MarketIndicatorListResponse(days=days, items=items)

    def get_indicator(self, key: str, days: int | None = None) -> MarketIndicatorResponse:
        definition = INDICATOR_MAP.get(key)
        if definition is None:
            raise MarketAssetNotFound()
        points = self._clip(self._indicator_full(key), days)
        if len(points) < 2:
            raise MarketAssetNotFound()
        values = [value for _, value in points]
        latest = values[-1]
        return MarketIndicatorResponse(
            key=key,
            name=definition["name"],
            kind=definition["kind"],
            unit=definition["unit"],
            description=definition["description"],
            start_date=date.fromisoformat(points[0][0]),
            end_date=date.fromisoformat(points[-1][0]),
            latest=latest,
            change=latest - values[0],
            min_value=min(values),
            max_value=max(values),
            points=points,
        )
