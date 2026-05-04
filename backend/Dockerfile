# ═══════════════════════════════════════════════════════════
# SARTORIAL AGENTIC — Backend Dockerfile
# Python 3.12 · FastAPI · Uvicorn
# ═══════════════════════════════════════════════════════════

FROM python:3.12-slim AS base

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p /app/logs && chown -R appuser:appuser /app
USER appuser

# Expose
EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
