import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.exc import SQLAlchemyError

from app.errors import VersionConflict
from app.repository import FundArchiveRepository
from app.schemas import RedemptionRulePayload, RedemptionRuleSaveRequest
from app.service import EtlRedemptionRuleService, FundArchiveService
from app.tables import fund_archive, fund_redemption_rule

TEST_MYSQL_URL = os.getenv("TEST_MYSQL_URL")
DDL_FILE = Path(__file__).resolve().parents[1] / "migrations" / "V001__add_fund_archive.sql"

pytestmark = pytest.mark.skipif(
    not TEST_MYSQL_URL,
    reason="设置指向专用 MySQL 测试库的 TEST_MYSQL_URL 后运行集成测试",
)


@pytest.fixture()
def database():
    engine = create_engine(TEST_MYSQL_URL, pool_pre_ping=True)
    if not (engine.url.database or "").endswith("_test"):
        engine.dispose()
        pytest.fail("集成测试只允许使用名称以 _test 结尾的专用数据库")

    statements = [statement.strip() for statement in DDL_FILE.read_text(encoding="utf-8").split(";") if statement.strip()]
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS fund_redemption_rule")
        connection.exec_driver_sql("DROP TABLE IF EXISTS fund_archive")
        for statement in statements:
            connection.exec_driver_sql(statement)
        connection.execute(
            insert(fund_archive),
            {"fund_code": "F001", "fund_name": "集成测试基金", "fund_status": "NORMAL"},
        )

    repository = FundArchiveRepository(engine)
    yield engine, repository, FundArchiveService(repository), EtlRedemptionRuleService(repository, "etl-test")
    engine.dispose()


def rule_payload() -> RedemptionRulePayload:
    return RedemptionRulePayload(
        purchase_status="OPEN",
        redeem_status="OPEN",
        min_purchase_amount="1000.00",
        min_additional_purchase_amount="100.00",
        min_redeem_shares="1.0000",
        min_holding_shares="0.0000",
        purchase_fee_rate="0.150000",
        redeem_fee_rate="0.500000",
        purchase_confirm_days=1,
        redeem_confirm_days=1,
        redeem_arrival_days=2,
        effective_date="2026-11-21",
        remark="ETL 初始值",
    )


def save_request(current=None, **changes) -> RedemptionRuleSaveRequest:
    data = rule_payload().model_dump(mode="json")
    data.update(changes)
    data["expected_rule_id"] = current.rule_id if current else None
    data["expected_version_no"] = current.version_no if current else 0
    return RedemptionRuleSaveRequest(**data)


def test_manual_priority_etl_isolation_and_batch_idempotency(database) -> None:
    engine, _, service, etl_service = database
    with engine.connect() as connection:
        original_updated_at = connection.execute(
            select(fund_archive.c.updated_at).where(fund_archive.c.fund_code == "F001")
        ).scalar_one()

    etl_detail = etl_service.save_etl_rule("F001", rule_payload(), "batch-1")
    assert etl_detail.redemption_rule.source_type == "ETL"
    old_etl_id = etl_detail.redemption_rule.rule_id

    manual_detail = service.save_manual_rule(
        "F001",
        save_request(etl_detail.redemption_rule, min_purchase_amount="100.00", remark="人工值"),
        "alice",
    )
    assert manual_detail.redemption_rule.source_type == "MANUAL"
    assert manual_detail.redemption_rule.version_no == 2
    assert manual_detail.redemption_rule.min_purchase_amount == 100
    assert manual_detail.redemption_rule.min_redeem_shares == 1

    with engine.connect() as connection:
        archived_etl = connection.execute(
            select(fund_redemption_rule).where(fund_redemption_rule.c.rule_id == old_etl_id)
        ).mappings().one()
        assert archived_etl["is_deleted"] == 1
        assert archived_etl["deleted_by"] == "alice"
        assert archived_etl["deleted_at"] is not None
        manual_before = dict(
            connection.execute(
                select(fund_redemption_rule).where(fund_redemption_rule.c.rule_id == manual_detail.redemption_rule.rule_id)
            ).mappings().one()
        )

    etl_service.save_etl_rule("F001", rule_payload(), "batch-2")
    etl_service.save_etl_rule("F001", rule_payload(), "batch-2")
    detail_after_etl = service.get_fund_detail("F001")
    assert detail_after_etl.redemption_rule.rule_id == manual_detail.redemption_rule.rule_id
    assert detail_after_etl.redemption_rule.source_type == "MANUAL"
    assert detail_after_etl.redemption_rule.min_purchase_amount == 100

    with engine.connect() as connection:
        rows = connection.execute(
            select(fund_redemption_rule).where(fund_redemption_rule.c.fund_code == "F001")
        ).mappings().all()
        assert len(rows) == 3
        assert len([row for row in rows if not row["is_deleted"] and row["source_type"] == "MANUAL"]) == 1
        assert len([row for row in rows if not row["is_deleted"] and row["source_type"] == "ETL"]) == 1
        manual_after = connection.execute(
            select(fund_redemption_rule).where(fund_redemption_rule.c.rule_id == manual_detail.redemption_rule.rule_id)
        ).mappings().one()
        assert dict(manual_after) == manual_before
        assert connection.execute(
            select(fund_archive.c.updated_at).where(fund_archive.c.fund_code == "F001")
        ).scalar_one() == original_updated_at


def test_first_manual_rule_starts_at_version_one(database) -> None:
    _, _, service, _ = database
    detail = service.save_manual_rule("F001", save_request(), "alice")
    assert detail.redemption_rule.source_type == "MANUAL"
    assert detail.redemption_rule.version_no == 1
    assert detail.redemption_rule.rule_id > 0


def test_concurrent_stale_save_returns_409(database) -> None:
    engine, _, service, etl_service = database
    current = etl_service.save_etl_rule("F001", rule_payload(), "batch-1").redemption_rule
    request = save_request(current)
    barrier = Barrier(2)

    def save(operator: str) -> int:
        barrier.wait()
        try:
            service.save_manual_rule("F001", request, operator)
            return 200
        except VersionConflict:
            return 409

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, ("alice", "bob")))
    assert sorted(results) == [200, 409]

    with engine.connect() as connection:
        assert connection.execute(
            select(func.count()).select_from(fund_redemption_rule).where(fund_redemption_rule.c.fund_code == "F001")
        ).scalar_one() == 2


def test_insert_failure_rolls_back_archive(database, monkeypatch) -> None:
    engine, repository, service, etl_service = database
    current = etl_service.save_etl_rule("F001", rule_payload(), "batch-1").redemption_rule

    def fail_insert(*args, **kwargs):
        raise SQLAlchemyError("forced insert failure")

    monkeypatch.setattr(repository, "insert_rule", fail_insert)
    with pytest.raises(SQLAlchemyError):
        service.save_manual_rule("F001", save_request(current), "alice")

    with engine.connect() as connection:
        rows = connection.execute(
            select(fund_redemption_rule).where(fund_redemption_rule.c.fund_code == "F001")
        ).mappings().all()
        assert len(rows) == 1
        assert rows[0]["rule_id"] == current.rule_id
        assert rows[0]["is_deleted"] == 0
        assert rows[0]["deleted_by"] is None
        assert rows[0]["deleted_at"] is None
