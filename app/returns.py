"""Returns calculation: compound interest, inflation adjustment, NPS tax benefit."""

from typing import Literal

# Rates from problem
NPS_RATE = 0.0711
INDEX_RATE = 0.1449
NPS_MAX_DEDUCTION = 200_000  # ₹2,00,000

# Tax slabs (simplified): (upper_bound, rate on amount above previous slab)
TAX_SLABS = [
    (0, 0.0),
    (700_000, 0.0),
    (1_000_000, 0.10),
    (1_200_000, 0.15),
    (1_500_000, 0.20),
    (float("inf"), 0.30),
]


def years_to_retirement(age: int) -> int:
    """Years until 60; if age >= 60, use 5 (per problem)."""
    if age >= 60:
        return 5
    return 60 - age


def compound_amount(principal: float, rate: float, years: int) -> float:
    """A = P * (1 + r)^t (annual compounding)."""
    if years <= 0:
        return principal
    return principal * ((1 + rate) ** years)


def inflation_adjust(amount: float, inflation: float, years: int) -> float:
    """A_real = A / (1 + inflation)^t."""
    if years <= 0:
        return amount
    return amount / ((1 + inflation) ** years)


def tax_on_income(income: float) -> float:
    """Tax using simplified slabs."""
    if income <= 0:
        return 0.0
    tax = 0.0
    prev_bound = 0
    for bound, rate in TAX_SLABS:
        if income <= prev_bound:
            break
        slice_ = min(income, bound) - prev_bound
        tax += slice_ * rate
        prev_bound = bound
    return tax


def nps_deduction(invested: float, annual_income: float) -> float:
    """min(invested, 10% of annual_income, 200_000)."""
    cap_10pct = 0.1 * annual_income
    return min(invested, cap_10pct, NPS_MAX_DEDUCTION)


def tax_benefit(annual_income: float, nps_deduction_amount: float) -> float:
    """Tax(income) - Tax(income - NPS_Deduction)."""
    return tax_on_income(annual_income) - tax_on_income(annual_income - nps_deduction_amount)


def compute_return(
    amount: float,
    age: int,
    inflation: float,
    kind: Literal["nps", "index"],
    annual_income: float,
) -> tuple[float, float | None, float | None]:
    """
    Compute inflation-adjusted return. For NPS also return tax benefit.
    Returns (inflation_adjusted_profit_or_return, tax_benefit or None, raw_future_value or None).
    """
    t = years_to_retirement(age)
    rate = NPS_RATE if kind == "nps" else INDEX_RATE
    future = compound_amount(amount, rate, t)
    real = inflation_adjust(future, inflation, t)
    profit = real - amount  # inflation-adjusted gain (same meaning for nps and index)

    tax_ben = None
    if kind == "nps":
        ded = nps_deduction(amount, annual_income)
        tax_ben = tax_benefit(annual_income, ded)

    return (profit, tax_ben, future)
