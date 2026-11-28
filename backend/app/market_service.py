import math
from datetime import date, timedelta

from app.errors import MarketAssetNotFound
from app.market_repository import MarketDataRepository
from app.schemas import (
    MarketAssetInfo,
    MarketAssetListResponse,
    MarketScatterPoint,
    MarketScatterResponse,
    MarketSeriesResponse,
)

RISK_FREE_RATE = 0.02
MIN_SCATTER_POINTS = 60


def _daily_returns(values: list[float]) -> list[float]:
    returns: list[float] = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        if previous != 0:
            returns.append(values[index] / previous - 1)
    return returns


def _max_drawdown(values: list[float]) -> float:
    peak = values[0]
    worst = 0.0
    for value in values[1:]:
        if value > peak:
            peak = value
        if peak != 0:
            worst = min(worst, value / peak - 1)
    return worst


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

    def get_scatter(self, years: int | None = 3) -> MarketScatterResponse:
        """按年化波动率（风险）与年化收益率（收益）汇总全部价格类标的。"""
        assets = self._repository.list_assets()
        series_by_name: dict[str, list[tuple[str, float]]] = {}
        excluded: list[str] = []
        latest: date | None = None

        for asset in assets:
            name = str(asset["name"])
            if str(asset["field"]) == "yield":
                # 收益率为利率指标，无法折算成价格收益，不参与散点统计。
                excluded.append(name)
                continue
            points = self._repository.get_series(name) or []
            if len(points) < MIN_SCATTER_POINTS:
                continue
            series_by_name[name] = points
            end = date.fromisoformat(points[-1][0])
            if latest is None or end > latest:
                latest = end

        cutoff: date | None = None
        if latest is not None and years is not None:
            cutoff = latest - timedelta(days=365 * years)

        items: list[MarketScatterPoint] = []
        for asset in assets:
            name = str(asset["name"])
            points = series_by_name.get(name)
            if not points:
                continue
            if cutoff is not None:
                points = [point for point in points if date.fromisoformat(point[0]) >= cutoff]
            if len(points) < MIN_SCATTER_POINTS:
                continue

            values = [point[1] for point in points]
            if values[0] <= 0:
                continue
            span_days = (
                date.fromisoformat(points[-1][0]) - date.fromisoformat(points[0][0])
            ).days
            if span_days <= 0:
                continue
            span_years = span_days / 365
            # 按实际日历跨度折算年化，兼容交易日序列（约 250 期/年）与 7×24 序列（约 365 期/年）。
            periods_per_year = (len(values) - 1) / span_years
            growth = values[-1] / values[0]
            annual_return = growth ** (1 / span_years) - 1
            returns = _daily_returns(values)
            if len(returns) < MIN_SCATTER_POINTS - 1:
                continue
            mean = sum(returns) / len(returns)
            variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
            annual_volatility = math.sqrt(variance) * math.sqrt(periods_per_year)
            sharpe = (
                (annual_return - RISK_FREE_RATE) / annual_volatility
                if annual_volatility > 0
                else None
            )
            items.append(
                MarketScatterPoint(
                    name=name,
                    category=str(asset["category"]),
                    wind_code=asset["wind_code"],  # type: ignore[arg-type]
                    annual_return=annual_return,
                    annual_volatility=annual_volatility,
                    sharpe=sharpe,
                    max_drawdown=_max_drawdown(values),
                    start_date=date.fromisoformat(points[0][0]),
                    end_date=date.fromisoformat(points[-1][0]),
                    sample_count=len(points),
                )
            )

        return MarketScatterResponse(
            years=years,
            latest_date=latest,
            risk_free_rate=RISK_FREE_RATE,
            items=items,
            excluded=excluded,
        )
