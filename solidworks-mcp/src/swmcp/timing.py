"""Elapsed-time helpers.

Small, but they earn their place twice over: durations are reported in one consistent
form everywhere, and the scattered ``round((time.monotonic() - t) * 1000, 2)`` idiom
disappears — which matters because the unit-conversion guard in
``tests/test_no_second_source_of_truth.py`` is deliberately absolute about ``* 1000``.
Length conversions live in :mod:`swmcp.units`; time conversions live here.
"""

from __future__ import annotations

import time

_MS_PER_SECOND = 1_000.0
_PRECISION = 2


def seconds_to_ms(seconds: float) -> float:
    return round(float(seconds) * _MS_PER_SECOND, _PRECISION)


def elapsed_ms(started_monotonic: float) -> float:
    """Milliseconds since a ``time.monotonic()`` reading."""
    return seconds_to_ms(time.monotonic() - started_monotonic)


def elapsed_s(started_monotonic: float, precision: int = 3) -> float:
    return round(time.monotonic() - started_monotonic, precision)
