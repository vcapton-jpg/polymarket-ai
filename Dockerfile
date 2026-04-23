# ── Build stage ────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.11-bookworm AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project --no-editable --locked

# ── Runtime stage ─────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY prompts ./prompts
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN python -m compileall -q .
RUN useradd -ms /bin/bash appuser && chown -R appuser:appuser .
USER appuser

EXPOSE 8000/tcp

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
