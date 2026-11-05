# ==============================================================================
# Production Dockerfile for Resume Analyzer Backend
# Base: Python 3.11-slim with multi-worker Gunicorn/Uvicorn ASGI runtime
# ==============================================================================

FROM python:3.11-slim AS runtime

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WORKERS=2 \
    TIMEOUT=120 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install essential runtime and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root application user and group for security compliance
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application source code
COPY . .

# Pre-train and validate ML role model artifacts inside the container
RUN python train_role_model.py

# Ensure upload and working data directories exist with proper non-root permissions
RUN mkdir -p uploads data && \
    chown -R appuser:appgroup ${APP_HOME}

# Switch to non-root execution
USER appuser

# Expose the default application port
EXPOSE 8000

# Container Healthcheck targeting FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1

# Production startup using Gunicorn with Uvicorn worker class (default 2 workers to fit cloud memory limits)
CMD ["sh", "-c", "exec gunicorn -w ${WORKERS:-2} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} --timeout ${TIMEOUT:-120} --access-logfile - --error-logfile - main:app"]
