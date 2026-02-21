"""Pydantic request/response models for the Retirement Auto-Savings API."""

import math
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_serializer, model_validator


# Timestamp format: "YYYY-MM-DD HH:mm:ss"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def _serialize_datetime(dt: datetime) -> str:
    return dt.strftime(DATETIME_FMT)


# --- Expense & Transaction ---


class Expense(BaseModel):
    """Input expense: timestamp (or date) and amount."""

    timestamp: datetime
    amount: float = Field(..., ge=0, lt=5e5)

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def timestamp_or_date(cls, data: object) -> object:
        if isinstance(data, dict) and "date" in data and "timestamp" not in data:
            return {**data, "timestamp": data["date"]}
        return data


class Transaction(BaseModel):
    """Parsed transaction with ceiling and remanent. Accepts 'date' or 'timestamp' in input.

    For flexibility (especially in /returns:* endpoints), ceiling and remanent are optional in
    input and are computed from amount when missing.
    """

    date: datetime
    amount: float
    ceiling: Optional[float] = None
    remanent: Optional[float] = None

    model_config = {"ser_json_timedelta": "iso8601"}

    @model_validator(mode="before")
    @classmethod
    def date_or_timestamp(cls, data: object) -> object:
        if isinstance(data, dict) and "timestamp" in data and "date" not in data:
            return {**data, "date": data["timestamp"]}
        return data

    @model_validator(mode="after")
    def compute_ceiling_remanent(self) -> "Transaction":
        if self.ceiling is None or self.remanent is None:
            ceiling = math.ceil(self.amount / 100) * 100
            remanent = ceiling - self.amount
            return self.model_copy(update={"ceiling": ceiling, "remanent": remanent})
        return self

    @field_serializer("date")
    def serialize_date(self, dt: datetime) -> str:
        return _serialize_datetime(dt)


# --- Periods q, p, k ---


class QPeriod(BaseModel):
    """Fixed amount override period (q)."""

    fixed: float = Field(..., ge=0, lt=5e5)
    start: datetime
    end: datetime

    @field_serializer("start", "end")
    def serialize_dt(self, dt: datetime) -> str:
        return _serialize_datetime(dt)


class PPeriod(BaseModel):
    """Extra amount addition period (p)."""

    extra: float = Field(..., ge=0, lt=5e5)
    start: datetime
    end: datetime

    @field_serializer("start", "end")
    def serialize_dt(self, dt: datetime) -> str:
        return _serialize_datetime(dt)


class KPeriod(BaseModel):
    """Evaluation grouping period (k)."""

    start: datetime
    end: datetime

    @field_serializer("start", "end")
    def serialize_dt(self, dt: datetime) -> str:
        return _serialize_datetime(dt)


# --- Parse ---


class ParseRequest(BaseModel):
    """Request body for /transactions:parse. Accepts {'expenses': [...]} or a bare list."""

    expenses: list[Expense]

    @model_validator(mode="before")
    @classmethod
    def wrap_list_if_needed(cls, data: object) -> object:
        if isinstance(data, list):
            return {"expenses": data}
        return data


class ParseResponse(BaseModel):
    """Response: list of transactions and optional totals."""

    transactions: list[Transaction]


# --- Validator ---


class ValidatorRequest(BaseModel):
    """Request body for /transactions:validator."""

    wage: float = Field(..., ge=0)
    transactions: list[Transaction]
    maxInvest: Optional[float] = Field(None, ge=0, lt=5e5)  # e.g. 200_000 for NPS


class InvalidTransaction(Transaction):
    """Transaction with validation error message."""

    message: str


class ValidatorResponse(BaseModel):
    """Response: valid, invalid, duplicate transactions."""

    valid: list[Transaction] = []
    invalid: list[InvalidTransaction] = []


# --- Filter ---


