# Test type: Integration
# Validation: All API endpoints—request/response shape, PDF example values, validation and error cases.
# Command: uv run pytest test/test_api.py -v

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "/blackrock/challenge/v1"

# PDF example data
EXPENSES = [
    {"timestamp": "2023-10-12 20:15:00", "amount": 250},
    {"timestamp": "2023-02-28 15:49:00", "amount": 375},
    {"timestamp": "2023-07-01 21:59:00", "amount": 620},
    {"timestamp": "2023-12-17 08:09:00", "amount": 480},
]
Q_PERIODS = [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:00"}]
P_PERIODS = [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:00"}]
K_PERIODS = [
    {"start": "2023-03-01 00:00:00", "end": "2023-11-30 23:59:00"},
    {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00"},
]


# --- /transactions:parse ---


def test_parse():
    r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 4
    assert sum(t["remanent"] for t in data) == 175
    assert sum(t["amount"] for t in data) == 250 + 375 + 620 + 480


def test_parse_response_shape():
    """Each transaction has date, amount, ceiling, remanent in YYYY-MM-DD HH:mm:ss format."""
    r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    assert r.status_code == 200
    data = r.json()
    for t in data:
        assert "date" in t and "amount" in t and "ceiling" in t and "remanent" in t
        assert t["ceiling"] == (t["amount"] + t["remanent"])
        assert t["ceiling"] >= t["amount"] and t["remanent"] >= 0
    assert data[0]["date"] == "2023-10-12 20:15:00"
    assert data[0]["amount"] == 250 and data[0]["ceiling"] == 300 and data[0]["remanent"] == 50


def test_parse_accepts_bare_array():
    """Parse accepts a bare array of expenses (wrapped as expenses by schema)."""
    r = client.post(f"{BASE}/transactions:parse", json=EXPENSES)
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_parse_accepts_date_alias():
    """Parse accepts 'date' as alias for 'timestamp' in expenses."""
    expenses_date = [{"date": "2023-01-15 12:00:00", "amount": 199}]
    r = client.post(f"{BASE}/transactions:parse", json={"expenses": expenses_date})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["amount"] == 199 and data[0]["ceiling"] == 200 and data[0]["remanent"] == 1


def test_parse_empty_expenses():
    r = client.post(f"{BASE}/transactions:parse", json={"expenses": []})
    assert r.status_code == 200
    assert r.json() == []


def test_parse_invalid_payload_returns_422():
    r = client.post(f"{BASE}/transactions:parse", json={"expenses": "not-a-list"})
    assert r.status_code == 422
    r2 = client.post(f"{BASE}/transactions:parse", json={})
    assert r2.status_code == 422


# --- /transactions:validator ---


def test_validator():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    r = client.post(
        f"{BASE}/transactions:validator",
        json={"wage": 50_000, "transactions": transactions},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["valid"]) == 4
    assert len(data["invalid"]) == 0


def test_validator_response_shape():
    r = client.post(
        f"{BASE}/transactions:validator",
        json={"wage": 1000, "transactions": []},
    )
    assert r.status_code == 200
    data = r.json()
    assert "valid" in data and "invalid" in data
    assert isinstance(data["valid"], list) and isinstance(data["invalid"], list)
    assert data["valid"] == [] and data["invalid"] == []


def test_validator_rejects_duplicates():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    dup = transactions + [transactions[0]]
    r = client.post(
        f"{BASE}/transactions:validator",
        json={"wage": 50_000, "transactions": dup},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["valid"]) == 4
    assert len(data["invalid"]) == 1
    assert "message" in data["invalid"][0]
    assert "duplicate" in data["invalid"][0]["message"].lower()


def test_validator_max_invest():
    """Transactions with remanent > maxInvest go to invalid."""
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    r = client.post(
        f"{BASE}/transactions:validator",
        json={"wage": 50_000, "transactions": transactions, "maxInvest": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["invalid"]) >= 1
    assert any("exceeds maximum" in inv["message"] for inv in data["invalid"])


def test_validator_invalid_payload_returns_422():
    r = client.post(f"{BASE}/transactions:validator", json={"wage": 1000})
    assert r.status_code == 422


# --- /transactions:filter ---


def test_filter():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    r = client.post(
        f"{BASE}/transactions:filter",
        json={
            "q": Q_PERIODS,
            "p": P_PERIODS,
            "k": K_PERIODS,
            "transactions": transactions,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["savingsByDates"]) == 2
    assert data["savingsByDates"][0]["amount"] == 75
    assert data["savingsByDates"][1]["amount"] == 145


def test_filter_response_shape():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    r = client.post(
        f"{BASE}/transactions:filter",
        json={"q": [], "p": [], "k": K_PERIODS, "transactions": transactions},
    )
    assert r.status_code == 200
    data = r.json()
    assert "valid" in data and "invalid" in data and "savingsByDates" in data
    for t in data["valid"]:
        assert "date" in t and "amount" in t and "ceiling" in t and "remanent" in t and "inKPeriod" in t
    for item in data["savingsByDates"]:
        assert "start" in item and "end" in item and "amount" in item


def test_filter_empty_periods():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    r = client.post(
        f"{BASE}/transactions:filter",
        json={"q": [], "p": [], "k": [], "transactions": transactions},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["savingsByDates"] == []


def test_filter_duplicate_transactions_invalid():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    dup = transactions + [transactions[0]]
    r = client.post(
        f"{BASE}/transactions:filter",
        json={"q": [], "p": [], "k": K_PERIODS, "transactions": dup},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["invalid"]) >= 1
    assert any("Duplicate" in inv["message"] for inv in data["invalid"])


# --- /returns:nps ---


def test_profits_nps():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    r = client.post(
        f"{BASE}/returns:nps",
        json={
            "age": 29,
            "wage": 50_000,
            "inflation": 0.055,
            "q": Q_PERIODS,
            "p": P_PERIODS,
            "k": K_PERIODS,
            "transactions": transactions,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["savingsByDates"]) == 2
    assert data["savingsByDates"][1]["amount"] == 145
    assert abs(data["savingsByDates"][1]["profits"] - 86.88) < 2
    assert data["savingsByDates"][1]["taxBenefit"] == 0


def test_profits_nps_response_shape():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    r = client.post(
        f"{BASE}/returns:nps",
        json={
            "age": 29,
            "wage": 50_000,
            "inflation": 5.5,
            "q": Q_PERIODS,
            "p": P_PERIODS,
            "k": K_PERIODS,
            "transactions": transactions,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "transactionsTotalAmount" in data and "transactionsTotalCeiling" in data and "savingsByDates" in data
    for item in data["savingsByDates"]:
        assert "start" in item and "end" in item and "amount" in item and "profits" in item and "taxBenefit" in item


# --- /returns:index ---


def test_profits_index():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    r = client.post(
        f"{BASE}/returns:index",
        json={
            "age": 29,
            "wage": 50_000,
            "inflation": 0.055,
            "q": Q_PERIODS,
            "p": P_PERIODS,
            "k": K_PERIODS,
            "transactions": transactions,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["savingsByDates"]) == 2
    assert data["savingsByDates"][1]["amount"] == 145
    assert "profits" in data["savingsByDates"][1]
    # profits = inflation-adjusted gain (real value - principal), same semantics as NPS profits
    assert abs(data["savingsByDates"][1]["profits"] - (1829.5 - 145)) < 30


def test_profits_index_response_shape():
    parse_r = client.post(f"{BASE}/transactions:parse", json={"expenses": EXPENSES})
    transactions = parse_r.json()
    r = client.post(
        f"{BASE}/returns:index",
        json={
            "age": 60,
            "wage": 50_000,
            "inflation": 5.5,
            "q": [],
            "p": [],
            "k": K_PERIODS,
            "transactions": transactions,
        },
    )
    assert r.status_code == 200
    data = r.json()
    for item in data["savingsByDates"]:
        assert "profits" in item
        assert isinstance(item["profits"], (int, float))


def test_profits_invalid_payload_returns_422():
    r = client.post(
        f"{BASE}/returns:nps",
        json={"age": 29, "wage": 50_000},
    )
    assert r.status_code == 422


# --- /performance ---


def test_performance():
    r = client.get(f"{BASE}/performance")
    assert r.status_code == 200
    data = r.json()
    assert "time" in data
    assert "memory" in data and "MB" in data["memory"]
    assert "threads" in data and isinstance(data["threads"], int)


def test_performance_method_not_allowed():
    """Performance is GET only; POST should fail."""
    r = client.post(f"{BASE}/performance", json={})
    assert r.status_code == 405


# --- /health ---


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# --- Wrong method / path ---


def test_parse_get_not_allowed():
    r = client.get(f"{BASE}/transactions:parse")
    assert r.status_code == 405


def test_validator_get_not_allowed():
    r = client.get(f"{BASE}/transactions:validator")
    assert r.status_code == 405


def test_filter_get_not_allowed():
    r = client.get(f"{BASE}/transactions:filter")
    assert r.status_code == 405


def test_profits_nps_get_not_allowed():
    r = client.get(f"{BASE}/returns:nps")
    assert r.status_code == 405


def test_profits_index_get_not_allowed():
    r = client.get(f"{BASE}/returns:index")
    assert r.status_code == 405


def test_nonexistent_path_returns_404():
    r = client.get(f"{BASE}/nonexistent")
    assert r.status_code == 404
