from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, Engine, case, func, insert, or_, select, update

from app.tables import fund_archive, fund_redemption_rule

RowData = Mapping[str, Any]


def _keyword_pattern(keyword: str) -> str:
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class FundArchiveRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def list_funds(self, keyword: str | None, page: int, page_size: int) -> tuple[list[RowData], int]:
        conditions = []
        if keyword:
            pattern = _keyword_pattern(keyword)
            conditions.append(
                or_(
                    fund_archive.c.fund_code.like(pattern, escape="\\"),
                    fund_archive.c.fund_name.like(pattern, escape="\\"),
                )
            )

        count_statement = select(func.count()).select_from(fund_archive)
        statement = select(fund_archive).order_by(fund_archive.c.fund_code)
        if conditions:
            count_statement = count_statement.where(*conditions)
            statement = statement.where(*conditions)
        statement = statement.limit(page_size).offset((page - 1) * page_size)

        with self.engine.connect() as connection:
            total = connection.execute(count_statement).scalar_one()
            rows = connection.execute(statement).mappings().all()
        return rows, total

    def get_fund(self, connection: Connection, fund_code: str) -> RowData | None:
        return connection.execute(
            select(fund_archive).where(fund_archive.c.fund_code == fund_code)
        ).mappings().first()

    def lock_fund(self, connection: Connection, fund_code: str) -> RowData | None:
        return connection.execute(
            select(fund_archive.c.fund_code)
            .where(fund_archive.c.fund_code == fund_code)
            .with_for_update()
        ).mappings().first()

    def get_current_rule(self, connection: Connection, fund_code: str) -> RowData | None:
        priority = case((fund_redemption_rule.c.source_type == "MANUAL", 1), else_=2)
        return connection.execute(
            select(fund_redemption_rule)
            .where(
                fund_redemption_rule.c.fund_code == fund_code,
                fund_redemption_rule.c.is_deleted == 0,
                fund_redemption_rule.c.source_type.in_(("MANUAL", "ETL")),
            )
            .order_by(priority)
            .limit(1)
        ).mappings().first()

    def get_active_rule_by_source(
        self,
        connection: Connection,
        fund_code: str,
        source_type: str,
    ) -> RowData | None:
        return connection.execute(
            select(fund_redemption_rule)
            .where(
                fund_redemption_rule.c.fund_code == fund_code,
                fund_redemption_rule.c.is_deleted == 0,
                fund_redemption_rule.c.source_type == source_type,
            )
            .limit(1)
        ).mappings().first()

    def get_etl_rule_by_batch(
        self,
        connection: Connection,
        fund_code: str,
        etl_batch_id: str,
    ) -> RowData | None:
        return connection.execute(
            select(fund_redemption_rule)
            .where(
                fund_redemption_rule.c.fund_code == fund_code,
                fund_redemption_rule.c.source_type == "ETL",
                fund_redemption_rule.c.etl_batch_id == etl_batch_id,
            )
            .order_by(fund_redemption_rule.c.version_no.desc())
            .limit(1)
        ).mappings().first()

    def get_max_version(self, connection: Connection, fund_code: str) -> int:
        return connection.execute(
            select(func.coalesce(func.max(fund_redemption_rule.c.version_no), 0)).where(
                fund_redemption_rule.c.fund_code == fund_code
            )
        ).scalar_one()

    def archive_rule(
        self,
        connection: Connection,
        rule_id: int,
        operator: str,
        archived_at: datetime,
    ) -> int:
        result = connection.execute(
            update(fund_redemption_rule)
            .where(
                fund_redemption_rule.c.rule_id == rule_id,
                fund_redemption_rule.c.is_deleted == 0,
            )
            .values(is_deleted=1, deleted_by=operator, deleted_at=archived_at)
        )
        return result.rowcount

    def insert_rule(
        self,
        connection: Connection,
        fund_code: str,
        version_no: int,
        payload: RowData,
        source_type: str,
        operator: str,
        created_at: datetime,
        etl_batch_id: str | None = None,
    ) -> int:
        values = dict(payload)
        values.update(
            fund_code=fund_code,
            version_no=version_no,
            source_type=source_type,
            etl_batch_id=etl_batch_id,
            is_deleted=0,
            created_by=operator,
            created_at=created_at,
        )
        result = connection.execute(insert(fund_redemption_rule), values)
        return int(result.inserted_primary_key[0])
