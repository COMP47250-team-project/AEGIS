FROM python:3.12-slim

# Copy uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Build deps: gcc for asyncpg C extension; curl for health-check in compose
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps before copying source so this layer is cached.
# UV_SYSTEM_PYTHON=1 installs into the system Python (not a project .venv),
# so docker-compose volume mounts don't shadow installed packages.
ENV UV_SYSTEM_PYTHON=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Source is mounted at run time in development (see docker-compose volumes).
# Copying here ensures the image is self-contained for CI / production builds.
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
