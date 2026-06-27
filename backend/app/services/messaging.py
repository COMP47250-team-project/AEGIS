"""Helpers for publishing telemetry to Service Bus and appending session tapes.

This module performs best-effort, non-blocking publishing. Failures are
logged but do not raise to the caller.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


async def _publish_to_service_bus(message: dict[str, Any]) -> None:
    """Publish a single message to Azure Service Bus (best-effort).

    If the azure-servicebus package or connection string are missing, log
    and return. Any exception during publishing is caught and logged.
    """
    conn_str = settings.azure_service_bus_connection_string
    queue = settings.aegis_events_queue_name
    if not conn_str:
        logger.debug("No Service Bus connection string configured; skipping publish")
        return

    try:
        # Import lazily so tests and environments without the package don't fail
        from azure.servicebus.aio import ServiceBusClient
        from azure.servicebus import ServiceBusMessage

        async with ServiceBusClient.from_connection_string(conn_str) as client:
            async with client.get_queue_sender(queue_name=queue) as sender:
                await sender.send_messages(ServiceBusMessage(json.dumps(message)))
    except Exception as exc:  # pragma: no cover - runtime environmental
        logger.warning("Service Bus publish failed: %s", exc)


def publish_event_fire_and_forget(message: dict[str, Any]) -> None:
    """Fire-and-forget wrapper that schedules an async publish task.

    Any exceptions during scheduling are logged. The background task logs
    failures; the caller continues immediately.
    """
    try:
        asyncio.create_task(_publish_to_service_bus(message))
    except Exception:  # pragma: no cover - extremely unlikely
        logger.exception("Failed to schedule Service Bus publish task")


def append_session_tape(raw_message: str, session_id: str | None) -> None:
    """Append the raw JSON line to a session tape.

    If Azure Blob Storage is configured and the SDK is available, attempt to
    append to a remote blob. Otherwise write to a local file under
    `backend/session_tapes/sessions/{session_id}/{date}.jsonl`.
    """
    if not session_id:
        # Nothing to append to
        return

    date_str = datetime.now(timezone.utc).date().isoformat()

    # Try remote blob if configured and SDK present
    try:
        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if conn_str:  # pragma: no cover - requires env in CI to test
            from azure.storage.blob.aio import BlobServiceClient  # type: ignore

            container = "session-tapes"
            blob_name = f"sessions/{session_id}/{date_str}.jsonl"

            async def _upload():
                async with BlobServiceClient.from_connection_string(conn_str) as client:
                    container_client = client.get_container_client(container)
                    try:
                        await container_client.create_container()
                    except Exception:
                        pass
                    blob_client = container_client.get_blob_client(blob_name)
                    try:
                        # Append by downloading existing and re-uploading appended
                        exists = await blob_client.exists()
                        if exists:
                            existing = await blob_client.download_blob()
                            data = await existing.readall()
                            data = data + (raw_message + "\n").encode("utf-8")
                        else:
                            data = (raw_message + "\n").encode("utf-8")
                        await blob_client.upload_blob(data, overwrite=True)
                    except Exception as exc:
                        logger.warning(
                            "Failed to append to blob %s: %s", blob_name, exc
                        )

            asyncio.create_task(_upload())
            return
    except Exception:  # pragma: no cover
        logger.exception("Error while attempting remote blob append")

    # Fallback: local file append
    try:
        base = os.path.join(os.path.dirname(__file__), "..", "..", "session_tapes")
        path = os.path.join(base, "sessions", session_id)
        os.makedirs(path, exist_ok=True)
        file_path = os.path.join(path, f"{date_str}.jsonl")
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(raw_message + "\n")
    except Exception:  # pragma: no cover - filesystem issues
        logger.exception(
            "Failed to append session tape locally for session %s", session_id
        )
