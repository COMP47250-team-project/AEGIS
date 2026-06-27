"""Integration tests for compute_component_scores: wiring and weights.

The per-signal maths live in the dedicated component test files
(test_tab_blur_scorer, test_paste_scorer, test_first_keypress_scorer,
test_answer_time_scorer, test_resize_scorer). Here we only check that
compute_component_scores wires them together and that the weights are valid.
"""

import pytest

from app.models.telemetry import TelemetryEvent
from app.services.scorer import _WEIGHTS, compute_component_scores

_COMPONENTS = {"tab_switch", "paste", "iki", "first_keypress", "answer_time", "resize"}


def _event(event_type: str, payload: dict) -> TelemetryEvent:
    return TelemetryEvent(event_type=event_type, payload=payload)


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


def test_iki_remains_inline() -> None:
    # Fast mean interval -> high iki (still computed inline, AEGIS-55 pending).
    events = [_event("key_interval", {"interval_ms": 50}) for _ in range(3)]
    assert compute_component_scores(events)["iki"] == pytest.approx((400 - 50) / 400)
