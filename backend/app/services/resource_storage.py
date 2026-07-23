"""Durable storage for open-book exam resource files (AEGIS-121).

Unlike ``messaging.append_session_tape`` (fire-and-forget telemetry tapes),
uploaded resources are authored exam content, so writes here are **awaited and
error-surfacing** — the caller turns a failure into an HTTP 5xx rather than
silently losing the file.

Backend selection:
  * If ``AZURE_STORAGE_CONNECTION_STRING`` is set, files go to Blob Storage
    (durable across restarts — the correct prod path on Azure Container Apps).
  * Otherwise they fall back to local disk under ``backend/resource_files/``.
    NOTE: local disk is ephemeral on Container Apps — the fallback is for local
    development only and files will not survive a redeploy in the cloud.

The storage key is always server-generated ("{exam_id}/{uuid4}.pdf"), never
derived from the uploaded filename, so it can't be used for path traversal.
"""

import logging
import os
import uuid

logger = logging.getLogger(__name__)

_CONTAINER = "exam-resources"

# Only PDFs are accepted for now — served inline, so the type must be one the
# browser renders safely (never HTML/SVG, which would enable stored XSS).
ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


def _local_base() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", "resource_files")


def build_blob_ref(exam_id: uuid.UUID) -> str:
    """Return a fresh server-generated storage key for an exam's resource."""
    return f"{exam_id}/{uuid.uuid4()}.pdf"


async def store_file(blob_ref: str, data: bytes) -> None:
    """Persist file bytes durably. Raises on failure (caller maps to HTTP 5xx)."""
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        from azure.storage.blob.aio import BlobServiceClient  # type: ignore

        async with BlobServiceClient.from_connection_string(conn_str) as client:
            container_client = client.get_container_client(_CONTAINER)
            try:
                await container_client.create_container()
            except Exception:
                pass  # already exists
            blob_client = container_client.get_blob_client(blob_ref)
            await blob_client.upload_blob(data, overwrite=True)
        return

    # Local fallback (dev only — not durable on Container Apps).
    path = os.path.normpath(os.path.join(_local_base(), blob_ref))
    base = os.path.normpath(_local_base())
    if not path.startswith(base + os.sep):
        raise ValueError("Resolved resource path escapes storage root")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


async def load_file(blob_ref: str) -> bytes:
    """Read file bytes back for serving. Raises FileNotFoundError if missing."""
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        from azure.storage.blob.aio import BlobServiceClient  # type: ignore

        async with BlobServiceClient.from_connection_string(conn_str) as client:
            blob_client = client.get_blob_client(_CONTAINER, blob_ref)
            stream = await blob_client.download_blob()
            return await stream.readall()

    path = os.path.normpath(os.path.join(_local_base(), blob_ref))
    base = os.path.normpath(_local_base())
    if not path.startswith(base + os.sep):
        raise FileNotFoundError("Resolved resource path escapes storage root")
    with open(path, "rb") as f:
        return f.read()
