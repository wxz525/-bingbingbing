import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.errors import FundNotFound, RequestValidationFailed, VersionConflict
from app.repository import FundArchiveRepository, RowData
from app.schemas import (
    FundArchiveDetailResponse,
    FundArchiveListResponse,
    FundBasicInfo,
    RedemptionRulePayload,
    RedemptionRuleResponse,
    RedemptionRuleSaveRequest,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_fund_code(fund_code: str) -> str:
    normalized = fund_code.strip()
    if not normalized or len(normalized) > 32:
        raise RequestValidationFailed({"fundCode": "去除首尾空白后长度必须为 1～32 个字符"})
    return normalized


def _detail_from_rows(basic: RowData, rule: RowData | None) -> FundArchiveDetailResponse:
    return FundArchiveDetailResponse(
        basic_info=FundBasicInfo.model_validate(dict(basic)),
        redemption_rule=RedemptionRuleResponse.model_validate(dict(rule)) if rule else None,
    )


def _is_duplicate_key(exc: IntegrityError) -> bool:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    return bool(args) and args[0] == 1062


class FundArchiveService:
    def __init__(self, repository: FundArchiveRepository) -> None:
        self.repository = repository

    def list_funds(self, keyword: str | None, page: int, page_size: int) -> FundArchiveListResponse:
        normalized_keyword = keyword.strip() if keyword else None
        rows, total = self.repository.list_funds(normalized_keyword, page, page_size)
        return FundArchiveListResponse(
            items=[FundBasicInfo.model_validate(dict(row)) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_fund_detail(self, fund_code: str) -> FundArchiveDetailResponse:
        fund_code = _normalize_fund_code(fund_code)
        with self.repository.engine.connect() as connection:
            basic = self.repository.get_fund(connection, fund_code)
            if basic is None:
                raise FundNotFound()
            rule = self.repository.get_current_rule(connection, fund_code)
        return _detail_from_rows(basic, rule)

    def save_manual_rule(
        self,
        fund_code: str,
        payload: RedemptionRuleSaveRequest,
        operator: str,
    ) -> FundArchiveDetailResponse:
        fund_code = _normalize_fund_code(fund_code)
        old_rule_id: int | None = None
        old_version: int | None = None
        old_source: str | None = None
        new_rule_id: int | None = None
        new_version: int | None = None

        try:
            with self.repository.engine.begin() as connection:
                if self.repository.lock_fund(connection, fund_code) is None:
                    raise FundNotFound()

                current = self.repository.get_current_rule(connection, fund_code)
                if current is not None:
                    old_rule_id = int(current["rule_id"])
                    old_version = int(current["version_no"])
                    old_source = str(current["source_type"])
                    matches = (
                        payload.expected_rule_id == old_rule_id
                        and payload.expected_version_no == old_version
                    )
                else:
                    matches = payload.expected_rule_id is None and payload.expected_version_no == 0
                if not matches:
                    raise VersionConflict()

                now = _utc_now()
                if current is not None:
                    if self.repository.archive_rule(connection, old_rule_id, operator, now) != 1:
                        raise VersionConflict()

                new_version = int(self.repository.get_max_version(connection, fund_code)) + 1
                new_rule_id = self.repository.insert_rule(
                    connection=connection,
                    fund_code=fund_code,
                    version_no=new_version,
                    payload=payload.business_data(),
                    source_type="MANUAL",
                    operator=operator,
                    created_at=now,
                )
        except VersionConflict:
            logger.warning(
                "Manual rule save result=conflict",
                extra=self._audit_fields(
                    fund_code, old_rule_id, old_version, old_source, new_rule_id, new_version, operator
                ),
            )
            raise
        except FundNotFound:
            logger.warning(
                "Manual rule save result=not_found",
                extra=self._audit_fields(
                    fund_code, old_rule_id, old_version, old_source, new_rule_id, new_version, operator
                ),
            )
            raise
        except IntegrityError as exc:
            if _is_duplicate_key(exc):
                logger.warning(
                    "Manual rule save result=conflict_duplicate_key",
                    extra=self._audit_fields(
                        fund_code, old_rule_id, old_version, old_source, new_rule_id, new_version, operator
                    ),
                )
                raise VersionConflict() from exc
            logger.exception(
                "Manual rule save result=database_error",
                extra=self._audit_fields(
                    fund_code, old_rule_id, old_version, old_source, new_rule_id, new_version, operator
                ),
            )
            raise
        except Exception:
            logger.exception(
                "Manual rule save result=failed",
                extra=self._audit_fields(
                    fund_code, old_rule_id, old_version, old_source, new_rule_id, new_version, operator
                ),
            )
            raise

        logger.info(
            "Manual rule save result=success",
            extra=self._audit_fields(
                fund_code, old_rule_id, old_version, old_source, new_rule_id, new_version, operator
            ),
        )
        return self.get_fund_detail(fund_code)

    @staticmethod
    def _audit_fields(
        fund_code: str,
        old_rule_id: int | None,
        old_version: int | None,
        old_source: str | None,
        new_rule_id: int | None,
        new_version: int | None,
        operator: str,
    ) -> dict[str, object]:
        return {
            "fund_code": fund_code,
            "old_rule_id": old_rule_id,
            "old_version": old_version,
            "old_source": old_source,
            "new_rule_id": new_rule_id,
            "new_version": new_version,
            "operator": operator,
        }


class EtlRedemptionRuleService:
    """ETL 专用入口：只归档 ETL 行，绝不更新或归档 MANUAL 行。"""

    def __init__(self, repository: FundArchiveRepository, etl_operator: str) -> None:
        self.repository = repository
        self.etl_operator = etl_operator

    def save_etl_rule(
        self,
        fund_code: str,
        payload: RedemptionRulePayload,
        etl_batch_id: str,
    ) -> FundArchiveDetailResponse:
        fund_code = _normalize_fund_code(fund_code)
        etl_batch_id = etl_batch_id.strip()
        if not etl_batch_id or len(etl_batch_id) > 64:
            raise RequestValidationFailed({"etl_batch_id": "批次幂等键长度必须为 1～64 个字符"})

        old_rule_id: int | None = None
        new_rule_id: int | None = None
        new_version: int | None = None
        result = "success"

        try:
            with self.repository.engine.begin() as connection:
                if self.repository.lock_fund(connection, fund_code) is None:
                    raise FundNotFound()

                # 基金锁串行化同批次写入；历史行命中也表示该批次已处理，直接幂等返回。
                if self.repository.get_etl_rule_by_batch(connection, fund_code, etl_batch_id) is not None:
                    result = "idempotent_replay"
                else:
                    active_etl = self.repository.get_active_rule_by_source(connection, fund_code, "ETL")
                    now = _utc_now()
                    if active_etl is not None:
                        old_rule_id = int(active_etl["rule_id"])
                        if self.repository.archive_rule(
                            connection, old_rule_id, self.etl_operator, now
                        ) != 1:
                            raise VersionConflict()

                    new_version = int(self.repository.get_max_version(connection, fund_code)) + 1
                    new_rule_id = self.repository.insert_rule(
                        connection=connection,
                        fund_code=fund_code,
                        version_no=new_version,
                        payload=payload.business_data(),
                        source_type="ETL",
                        operator=self.etl_operator,
                        created_at=now,
                        etl_batch_id=etl_batch_id,
                    )
        except IntegrityError as exc:
            if _is_duplicate_key(exc):
                raise VersionConflict() from exc
            raise

        logger.info(
            "ETL rule save result=%s",
            result,
            extra={
                "fund_code": fund_code,
                "old_rule_id": old_rule_id,
                "new_rule_id": new_rule_id,
                "new_version": new_version,
                "source_type": "ETL",
                "operator": self.etl_operator,
                "etl_batch_id": etl_batch_id,
            },
        )
        return self.get_detail(fund_code)

    def get_detail(self, fund_code: str) -> FundArchiveDetailResponse:
        with self.repository.engine.connect() as connection:
            basic = self.repository.get_fund(connection, fund_code)
            if basic is None:
                raise FundNotFound()
            rule = self.repository.get_current_rule(connection, fund_code)
        return _detail_from_rows(basic, rule)
