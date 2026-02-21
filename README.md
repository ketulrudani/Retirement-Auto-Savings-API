# Retirement Auto-Savings API

Production-grade API for automated retirement savings via expense rounding. It parses expenses into transactions (ceiling/remanent), validates them, applies temporal rules (q/p/k periods), and computes NPS and Index fund returns with tax benefit and inflation adjustment.

## Requirements

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** (package manager)

## Setup

```bash
# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# With dev dependencies (for tests)
uv sync --all-groups
```

## Run locally

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 5477
```

- **Base URL:** `http://localhost:5477`
- **OpenAPI docs:** `http://localhost:5477/docs`
- **Health:** `http://localhost:5477/health`

## Docker

```bash
docker build -t blk-hacking-ind-ketul-patel .

# Run
docker run -d -p 5477:5477 blk-hacking-ind-ketul-patel
```

Or with Docker Compose:

```bash
docker compose up --build -d
```

The app listens on **port 5477** (host and container).

## API summary

All endpoints are under **`/blackrock/challenge/v1`**.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/transactions:parse` | POST | Parse expenses (date + amount) → list of transactions with ceiling and remanent. Request: `{"expenses": [...]}` or a bare array. Response: array of `{date, amount, ceiling, remanent}`. |
| `/transactions:validator` | POST | Validate transactions (wage, optional maxInvest). Returns `valid` and `invalid` (duplicates and rule violations in `invalid` with `message`). |
| `/transactions:filter` | POST | Apply q (fixed override), p (extra amount), k (evaluation ranges). Accepts expenses (date + amount); ceiling/remanent computed when missing. Accepts `q` or `a` for fixed periods. Returns `valid` (with `inKPeriod`), `invalid` (date, amount, message only), `savingsByDates`. |
| `/returns:nps` | POST | NPS returns per k period: amount, profits (inflation-adjusted gain), taxBenefit. Uses 7.11% rate, min(invested, 10% annual income, ₹2L) for tax deduction. |
| `/returns:index` | POST | Index fund returns per k period: amount, return (inflation-adjusted final value). Uses 14.49% rate, no tax. |
| `/performance` | GET | Response time (HH:mm:ss.SSS), process memory (MB), thread count. |

### Returns request body

- **age:** integer (years to retirement = 60 − age, or 5 if age ≥ 60).
- **wage:** monthly salary in INR; annual income = wage × 12 for tax/NPS limits.
- **inflation:** annual rate; send as percentage (e.g. `5.5`) or fraction (e.g. `0.055`).
- **q, p, k:** period lists (same as filter).
- **transactions:** list of transactions; `date` + `amount` are enough (ceiling/remanent optional, computed if missing).

### Processing order

1. Ceiling and remanent (round up to next multiple of 100).
2. q periods: replace remanent with fixed amount (latest-start wins if multiple match).
3. p periods: add extra to remanent (sum all matching).
4. k periods: sum remanents per range.
5. Returns: compound interest → inflation adjustment; NPS also computes tax benefit separately.

## Tests

```bash
uv run pytest test/ -v
```

- **Unit:** `test/test_domain.py` (parse, q/p/k), `test/test_profits.py` (tax, compound, inflation, profits).
- **Integration:** `test/test_api.py` (all endpoints with example data).

Test files include a header comment with test type, validation goal, and run command.

## Project layout

```
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── compose.yaml
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── domain.py      # parse, q/p/k, k sums
│   ├── returns.py     # compound, inflation, NPS tax
│   ├── schemas.py     # Pydantic models
│   └── routers/
│       ├── transactions.py
│       ├── returns.py
│       └── performance.py
└── test/
    ├── test_domain.py
    ├── test_profits.py
    └── test_api.py
```

No database or external services are required; the API runs standalone.
