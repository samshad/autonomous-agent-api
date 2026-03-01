# ==========================================
# Stage 1: Builder
# ==========================================
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock* ./

RUN uv sync --frozen --no-dev --no-install-project

# ==========================================
# Stage 2: Production Runtime
# ==========================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -M appuser

COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

COPY --chown=appuser:appgroup src/ ./src/

USER appuser

EXPOSE 8000

CMD ["uvicorn", "agent_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]
