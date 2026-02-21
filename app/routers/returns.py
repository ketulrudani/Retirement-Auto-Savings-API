"""Returns endpoints: NPS and Index."""

from fastapi import APIRouter

from app import domain
from app.returns import compute_return, years_to_retirement
from app.schemas import (
    ReturnsRequest,
    ReturnsResponse,
    SavingsByDatesItem,
)

router = APIRouter()


def _run_returns_pipeline(req: ReturnsRequest) -> tuple[list, list]:
    """Run parse -> q -> p -> k; return (transactions as tuples, k_sums)."""
    expenses = [(t.date, t.amount) for t in req.transactions if t.amount > 0]
    raw = domain.parse_expenses(expenses)
    raw = domain.apply_q_rules(raw, req.q)
    raw = domain.apply_p_rules(raw, req.p)
    k_sums = domain.aggregate_k_periods(raw, req.k)
    return raw, k_sums


@router.post("/returns:nps", response_model=ReturnsResponse)
def returns_nps(body: ReturnsRequest) -> ReturnsResponse:
    """Compute NPS returns per k period: amount, profits (inflation-adjusted), taxBenefit."""
    raw, k_sums = _run_returns_pipeline(body)
    annual_income = body.wage * 12

    total_amount = sum(t[1] for t in raw)
    total_ceiling = sum(t[2] for t in raw)

    savings_by_dates = []
    for (start, end, amount) in k_sums:
        profit, tax_ben, _ = compute_return(
            amount, body.age, body.inflation, "nps", annual_income
        )
        savings_by_dates.append(
            SavingsByDatesItem(
                start=start,
                end=end,
                amount=amount,
                profits=round(profit, 2),
                taxBenefit=round(tax_ben, 2) if tax_ben is not None else 0.0,
            )
        )

    return ReturnsResponse(
        transactionsTotalAmount=total_amount,
        transactionsTotalCeiling=total_ceiling,
        savingsByDates=savings_by_dates,
    )


@router.post("/returns:index", response_model=ReturnsResponse)
def returns_index(body: ReturnsRequest) -> ReturnsResponse:
    """Compute Index fund returns per k period: amount, return (inflation-adjusted)."""
    raw, k_sums = _run_returns_pipeline(body)
    total_amount = sum(t[1] for t in raw)
    total_ceiling = sum(t[2] for t in raw)

    savings_by_dates = []
    for (start, end, amount) in k_sums:
        profit, _, _ = compute_return(
            amount, body.age, body.inflation, "index", 0.0
        )
        rounded = round(profit, 2)
        savings_by_dates.append(
            SavingsByDatesItem(
                start=start,
                end=end,
                amount=amount,
                profits=rounded,
            )
        )

    return ReturnsResponse(
        transactionsTotalAmount=total_amount,
        transactionsTotalCeiling=total_ceiling,
        savingsByDates=savings_by_dates,
    )
