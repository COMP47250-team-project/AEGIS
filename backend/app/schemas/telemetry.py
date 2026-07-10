from __future__ import annotations

from pydantic import BaseModel, TypeAdapter


class TelemetryEvent(BaseModel):
    """A telemetry frame from the browser SDK.

    Permissive by design: it accepts ANY event type the SDK emits (paste,
    tab_blur, tab_return, key_interval, resize, answer_start, question_time, …)
    as long as ``type`` is a string and ``payload`` (if present) is an object.

    A previous strict discriminated union only accepted ``key_interval`` and
    ``resize`` and silently dropped every other event at ingestion. That zeroed
    the tab-switch and paste sub-scores (55% of the risk score) and left those
    events out of the professor timeline. A per-type allow-list is a footgun —
    every new signal would silently break again — so we validate the frame shape
    and let the scorer/timeline decide what each event means. Frames with a
    missing/invalid ``type`` or a non-object ``payload`` are still rejected.
    """

    type: str
    sessionId: str | None = None
    clientTs: int | None = None
    payload: dict | None = None


TelemetryEventSchema = TypeAdapter(TelemetryEvent)
