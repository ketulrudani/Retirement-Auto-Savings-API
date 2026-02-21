# Build: docker build -t blk-hacking-ind-ketul-patel .
# Base: python:3.12-slim (Debian-based; slim for smaller image size and security)
FROM python:3.12-slim

LABEL description="Expense-rounding micro-savings, NPS/Index returns, tax and inflation. Runs on port 5477."

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY app ./app

RUN uv sync --frozen --no-dev

EXPOSE 5477

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5477"]
