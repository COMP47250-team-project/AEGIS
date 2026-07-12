"""The telemetry ingestion schema must accept every event the SDK emits.

Regression guard: a strict discriminated union once accepted only key_interval
and resize, so paste/tab_blur/answer_start/question_time were silently dropped
before storage — zeroing those scores and hiding them from the timeline.
"""

import pytest
from pydantic import ValidationError

from app.schemas.telemetry import TelemetryEventSchema

# Every event type the frontend telemetry SDK actually emits.
REAL_EVENTS = [
    {"type": "key_interval", "payload": {"interval_ms": 120, "question_id": "q1"}},
    {"type": "resize", "payload": {"width": 800, "height": 600}},
    {"type": "paste", "payload": {"question_id": "q1", "char_count": 300}},
    {"type": "tab_blur", "payload": {"reason": "tab_hidden", "away_ms": 5000}},
    {"type": "tab_return", "payload": {}},
    {"type": "answer_start", "payload": {"question_id": "q1", "elapsed_ms": 4000}},
    {
        "type": "question_time",
        "payload": {"question_id": "q1", "duration_ms": 90000, "position": 0},
    },
]


@pytest.mark.parametrize("event", REAL_EVENTS, ids=[e["type"] for e in REAL_EVENTS])
def test_all_real_event_types_validate(event: dict) -> None:
    # Must not raise — these are the frames that were being dropped.
    TelemetryEventSchema.validate_python(event)


def test_frame_without_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TelemetryEventSchema.validate_python({"payload": {"x": 1}})


def test_non_object_payload_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TelemetryEventSchema.validate_python({"type": "paste", "payload": "nope"})
