"""Scoring-preset tests (AEGIS-84): each preset applies its own weights.

Using a component vector where only tab_switch is 1.0 isolates the tab_switch
weight, so the aggregate risk equals that preset's tab_switch weight — a direct
check that the correct weight set is applied and that presets differ.
"""

import pytest

from app.services.scorer import DEFAULT_PRESET, PRESETS, compute_risk_score

# Only tab_switch active → risk == preset's tab_switch weight.
_TAB_ONLY = {
    "tab_switch": 1.0,
    "paste": 0.0,
    "iki": 0.0,
    "first_keypress": 0.0,
    "answer_time": 0.0,
    "resize": 0.0,
}


def test_strict_applies_strict_weights() -> None:
    assert compute_risk_score(_TAB_ONLY, "strict") == pytest.approx(0.35)


def test_standard_applies_standard_weights() -> None:
    assert compute_risk_score(_TAB_ONLY, "standard") == pytest.approx(0.30)


def test_lenient_applies_lenient_weights() -> None:
    assert compute_risk_score(_TAB_ONLY, "lenient") == pytest.approx(0.15)


def test_presets_produce_different_outputs() -> None:
    results = {p: compute_risk_score(_TAB_ONLY, p) for p in PRESETS}
    assert len(set(results.values())) == 3  # all distinct


def test_default_preset_is_standard() -> None:
    assert DEFAULT_PRESET == "standard"
    assert compute_risk_score(_TAB_ONLY) == compute_risk_score(_TAB_ONLY, "standard")


def test_unknown_preset_falls_back_to_default() -> None:
    assert compute_risk_score(_TAB_ONLY, "bogus") == compute_risk_score(
        _TAB_ONLY, DEFAULT_PRESET
    )


def test_every_preset_sums_to_one() -> None:
    for weights in PRESETS.values():
        assert sum(weights.values()) == pytest.approx(1.0)
