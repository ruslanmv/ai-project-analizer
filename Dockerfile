# ═══════════════════════════════════════════════════════════════════════════
# Stage 1: Builder - Install dependencies and build the application
# ═══════════════════════════════════════════════════════════════════════════
FROM python:3.12-slim as builder

# Install system dependencies required for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install UV for lightning-fast dependency resolution
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Set working directory
WORKDIR /build

# Copy dependency files first (for layer caching)
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN uv pip install --no-cache -e .

# ═══════════════════════════════════════════════════════════════════════════
# Stage 2: Runtime - Minimal production image
# ═══════════════════════════════════════════════════════════════════════════
FROM python:3.12-slim

# Metadata
LABEL maintainer="Ruslan Magana <contact@ruslanmv.com>"
LABEL description="AI Project Analyzer - Enterprise-grade codebase analysis with AI"
LABEL version="2.0.0"

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser static/ ./static/
COPY --chown=appuser:appuser templates/ ./templates/
COPY --chown=appuser:appuser beeai.yaml ./
COPY --chown=appuser:appuser pyproject.toml README.md ./

# Create necessary directories
RUN mkdir -p /app/temp /app/logs && chown -R appuser:appuser /app

# Set environment variables
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH="/app/src:${PYTHONPATH}" \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    LOG_LEVEL=INFO

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "ai_project_analyzer.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
