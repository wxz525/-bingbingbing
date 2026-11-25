import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

RULE_BUSINESS_FIELDS = (
    "purchase_status",
    "redeem_status",
    "min_purchase_amount",
    "min_additional_purchase_amount",
    "daily_purchase_limit",
    "min_redeem_shares",
    "min_holding_shares",
    "purchase_fee_rate",
    "redeem_fee_rate",
    "purchase_confirm_days",
    "redeem_confirm_days",
    "redeem_arrival_days",
    "effective_date",
    "remark",
)

AMOUNT_FIELDS = (
    "min_purchase_amount",
    "min_additional_purchase_amount",
    "daily_purchase_limit",
)
SHARE_FIELDS = ("min_redeem_shares", "min_holding_shares")
FEE_FIELDS = ("purchase_fee_rate", "redeem_fee_rate")
DAY_FIELDS = ("purchase_confirm_days", "redeem_confirm_days", "redeem_arrival_days")
STATUS_FIELDS = ("purchase_status", "redeem_status")
DECIMAL_PATTERN = re.compile(r"^[+]?(?:\d+(?:\.\d*)?|\.\d+)$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_decimal(value: Any, precision: int, scale: int, maximum: Decimal | None = None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("必须使用十进制字符串")
    text = str(value).strip()
    if not DECIMAL_PATTERN.fullmatch(text):
        raise ValueError("必须是合法的非负十进制数")
    try:
        decimal_value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("必须是合法的非负十进制数") from exc
    if decimal_value < 0:
        raise ValueError("必须大于或等于 0")
    actual_scale = max(-decimal_value.as_tuple().exponent, 0)
    if actual_scale > scale:
        raise ValueError(f"小数位不得超过 {scale} 位")
    if decimal_value >= Decimal(10) ** (precision - scale):
        raise ValueError("数值超出数据库字段精度范围")
    if maximum is not None and decimal_value > maximum:
        raise ValueError(f"必须小于或等于 {maximum}")
    return decimal_value


def _format_decimal(value: Decimal | None, scale: int) -> str | None:
    if value is None:
        return None
    return f"{value:.{scale}f}"


class RedemptionRulePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_status: str | None = None
    redeem_status: str | None = None
    min_purchase_amount: Decimal | None = None
    min_additional_purchase_amount: Decimal | None = None
    daily_purchase_limit: Decimal | None = None
    min_redeem_shares: Decimal | None = None
    min_holding_shares: Decimal | None = None
    purchase_fee_rate: Decimal | None = None
    redeem_fee_rate: Decimal | None = None
    purchase_confirm_days: int | None = None
    redeem_confirm_days: int | None = None
    redeem_arrival_days: int | None = None
    effective_date: date | None = None
    remark: str | None = Field(default=None, max_length=512)

    _decimal_rules: ClassVar[dict[str, tuple[int, int, Decimal | None]]] = {
        **{field: (18, 2, None) for field in AMOUNT_FIELDS},
        **{field: (18, 4, None) for field in SHARE_FIELDS},
        **{field: (10, 6, Decimal("100")) for field in FEE_FIELDS},
    }

    @field_validator(*AMOUNT_FIELDS, *SHARE_FIELDS, *FEE_FIELDS, mode="before")
    @classmethod
    def validate_decimals(cls, value: Any, info: Any) -> Decimal | None:
        precision, scale, maximum = cls._decimal_rules[info.field_name]
        return _validate_decimal(value, precision, scale, maximum)

    @field_validator(*DAY_FIELDS, mode="before")
    @classmethod
    def validate_days(cls, value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("必须是整数")
        if not 0 <= value <= 32767:
            raise ValueError("必须在 0～32767 之间")
        return value

    @field_validator(*STATUS_FIELDS, mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or value not in {"OPEN", "CLOSED", "SUSPENDED"}:
            raise ValueError("仅允许 OPEN、CLOSED、SUSPENDED")
        return value

    @field_validator("effective_date", mode="before")
    @classmethod
    def validate_effective_date(cls, value: Any) -> date | None:
        if value is None:
            return None
        if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
            raise ValueError("必须使用 YYYY-MM-DD 格式")
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("必须是合法日期") from exc

    @field_validator("remark", mode="before")
    @classmethod
    def normalize_remark(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("必须是字符串")
        return value.strip() or None

    def business_data(self) -> dict[str, Any]:
        return self.model_dump(include=set(RULE_BUSINESS_FIELDS))


class RedemptionRuleSaveRequest(RedemptionRulePayload):
    expected_rule_id: int | None = Field(...)
    expected_version_no: int = Field(...)

    @field_validator("expected_rule_id", mode="before")
    @classmethod
    def validate_expected_rule_id(cls, value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("必须为大于 0 的整数或 null")
        return value

    @field_validator("expected_version_no", mode="before")
    @classmethod
    def validate_expected_version(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("必须为大于或等于 0 的整数")
        return value

    @model_validator(mode="after")
    def validate_expected_pair(self) -> "RedemptionRuleSaveRequest":
        if self.expected_rule_id is None and self.expected_version_no != 0:
            raise ValueError("首次创建时 expected_rule_id 必须为 null 且 expected_version_no 必须为 0")
        if self.expected_rule_id is not None and self.expected_version_no < 1:
            raise ValueError("已有规则时 expected_version_no 必须大于 0")
        return self


class FundBasicInfo(BaseModel):
    fund_code: str
    fund_name: str
    fund_type: str | None = None
    manager_name: str | None = None
    custodian_name: str | None = None
    establish_date: date | None = None
    currency: str | None = None
    fund_status: str | None = None


class RedemptionRuleResponse(BaseModel):
    rule_id: int
    version_no: int
    source_type: str
    purchase_status: str | None = None
    redeem_status: str | None = None
    min_purchase_amount: Decimal | None = None
    min_additional_purchase_amount: Decimal | None = None
    daily_purchase_limit: Decimal | None = None
    min_redeem_shares: Decimal | None = None
    min_holding_shares: Decimal | None = None
    purchase_fee_rate: Decimal | None = None
    redeem_fee_rate: Decimal | None = None
    purchase_confirm_days: int | None = None
    redeem_confirm_days: int | None = None
    redeem_arrival_days: int | None = None
    effective_date: date | None = None
    remark: str | None = None

    @field_serializer(*AMOUNT_FIELDS)
    def serialize_amounts(self, value: Decimal | None, info: Any) -> str | None:
        return _format_decimal(value, 2)

    @field_serializer(*SHARE_FIELDS)
    def serialize_shares(self, value: Decimal | None, info: Any) -> str | None:
        return _format_decimal(value, 4)

    @field_serializer(*FEE_FIELDS)
    def serialize_fees(self, value: Decimal | None, info: Any) -> str | None:
        return _format_decimal(value, 6)


class FundArchiveDetailResponse(BaseModel):
    basic_info: FundBasicInfo
    redemption_rule: RedemptionRuleResponse | None = None


class FundArchiveListResponse(BaseModel):
    items: list[FundBasicInfo]
    page: int
    page_size: int
    total: int


class MarketAssetInfo(BaseModel):
    name: str
    category: str
    wind_code: str | None = None
    field: str
    start_date: date
    end_date: date
    row_count: int


class MarketAssetListResponse(BaseModel):
    items: list[MarketAssetInfo]


class MarketSeriesResponse(BaseModel):
    name: str
    category: str
    wind_code: str | None = None
    field: str
    start_date: date
    end_date: date
    points: list[tuple[str, float]]
