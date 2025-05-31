# -------------------------------------------------
# Stage 0  (builder) – install Python deps
# -------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

# -------------------------------------------------
# Stage 1  (runtime image)
# -------------------------------------------------
FROM python:3.11-slim

# system packages for fastapi + zip handling
RUN apt-get update && apt-get install -y --no-install-recommends \
      libmagic1 unzip curl && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH"

# Copy site-packages from builder stage
COPY --from=builder /install /usr/local

# Copy project files
WORKDIR /app
COPY . .

# Expose FastAPI’s port
EXPOSE 8000

# Healthcheck: hit the /health endpoint
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

ENTRYPOINT ["bash", "start.sh"]
