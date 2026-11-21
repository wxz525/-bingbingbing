from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import router
from app.errors import VersionConflict, register_exception_handlers
from app.schemas import (
    FundArchiveDetailResponse,
    FundArchiveListResponse,
    FundBasicInfo,
    RedemptionRuleResponse,
)


class FakeFundArchiveService:
    def __init__(self) -> None:
        self.save_error: Exception | None = None
        self.saved_operator: str | None = None

    @staticmethod
    def detail() -> FundArchiveDetailResponse:
        return FundArchiveDetailResponse(
            basic_info=FundBasicInfo(fund_code="000001", fund_name="示例基金", currency="CNY"),
            redemption_rule=RedemptionRuleResponse(
                rule_id=1,
                version_no=1,
                source_type="MANUAL",
                purchase_status="OPEN",
                redeem_status="OPEN",
                min_purchase_amount=Decimal("100"),
                min_redeem_shares=Decimal("0"),
                purchase_fee_rate=Decimal("0.15"),
                effective_date=date(2026, 11, 21),
            ),
        )

    def list_funds(self, keyword: str | None, page: int, page_size: int) -> FundArchiveListResponse:
        return FundArchiveListResponse(
            items=[self.detail().basic_info],
            page=page,
            page_size=page_size,
            total=1,
        )

    def get_fund_detail(self, fund_code: str) -> FundArchiveDetailResponse:
        return self.detail()

    def save_manual_rule(self, fund_code: str, payload, operator: str) -> FundArchiveDetailResponse:
        if self.save_error:
            raise self.save_error
        self.saved_operator = operator
        return self.detail()


@pytest.fixture()
def service() -> FakeFundArchiveService:
    return FakeFundArchiveService()


@pytest.fixture()
def client(service: FakeFundArchiveService) -> TestClient:
    application = FastAPI()
    application.state.default_operator = "system-test"
    application.state.fund_archive_service = service

    @application.middleware("http")
    async def login_context(request, call_next):
        request.state.current_user = {"sub": "alice"}
        return await call_next(request)

    application.include_router(router)
    register_exception_handlers(application)
    return TestClient(application)


def valid_payload() -> dict:
    return {
        "expected_rule_id": None,
        "expected_version_no": 0,
        "purchase_status": "OPEN",
        "redeem_status": "OPEN",
        "min_purchase_amount": "100.00",
        "min_redeem_shares": "0.0000",
        "purchase_fee_rate": "0.150000",
        "purchase_confirm_days": 1,
        "effective_date": "2026-11-21",
        "remark": "  人工维护  ",
    }


def test_list_and_decimal_json_types(client: TestClient) -> None:
    list_response = client.get("/api/v1/fund-archives?page=1&page_size=20")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    detail_response = client.get("/api/v1/fund-archives/000001")
    assert detail_response.status_code == 200
    rule = detail_response.json()["redemption_rule"]
    assert rule["min_purchase_amount"] == "100.00"
    assert rule["min_redeem_shares"] == "0.0000"
    assert rule["purchase_fee_rate"] == "0.150000"
    assert rule["daily_purchase_limit"] is None


@pytest.mark.parametrize("query", ["page=0", "page=1&page_size=101", "page=abc"])
def test_invalid_pagination_returns_400(client: TestClient, query: str) -> None:
    response = client.get(f"/api/v1/fund-archives?{query}")
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_controlled_fields_are_rejected(client: TestClient) -> None:
    payload = valid_payload() | {"created_by": "attacker", "source_type": "ETL", "is_deleted": 1}
    response = client.put("/api/v1/fund-archives/000001/redemption-rule", json=payload)
    assert response.status_code == 400
    assert set(response.json()["field_errors"]) >= {"created_by", "source_type", "is_deleted"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_purchase_amount", "-0.01"),
        ("min_redeem_shares", "0.00001"),
        ("purchase_fee_rate", "100.000001"),
        ("purchase_status", "UNKNOWN"),
        ("purchase_confirm_days", 32768),
        ("effective_date", "2026-02-30"),
        ("min_purchase_amount", 1.25),
    ],
)
def test_invalid_rule_fields_return_400(client: TestClient, field: str, value) -> None:
    response = client.put(
        "/api/v1/fund-archives/000001/redemption-rule",
        json=valid_payload() | {field: value},
    )
    assert response.status_code == 400
    assert field in response.json()["field_errors"]


def test_operator_comes_from_login_context(client: TestClient, service: FakeFundArchiveService) -> None:
    response = client.put("/api/v1/fund-archives/000001/redemption-rule", json=valid_payload())
    assert response.status_code == 200
    assert service.saved_operator == "alice"


def test_version_conflict_response(client: TestClient, service: FakeFundArchiveService) -> None:
    service.save_error = VersionConflict()
    response = client.put("/api/v1/fund-archives/000001/redemption-rule", json=valid_payload())
    assert response.status_code == 409
    assert response.json() == {
        "code": "VERSION_CONFLICT",
        "message": "申赎要素已更新，请刷新后重试",
        "field_errors": {},
    }
