"""Face and edge probes (REF-005).

One filtered probe replaces the usual scatter of "get planar face", "get cylindrical
face", "get feature faces", and "get largest face" helpers. Filters are what let a
caller narrow a search down to a single entity *before* acting, which is the practical
answer to ambiguity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from swmcp.com.marshal import try_com_member
from swmcp.refs.capture import capture, edges_of, faces_of
from swmcp.refs.model import EntityRef
from swmcp.refs.resolve import _all_bodies, _find_feature

EntityClass = Literal["face", "edge"]


@dataclass(frozen=True, slots=True)
class ProbeFilters:
    """Filter bounds, all already normalized to API units (metres, square metres)."""

    geometry_type: str | None = None
    radius_min_m: float | None = None
    radius_max_m: float | None = None
    area_min_m2: float | None = None
    area_max_m2: float | None = None
    #: Length is to an edge what area is to a face, and it is the bound that decides
    #: which edges are worth rounding: the short ones a fillet would swallow are also
    #: the ones that make it fail.
    length_min_m: float | None = None
    length_max_m: float | None = None
    normal: tuple[float, float, float] | None = None
    normal_within_deg: float = 5.0
    contains_point_m: tuple[float, float, float] | None = None
    contains_tolerance_m: float = 0.001


def _angle_to(direction: list[float] | None, wanted: tuple[float, float, float]) -> float | None:
    if not direction or len(direction) != 3:
        return None
    norm = math.sqrt(sum(v * v for v in direction))
    wanted_norm = math.sqrt(sum(v * v for v in wanted))
    if norm == 0 or wanted_norm == 0:
        return None
    dot = sum(a * b for a, b in zip(direction, wanted, strict=True)) / (norm * wanted_norm)
    # A face normal may be reported flipped; treat antiparallel as aligned.
    return math.degrees(math.acos(max(-1.0, min(1.0, abs(dot)))))


def _matches(ref: EntityRef, filters: ProbeFilters) -> bool:
    measurements = ref.semantic.measurements

    if filters.geometry_type and ref.semantic.geometry_type != filters.geometry_type:
        return False

    if filters.radius_min_m is not None or filters.radius_max_m is not None:
        if measurements.radius_m is None:
            return False
        if filters.radius_min_m is not None and measurements.radius_m < filters.radius_min_m:
            return False
        if filters.radius_max_m is not None and measurements.radius_m > filters.radius_max_m:
            return False

    if filters.area_min_m2 is not None or filters.area_max_m2 is not None:
        if measurements.area_m2 is None:
            return False
        if filters.area_min_m2 is not None and measurements.area_m2 < filters.area_min_m2:
            return False
        if filters.area_max_m2 is not None and measurements.area_m2 > filters.area_max_m2:
            return False

    if filters.length_min_m is not None or filters.length_max_m is not None:
        if measurements.length_m is None:
            return False
        if filters.length_min_m is not None and measurements.length_m < filters.length_min_m:
            return False
        if filters.length_max_m is not None and measurements.length_m > filters.length_max_m:
            return False

    if filters.normal is not None:
        angle = _angle_to(measurements.direction, filters.normal)
        if angle is None or angle > filters.normal_within_deg:
            return False

    if filters.contains_point_m is not None:
        if not measurements.bbox_m or len(measurements.bbox_m) != 6:
            return False
        tolerance = filters.contains_tolerance_m
        low = measurements.bbox_m[0:3]
        high = measurements.bbox_m[3:6]
        for value, lo, hi in zip(filters.contains_point_m, low, high, strict=True):
            if value < lo - tolerance or value > hi + tolerance:
                return False

    return True


def _owners(doc: Any, feature_name: str | None, body_name: str | None) -> list[Any]:
    if feature_name:
        feature = _find_feature(doc, feature_name)
        return [feature] if feature is not None else []
    bodies = _all_bodies(doc)
    if body_name:
        return [b for b in bodies if str(try_com_member(b, "Name", default="")) == body_name]
    return bodies


def probe_entities(
    session: Any,
    doc: Any,
    *,
    entity_class: EntityClass = "face",
    feature_name: str | None = None,
    body_name: str | None = None,
    filters: ProbeFilters | None = None,
    limit: int = 50,
) -> tuple[list[EntityRef], int]:
    """Return matching references plus how many entities were examined."""
    filters = filters or ProbeFilters()
    owners = _owners(doc, feature_name, body_name)

    captured: list[EntityRef] = []
    examined = 0
    for owner in owners:
        entities = edges_of(owner) if entity_class == "edge" else faces_of(owner)
        for entity in entities:
            examined += 1
            ref = capture(session, doc, entity)
            if _matches(ref, filters):
                captured.append(ref)

    # Largest first: the biggest face is usually the one a human means.
    captured.sort(
        key=lambda ref: (
            ref.semantic.measurements.area_m2 or ref.semantic.measurements.length_m or 0.0
        ),
        reverse=True,
    )
    return captured[:limit], examined
