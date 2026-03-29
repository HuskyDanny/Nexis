# ── Builder stage ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:0.5.10 /uv /usr/local/bin/uv

# Copy dependency spec and source (hatchling needs packages=["src"])
COPY pyproject.toml ./
COPY src/ ./src/

# Install production deps only — no editable install in builder
RUN uv venv /opt/venv \
    && uv pip install --python /opt/venv/bin/python --no-cache .

# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim

# Security: non-root user with writable home (CrewAI needs it for storage paths)
RUN groupadd -g 1001 app && useradd -u 1001 -g app -m -s /bin/false app

WORKDIR /app

# Copy venv from builder (outside /app to avoid volume mount hiding it)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY src/ ./src/

# Own files as app user
RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/live')" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
