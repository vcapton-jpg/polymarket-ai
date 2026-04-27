# ── Build stage ────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.11-bookworm AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project --no-editable --locked

# Pre-bake the spaCy model at image build time. Without this, every
# fresh worker container hits `Model en_core_web_lg not found, downloading...`
# on its first NER call and stalls for several minutes, blocking the
# pipeline (process_article → cluster → score → signal). The model is
# ~382 MiB and lives inside the venv, so it survives the multi-stage
# `COPY --from=builder /app/.venv /app/.venv` below. This makes
# `--force-recreate` safe: the new container has the model from the
# first second, no on-the-fly download.
RUN /app/.venv/bin/python -m spacy download en_core_web_lg

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
