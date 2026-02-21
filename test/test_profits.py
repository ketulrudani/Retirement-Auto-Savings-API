# Test type: Unit
# Validation: Tax slabs, NPS deduction, tax benefit, compound interest, inflation adjustment, years to retirement, profits.
# Command: uv run pytest test/test_profits.py -v

import pytest

from app.returns import (
    compound_amount,
    inflation_adjust,
    nps_deduction,
    tax_benefit,
    tax_on_income,
    years_to_retirement,
    compute_return,
)


def test_years_to_retirement():
    assert years_to_retirement(29) == 31
    assert years_to_retirement(60) == 5
    assert years_to_retirement(59) == 1


def test_compound_amount():
    # A = 145 * (1.0711)^31 ≈ 1219.45
    a = compound_amount(145, 0.0711, 31)
    assert abs(a - 1219.45) < 1
    # A = 145 * (1.1449)^31 ≈ 9619.7
    a2 = compound_amount(145, 0.1449, 31)
    assert abs(a2 - 9619.7) < 10


def test_inflation_adjust():
    # 1219.45 / (1.055)^31 ≈ 231.9
    real = inflation_adjust(1219.45, 0.055, 31)
    assert abs(real - 231.9) < 1


def test_tax_on_income():
    assert tax_on_income(0) == 0
    assert tax_on_income(600_000) == 0
    assert tax_on_income(700_000) == 0
    assert tax_on_income(800_000) == (800_000 - 700_000) * 0.10
    assert tax_on_income(1_100_000) == 30_000 + (1_100_000 - 1_000_000) * 0.15


def test_nps_deduction():
    assert nps_deduction(145, 600_000) == 145
    assert nps_deduction(200_000, 600_000) == 60_000
    assert nps_deduction(300_000, 3_000_000) == 200_000


def test_tax_benefit():
    # Income 6L is in 0% slab
    assert tax_benefit(600_000, 145) == 0


def test_compute_profits_nps():
    profit, tax_ben, future = compute_return(145, 29, 0.055, "nps", 600_000)
    assert abs(profit - 86.88) < 2
    assert tax_ben == 0


def test_compute_profits_index():
    # profit = inflation-adjusted gain (real terminal value - principal), same as NPS
    profit, _, _ = compute_return(145, 29, 0.055, "index", 0)
    # real terminal value ~1829.5, so profit ~1829.5 - 145
    assert abs(profit - (1829.5 - 145)) < 20
