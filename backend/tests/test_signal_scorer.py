"""Unit tests for the pure signal scorer engine.

These tests require no database, no fixtures, no async setup — the scorer
is a pure function, so we test it with plain inputs and outputs.
"""

import pytest

from app.scoring.signal_scorer import (
    WEIGHTS,
    SignalScoreResult,
    compute_signal_scores,
)


class TestWeights:
    def test_weights_sum_to_one(self) -> None:
        assert sum(WEIGHTS.values()) == pytest.approx(1.0)

    def test_weights_match_formula_specification(self) -> None:
        assert WEIGHTS["tab_blur_score"] == 0.30
        assert WEIGHTS["paste_score"] == 0.25
        assert WEIGHTS["iki_outlier_score"] == 0.20
        assert WEIGHTS["first_keypress_score"] == 0.10
        assert WEIGHTS["answer_time_score"] == 0.10
        assert WEIGHTS["resize_score"] == 0.05


class TestZeroEvents:
    def test_zero_events_gives_zero_risk_score(self) -> None:
        """No signals at all → result is fully zeroed, not suspicious."""
        result = compute_signal_scores()

        assert result.risk_score == 0.0
        assert result.tab_blur_score == 0.0
        assert result.paste_score == 0.0
        assert result.iki_outlier_score == 0.0
        assert result.first_keypress_score == 0.0
        assert result.answer_time_score == 0.0
        assert result.resize_score == 0.0

    def test_zero_events_returns_signal_score_result_model(self) -> None:
        result = compute_signal_scores()
        assert isinstance(result, SignalScoreResult)


class TestAllEventsPresent:
    def test_all_components_at_maximum_gives_risk_score_one(self) -> None:
        """Every signal maxed out → aggregate should be the full 1.0."""
        result = compute_signal_scores(
            tab_blur_score=1.0,
            paste_score=1.0,
            iki_outlier_score=1.0,
            first_keypress_score=1.0,
            answer_time_score=1.0,
            resize_score=1.0,
        )
        assert result.risk_score == pytest.approx(1.0)

    def test_weighted_combination_matches_formula(self) -> None:
        """Verify the exact weighted-sum formula with distinct, non-trivial
        values for every component."""
        result = compute_signal_scores(
            tab_blur_score=0.8,
            paste_score=0.6,
            iki_outlier_score=0.4,
            first_keypress_score=0.2,
            answer_time_score=0.5,
            resize_score=0.9,
        )
        expected = (
            0.30 * 0.8 + 0.25 * 0.6 + 0.20 * 0.4 + 0.10 * 0.2 + 0.10 * 0.5 + 0.05 * 0.9
        )
        assert result.risk_score == pytest.approx(expected)

    def test_all_components_preserved_in_result(self) -> None:
        result = compute_signal_scores(
            tab_blur_score=0.3,
            paste_score=0.4,
            iki_outlier_score=0.5,
            first_keypress_score=0.6,
            answer_time_score=0.7,
            resize_score=0.8,
        )
        assert result.tab_blur_score == 0.3
        assert result.paste_score == 0.4
        assert result.iki_outlier_score == 0.5
        assert result.first_keypress_score == 0.6
        assert result.answer_time_score == 0.7
        assert result.resize_score == 0.8


class TestSomeEventsMissing:
    def test_only_tab_blur_present_others_default_to_zero(self) -> None:
        """A student with only tab-switch signal — every other component
        should default to 0.0 (no suspicion) rather than raising."""
        result = compute_signal_scores(tab_blur_score=0.9)

        assert result.tab_blur_score == 0.9
        assert result.paste_score == 0.0
        assert result.iki_outlier_score == 0.0
        assert result.risk_score == pytest.approx(0.30 * 0.9)

    def test_only_paste_and_iki_present(self) -> None:
        result = compute_signal_scores(paste_score=0.5, iki_outlier_score=0.5)

        expected = 0.25 * 0.5 + 0.20 * 0.5
        assert result.risk_score == pytest.approx(expected)
        assert result.tab_blur_score == 0.0
        assert result.first_keypress_score == 0.0


class TestClamping:
    def test_values_above_one_are_clamped(self) -> None:
        result = compute_signal_scores(tab_blur_score=5.0)
        assert result.tab_blur_score == 1.0

    def test_negative_values_are_clamped_to_zero(self) -> None:
        result = compute_signal_scores(paste_score=-2.0)
        assert result.paste_score == 0.0

    def test_risk_score_never_exceeds_one_even_with_extreme_inputs(self) -> None:
        result = compute_signal_scores(
            tab_blur_score=10.0,
            paste_score=10.0,
            iki_outlier_score=10.0,
            first_keypress_score=10.0,
            answer_time_score=10.0,
            resize_score=10.0,
        )
        assert result.risk_score == 1.0


class TestPurity:
    def test_function_is_deterministic(self) -> None:
        """Same inputs must always produce the same output — no hidden
        state or randomness."""
        result1 = compute_signal_scores(tab_blur_score=0.42, paste_score=0.17)
        result2 = compute_signal_scores(tab_blur_score=0.42, paste_score=0.17)
        assert result1 == result2

    def test_function_does_not_mutate_weights_dict(self) -> None:
        original_weights = dict(WEIGHTS)
        compute_signal_scores(tab_blur_score=0.9, paste_score=0.8)
        assert WEIGHTS == original_weights
