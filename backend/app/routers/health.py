"""Health endpoint with subsystem status checks (AEGIS-89).

`GET /api/health` (and the legacy `/healthz`) report the status of the database,
Azure Service Bus, and Blob Storage, plus the app version. Not behind JWT auth.
Each subsystem check is time-bounded and the checks run concurrently, so the
whole call completes in well under 3 seconds. Returns HTTP 503 when the DB is
down (so load balancers / smoke tests can treat it as unhealthy).
"""

import asyncio
import logging
import os
import tomllib
from pathlib import Path

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Per-check timeouts. The DB check is local and fast (1s). Service Bus and Blob
# reach out to Azure and, on a cold start, the first call must open a fresh TLS
# connection + authenticate, which exceeds 1s and caused spurious "degraded"
# readings right after a deploy (AEGIS-74 follow-up). Checks run in parallel, so
# the endpoint's worst case is ~4s, not the sum.
_DB_TIMEOUT_S = 1.0
_SB_TIMEOUT_S = 4.0
_BLOB_TIMEOUT_S = 4.0
_STORAGE_CONTAINER = "session-tapes"


async def _check_db(session: AsyncSession) -> str:
    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=_DB_TIMEOUT_S)
        return "ok"
    except Exception as exc:
        logger.warning("Health: DB check failed: %s", exc)
        return "error"


async def _check_service_bus() -> str:
    conn = settings.azure_service_bus_connection_string
    if not conn:
        return "disabled"

    def _get_props() -> None:
        from azure.servicebus.management import ServiceBusAdministrationClient

        with ServiceBusAdministrationClient.from_connection_string(conn) as client:
            client.get_namespace_properties()

    try:
        await asyncio.wait_for(asyncio.to_thread(_get_props), timeout=_SB_TIMEOUT_S)
        return "ok"
    except Exception as exc:
        logger.warning("Health: Service Bus check failed: %s", exc)
        return "error"


async def _check_blob() -> str:
    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        return "disabled"

    async def _get_props() -> None:
        from azure.storage.blob.aio import BlobServiceClient

        async with BlobServiceClient.from_connection_string(conn) as client:
            container = client.get_container_client(_STORAGE_CONTAINER)
            await container.get_container_properties()

    try:
        await asyncio.wait_for(_get_props(), timeout=_BLOB_TIMEOUT_S)
        return "ok"
    except Exception as exc:
        logger.warning("Health: Blob check failed: %s", exc)
        return "error"


def _version() -> str:
    env = os.environ.get("APP_VERSION")
    if env:
        return env
    try:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with pyproject.open("rb") as f:
            return str(tomllib.load(f)["project"]["version"])
    except Exception:
        return "unknown"


@router.get("/api/health")
@router.get("/healthz")
async def health(
    response: Response,
    db_session: AsyncSession = Depends(get_db),
) -> dict:
    """Report DB / Service Bus / Blob status + app version.

    Overall status: ``ok`` if all non-disabled subsystems are ok; ``degraded`` if
    a non-DB subsystem errors but the DB is ok; ``error`` (HTTP 503) if the DB is
    down.
    """
    db, service_bus, blob = await asyncio.gather(
        _check_db(db_session), _check_service_bus(), _check_blob()
    )

    if db == "error":
        overall = "error"
    elif "error" in (service_bus, blob):
        overall = "degraded"
    else:
        overall = "ok"

    if overall == "error":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall,
        "db": db,
        "service_bus": service_bus,
        "blob": blob,
        "version": _version(),
    }
