# ── Builder stage ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency spec first (layer caching)
COPY pyproject.toml ./

# Install production deps only — no editable install in builder
RUN uv venv /app/.venv \
    && uv pip install --python /app/.venv/bin/python --no-cache .

# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim

# Security: non-root user
RUN groupadd -g 1001 app && useradd -u 1001 -g app -s /bin/false app

WORKDIR /app

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source
COPY src/ ./src/

# Own files as app user
RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/live')" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
