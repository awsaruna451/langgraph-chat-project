# ============================================
# Build stage - install deps into a venv
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ============================================
# Runtime stage
# ============================================
FROM python:3.11-slim

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser

WORKDIR /app

# Bring in the pre-built virtual environment
COPY --from=builder /opt/venv /opt/venv

# App source only (see .dockerignore for exclusions: .env, notebooks, __pycache__, etc.)
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser application ./application
COPY --chown=appuser:appuser schema ./schema
COPY --chown=appuser:appuser service ./service

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=10s \
    --retries=3 \
    CMD python -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000/health', timeout=3); exit(0 if r.status == 200 else 1)" || exit 1

# --loop asyncio avoids uvloop (a compiled/Cython extension pulled in by
# uvicorn[standard]) which has been unreliable on emulated/virtualized ARM
# environments (e.g. Apple Silicon under Docker Desktop). Safe everywhere else too.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--loop", "asyncio"]