class FilterTransactionInput(BaseModel):
    """Input for filter: date/timestamp + amount; ceiling/remanent optional (computed when missing)."""

    date: datetime
    amount: float  # allow negative so we can return invalid with message
    ceiling: Optional[float] = None
    remanent: Optional[float] = None

    model_config = {"extra": "ignore"}

    @model_validator(mode="before")
    @classmethod
    def date_or_timestamp(cls, data: object) -> object:
        if isinstance(data, dict) and "timestamp" in data and "date" not in data:
            return {**data, "date": data["timestamp"]}
        return data

    @model_validator(mode="after")
    def compute_ceiling_remanent(self) -> "FilterTransactionInput":
        if self.ceiling is None or self.remanent is None:
            ceiling = math.ceil(self.amount / 100) * 100
            remanent = ceiling - self.amount
            return self.model_copy(update={"ceiling": ceiling, "remanent": remanent})
        return self


class FilterRequest(BaseModel):
    """Request body for /transactions:filter. Accepts q (or 'a'), p, k, transactions (date+amount; ceiling/remanent optional)."""

    q: list[QPeriod] = []
    p: list[PPeriod] = []
    k: list[KPeriod] = []
    transactions: list[FilterTransactionInput]

    model_config = {"extra": "ignore"}

    @model_validator(mode="before")
    @classmethod
    def q_or_a(cls, data: object) -> object:
        if isinstance(data, dict) and "a" in data and "q" not in data:
            return {**data, "q": data["a"]}
        return data


class FilterValidTransaction(Transaction):
    """Valid transaction with inKPeriod flag for filter response."""

    inKPeriod: bool = False


class FilterInvalidTransaction(BaseModel):
    """Invalid transaction in filter response: extends transaction with message (per API spec)."""

    date: datetime
    amount: float
    ceiling: Optional[float] = None
    remanent: Optional[float] = None
    message: str

    @field_serializer("date")
    def serialize_date(self, dt: datetime) -> str:
        return _serialize_datetime(dt)


class KPeriodAmount(BaseModel):
    """K period with summed amount."""

    start: datetime
    end: datetime
    amount: float

    @field_serializer("start", "end")
    def serialize_dt(self, dt: datetime) -> str:
        return _serialize_datetime(dt)


class FilterResponse(BaseModel):
    """Response: valid (with inKPeriod), invalid (date, amount, message only), savingsByDates."""

    valid: list[FilterValidTransaction] = []
    invalid: list[FilterInvalidTransaction] = []
    savingsByDates: list[KPeriodAmount] = []


# --- Returns (NPS / Index) ---


class ReturnsRequest(BaseModel):
    """Request body for /returns:nps and /returns:index."""

    age: int = Field(..., ge=0, lt=120)
    wage: float = Field(..., ge=0)  # monthly salary in INR
    inflation: float = Field(..., ge=0, le=100)
    q: list[QPeriod] = []
    p: list[PPeriod] = []
    k: list[KPeriod] = []
    transactions: list[Transaction]

    @model_validator(mode="after")
    def normalize_inflation(self) -> "ReturnsRequest":
        """Allow inflation as percentage (e.g. 5.5) or fraction (0.055); store as fraction."""
        if self.inflation > 1:
            return self.model_copy(update={"inflation": self.inflation / 100.0})
        return self


class SavingsByDatesItem(BaseModel):
    """Per-k-period result: amount, profits (NPS), taxBenefit (NPS), or return (Index)."""

    start: datetime
    end: datetime
    amount: float
    profits: Optional[float] = None
    taxBenefit: Optional[float] = None

    model_config = {"populate_by_name": True}

    @field_serializer("start", "end")
    def serialize_dt(self, dt: datetime) -> str:
        return _serialize_datetime(dt)


class ReturnsResponse(BaseModel):
    """Response for /returns:nps and /returns:index."""

    transactionsTotalAmount: float
    transactionsTotalCeiling: float
    savingsByDates: list[SavingsByDatesItem]


# --- Performance ---


class PerformanceResponse(BaseModel):
    """Response for /performance."""

    time: str  # HH:mm:ss.SSS or duration in ms
    memory: str  # XXX.XX MB
    threads: int
