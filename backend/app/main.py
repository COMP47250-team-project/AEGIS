import logging
from sqlalchemy import text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import (
    auth,
    courses,
    exams,
    quizzes,
    sessions,
    student,
    telemetry,
    users,
)
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AEGIS",
    description="Adaptive Exam Guardian and Integrity System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_origin_regex=r"https://.*\.azurecontainerapps\.io",  # allow all ACA subdomains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(quizzes.router)
app.include_router(exams.router)
app.include_router(courses.router)
app.include_router(student.router)
app.include_router(users.router)
app.include_router(telemetry.router)
app.include_router(sessions.router)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict:
    """Deep health check — verifies DB connectivity and reports service bus status."""
    result: dict = {"status": "ok"}

    # Check database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        result["db"] = "ok"
    except Exception as exc:
        logger.warning("Health check: DB unreachable: %s", exc)
        result["db"] = "error"
        result["status"] = "degraded"

    # Check service bus (non-fatal if absent — optional in dev)
    if settings.azure_service_bus_connection_string:
        result["service_bus"] = "configured"
    else:
        result["service_bus"] = "disabled"

    return result

