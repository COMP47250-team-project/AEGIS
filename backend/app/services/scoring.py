"""Score computation job dispatcher.

When an exam is closed, this module publishes a message to the Azure Service Bus
score-jobs queue so the scoring service can compute integrity reports asynchronously.

If the Service Bus connection string is not configured (local dev / CI), the dispatch
is skipped with a warning rather than raising — exam closure must never be blocked by
an optional downstream service.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)

# Sentinel that marks a connection string as unconfigured
_PLACEHOLDER_PREFIXES = ("Endpoint=sb://...", "")


def _bus_configured() -> bool:
    cs = settings.azure_service_bus_connection_string
    if cs is None:
        return False
    return not any(cs.startswith(p) for p in _PLACEHOLDER_PREFIXES)


async def dispatch_score_job(exam_id: uuid.UUID) -> None:
    """Publish a score-computation job for the given exam to the Service Bus queue.

    Safe to call even when Azure Service Bus is not configured; logs a warning
    and returns instead of raising.
    """
    if not _bus_configured():
        logger.warning(
            "Service Bus not configured — skipping score job dispatch for exam %s", exam_id
        )
        return

    message_body = json.dumps(
        {
            "event": "score_exam",
            "exam_id": str(exam_id),
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    try:
        # Import lazily so the module loads even when azure-servicebus is not installed
        from azure.servicebus.aio import ServiceBusClient  # type: ignore[import-untyped]

        async with ServiceBusClient.from_connection_string(
            settings.azure_service_bus_connection_string  # type: ignore[arg-type]
        ) as client:
            async with client.get_queue_sender(settings.score_queue_name) as sender:
                from azure.servicebus import ServiceBusMessage  # type: ignore[import-untyped]

                await sender.send_messages(ServiceBusMessage(message_body))

        logger.info("Score job dispatched for exam %s → queue '%s'", exam_id, settings.score_queue_name)

    except Exception:
        # Log but do not re-raise — scoring is async and can be retried separately
        logger.exception("Failed to dispatch score job for exam %s", exam_id)
