# ============================================
# Build stage
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./
COPY app ./app

# Create virtual environment and install application
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python .


# ============================================
# Runtime stage
# ============================================
FROM python:3.11-slim

# Create non-root user
RUN useradd \
    --create-home \
    --uid 1000 \
    --shell /usr/sbin/nologin \
    appuser

WORKDIR /app

# Copy virtual environment
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY --chown=appuser:appuser app ./app

# Environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=10s \
    --retries=3 \
    CMD python -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000/health', timeout=3); exit(0 if r.status == 200 else 1)" || exit 1

CMD ["python", "-m", "app.main"]