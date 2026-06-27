"""Tests for resize_score (AEGIS-56)."""

import pytest

from app.services.scoring import Event
from app.services.scoring.components.resize import resize_score


def _resize(width: float) -> Event:
    return Event("resize", {"width": width})


def test_no_significant_resizes_scores_zero() -> None:
    # First sets baseline 1000; 1050 is only a 5% change -> not significant.
    assert resize_score([_resize(1000), _resize(1050)]) == 0.0


def test_one_or_two_significant_resizes() -> None:
    # baseline 1000; 1300 is a 30% change -> 1 significant -> 0.3.
    assert resize_score([_resize(1000), _resize(1300)]) == 0.3


def test_three_significant_resizes() -> None:
    events = [_resize(1000), _resize(1300), _resize(700), _resize(1400)]
    assert resize_score(events) == 0.7


def test_tab_blur_correlation_bonus() -> None:
    # 1 significant resize (0.3) + a tab_blur present -> +0.20 -> 0.5.
    events = [_resize(1000), _resize(1300), Event("tab_blur", {})]
    assert resize_score(events) == pytest.approx(0.5)


def test_no_bonus_without_a_significant_resize() -> None:
    # tab_blur present but no significant resize -> stays 0.0.
    events = [_resize(1000), _resize(1010), Event("tab_blur", {})]
    assert resize_score(events) == 0.0
