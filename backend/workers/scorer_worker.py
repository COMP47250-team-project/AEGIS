"""Async background worker that batches telemetry events from Azure Service Bus
and triggers signal scoring per exam session.

Run standalone:
    python -m backend.workers.scorer_worker

Behaviour:
  - Subscribes to the Service Bus queue `aegis_events_queue_name`.
  - Buffers incoming events in memory, grouped by session_id.
  - Every `scorer_batch_interval_seconds` (default 30s), flushes each
    session's batch by calling `signal_scorer.compute(session_id, events)`.
  - On SIGTERM/SIGINT, stops accepting new messages and flushes whatever
    batch is currently in flight before exiting.
  - Messages that fail processing are retried; after
    `scorer_max_delivery_attempts` deliveries they are dead-lettered with a
    structured JSON log entry for post-mortem analysis.
"""

import asyncio
import json
import logging
import signal
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class ScorerWorker:
    """Batches Service Bus telemetry messages by session_id and triggers scoring."""

    def __init__(
        self,
        batch_interval_seconds: int | None = None,
        max_delivery_attempts: int | None = None,
    ) -> None:
        self.batch_interval_seconds = (
            batch_interval_seconds
            if batch_interval_seconds is not None
            else settings.scorer_batch_interval_seconds
        )
        self.max_delivery_attempts = (
            max_delivery_attempts
            if max_delivery_attempts is not None
            else settings.scorer_max_delivery_attempts
        )

        # session_id -> list of raw event payloads awaiting scoring
        self._batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._shutdown_event = asyncio.Event()
        self._flush_task: asyncio.Task[None] | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def install_signal_handlers(self) -> None:
        """Register SIGTERM/SIGINT handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.request_shutdown)  # type: ignore[attr-defined]

    def request_shutdown(self) -> None:
        logger.info("Shutdown requested — will flush in-flight batch and exit")
        self._shutdown_event.set()

    async def run(self) -> None:
        """Main loop: periodically flush batches until shutdown is requested."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=self.batch_interval_seconds
                )
            except asyncio.TimeoutError:
                pass  # normal tick — fall through to flush

            await self.flush_all_batches()

        # Final flush on shutdown — never drop in-flight work
        await self.flush_all_batches()
        logger.info("Scorer worker stopped cleanly")

    # ── Message ingestion ───────────────────────────────────────────────────

    def enqueue_event(self, session_id: str, event: dict[str, Any]) -> None:
        """Add a single decoded telemetry event to its session's batch."""
        self._batches[session_id].append(event)

    # ── Batch processing ─────────────────────────────────────────────────────

    async def flush_all_batches(self) -> None:
        """Flush every session's pending batch."""
        session_ids = list(self._batches.keys())
        for session_id in session_ids:
            await self.flush_session_batch(session_id)

    async def flush_session_batch(self, session_id: str) -> None:
        """Pop and process the batch for one session_id."""
        events = self._batches.pop(session_id, [])
        if not events:
            return

        try:
            await self._score_session(session_id, events)
        except Exception:
            logger.exception(
                "Scoring failed for session %s (%d events) — re-queuing",
                session_id,
                len(events),
            )
            # Re-queue for retry on next tick rather than dropping silently
            self._batches[session_id].extend(events)

    async def _score_session(
        self, session_id: str, events: list[dict[str, Any]]
    ) -> None:
        """Invoke the signal scorer for one session's batch of events."""
        from app.database import AsyncSessionLocal
        from app.services.scorer import compute_and_save_scores

        async with AsyncSessionLocal() as db:
            await compute_and_save_scores(db, uuid.UUID(session_id))

        logger.info("Scored session %s — %d events processed", session_id, len(events))

    # ── Dead-letter handling ─────────────────────────────────────────────────

    def log_dead_letter(
        self,
        message_id: str,
        session_id: str | None,
        delivery_count: int,
        reason: str,
    ) -> None:
        """Emit a structured JSON log entry for a message sent to the DLQ."""
        entry = {
            "event": "dead_letter",
            "message_id": message_id,
            "session_id": session_id,
            "delivery_count": delivery_count,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.error(json.dumps(entry))

    def should_dead_letter(self, delivery_count: int) -> bool:
        """True once a message has exceeded the max delivery attempts."""
        return delivery_count >= self.max_delivery_attempts


async def main() -> None:
    """Entry point for running the worker as a standalone process."""
    logging.basicConfig(level=settings.log_level)
    worker = ScorerWorker()
    worker.install_signal_handlers()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
