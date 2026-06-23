"""Tests for the async scorer worker — batching, shutdown, and DLQ behaviour."""

import asyncio
import uuid

import pytest

from workers.scorer_worker import ScorerWorker


@pytest.fixture
def worker() -> ScorerWorker:
    return ScorerWorker(batch_interval_seconds=1, max_delivery_attempts=3)


class TestBatching:
    def test_enqueue_groups_events_by_session_id(self, worker: ScorerWorker) -> None:
        worker.enqueue_event("session-1", {"type": "tab_blur"})
        worker.enqueue_event("session-1", {"type": "paste"})
        worker.enqueue_event("session-2", {"type": "tab_blur"})

        assert len(worker._batches["session-1"]) == 2
        assert len(worker._batches["session-2"]) == 1

    @pytest.mark.asyncio
    async def test_flush_session_batch_clears_the_batch(
        self, worker: ScorerWorker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session_id = str(uuid.uuid4())
        worker.enqueue_event(session_id, {"type": "tab_blur"})

        async def fake_score(self_, sid, events):  # noqa: ANN001
            await asyncio.sleep(0)

        monkeypatch.setattr(ScorerWorker, "_score_session", fake_score)

        await worker.flush_session_batch(session_id)

        assert session_id not in worker._batches

    @pytest.mark.asyncio
    async def test_flush_all_batches_processes_every_session(
        self, worker: ScorerWorker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scored: list[str] = []

        async def fake_score(self_, sid, events):  # noqa: ANN001
            await asyncio.sleep(0)
            scored.append(sid)

        monkeypatch.setattr(ScorerWorker, "_score_session", fake_score)

        s1, s2 = str(uuid.uuid4()), str(uuid.uuid4())
        worker.enqueue_event(s1, {"type": "tab_blur"})
        worker.enqueue_event(s2, {"type": "paste"})

        await worker.flush_all_batches()

        assert set(scored) == {s1, s2}
        assert worker._batches == {}

    @pytest.mark.asyncio
    async def test_failed_scoring_requeues_events_for_retry(
        self, worker: ScorerWorker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session_id = str(uuid.uuid4())
        worker.enqueue_event(session_id, {"type": "tab_blur"})

        async def fake_score(self_, sid, events):  # noqa: ANN001
            await asyncio.sleep(0)
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(ScorerWorker, "_score_session", fake_score)

        await worker.flush_session_batch(session_id)

        # Event should still be present, ready for the next tick
        assert len(worker._batches[session_id]) == 1


class TestGracefulShutdown:
    @pytest.mark.asyncio
    async def test_run_flushes_in_flight_batch_on_shutdown(
        self, worker: ScorerWorker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scored: list[str] = []

        async def fake_score(self_, sid, events):  # noqa: ANN001
            await asyncio.sleep(0)
            scored.append(sid)

        monkeypatch.setattr(ScorerWorker, "_score_session", fake_score)

        session_id = str(uuid.uuid4())
        worker.enqueue_event(session_id, {"type": "tab_blur"})

        run_task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.05)
        worker.request_shutdown()
        await run_task

        assert session_id in scored

    def test_request_shutdown_sets_event(self, worker: ScorerWorker) -> None:
        assert not worker._shutdown_event.is_set()
        worker.request_shutdown()
        assert worker._shutdown_event.is_set()


class TestDeadLetterQueue:
    def test_should_dead_letter_below_threshold(self, worker: ScorerWorker) -> None:
        assert worker.should_dead_letter(1) is False
        assert worker.should_dead_letter(2) is False

    def test_should_dead_letter_at_threshold(self, worker: ScorerWorker) -> None:
        assert worker.should_dead_letter(3) is True

    def test_should_dead_letter_above_threshold(self, worker: ScorerWorker) -> None:
        assert worker.should_dead_letter(5) is True

    def test_log_dead_letter_emits_structured_json(
        self, worker: ScorerWorker, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        with caplog.at_level(logging.ERROR):
            worker.log_dead_letter(
                message_id="msg-123",
                session_id="session-456",
                delivery_count=3,
                reason="malformed payload",
            )

        assert len(caplog.records) == 1
        import json

        payload = json.loads(caplog.records[0].message)
        assert payload["event"] == "dead_letter"
        assert payload["message_id"] == "msg-123"
        assert payload["session_id"] == "session-456"
        assert payload["delivery_count"] == 3
        assert payload["reason"] == "malformed payload"


class TestThroughput:
    @pytest.mark.asyncio
    async def test_100_events_processed_within_35_seconds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Acceptance criteria: 100 events across sessions all processed within 35s."""
        worker = ScorerWorker(batch_interval_seconds=1, max_delivery_attempts=3)
        processed_count = 0

        async def fake_score(self_, sid, events):  # noqa: ANN001
            await asyncio.sleep(0)
            nonlocal processed_count
            processed_count += len(events)

        monkeypatch.setattr(ScorerWorker, "_score_session", fake_score)

        session_ids = [str(uuid.uuid4()) for _ in range(10)]
        for i in range(100):
            worker.enqueue_event(session_ids[i % 10], {"type": "tab_blur", "i": i})

        start = asyncio.get_event_loop().time()

        run_task = asyncio.create_task(worker.run())
        await asyncio.sleep(1.2)  # allow at least one batch tick
        worker.request_shutdown()
        await run_task

        elapsed = asyncio.get_event_loop().time() - start

        assert processed_count == 100
        assert elapsed < 35.0
