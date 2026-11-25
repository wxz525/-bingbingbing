from datetime import date

from app.errors import MarketAssetNotFound
from app.market_repository import MarketDataRepository
from app.schemas import MarketAssetInfo, MarketAssetListResponse, MarketSeriesResponse


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
