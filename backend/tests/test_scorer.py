"""Integration tests for compute_component_scores: wiring and weights.

The per-signal maths live in the dedicated component test files
(test_tab_blur_scorer, test_paste_scorer, test_first_keypress_scorer,
test_answer_time_scorer, test_resize_scorer). Here we only check that
compute_component_scores wires them together and that the weights are valid.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.models.telemetry import TelemetryEvent
from app.services.scorer import _WEIGHTS, compute_component_scores

_COMPONENTS = {"tab_switch", "paste", "iki", "first_keypress", "answer_time", "resize"}

_T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _event(event_type: str, payload: dict) -> TelemetryEvent:
    return TelemetryEvent(event_type=event_type, payload=payload)


def _ts_event(event_type: str, payload: dict, occurred_at: datetime) -> TelemetryEvent:
    return TelemetryEvent(
        event_type=event_type, payload=payload, occurred_at=occurred_at
    )


def test_weights_sum_to_one() -> None:
    assert sum(_WEIGHTS.values()) == pytest.approx(1.0)
    assert _WEIGHTS.keys() == _COMPONENTS


def test_all_components_present_and_in_range() -> None:
    scores = compute_component_scores([])
    assert set(scores) == _COMPONENTS
    assert all(0.0 <= v <= 1.0 for v in scores.values())


def test_answer_time_uses_cv_distribution() -> None:
    # Even per-question times -> CV 0 -> answer_time 0.0 (AEGIS-56 semantics).
    events = [
        _event("question_time", {"question_id": f"q{i}", "duration_ms": 60_000})
        for i in range(3)
    ]
    assert compute_component_scores(events)["answer_time"] == pytest.approx(0.0)


def test_iki_uses_zscore_baseline() -> None:
    # AEGIS-55: IKI is now a z-score against a per-student baseline, not the old
    # inline (400 - mean)/400. A short session with no baseline window (< the
    # 5-min baseline / <50 keystrokes) is insufficient → the sub-score is 0.0
    # rather than firing on a couple of fast intervals.
    events = [_event("key_interval", {"interval_ms": 50}) for _ in range(3)]
    assert compute_component_scores(events)["iki"] == pytest.approx(0.0)


def test_iki_zscore_fires_on_cadence_anomaly() -> None:
    # AEGIS-55 end-to-end: a sufficient baseline (60 intervals, median ~200ms)
    # followed by a later window that deviates strongly (450ms → z ≈ +5) yields
    # a high IKI sub-score via the z-score path — not the old linear heuristic.
    events: list[TelemetryEvent] = []
    for i in range(60):  # baseline window: 0..236s, >=50 samples → sufficient
        events.append(
            _ts_event(
                "key_interval",
                {"interval_ms": 150 if i % 2 == 0 else 250},
                _T0 + timedelta(seconds=i * 4),
            )
        )
    for i in range(15):  # anomalous window at T+6min
        events.append(
            _ts_event(
                "key_interval", {"interval_ms": 450}, _T0 + timedelta(seconds=360 + i)
            )
        )
    assert compute_component_scores(events)["iki"] > 0.7


def test_iki_zscore_low_for_steady_typing() -> None:
    # Same baseline, and the later window keeps typing at the baseline median
    # (200ms) → z ≈ 0 → low suspicion. Using a constant 200ms (rather than the
    # alternating 150/250 pattern) makes the window median exactly 200 for ANY
    # count, so the test can't silently break on an odd/even off-by-one: the
    # scorer compares the window *median* to the baseline median, and matching it
    # is precisely what "steady typing at the established rhythm" means.
    events: list[TelemetryEvent] = []
    for i in range(60):
        events.append(
            _ts_event(
                "key_interval",
                {"interval_ms": 150 if i % 2 == 0 else 250},
                _T0 + timedelta(seconds=i * 4),
            )
        )
    for i in range(15):  # later window typed steadily at the baseline median
        events.append(
            _ts_event(
                "key_interval", {"interval_ms": 200}, _T0 + timedelta(seconds=360 + i)
            )
        )
    assert compute_component_scores(events)["iki"] < 0.2


def test_fullscreen_exit_events_do_not_affect_score() -> None:
    """fullscreen_exit is evidence-only — it must never influence the risk/
    confidence score. compute_component_scores must return identical
    results whether or not fullscreen_exit events are present, proving the
    scorer simply doesn't process this event type."""
    base_events = [
        _event("tab_blur", {}),
        _event("paste", {}),
    ]
    with_fullscreen_exit = base_events + [
        _event("fullscreen_exit", {}),
        _event("fullscreen_exit", {}),
    ]

    scores_without = compute_component_scores(base_events)
    scores_with = compute_component_scores(with_fullscreen_exit)

    assert scores_with == scores_without
