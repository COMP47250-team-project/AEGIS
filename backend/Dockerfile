FROM python:3.12-slim

WORKDIR /app

# Build deps: gcc for asyncpg C extension; curl for health-check in compose
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps before copying source so this layer is cached
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Source is mounted at run time in development (see docker-compose volumes).
# Copying here ensures the image is self-contained for CI / production builds.
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
