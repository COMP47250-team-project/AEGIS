FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Build deps: gcc for asyncpg C extension; curl for health-check in compose
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Place the venv outside /app so docker-compose volume mounts don't shadow it.
# UV_SYSTEM_PYTHON=1 only applies to `uv pip` — `uv sync` always uses a venv.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH=/opt/venv/bin:$PATH

# Install dependencies before copying source (layer caching).
# --no-install-project: the source isn't here yet, so skip installing the local
# aegis-backend package. All runtime deps (alembic, uvicorn, …) are installed.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Source is mounted at run time in development (see docker-compose volumes).
# Copying here ensures the image is self-contained for CI / production builds.
COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
