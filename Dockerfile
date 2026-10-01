# syntax=docker/dockerfile:1

# ---- build stage: install deps into a venv ---------------------------------
FROM python:3.11-slim AS builder
WORKDIR /app

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Copy only what's needed to resolve + install, for layer caching.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data

RUN uv sync --frozen --no-dev --extra web --extra azure

# ---- runtime stage: slim, non-root -----------------------------------------
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd -r app && useradd -r -g app app

COPY --from=builder /app /app
# Writable dir for the local (non-Cosmos) persistence fallback.
RUN chown -R app:app /app/data

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=3)"]

CMD ["uvicorn", "gravity_trade.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
