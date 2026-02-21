"""Transaction endpoints: parse, validator, filter."""

from fastapi import APIRouter

from app import domain
from app.domain import _in_range
from app.schemas import (
    FilterInvalidTransaction,
    FilterRequest,
    FilterResponse,
    FilterValidTransaction,
    InvalidTransaction,
    KPeriodAmount,
    ParseRequest,
    Transaction,
    ValidatorRequest,
    ValidatorResponse,
)

router = APIRouter()


@router.post("/transactions:parse", response_model=list[Transaction])
def parse_transactions(body: ParseRequest) -> list[Transaction]:
    """Parse expenses into transactions with ceiling and remanent. Returns a bare array."""
    expenses = [(e.timestamp, e.amount) for e in body.expenses]
    raw = domain.parse_expenses(expenses)
    return domain.build_transactions(raw)


def _validator_classify(
    wage: float,
    transactions: list[Transaction],
    max_invest: float | None,
) -> tuple[list[Transaction], list[InvalidTransaction]]:
    """Classify into valid, invalid. Duplicates go to invalid with message."""
    seen: set[tuple[str, float]] = set()
    valid: list[Transaction] = []
    invalid: list[InvalidTransaction] = []

    for t in transactions:
        key = (t.date.isoformat(), t.amount)
        if key in seen:
            invalid.append(InvalidTransaction(**t.model_dump(), message="duplicate transaction (same date and amount)"))
            continue
        seen.add(key)

        msg = None
        if t.remanent is not None and t.remanent < 0:
            msg = "remanent cannot be negative"
        elif max_invest is not None and t.remanent is not None and t.remanent > max_invest:
            msg = f"remanent {t.remanent} exceeds maximum invest {max_invest}"
        elif t.amount <= 0:
            msg = "amount must be positive"
        elif t.ceiling is not None and t.remanent is not None and t.amount != (t.ceiling - t.remanent):
            msg = "amount must be equal to the ceiling minus the remanent"

        if msg:
            invalid.append(InvalidTransaction(**t.model_dump(), message=msg))
        else:
            valid.append(t)

    return valid, invalid


@router.post("/transactions:validator", response_model=ValidatorResponse)
def validate_transactions(body: ValidatorRequest) -> ValidatorResponse:
    """Validate transactions by wage and max invest; duplicates are returned in invalid with message."""
    valid, invalid = _validator_classify(
        body.wage,
        body.transactions,
        body.maxInvest,
    )
    return ValidatorResponse(valid=valid, invalid=invalid)


def _filter_classify(
    inputs: list,
    q_periods: list,
    k_periods: list,
) -> tuple[list, list[FilterInvalidTransaction]]:
    """Split into valid inputs and invalid (date, amount, message only)."""
    seen: set[tuple[str, float]] = set()
    valid_inputs: list = []
    invalid: list[FilterInvalidTransaction] = []

    for t in inputs:
        key = (t.date.isoformat(), t.amount)
        if t.amount < 0:
            invalid.append(
                FilterInvalidTransaction(
                    date=t.date,
                    amount=t.amount,
                    ceiling=t.ceiling,
                    remanent=t.remanent,
                    message="Negative amounts are not allowed",
                )
            )
            continue
        if key in seen:
            invalid.append(
                FilterInvalidTransaction(
                    date=t.date,
                    amount=t.amount,
                    ceiling=t.ceiling,
                    remanent=t.remanent,
                    message="Duplicate transaction",
                )
            )
            continue
        seen.add(key)
        valid_inputs.append(t)

    return valid_inputs, invalid


@router.post("/transactions:filter", response_model=FilterResponse)
def filter_transactions(body: FilterRequest) -> FilterResponse:
    """Apply q, p, k periods; return valid (with inKPeriod), invalid (with message), savingsByDates."""
    valid_inputs, invalid = _filter_classify(
        list(body.transactions), body.q, body.k
    )
    raw = [
        (t.date, t.amount, t.ceiling or 0, t.remanent or 0)
        for t in valid_inputs
    ]
    raw = domain.apply_q_rules(raw, body.q)
    raw = domain.apply_p_rules(raw, body.p)
    k_sums = domain.aggregate_k_periods(raw, body.k)
    savings_by_dates = [
        KPeriodAmount(start=s, end=e, amount=a) for s, e, a in k_sums
    ]
    valid_txs = []
    for (date, amount, ceiling, remanent) in raw:
        in_k = any(
            _in_range(date, k.start, k.end) for k in body.k
        )
        valid_txs.append(
            FilterValidTransaction(
                date=date,
                amount=amount,
                ceiling=ceiling,
                remanent=remanent,
                inKPeriod=in_k,
            )
        )
    return FilterResponse(
        valid=valid_txs,
        invalid=invalid,
        savingsByDates=savings_by_dates,
    )
