from fastapi import APIRouter, Depends, Query, Request

from app.auth import get_current_operator
from app.schemas import (
    FundArchiveDetailResponse,
    FundArchiveListResponse,
    RedemptionRuleSaveRequest,
)

router = APIRouter(prefix="/api/v1", tags=["fund-archive"])


def _fund_service(request: Request):
    return request.app.state.fund_archive_service


@router.get("/fund-archives", response_model=FundArchiveListResponse)
def list_fund_archives(
    request: Request,
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> FundArchiveListResponse:
    return _fund_service(request).list_funds(keyword=keyword, page=page, page_size=page_size)


@router.get("/fund-archives/{fundCode}", response_model=FundArchiveDetailResponse)
def get_fund_archive(request: Request, fundCode: str) -> FundArchiveDetailResponse:
    return _fund_service(request).get_fund_detail(fundCode)


@router.put("/fund-archives/{fundCode}/redemption-rule", response_model=FundArchiveDetailResponse)
def save_redemption_rule(
    request: Request,
    fundCode: str,
    payload: RedemptionRuleSaveRequest,
    operator: str = Depends(get_current_operator),
) -> FundArchiveDetailResponse:
    return _fund_service(request).save_manual_rule(fundCode, payload, operator)
