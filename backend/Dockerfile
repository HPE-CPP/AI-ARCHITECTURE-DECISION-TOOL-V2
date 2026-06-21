# ────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — installs all Python deps into a venv
# We use a separate stage so build tools (gcc, etc.) don't end up in the
# final runtime image, keeping it lean and secure.
# ────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies required by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install into an isolated venv so we can copy it cleanly to the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime — final production image
# ────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Production Python settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install only the runtime system libraries (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Create a non-root user and group for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

# Copy only the application source — .dockerignore excludes secrets and junk
COPY --chown=appuser:appgroup . .

# Pre-create runtime directories that the app writes to at startup
RUN mkdir -p faiss_index logs && chown appuser:appgroup faiss_index logs

# Switch to non-root user
USER appuser

EXPOSE 8000

# Docker-level health check — used by orchestrators (Railway, ECS, k8s, etc.)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/api/v1/ping')" || exit 1

# Production entrypoint:
# - gunicorn manages multiple worker processes
# - UvicornWorker gives us async ASGI support inside gunicorn
# - Workers = 2*(CPU cores)+1 is a common production formula; we default to 2
#   but allow override via GUNICORN_WORKERS env var
CMD gunicorn main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers ${GUNICORN_WORKERS:-2} \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --log-level info \
    --access-logfile -
