"""In-memory aggregates for the professor's live risk dashboard.

Student telemetry frames update per-student counters in process memory as they
arrive. The professor WebSocket reads a snapshot every 5s, so each broadcast is
a pure memory read — no DB query per tick. The DB still gets every event for the
authoritative score computed at exam close; this layer is only the live view.

State is per-process, so with multiple workers a professor only sees students
whose telemetry hit the same worker. Fine for the single-worker deployment.
"""

import time
from dataclasses import dataclass, field

from app.services.scorer import compute_risk_score
from app.services.scoring import Event
from app.services.scoring.components.paste import paste_score
from app.services.scoring.components.tab_blur import tab_blur_score

# No frame for this long => the student is treated as gone.
ACTIVE_WINDOW_S = 60.0

# Same normalisation the DB scorer uses, so the live score matches the final one.
# tab_blur + paste delegate to the shared component scorers (AEGIS-54); the other
# four stay inline until their own tickets unify them.
_RESIZE_DIVISOR = 5.0
_IKI_BASELINE_MS = 400.0
_QUICK_KEYPRESS_MS = 1000.0
_FAST_ANSWER_MS = 10_000.0


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


@dataclass
class StudentAggregate:
    """Running telemetry totals for one student in one session."""

    name: str | None = None
    email: str | None = None
    tab_blurs: int = 0
    pastes: int = 0
    resizes: int = 0
    iki_sum_ms: float = 0.0
    iki_count: int = 0
    keypresses: int = 0  # answer_start events
    quick_keypresses: int = 0  # ...answered in under a second
    question_durations: dict[str, float] = field(default_factory=dict)
    # Buffered tab_blur/tab_return/paste frames fed to the shared component
    # scorers (low-frequency, so memory stays bounded).
    signal_events: list[Event] = field(default_factory=list)
    last_event: str | None = None
    last_seen: float | None = None  # monotonic seconds; None until first frame

    def record(self, event_type: str, payload: dict, now: float) -> None:
        if event_type == "tab_blur":
            self.tab_blurs += 1
            self.signal_events.append(Event(event_type, payload))
        elif event_type == "tab_return":
            self.signal_events.append(Event(event_type, payload))
        elif event_type == "paste":
            self.pastes += 1
            self.signal_events.append(Event(event_type, payload))
        elif event_type == "resize":
            self.resizes += 1
        elif event_type == "key_interval":
            interval = payload.get("interval_ms")
            if isinstance(interval, (int, float)):
                self.iki_sum_ms += float(interval)
                self.iki_count += 1
        elif event_type == "answer_start":
            self.keypresses += 1
            elapsed = payload.get("elapsed_ms")
            if isinstance(elapsed, (int, float)) and float(elapsed) < _QUICK_KEYPRESS_MS:
                self.quick_keypresses += 1
        elif event_type == "question_time":
            qid = payload.get("question_id")
            duration = payload.get("duration_ms")
            # Cumulative per question, so keep the largest value seen.
            if isinstance(qid, str) and isinstance(duration, (int, float)):
                prev = self.question_durations.get(qid, 0.0)
                self.question_durations[qid] = max(prev, float(duration))

        self.last_event = event_type
        self.last_seen = now

    def _components(self) -> dict[str, float]:
        if self.iki_count:
            mean_iki = self.iki_sum_ms / self.iki_count
            iki = _clamp((_IKI_BASELINE_MS - mean_iki) / _IKI_BASELINE_MS)
        else:
            iki = 0.0

        first_keypress = (
            _clamp(self.quick_keypresses / self.keypresses) if self.keypresses else 0.0
        )

        durations = self.question_durations
        if durations:
            fast = sum(1 for d in durations.values() if d < _FAST_ANSWER_MS)
            answer_time = _clamp(fast / len(durations))
        else:
            answer_time = 0.0

        return {
            "tab_switch": tab_blur_score(self.signal_events),
            "paste": paste_score(self.signal_events),
            "iki": iki,
            "first_keypress": first_keypress,
            "answer_time": answer_time,
            "resize": _clamp(self.resizes / _RESIZE_DIVISOR),
        }

    def summarize(self, student_id: str, now: float) -> dict:
        components = self._components()
        risk = round(compute_risk_score(components), 3)
        active = self.last_seen is not None and now - self.last_seen <= ACTIVE_WINDOW_S
        return {
            "student_id": student_id,
            "name": self.name,
            "email": self.email,
            "risk_score": risk,
            "tab_blurs": self.tab_blurs,
            "pastes": self.pastes,
            "last_event": self.last_event,
            "active": active,
            # Kept so the existing professor console keeps rendering.
            "integrity_score": risk,
            "tab_switch_score": round(components["tab_switch"], 3),
            "paste_score": round(components["paste"], 3),
            "keystroke_score": round(components["iki"], 3),
        }


class LiveMonitor:
    """Holds the live aggregates for every running exam, keyed by exam id."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, StudentAggregate]] = {}

    def _student(self, exam_id: str, student_id: str) -> StudentAggregate:
        students = self._sessions.setdefault(exam_id, {})
        return students.setdefault(student_id, StudentAggregate())

    def seed_student(
        self,
        exam_id: str,
        student_id: str,
        name: str | None,
        email: str | None = None,
    ) -> None:
        """Register an enrolled student so they show (inactive) before any event."""
        agg = self._student(exam_id, student_id)
        if name is not None:
            agg.name = name
        if email is not None:
            agg.email = email

    def record_event(
        self,
        exam_id: str,
        student_id: str,
        event_type: str,
        payload: dict,
        name: str | None = None,
        email: str | None = None,
        now: float | None = None,
    ) -> None:
        agg = self._student(exam_id, student_id)
        if name is not None:
            agg.name = name
        if email is not None:
            agg.email = email
        agg.record(event_type, payload, time.monotonic() if now is None else now)

    def snapshot(self, exam_id: str, now: float | None = None) -> dict:
        """Build the broadcast payload for an exam — pure in-memory read."""
        ts = time.monotonic() if now is None else now
        students = self._sessions.get(exam_id, {})
        return {
            "exam_id": exam_id,
            "students": [agg.summarize(sid, ts) for sid, agg in students.items()],
        }

    def clear(self, exam_id: str) -> None:
        self._sessions.pop(exam_id, None)


# Process-wide instance shared by the WebSocket handlers.
live_monitor = LiveMonitor()
