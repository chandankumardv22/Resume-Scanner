# ==============================================================================
# Production Multi-Stage Full-Stack Dockerfile
# Builds React frontend and bundles it directly with FastAPI ASGI backend
# Deployable to: Google Cloud Run, AWS App Runner, Fly.io, Railway, Render, VPS
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Frontend Assets
# ------------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit

COPY frontend/ ./
ARG REACT_APP_API_URL=""
ENV REACT_APP_API_URL=${REACT_APP_API_URL} \
    CI=false \
    GENERATE_SOURCEMAP=false

RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Production Python Backend Runtime
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WORKERS=2 \
    TIMEOUT=120 \
    APP_HOME=/app \
    FRONTEND_BUILD_DIR=/app/frontend/build

WORKDIR ${APP_HOME}

# Install essential runtime and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create secure non-root application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

# Install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend application source
COPY backend/ ./backend/

# Copy compiled frontend assets from builder stage
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Pre-train and validate ML role model inside container environment
WORKDIR ${APP_HOME}/backend
RUN python train_role_model.py

# Ensure uploads and persistent data directories exist with proper permissions
RUN mkdir -p uploads data && \
    chown -R appuser:appgroup ${APP_HOME}

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1

# Production startup using Gunicorn with Uvicorn ASGI workers
CMD ["sh", "-c", "exec gunicorn -w ${WORKERS:-2} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} --timeout ${TIMEOUT:-120} --access-logfile - --error-logfile - main:app"]

