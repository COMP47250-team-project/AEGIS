"""Signal scoring package (AEGIS-54+).

Holds the pure per-signal scorers under ``components`` plus the score-job
dispatcher. ``dispatch_score_job`` is re-exported here so existing
``from app.services.scoring import dispatch_score_job`` imports keep working
after ``scoring`` became a package.

The component scorers are side-effect-free functions that turn a student's
telemetry events into a 0–1 sub-score. Both the batch scorer
(``app.services.scorer``) and the live monitor (``app.services.live_monitor``)
call the same functions, so the live score and the final score never diverge.
"""

from typing import NamedTuple, Protocol

from app.services.scoring.dispatch import dispatch_score_job

__all__ = ["Event", "ScoringEvent", "dispatch_score_job"]


class ScoringEvent(Protocol):
    """Minimal (read-only) shape a telemetry event must expose to be scored.

    Satisfied structurally by the SQLAlchemy ``TelemetryEvent`` ORM model and by
    the live monitor's buffered ``Event`` tuples alike, so the scorers stay
    decoupled from where the events come from.
    """

    @property
    def event_type(self) -> str: ...

    @property
    def payload(self) -> dict: ...


class Event(NamedTuple):
    """Concrete read-only ``ScoringEvent`` for callers without ORM rows."""

    event_type: str
    payload: dict
