"""Pre-create required Azurite blob containers so /healthz reports 'ok' from the start.

Usage (from the backend/ directory):
    python -m scripts.init_blob

Idempotent: creating a container that already exists is silently ignored.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_CONTAINERS = ["session-tapes", "exam-resources"]


async def main() -> None:
    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if not conn:
        print("AZURE_STORAGE_CONNECTION_STRING not set — skipping blob init")
        return

    from azure.storage.blob.aio import BlobServiceClient  # type: ignore

    async with BlobServiceClient.from_connection_string(conn) as client:
        for name in _CONTAINERS:
            try:
                await client.create_container(name)
                print(f"created container: {name}")
            except Exception:
                print(f"already exists:    {name}")


if __name__ == "__main__":
    asyncio.run(main())
