"""The invariants ``sw_safe_execute`` checks, tested without SOLIDWORKS.

Deciding whether an invariant held is a pure function of two model snapshots, so every
branch can be exercised here — including the ones a live test would struggle to
produce, like a feature that rebuilt with an error.

Each result carries what was wanted and what was found, because "invariants_held:
false" on its own tells a caller nothing about which one, or by how much.
"""

from __future__ import annotations

import pytest

from swmcp.handlers.review import _check_invariants, _EndState
from swmcp.schemas.review import Invariants


def _state(**overrides) -> _EndState:
    before = {"body_count": 1, "face_count": 6, "volume_m3": 4.8e-05, "volume_mm3": 48000.0}
    after = {"body_count": 1, "face_count": 6, "volume_m3": 4.8e-05, "volume_mm3": 48000.0}
    return _EndState(
        before=overrides.get("before", before),
        after=overrides.get("after", after),
        features=overrides.get("features", {"Plate", "Corners"}),
        features_in_error=overrides.get("features_in_error", []),
        rebuild_errors=overrides.get("rebuild_errors", []),
    )


def _held(invariants: Invariants, state: _EndState) -> dict[str, bool]:
    return {entry["invariant"]: entry["held"] for entry in _check_invariants(invariants, state)}


def test_no_invariants_still_checks_the_two_that_default_on():
    """An empty declaration means "run these atomically", not "check nothing"."""
    results = _check_invariants(Invariants(), _state())
    names = {entry["invariant"] for entry in results}

    assert names == {"no_features_in_error", "no_rebuild_errors"}
    assert all(entry["held"] for entry in results)


def test_a_feature_in_error_fails_the_default_invariant():
    results = _check_invariants(Invariants(), _state(features_in_error=["Fillet1"]))
    entry = next(r for r in results if r["invariant"] == "no_features_in_error")

    assert entry["held"] is False
    assert entry["found"] == ["Fillet1"], "the caller needs to know which feature"


def test_a_rebuild_failure_fails_the_default_invariant():
    results = _check_invariants(Invariants(), _state(rebuild_errors=["ForceRebuild3 failed"]))
    assert not next(r for r in results if r["invariant"] == "no_rebuild_errors")["held"]


@pytest.mark.parametrize(("wanted", "actual", "expected"), [(1, 1, True), (1, 2, False)])
def test_body_count_is_exact(wanted, actual, expected):
    state = _state(after={"body_count": actual, "face_count": 6, "volume_m3": 1.0, "volume_mm3": 1.0})
    assert _held(Invariants(body_count=wanted), state)["body_count"] is expected


def test_face_count_is_exact():
    state = _state(after={"body_count": 1, "face_count": 12, "volume_m3": 1.0, "volume_mm3": 1.0})
    assert _held(Invariants(face_count=12), state)["face_count"] is True
    assert _held(Invariants(face_count=6), state)["face_count"] is False


def test_volume_bounds_are_inclusive():
    checks = _held(Invariants(min_volume_mm3=48000.0, max_volume_mm3=48000.0), _state())
    assert checks["min_volume_mm3"] is True
    assert checks["max_volume_mm3"] is True


def test_a_volume_outside_its_bounds_fails():
    assert _held(Invariants(min_volume_mm3=50000.0), _state())["min_volume_mm3"] is False
    assert _held(Invariants(max_volume_mm3=100.0), _state())["max_volume_mm3"] is False


@pytest.mark.parametrize(
    ("direction", "ended", "expected"),
    [
        ("increase", 5.0e-05, True),
        ("increase", 4.0e-05, False),
        ("decrease", 4.0e-05, True),
        ("decrease", 5.0e-05, False),
        ("unchanged", 4.8e-05, True),
        ("unchanged", 4.9e-05, False),
    ],
)
def test_volume_change_compares_the_two_snapshots(direction, ended, expected):
    state = _state(
        after={"body_count": 1, "face_count": 6, "volume_m3": ended, "volume_mm3": ended * 1e9}
    )
    assert _held(Invariants(volume_change=direction), state)["volume_change"] is expected


def test_required_and_forbidden_features_are_reported_by_name():
    results = _check_invariants(
        Invariants(require_features=["Plate", "Missing"], forbid_features=["Corners"]),
        _state(),
    )
    required = [r for r in results if r["invariant"] == "require_feature"]
    forbidden = [r for r in results if r["invariant"] == "forbid_feature"]

    assert [r["wanted"] for r in required] == ["Plate", "Missing"]
    assert [r["held"] for r in required] == [True, False]
    assert forbidden[0]["held"] is False, "Corners is present, so forbidding it fails"


def test_bounds_that_cannot_both_hold_are_refused_by_the_schema():
    with pytest.raises(ValueError, match="greater than"):
        Invariants(min_volume_mm3=100.0, max_volume_mm3=10.0)


def test_every_result_says_what_was_wanted_and_what_was_found():
    """A bare pass/fail would leave the caller guessing."""
    results = _check_invariants(
        Invariants(body_count=2, volume_change="increase", require_features=["Nope"]),
        _state(),
    )
    assert results
    for entry in results:
        assert set(entry) == {"invariant", "held", "wanted", "found"}
        assert entry["wanted"] is not None
