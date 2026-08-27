"""Geometry signatures and tolerance-aware scoring.

A hash of rounded geometry is a fast equality test, but hashes are all-or-nothing: a
face that moved by a micron would look like a different face. So the hash is only the
fast path, and scoring falls back to comparing each measurement within a tolerance.

Scoring is deliberately conservative. ``MIN_SCORE`` is set so that a bare
geometry-type-plus-area match is *not* enough to act on — matching the wrong face and
cutting a hole in it is worse than reporting that the reference could not be resolved.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

from swmcp.refs.model import RefMeasurements, RefTolerance, SemanticRef
from swmcp.units import from_meters

#: Rounding to 1e-9 m (a nanometre) before hashing: far below any real CAD tolerance,
#: but enough to stop float noise producing a different hash for the same face.
_ROUND_DIGITS = 9

#: Weights. The geometry type is a gate rather than a score.
W_SIGNATURE = 6
W_POINT_EXACT = 4
W_POINT_NEAR = 2
W_DIRECTION = 3
W_RADIUS = 3
W_AREA = 2
W_ANCESTRY = 3
W_COMPONENT = 3

#: Below this, a candidate is not trustworthy enough to act on.
MIN_SCORE = 7


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), _ROUND_DIGITS)


def _round_all(values: list[float] | None) -> list[float] | None:
    return None if values is None else [round(float(v), _ROUND_DIGITS) for v in values]


def geometry_signature(geometry_type: str, measurements: RefMeasurements) -> str:
    """A stable hash of the rounded geometry."""
    payload = {
        "geometry_type": geometry_type,
        "point_m": _round_all(measurements.point_m),
        "direction": _round_all(measurements.direction),
        "radius_m": _round(measurements.radius_m),
        "area_m2": _round(measurements.area_m2),
        "length_m": _round(measurements.length_m),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _distance(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b or len(a) != len(b):
        return None
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def _angle_between(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b or len(a) != len(b):
        return None
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return None
    dot = sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)
    # A face normal may be reported flipped; treat antiparallel as aligned.
    return math.acos(max(-1.0, min(1.0, abs(dot))))


def _relative_close(a: float | None, b: float | None, relative: float) -> bool | None:
    if a is None or b is None:
        return None
    scale = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / scale <= relative


@dataclass
class Score:
    total: int = 0
    geometry_type_matches: bool = False
    reasons: list[str] = field(default_factory=list)

    def add(self, points: int, reason: str) -> None:
        self.total += points
        self.reasons.append(reason)


def score_candidate(
    wanted: SemanticRef, candidate: SemanticRef, tolerance: RefTolerance | None = None
) -> Score:
    """How well ``candidate`` matches ``wanted``."""
    tol = tolerance or wanted.tolerance
    result = Score()

    # Geometry type is a gate, not a score: a cylinder is never the plane you meant.
    if wanted.geometry_type not in ("unknown", candidate.geometry_type):
        return result
    result.geometry_type_matches = True

    if wanted.signature and wanted.signature == candidate.signature:
        result.add(W_SIGNATURE, "geometry signature is identical")

    distance = _distance(wanted.measurements.point_m, candidate.measurements.point_m)
    if distance is not None:
        if distance <= tol.linear_m:
            result.add(W_POINT_EXACT, f"point matches within {tol.linear_m:g} m")
        elif distance <= tol.linear_m * 10:
            result.add(W_POINT_NEAR, f"point is within {distance:.3g} m")

    angle = _angle_between(wanted.measurements.direction, candidate.measurements.direction)
    if angle is not None and angle <= tol.angular_rad:
        result.add(W_DIRECTION, "direction matches")

    if _relative_close(wanted.measurements.radius_m, candidate.measurements.radius_m, tol.relative):
        result.add(W_RADIUS, "radius matches")

    if _relative_close(wanted.measurements.area_m2, candidate.measurements.area_m2, tol.relative):
        result.add(W_AREA, "area matches")

    if wanted.feature_type_names and _tail_matches(
        wanted.feature_type_names, candidate.feature_type_names
    ):
        result.add(W_ANCESTRY, "feature ancestry matches")
    elif wanted.feature_ancestry and _tail_matches(
        wanted.feature_ancestry, candidate.feature_ancestry
    ):
        result.add(W_ANCESTRY, "feature names match")

    if wanted.component_path and wanted.component_path == candidate.component_path:
        result.add(W_COMPONENT, "component path matches")

    return result


def _tail_matches(wanted: list[str], candidate: list[str]) -> bool:
    if not wanted or not candidate:
        return False
    depth = min(len(wanted), len(candidate))
    return wanted[-depth:] == candidate[-depth:]


def drift_between(
    wanted: RefMeasurements, found: RefMeasurements
) -> tuple[float | None, float | None, float | None]:
    """``(moved_mm, radius_delta_mm, area_ratio)`` between a stored and a fresh capture."""
    distance = _distance(wanted.point_m, found.point_m)
    moved_mm = None if distance is None else from_meters(distance, "mm")

    radius_delta_mm = None
    if wanted.radius_m is not None and found.radius_m is not None:
        radius_delta_mm = from_meters(found.radius_m - wanted.radius_m, "mm")

    area_ratio = None
    if wanted.area_m2 and found.area_m2:
        area_ratio = found.area_m2 / wanted.area_m2

    return moved_mm, radius_delta_mm, area_ratio
