import asyncio
import logging
import os
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


async def _check_db() -> str:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        logger.warning("Health check: DB unreachable: %s", exc)
        return "error"


async def _check_service_bus() -> str:
    """Actively verify Service Bus connectivity by peeking the events queue."""
    conn = settings.azure_service_bus_connection_string
    if not conn:
        return "disabled"
    try:
        from azure.servicebus.aio import ServiceBusClient

        async def _peek() -> None:
            async with ServiceBusClient.from_connection_string(conn) as client:
                async with client.get_queue_receiver(
                    settings.aegis_events_queue_name
                ) as receiver:
                    await receiver.peek_messages(max_message_count=1)

        await asyncio.wait_for(_peek(), timeout=6)
        return "ok"
    except Exception as exc:
        logger.warning("Health check: Service Bus unreachable: %s", exc)
        return "error"


async def _check_blob() -> str:
    """Actively verify Blob Storage by reading the session-tapes container."""
    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        return "disabled"
    try:
        from azure.storage.blob.aio import BlobServiceClient

        async def _probe() -> None:
            async with BlobServiceClient.from_connection_string(conn) as client:
                container = client.get_container_client("session-tapes")
                await container.get_container_properties()

        await asyncio.wait_for(_probe(), timeout=6)
        return "ok"
    except Exception as exc:
        logger.warning("Health check: Blob Storage unreachable: %s", exc)
        return "error"


@app.get("/healthz", tags=["health"])
@app.get("/api/health", tags=["health"])
async def health() -> dict:
    """Deep health check — actively verifies DB, Service Bus, and Blob Storage.

    Returns 200 always (so the platform probe doesn't kill the app for a
    degraded dependency); inspect the body for per-dependency status. A value
    of "disabled" means the connection string isn't set (expected in local dev).
    """
    db, service_bus, blob = await asyncio.gather(
        _check_db(), _check_service_bus(), _check_blob()
    )
    healthy = (
        db == "ok"
        and service_bus in ("ok", "disabled")
        and blob in ("ok", "disabled")
    )
    return {
        "status": "ok" if healthy else "degraded",
        "db": db,
        "service_bus": service_bus,
        "blob": blob,
    }

