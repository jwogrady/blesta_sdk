"""Tests for _retry.py — jitter_delay helper (issue #66)."""

from __future__ import annotations

from unittest.mock import patch

from blesta_sdk._retry import jitter_delay


def test_jitter_delay_attempt_0_range():
    """attempt=0 → base=1, result in [0.5, 1.0]."""
    for _ in range(20):
        result = jitter_delay(0)
        assert 0.5 <= result <= 1.0


def test_jitter_delay_attempt_1_range():
    """attempt=1 → base=2, result in [1.0, 2.0]."""
    for _ in range(20):
        result = jitter_delay(1)
        assert 1.0 <= result <= 2.0


def test_jitter_delay_attempt_2_range():
    """attempt=2 → base=4, result in [2.0, 4.0]."""
    for _ in range(20):
        result = jitter_delay(2)
        assert 2.0 <= result <= 4.0


def test_jitter_delay_min_at_random_zero():
    """random=0.0 → result is exactly 50% of base."""
    with patch("blesta_sdk._retry.random.random", return_value=0.0):
        assert jitter_delay(0) == 0.5
        assert jitter_delay(1) == 1.0
        assert jitter_delay(3) == 4.0


def test_jitter_delay_max_at_random_one():
    """random=1.0 → result is exactly 100% of base."""
    with patch("blesta_sdk._retry.random.random", return_value=1.0):
        assert jitter_delay(0) == 1.0
        assert jitter_delay(1) == 2.0
        assert jitter_delay(3) == 8.0


def test_jitter_delay_returns_float():
    assert isinstance(jitter_delay(0), float)
