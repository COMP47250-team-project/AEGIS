"""Unit tests for the pure baseline calculator.

No database, no fixtures, no async setup — purely tests inputs and outputs.
"""

import pytest

from app.scoring.baseline_calculator import (
    MIN_KEYSTROKES_FOR_BASELINE,
    BaselineResult,
    compute_baseline,
)


class TestInsufficientData:
    def test_fewer_than_50_keystrokes_marks_insufficient(self) -> None:
        """Ticket: fewer than 50 chars in 5 min → baseline marked insufficient."""
        result = compute_baseline(
            iki_samples_ms=[200.0] * 10,
            char_count=10,
            first_keypress_latencies_ms=[500.0],
        )
        assert result.is_sufficient is False

    def test_insufficient_baseline_has_null_numeric_fields(self) -> None:
        result = compute_baseline(
            iki_samples_ms=[200.0] * 5,
            char_count=5,
            first_keypress_latencies_ms=[],
        )
        assert result.median_iki_ms is None
        assert result.iki_stddev_ms is None
        assert result.typing_speed_chars_per_min is None
        assert result.avg_time_to_first_keypress_ms is None

    def test_zero_keystrokes_is_insufficient(self) -> None:
        result = compute_baseline(
            iki_samples_ms=[],
            char_count=0,
            first_keypress_latencies_ms=[],
        )
        assert result.is_sufficient is False
        assert result.sample_count == 0

    def test_exactly_49_keystrokes_is_insufficient(self) -> None:
        """Boundary check — one below the minimum threshold."""
        samples = [200.0] * (MIN_KEYSTROKES_FOR_BASELINE - 1)
        result = compute_baseline(
            iki_samples_ms=samples,
            char_count=MIN_KEYSTROKES_FOR_BASELINE - 1,
            first_keypress_latencies_ms=[],
        )
        assert result.is_sufficient is False

    def test_insufficient_char_count_even_with_enough_samples(self) -> None:
        """50+ IKI samples but char_count below threshold should still be
        insufficient — char_count is the authoritative sufficiency check."""
        result = compute_baseline(
            iki_samples_ms=[200.0] * MIN_KEYSTROKES_FOR_BASELINE,
            char_count=10,
            first_keypress_latencies_ms=[],
        )
        assert result.is_sufficient is False


class TestSufficientData:
    def test_exactly_50_keystrokes_is_sufficient(self) -> None:
        """Boundary check — exactly at the minimum threshold."""
        samples = [200.0] * MIN_KEYSTROKES_FOR_BASELINE
        result = compute_baseline(
            iki_samples_ms=samples,
            char_count=MIN_KEYSTROKES_FOR_BASELINE,
            first_keypress_latencies_ms=[300.0],
        )
        assert result.is_sufficient is True

    def test_median_iki_computed_correctly(self) -> None:
        samples = [100.0, 200.0, 300.0] + [200.0] * (MIN_KEYSTROKES_FOR_BASELINE - 3)
        result = compute_baseline(
            iki_samples_ms=samples,
            char_count=len(samples),
            first_keypress_latencies_ms=[],
        )
        assert result.median_iki_ms == pytest.approx(200.0)

    def test_stddev_computed_correctly(self) -> None:
        samples = [200.0] * MIN_KEYSTROKES_FOR_BASELINE
        result = compute_baseline(
            iki_samples_ms=samples,
            char_count=len(samples),
            first_keypress_latencies_ms=[],
        )
        # Identical samples → zero variance
        assert result.iki_stddev_ms == pytest.approx(0.0)

    def test_typing_speed_computed_from_char_count_and_window(self) -> None:
        """600 chars over the 5-minute baseline window → 120 chars/min."""
        samples = [200.0] * MIN_KEYSTROKES_FOR_BASELINE
        result = compute_baseline(
            iki_samples_ms=samples,
            char_count=600,
            first_keypress_latencies_ms=[],
        )
        assert result.typing_speed_chars_per_min == pytest.approx(120.0)

    def test_avg_first_keypress_latency_computed_correctly(self) -> None:
        samples = [200.0] * MIN_KEYSTROKES_FOR_BASELINE
        result = compute_baseline(
            iki_samples_ms=samples,
            char_count=len(samples),
            first_keypress_latencies_ms=[100.0, 200.0, 300.0],
        )
        assert result.avg_time_to_first_keypress_ms == pytest.approx(200.0)

    def test_no_first_keypress_samples_gives_none(self) -> None:
        samples = [200.0] * MIN_KEYSTROKES_FOR_BASELINE
        result = compute_baseline(
            iki_samples_ms=samples,
            char_count=len(samples),
            first_keypress_latencies_ms=[],
        )
        assert result.avg_time_to_first_keypress_ms is None

    def test_sample_count_reflects_iki_sample_length(self) -> None:
        samples = [200.0] * 75
        result = compute_baseline(
            iki_samples_ms=samples,
            char_count=75,
            first_keypress_latencies_ms=[],
        )
        assert result.sample_count == 75


class TestPurity:
    def test_function_returns_baseline_result_model(self) -> None:
        result = compute_baseline(
            iki_samples_ms=[200.0] * MIN_KEYSTROKES_FOR_BASELINE,
            char_count=MIN_KEYSTROKES_FOR_BASELINE,
            first_keypress_latencies_ms=[300.0],
        )
        assert isinstance(result, BaselineResult)

    def test_function_is_deterministic(self) -> None:
        samples = [150.0, 250.0, 180.0] * 20
        result1 = compute_baseline(samples, len(samples), [400.0])
        result2 = compute_baseline(samples, len(samples), [400.0])
        assert result1 == result2

    def test_function_does_not_mutate_input_list(self) -> None:
        samples = [200.0] * MIN_KEYSTROKES_FOR_BASELINE
        original = list(samples)
        compute_baseline(samples, len(samples), [300.0])
        assert samples == original
