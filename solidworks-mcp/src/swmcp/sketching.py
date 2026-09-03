"""Shared sketch helpers: segment identity, creation, and solver state.

Segment identity is the piece everything else depends on: relations, dimensions, and
deletes all address segments by handle rather than by relying on selection order.

``ISketchSegment.GetID`` returns a two-integer pair that is stable for the life of the
sketch, but it is only unique *within* a segment type - a line and an arc in the same
sketch both answer ``0:1``. The handle therefore carries the type as well, and
:func:`segments_by_id` refuses a sketch whose handles still collide rather than
quietly dropping a segment from the map.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from swmcp.com import swconst
from swmcp.com.marshal import normalize_sequence, null_dispatch, try_com_member
from swmcp.errors import SwMcpError, make_error
from swmcp.units import COORDINATE_TOLERANCE_M, from_meters, to_meters

#: swConstrainedStatus_e -> a readable state.
_STATUS_NAMES = {
    "swUnknownConstraint": "unknown",
    "swUnderConstrained": "under_defined",
    "swFullyConstrained": "fully_defined",
    "swOverConstrained": "over_defined",
    "swNoSolution": "no_solution",
    "swInvalidSolution": "invalid_solution",
    "swAutosolveOff": "autosolve_off",
}

#: Our relation names -> the SOLIDWORKS ``SketchAddConstraints`` tokens.
RELATION_TOKENS = {
    "horizontal": "sgHORIZONTAL",
    "vertical": "sgVERTICAL",
    "coincident": "sgCOINCIDENT",
    "collinear": "sgCOLINEAR",
    "parallel": "sgPARALLEL",
    "perpendicular": "sgPERPENDICULAR",
    "tangent": "sgTANGENT",
    "equal": "sgSAME",
    "concentric": "sgCONCENTRIC",
    "midpoint": "sgATMIDDLE",
    "symmetric": "sgSYMMETRIC",
    "fix": "sgFIXED",
    "merge": "sgMERGEPOINTS",
}

#: How many entities each relation needs selected.
RELATION_ARITY = {
    "horizontal": (1, 2),
    "vertical": (1, 2),
    "coincident": (2, 2),
    "collinear": (2, 2),
    "parallel": (2, 2),
    "perpendicular": (2, 2),
    "tangent": (2, 2),
    "equal": (2, 2),
    "concentric": (2, 2),
    "midpoint": (2, 2),
    "symmetric": (3, 3),
    "fix": (1, 1),
    "merge": (2, 2),
}


def segment_kind(segment: Any) -> str:
    """The segment's type token, lowercased: ``line``, ``arc``, ``spline``, ``ellipse``."""
    raw = try_com_member(segment, "GetType", default=None)
    name = swconst.name_of("swSketchSegments_e", raw) if isinstance(raw, int) else None
    return (name or "unknown").replace("swSketch", "").lower()


def segment_id(segment: Any) -> str:
    """A handle that addresses exactly one segment in the sketch.

    ``ISketchSegment.GetID`` is a pair of ints, but SOLIDWORKS scopes that pair *per
    segment type*: a line and an arc in one sketch both answer ``0:1``. Keying anything
    on the bare pair silently collapses the two, which drops a segment from every count
    and points deletes at whichever one happened to be built last. The type qualifies
    the handle so it stays unique sketch-wide.
    """
    raw = normalize_sequence(try_com_member(segment, "GetID", default=None))
    kind = segment_kind(segment)
    if len(raw) >= 2:
        return f"{kind}:{int(raw[0])}:{int(raw[1])}"
    return f"{kind}:{raw[0]}" if raw else f"{kind}:unknown"


def active_sketch(doc: Any) -> Any | None:
    manager = try_com_member(doc, "SketchManager", default=None)
    if manager is None:
        return None
    return try_com_member(manager, "ActiveSketch", default=None)


def require_active_sketch(doc: Any) -> Any:
    sketch = active_sketch(doc)
    if sketch is None:
        raise SwMcpError(
            make_error(
                "NO_ACTIVE_SKETCH",
                "validation",
                "No sketch is open for editing.",
                remediation=[
                    "Start a sketch first, or name an existing one to edit.",
                ],
            )
        )
    return sketch


def find_sketch(doc: Any, name: str) -> Any | None:
    """Locate a sketch feature by name and return its ``ISketch``."""
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        if str(try_com_member(feature, "Name", default="")) == name:
            return try_com_member(feature, "GetSpecificFeature2", default=None)
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return None


def sketch_segments(sketch: Any) -> list[Any]:
    found = normalize_sequence(try_com_member(sketch, "GetSketchSegments", default=None))
    return [segment for segment in found if segment is not None]


def segments_by_id(sketch: Any) -> dict[str, Any]:
    """Address every segment by its handle.

    Callers delete and count through this map, so a duplicate key must not be absorbed:
    dropping a segment here is how a delete silently takes the wrong geometry. Refuse
    instead, and name the handles that clashed.
    """
    segments = sketch_segments(sketch)
    mapped = {segment_id(segment): segment for segment in segments}
    if len(mapped) != len(segments):
        counts = Counter(segment_id(segment) for segment in segments)
        raise SwMcpError(
            make_error(
                "SEGMENT_ID_COLLISION",
                "reference",
                "Two sketch segments share one handle, so the sketch cannot be addressed safely.",
                context={"colliding_ids": sorted(k for k, n in counts.items() if n > 1)},
                remediation=[
                    "This is a defect in the server's segment identity, not in the model.",
                    "Report the sketch that produced it; no geometry has been changed.",
                ],
            )
        )
    return mapped


def describe_segment(segment: Any) -> dict[str, Any]:
    """What a segment is, plus - for an arc - how far it actually turns.

    The sweep is reported because it is the only field that distinguishes a
    centre-point arc from its complement: both share a centre, a radius and both
    endpoints, so a caller who named the wrong ``direction`` gets back a description
    identical to the one they intended. ``length_m`` always implied the answer;
    stating it in degrees means nobody has to divide by the radius to notice.
    """
    described: dict[str, Any] = {
        "sketch_local_id": segment_id(segment),
        "type": segment_kind(segment),
        "construction": bool(try_com_member(segment, "ConstructionGeometry", default=False)),
        "length_m": try_com_member(segment, "GetLength", default=None),
    }
    frame = arc_frame(segment)
    if frame is not None:
        sweep = arc_sweep(segment, frame)
        described["radius_mm"] = round(from_meters(frame[1], "mm"), 6)
        if sweep is not None:
            described["sweep_deg"] = round(math.degrees(sweep), 4)
    return described


def _relations(sketch: Any, filter_name: str) -> list[dict[str, Any]]:
    manager = try_com_member(sketch, "RelationManager", default=None)
    if manager is None:
        return []
    code = swconst.value("swSketchRelationFilterType_e", filter_name)
    found = normalize_sequence(try_com_member(manager, "GetRelations", code, default=None))
    described = []
    for relation in found:
        if relation is None:
            continue
        described.append(
            {
                "name": str(try_com_member(relation, "GetName", default="") or ""),
                "entity_count": try_com_member(relation, "GetEntitiesCount", default=None),
            }
        )
    return described


def sketch_state(sketch: Any) -> dict[str, Any]:
    """CON-005 evidence: the solver's verdict plus what is wrong with it."""
    raw = try_com_member(sketch, "GetConstrainedStatus", default=None)
    name = swconst.name_of("swConstrainedStatus_e", raw) if isinstance(raw, int) else None
    status = _STATUS_NAMES.get(name or "", "unknown")

    return {
        "status": status,
        "status_code": int(raw) if isinstance(raw, int) else -1,
        "fully_defined": status == "fully_defined",
        "over_defined": status == "over_defined",
        "relation_count": len(_relations(sketch, "swAll")),
        "dangling_relations": _relations(sketch, "swDangling"),
        "over_defining_relations": _relations(sketch, "swOverDefining"),
    }


def under_defined_count(sketch: Any) -> int:
    """How many segments are not yet fully defined."""
    count = 0
    for segment in sketch_segments(sketch):
        raw = try_com_member(segment, "GetConstrainedStatus", default=None)
        name = swconst.name_of("swConstrainedStatus_e", raw) if isinstance(raw, int) else None
        if _STATUS_NAMES.get(name or "") != "fully_defined":
            count += 1
    return count


def select_segments(doc: Any, segments: list[Any], *, mark: int = 0) -> int:
    """Select a list of segments, returning how many selections actually took.

    ``Select2`` carries a selection mark, which several feature APIs use to tell one
    input from another; ``Select4`` does not, so it is only the fallback.
    """
    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = 0
    for segment in segments:
        if try_com_member(segment, "Select2", True, mark, default=False):
            selected += 1
            continue
        if try_com_member(segment, "Select4", True, null_dispatch(), default=False):
            selected += 1
    return selected


# --- coordinate fidelity and contour topology ---------------------------------


Point = tuple[float, float]


def distance(first: Point, second: Point) -> float:
    """Plane distance between two 2-D points, in whatever unit they arrived in."""
    return math.hypot(first[0] - second[0], first[1] - second[1])


def point_of(sketch_point: Any) -> Point | None:
    """Read an ``ISketchPoint`` as a 2-D tuple in metres."""
    if sketch_point is None:
        return None
    x = try_com_member(sketch_point, "X", default=None)
    y = try_com_member(sketch_point, "Y", default=None)
    if x is None or y is None:
        return None
    return (float(x), float(y))


def _spline_endpoints(segment: Any) -> tuple[Point, Point] | None:
    """A spline's first and last interpolation points, in metres.

    ``GetStartPoint2`` and ``GetEndPoint2`` live on ``ISketchLine`` and ``ISketchArc``,
    not on ``ISketchSegment``: asking a spline for either raises ``AttributeError``.
    ``ISketchSpline::GetPoints`` answers instead, as a flat array of three doubles per
    through-point in sketch space, so the ends are the first and last triples.

    Measured on 2026 (34.3.0): a seven-point spline returns 21 doubles whose first and
    last triples are exactly the coordinates it was drawn with. ``GetPoints2`` returns
    point *objects* rather than doubles, which is why this reads ``GetPoints``.
    """
    values = normalize_sequence(try_com_member(segment, "GetPoints", default=None))
    if len(values) < 6 or len(values) % 3:
        return None
    try:
        numbers = [float(value) for value in values]
    except (TypeError, ValueError):
        return None
    return (numbers[0], numbers[1]), (numbers[-3], numbers[-2])


def read_endpoints(segment: Any) -> tuple[list[Point], bool]:
    """The segment's two ends in metres, and whether they could be read at all.

    The flag is the load-bearing half. "Has no ends" and "would not say" are different
    facts that used to arrive as the same empty list, and contour analysis reads an
    empty list as *closed* - so every spline counted as a closed ring, and the open
    chain of lines left behind was reported as a profile that does not close. A
    knight's head of three splines and three lines reported three closed contours and
    two broken ones, and neither number was real.
    """
    start = point_of(try_com_member(segment, "GetStartPoint2", default=None))
    end = point_of(try_com_member(segment, "GetEndPoint2", default=None))
    if start is None or end is None:
        ends = _spline_endpoints(segment)
        if ends is None:
            return [], False
        start, end = ends
    if distance(start, end) <= COORDINATE_TOLERANCE_M:
        return [], True  # a circle, or a spline closed back onto its own start
    return [start, end], True


def segment_endpoints(segment: Any) -> list[Point]:
    """The segment's two ends in metres, or ``[]`` when it has none."""
    return read_endpoints(segment)[0]


#: How finely a curve is flattened before it is tested for crossings. Ten degrees
#: puts 36 chords on a full circle, whose worst deviation from the true arc is
#: r*(1-cos(5deg)) = 0.4% of the radius - well under a millimetre on any gear tooth,
#: and cheap enough to run on every segment of a 240-segment profile.
_ARC_STEP_RAD = math.pi / 18.0
_MIN_ARC_SAMPLES = 4


def arc_frame(segment: Any) -> tuple[Point, float] | None:
    """An arc's centre and radius in metres, or ``None`` if it is not an arc.

    ``GetCenterPoint2`` and ``GetRadius`` live on ``ISketchArc``, not on
    ``ISketchSegment`` - the same split that ``GetStartPoint2`` has, and the reason
    this asks ``GetType`` **first** rather than trying the call and catching the
    failure. Probing a line or a spline with an arc's methods is a call into an
    interface the object does not implement, and this module has already been bitten
    once by assuming a missing member fails cleanly. A circle is an ``ISketchArc``
    too, so it passes this gate and is handled as the closed case below.
    """
    if segment_kind(segment) != "arc":
        return None
    centre = point_of(try_com_member(segment, "GetCenterPoint2", default=None))
    radius = try_com_member(segment, "GetRadius", default=None)
    if centre is None or radius is None:
        return None
    try:
        radius = float(radius)
    except (TypeError, ValueError):
        return None
    return (centre, radius) if radius > 0 else None


def arc_sweep(segment: Any, frame: tuple[Point, float] | None = None) -> float | None:
    """How far an arc actually turns, in radians.

    Derived from arc length over radius rather than from the two endpoints, because
    **the endpoints cannot tell you**: a 272 degree arc and the 88 degree one it
    complements share both of them. That ambiguity is not academic - ``arc_center``
    honours the ``direction`` it is given, so naming the wrong one builds the
    complement, and every endpoint-based check in this module reports the result as
    healthy. Length is the one reading that distinguishes them.
    """
    frame = frame or arc_frame(segment)
    if frame is None:
        return None
    length = try_com_member(segment, "GetLength", default=None)
    if length is None:
        return None
    try:
        return abs(float(length)) / frame[1]
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def sample_arc(
    centre: Point, radius: float, start: Point, end: Point | None, sweep: float
) -> list[Point]:
    """Flatten an arc to a polyline of ``sweep`` radians, starting at ``start``.

    The turn direction is recovered by asking which way round reaches ``end`` in the
    sweep the arc actually reports - so a major arc flattens as the major arc, which
    is the whole point of doing this rather than trusting the chord.
    """
    a0 = math.atan2(start[1] - centre[1], start[0] - centre[0])
    if end is None:  # a circle: no endpoints to disambiguate, and none needed
        signed = sweep
    else:
        a1 = math.atan2(end[1] - centre[1], end[0] - centre[0])
        ccw = (a1 - a0) % (2.0 * math.pi)
        # Whichever direction lands nearer the measured sweep is the one it turned.
        signed = sweep if abs(ccw - sweep) <= abs((2.0 * math.pi - ccw) - sweep) else -sweep
    steps = max(_MIN_ARC_SAMPLES, math.ceil(abs(sweep) / _ARC_STEP_RAD))
    return [
        (
            centre[0] + radius * math.cos(a0 + signed * i / steps),
            centre[1] + radius * math.sin(a0 + signed * i / steps),
        )
        for i in range(steps + 1)
    ]


def _spline_polyline(segment: Any) -> list[Point]:
    """A spline's interpolation points as a polyline, in metres.

    Type-gated for the same reason as :func:`arc_frame`: ``GetPoints`` is a spline
    member, and this is not the place to find out what a line does with it.
    """
    if segment_kind(segment) != "spline":
        return []
    values = normalize_sequence(try_com_member(segment, "GetPoints", default=None))
    if len(values) < 6 or len(values) % 3:
        return []
    try:
        numbers = [float(value) for value in values]
    except (TypeError, ValueError):
        return []
    return [(numbers[i], numbers[i + 1]) for i in range(0, len(numbers), 3)]


def segment_polyline(segment: Any, endpoints: list[Point]) -> list[Point]:
    """The segment flattened to points in metres, for geometric tests.

    Endpoints alone describe where a segment *starts and stops*, never where it goes -
    so they can say a profile closes while its edges cross straight through each
    other. This is what makes the difference visible. An unreadable segment returns
    ``[]`` and is left out of the crossing test rather than guessed at.
    """
    frame = arc_frame(segment)
    if frame is not None:
        centre, radius = frame
        sweep = arc_sweep(segment, frame)
        if sweep is None:
            sweep = 2.0 * math.pi if not endpoints else math.pi
        if not endpoints:  # closed: a full circle
            return sample_arc(centre, radius, (centre[0] + radius, centre[1]), None, sweep)
        return sample_arc(centre, radius, endpoints[0], endpoints[1], sweep)

    spline = _spline_polyline(segment)
    return spline or list(endpoints)


def _mm_point(point: Point) -> list[float]:
    return [round(from_meters(point[0], "mm"), 9), round(from_meters(point[1], "mm"), 9)]


def arc_direction(centre: Point, start: Point, end: Point, sweep: float | None) -> str:
    """Which way an arc turns, decided by the sweep it actually reports.

    The endpoints alone cannot answer this - that is the whole lesson of the 272
    degree fillet - so the measured sweep picks between the two candidates, and the
    minor arc is assumed only when there is no sweep to go on.
    """
    a0 = math.atan2(start[1] - centre[1], start[0] - centre[0])
    a1 = math.atan2(end[1] - centre[1], end[0] - centre[0])
    ccw = (a1 - a0) % (2.0 * math.pi)
    if sweep is None:
        return "counterclockwise" if ccw <= math.pi else "clockwise"
    nearer_ccw = abs(ccw - sweep) <= abs((2.0 * math.pi - ccw) - sweep)
    return "counterclockwise" if nearer_ccw else "clockwise"


def _arc_entity(
    segment: Any, ends: list[Point], *, construction: bool
) -> dict[str, Any] | None:
    """A circle or a centre-point arc, whichever this ``ISketchArc`` turns out to be.

    Split out from :func:`segment_to_entity` because the two shapes share a read but
    not a spec: a full circle has no endpoints to name, and an arc has no meaning
    without the direction its measured sweep implies.
    """
    frame = arc_frame(segment)
    if frame is None:
        return None
    centre, radius = frame
    if not ends:  # closed: a full circle rather than an arc
        return {
            "type": "circle",
            "center": _mm_point(centre),
            "radius": round(from_meters(radius, "mm"), 9),
            "construction": construction,
        }
    return {
        "type": "arc_center",
        "center": _mm_point(centre),
        "start": _mm_point(ends[0]),
        "end": _mm_point(ends[1]),
        "direction": arc_direction(centre, ends[0], ends[1], arc_sweep(segment, frame)),
        "construction": construction,
    }


def segment_to_entity(segment: Any) -> dict[str, Any] | None:
    """Rebuild the entity spec that would draw this segment again, in millimetres.

    The inverse of the sketch handlers' ``_create_entity``, and deliberately partial:
    ``None`` means "this segment cannot be restated as a primitive", which the caller
    reports rather than silently dropping. Ellipses, parabolas and sketch text have no
    lossless spec here and are refused by name.

    Only four shapes ever come out - line, arc, circle, spline - because that is all a
    *segment* can be. A rectangle, polygon or slot has already been decomposed into
    lines and arcs by the time SOLIDWORKS stores it, which is what makes the result
    closed under an arbitrary rotation: there is no axis-aligned spec left to break.
    """
    kind = segment_kind(segment)
    construction = bool(try_com_member(segment, "ConstructionGeometry", default=False))
    ends, read = read_endpoints(segment)

    if kind == "line":
        if not read or len(ends) != 2:
            return None
        return {
            "type": "line",
            "start": _mm_point(ends[0]),
            "end": _mm_point(ends[1]),
            "construction": construction,
        }

    if kind == "arc":
        return _arc_entity(segment, ends, construction=construction)

    if kind == "spline":
        points = _spline_polyline(segment)
        if len(points) < 2:
            return None
        return {
            "type": "spline",
            "points": [_mm_point(point) for point in points],
            "construction": construction,
        }

    return None


class SketchTransform:
    """A similarity transform applied to a derived sketch's geometry, in millimetres.

    Applied about ``about`` in a fixed order - mirror, scale, rotate, then translate -
    so a caller reading the arguments back knows what they asked for. Only similarity
    transforms are offered (no shear, no non-uniform scale) because anything else turns
    a circle into an ellipse and an arc into something with no ``arc_center`` spec at
    all, which would make the derived sketch unrepresentable rather than merely wrong.
    """

    __slots__ = ("about", "mirror", "rotate_deg", "scale", "translate")

    def __init__(
        self,
        *,
        scale: float = 1.0,
        rotate_deg: float = 0.0,
        mirror: str | None = None,
        translate: tuple[float, float] = (0.0, 0.0),
        about: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        self.scale = float(scale)
        self.rotate_deg = float(rotate_deg)
        self.mirror = mirror
        self.translate = (float(translate[0]), float(translate[1]))
        self.about = (float(about[0]), float(about[1]))

    @property
    def flips(self) -> bool:
        """Whether the mapping reverses handedness, which reverses every arc."""
        return self.mirror in ("x", "y")

    def point(self, point: tuple[float, float] | list[float]) -> list[float]:
        x = float(point[0]) - self.about[0]
        y = float(point[1]) - self.about[1]
        if self.mirror == "x":  # mirror across the x axis: y changes sign
            y = -y
        elif self.mirror == "y":
            x = -x
        x *= self.scale
        y *= self.scale
        if self.rotate_deg:
            angle = math.radians(self.rotate_deg)
            cos, sin = math.cos(angle), math.sin(angle)
            x, y = x * cos - y * sin, x * sin + y * cos
        return [
            round(x + self.about[0] + self.translate[0], 9),
            round(y + self.about[1] + self.translate[1], 9),
        ]

    def entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Transform one spec from :func:`segment_to_entity`."""
        out = dict(entity)
        for key in ("start", "end", "center"):
            if key in out:
                out[key] = self.point(out[key])
        if "points" in out:
            out["points"] = [self.point(point) for point in out["points"]]
        if "radius" in out:
            out["radius"] = round(float(out["radius"]) * abs(self.scale), 9)
        # A mirror swaps which way round an arc goes. Leaving the direction alone here
        # would rebuild the complement - the exact 272-degree fault this module exists
        # to catch, reintroduced by the transform itself.
        if self.flips and "direction" in out:
            out["direction"] = (
                "clockwise" if out["direction"] == "counterclockwise" else "counterclockwise"
            )
        return out


#: Model directions worth naming, so a frame reads as words rather than as a matrix.
_AXIS_NAMES = {
    (1, 0, 0): "+X", (-1, 0, 0): "-X",
    (0, 1, 0): "+Y", (0, -1, 0): "-Y",
    (0, 0, 1): "+Z", (0, 0, -1): "-Z",
}
#: How close a direction must be to an axis before it is named as that axis.
_AXIS_TOLERANCE = 1e-9


def _name_direction(vector: list[float]) -> str:
    for axis, name in _AXIS_NAMES.items():
        if all(abs(vector[i] - axis[i]) <= _AXIS_TOLERANCE for i in range(3)):
            return name
    return "[{}]".format(", ".join(format(v, ".6g") for v in vector))


def sketch_frame(sketch: Any) -> dict[str, Any] | None:
    """Where this sketch's own axes point in model space.

    ``ISketch::ModelToSketchTransform`` is named for the direction it does *not*
    conveniently give you, and its ``ArrayData`` is sixteen bare doubles with no
    documented layout, so this is measured rather than assumed. On 2026 (34.3.0):

        model = R . (sketch - t)

    with ``R`` the row-major 3x3 in slots 0-8, ``t`` the translation in 9-11, and the
    scale in 12. Verified on a case that could have falsified it - a plane offset 30mm
    from Top, where ``R`` is not identity and ``t`` is not zero at the same time. The
    four mapped corners of a known rectangle landed exactly on the extruded body's
    measured box.

    Why report it at all: a line drawn ``(0,0)->(0,-20)`` on Top runs along model
    **+Z**, and nothing in the sketch result used to say so. That had to be guessed and
    then confirmed after the fact from a swept body's bounding box, once per sketch
    plane, on work that was otherwise fully determined.
    """
    transform = try_com_member(sketch, "ModelToSketchTransform", default=None)
    raw = normalize_sequence(try_com_member(transform, "ArrayData", default=None))
    if len(raw) < 13:
        return None
    try:
        values = [float(value) for value in raw]
    except (TypeError, ValueError):
        return None

    rows = [values[0:3], values[3:6], values[6:9]]
    shift = values[9:12]

    def apply(point: tuple[float, float, float]) -> list[float]:
        moved = [point[i] - shift[i] for i in range(3)]
        return [sum(rows[r][c] * moved[c] for c in range(3)) for r in range(3)]

    origin = apply((0.0, 0.0, 0.0))
    # A direction is the image of a unit vector with the translation cancelled out,
    # which is exactly the corresponding column of R.
    axes = {
        "x_axis": [rows[r][0] for r in range(3)],
        "y_axis": [rows[r][1] for r in range(3)],
        "normal": [rows[r][2] for r in range(3)],
    }
    return {
        "origin_mm": [round(from_meters(value, "mm"), 9) for value in origin],
        **{name: [round(value, 12) for value in vector] for name, vector in axes.items()},
        "scale": round(values[12], 12),
        "maps": ", ".join(
            f"sketch {label} -> model {_name_direction(axes[key])}"
            for label, key in (("+X", "x_axis"), ("+Y", "y_axis"))
        )
        + f", normal -> model {_name_direction(axes['normal'])}",
    }


def segment_topology(sketch: Any) -> list[dict[str, Any]]:
    """Plain data for every segment: id, kind, construction flag, and endpoints.

    This is the only part of contour analysis that touches COM. Everything that
    decides whether a profile closes works on what this returns, so the topology can
    be tested without SOLIDWORKS attached.
    """
    topology = []
    for segment in sketch_segments(sketch):
        endpoints, read = read_endpoints(segment)
        sweep = arc_sweep(segment)
        topology.append(
            {
                "id": segment_id(segment),
                "kind": segment_kind(segment),
                "construction": bool(
                    try_com_member(segment, "ConstructionGeometry", default=False)
                ),
                "endpoints": endpoints,
                # Where the segment *goes*, not just where it ends, so crossings can be
                # found. Empty when the geometry would not read.
                "polyline": segment_polyline(segment, endpoints) if read else [],
                # Radians. Only arcs have one; it is the reading that separates a major
                # arc from the minor one sharing its endpoints.
                "sweep_rad": sweep,
                # False only when SOLIDWORKS would not say where the segment ends.
                # Absent is treated as True, so hand-built topology in tests reads the
                # way it always did.
                "endpoints_read": read,
            }
        )
    return topology


def anchor_deviation(requested: list[Point], actual: list[Point]) -> float | None:
    """How far the nearest real endpoint sits from each point that was asked for.

    Returns the worst such gap in metres, or ``None`` when there is nothing to
    compare. Nearest-match rather than positional match, because SOLIDWORKS is free
    to hand a segment's ends back in either order and a rectangle's four lines arrive
    in no promised sequence.
    """
    if not requested or not actual:
        return None
    return max(min(distance(want, got) for got in actual) for want in requested)


def cluster_points(
    points: list[Point], tolerance: float = COORDINATE_TOLERANCE_M
) -> tuple[list[Point], list[int]]:
    """Merge points within ``tolerance`` into shared vertices.

    Returns the vertex positions and, for each input point, the vertex it joined.
    Rounding to a grid would be faster but splits two points a hair apart into
    different buckets whenever they straddle a boundary, which is exactly the case
    this has to get right.
    """
    centres: list[Point] = []
    index: list[int] = []
    for point in points:
        for position, centre in enumerate(centres):
            if distance(point, centre) <= tolerance:
                index.append(position)
                break
        else:
            centres.append(point)
            index.append(len(centres) - 1)
    return centres, index


def _to_mm(point: Point) -> list[float]:
    return [round(from_meters(point[0], "mm"), 4), round(from_meters(point[1], "mm"), 4)]


def _bounds(points: list[Point]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _crossing(a1: Point, a2: Point, b1: Point, b2: Point) -> Point | None:
    """Where two straight spans properly cross, or ``None``.

    Parallel and merely-touching spans return ``None``: an endpoint shared with a
    neighbour is how a profile is *supposed* to be built, so counting it as a crossing
    would flag every closed contour ever drawn.
    """
    dxa, dya = a2[0] - a1[0], a2[1] - a1[1]
    dxb, dyb = b2[0] - b1[0], b2[1] - b1[1]
    denominator = dxa * dyb - dya * dxb
    if abs(denominator) < 1e-18:
        return None
    tx, ty = b1[0] - a1[0], b1[1] - a1[1]
    t = (tx * dyb - ty * dxb) / denominator
    u = (tx * dya - ty * dxa) / denominator
    # Strictly inside both spans. The margin keeps a shared vertex, which lands at
    # t or u of exactly 0 or 1, from reading as a crossing.
    if not (1e-9 < t < 1 - 1e-9) or not (1e-9 < u < 1 - 1e-9):
        return None
    return (a1[0] + t * dxa, a1[1] + t * dya)


def find_self_intersections(
    segments: list[dict[str, Any]],
    *,
    tolerance: float = COORDINATE_TOLERANCE_M,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Profile edges that cross each other, as ``{segments, at_mm}`` records.

    Closure and self-intersection are independent faults, and only the first of them
    was ever measured here. A profile can be a perfectly closed ring whose edges pass
    straight through one another - the commonest way being a centre-point arc built
    the long way round - and SOLIDWORKS then refuses the feature with a message that
    names neither the segments nor the reason. Every endpoint-based check passes,
    because the endpoints are genuinely fine.

    Junctions are excluded deliberately: a crossing within ``tolerance`` of a point
    both segments touch is two edges meeting, which is how profiles are drawn.
    """
    usable = [
        s
        for s in segments
        if not s.get("construction") and len(s.get("polyline") or []) >= 2
    ]
    boxes = [_bounds(s["polyline"]) for s in usable]

    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for i in range(len(usable)):
        for j in range(i + 1, len(usable)):
            # Broad phase. Almost every pair on a real profile is disjoint, and this
            # rejects those for the cost of four comparisons.
            if (
                boxes[i][2] < boxes[j][0] - tolerance
                or boxes[j][2] < boxes[i][0] - tolerance
                or boxes[i][3] < boxes[j][1] - tolerance
                or boxes[j][3] < boxes[i][1] - tolerance
            ):
                continue
            first, second = usable[i]["polyline"], usable[j]["polyline"]
            shared = [
                p
                for p in (first[0], first[-1])
                for q in (second[0], second[-1])
                if distance(p, q) <= tolerance
            ]
            for a in range(len(first) - 1):
                for b in range(len(second) - 1):
                    hit = _crossing(first[a], first[a + 1], second[b], second[b + 1])
                    if hit is None:
                        continue
                    if any(distance(hit, corner) <= tolerance * 4 for corner in shared):
                        continue
                    key = (
                        str(usable[i].get("id", "")),
                        str(usable[j].get("id", "")),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append({"segments": list(key), "at_mm": _to_mm(hit)})
                    break
                else:
                    continue
                break
            if len(found) >= limit:
                return found
    return found


def analyze_contours(
    segments: list[dict[str, Any]], *, tolerance: float = COORDINATE_TOLERANCE_M
) -> dict[str, Any]:
    """Group profile segments into contours and report which ones close.

    Takes what :func:`segment_topology` produces. Revolve and extrude both need a
    closed profile, and the solver state a sketch reports - under-defined,
    over-defined - says nothing about whether one exists. This answers the question
    those features actually ask.

    Construction geometry is excluded. A centerline is an axis, not part of the
    profile; counting it as an edge would report every revolve sketch ever drawn as
    having two loose ends.
    """
    profile = [s for s in segments if not s.get("construction")]
    # A segment whose ends could not be read says nothing about closure either way.
    # Counting it as a ring - which is what "no endpoints" used to mean - invents a
    # closed contour and orphans whatever it was joined to.
    unreadable = [s for s in profile if not s.get("endpoints_read", True)]
    known = [s for s in profile if s.get("endpoints_read", True)]
    rings = [s for s in known if not s.get("endpoints")]
    chained = [s for s in known if s.get("endpoints")]

    points: list[Point] = []
    for segment in chained:
        ends = segment["endpoints"]
        points.append((float(ends[0][0]), float(ends[0][1])))
        points.append((float(ends[1][0]), float(ends[1][1])))
    centres, index = cluster_points(points, tolerance)

    # Each segment owns two consecutive slots in `index`, in the order walked above.
    vertices = [(index[i * 2], index[i * 2 + 1]) for i in range(len(chained))]
    degree: Counter[int] = Counter()
    for first, second in vertices:
        degree[first] += 1
        degree[second] += 1

    parent = list(range(len(chained)))

    def root(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    by_vertex: dict[int, list[int]] = {}
    for position, (first, second) in enumerate(vertices):
        by_vertex.setdefault(first, []).append(position)
        by_vertex.setdefault(second, []).append(position)
    for members in by_vertex.values():
        for other in members[1:]:
            left, right = root(members[0]), root(other)
            if left != right:
                parent[left] = right

    groups: dict[int, list[int]] = {}
    for position in range(len(chained)):
        groups.setdefault(root(position), []).append(position)

    closed = len(rings)
    open_count = 0
    unjoined: list[str] = []
    for members in groups.values():
        touched = {vertex for position in members for vertex in vertices[position]}
        # A closed loop is exactly the case where every corner has two edges meeting.
        # Degree 1 leaves a gap; degree 3 or more branches, and neither revolves.
        if all(degree[vertex] == 2 for vertex in touched):
            closed += 1
        else:
            open_count += 1
            unjoined.extend(str(chained[position].get("id", "")) for position in members)

    crossings = find_self_intersections(profile, tolerance=tolerance)
    # A major arc is reported alongside the crossing rather than on its own: building
    # one is legitimate, so it is only worth mentioning when the profile is broken and
    # the arc is a plausible reason why.
    major_arcs = sorted(
        str(s.get("id", ""))
        for s in profile
        if (s.get("sweep_rad") or 0.0) > math.pi + 1e-9
    )

    return {
        "profile_segment_count": len(profile),
        "closed_contour_count": closed,
        "open_contour_count": open_count,
        "loose_ends_mm": [_to_mm(centres[v]) for v, n in sorted(degree.items()) if n == 1],
        "branch_points_mm": [_to_mm(centres[v]) for v, n in sorted(degree.items()) if n > 2],
        "open_segment_ids": sorted(set(unjoined)),
        # Empty in the ordinary case. When it is not, every other count here covers
        # only the segments that did answer, so closure is undecided rather than false.
        "unreadable_segment_ids": sorted(str(s.get("id", "")) for s in unreadable),
        # Independent of closure: a ring can be closed and still cross itself, and a
        # feature refuses that just as firmly.
        "self_intersections": crossings,
        "self_intersecting_segment_ids": sorted(
            {identifier for hit in crossings for identifier in hit["segments"]}
        ),
        "major_arc_segment_ids": major_arcs,
    }


def contour_warnings(contours: dict[str, Any]) -> list[str]:
    """What is worth saying out loud about a profile's closure, if anything.

    Shared so that creating a sketch and diagnosing one cannot drift into describing
    the same topology differently.
    """
    if not contours:
        return []
    warnings: list[str] = []
    unreadable = contours.get("unreadable_segment_ids") or []
    if contours.get("open_contour_count"):
        where = contours["loose_ends_mm"] or contours["branch_points_mm"]
        hedge = (
            " This ignores the segment(s) below that would not report their ends, so "
            "the gap may be theirs."
            if unreadable
            else ""
        )
        warnings.append(
            f"{contours['open_contour_count']} contour(s) do not close. An extrude will "
            f"refuse this profile; a revolve will too unless the gap lies on its axis, "
            f"which it closes by itself. Loose points (mm): {where}.{hedge}"
        )
    crossings = contours.get("self_intersections") or []
    if crossings:
        pairs = ", ".join(
            f"{hit['segments'][0]} x {hit['segments'][1]} at {hit['at_mm']}"
            for hit in crossings[:4]
        )
        more = "" if len(crossings) <= 4 else f" (+{len(crossings) - 4} more)"
        message = (
            f"{len(crossings)} profile self-intersection(s): {pairs}{more}. An extrude "
            f"or revolve will refuse this even though the contour closes."
        )
        implicated = set(contours.get("self_intersecting_segment_ids") or [])
        major = [a for a in (contours.get("major_arc_segment_ids") or []) if a in implicated]
        if major:
            message += (
                f" {len(major)} of the crossing segment(s) turn more than 180 degrees "
                f"({', '.join(major[:4])}); a centre-point arc built with the wrong "
                f"`direction` sweeps the long way round and looks exactly like this."
            )
        warnings.append(message)

    if unreadable:
        warnings.append(
            f"{len(unreadable)} segment(s) would not report their endpoints, so whether "
            f"they close was not determined either way: {unreadable}. The counts above "
            f"cover the rest."
        )
    return warnings


def coincident_axis_segments(
    segments: list[dict[str, Any]], *, tolerance: float = COORDINATE_TOLERANCE_M
) -> list[dict[str, str]]:
    """Centerlines drawn exactly on top of a profile edge.

    This reports a geometric fact, not a diagnosis, and the distinction is load-bearing.

    It was added believing the overlap *caused* a refusal: a revolve failed on exactly
    this arrangement, and redrawing it with the centerline extended past the profile
    succeeded. But the deliberate reproduction in
    ``tests/live/test_live_sketch_fidelity.py`` revolves the overlapping profile
    without complaint on 2026 (34.3.0), so the overlap alone is not sufficient. The
    original failure had a second difference nobody controlled for - it was drawn with
    sketch inference on, which moves endpoints - so an inference-induced gap is now the
    likelier explanation, and :func:`analyze_contours` is what would catch that.

    Kept because it is cheap and occasionally the thing a reader needs to see, and
    because deleting it would lose the record of what was ruled out. Callers should
    weight it accordingly: it is the last line of a diagnosis, never the headline.
    """
    centerlines = [s for s in segments if s.get("construction") and s.get("endpoints")]
    profile = [s for s in segments if not s.get("construction") and s.get("endpoints")]

    found: list[dict[str, str]] = []
    for axis in centerlines:
        axis_start, axis_end = axis["endpoints"][0], axis["endpoints"][1]
        for edge in profile:
            edge_start, edge_end = edge["endpoints"][0], edge["endpoints"][1]
            forward = (
                distance(axis_start, edge_start) <= tolerance
                and distance(axis_end, edge_end) <= tolerance
            )
            reversed_ = (
                distance(axis_start, edge_end) <= tolerance
                and distance(axis_end, edge_start) <= tolerance
            )
            if forward or reversed_:
                found.append(
                    {
                        "centerline": str(axis.get("id", "")),
                        "segment": str(edge.get("id", "")),
                    }
                )
    return found


def straddling_axes(
    segments: list[dict[str, Any]], *, tolerance: float = COORDINATE_TOLERANCE_M
) -> list[str]:
    """Centerlines that the profile crosses rather than merely touches.

    A revolve sweeps the profile around the axis, so material on both sides would pass
    through itself. SOLIDWORKS refuses it, and "the profile must not cross the axis" is
    the standard advice - but the advice is only useful if someone has checked whether
    it applies, which is what this does.

    Touching the axis is fine and common: a profile closed along the centerline sits
    exactly on it. Only points a clear ``tolerance`` either side count as crossing.
    """
    centerlines = [s for s in segments if s.get("construction") and s.get("endpoints")]
    profile_points: list[Point] = []
    for segment in segments:
        if segment.get("construction"):
            continue
        for end in segment.get("endpoints") or ():
            profile_points.append((float(end[0]), float(end[1])))

    crossed: list[str] = []
    for axis in centerlines:
        start, end = axis["endpoints"][0], axis["endpoints"][1]
        dx, dy = end[0] - start[0], end[1] - start[1]
        span = math.hypot(dx, dy)
        if span <= tolerance:
            continue
        sides = [
            (dx * (point[1] - start[1]) - dy * (point[0] - start[0])) / span
            for point in profile_points
        ]
        if any(side > tolerance for side in sides) and any(
            side < -tolerance for side in sides
        ):
            crossed.append(str(axis.get("id", "")))
    return crossed


def unsupported_loose_ends(
    loose_ends_mm: list[list[float]],
    segments: list[dict[str, Any]],
    *,
    tolerance: float = COORDINATE_TOLERANCE_M,
) -> list[list[float]]:
    """Loose ends a revolve axis cannot close for you, in millimetres.

    An open contour is not automatically a broken one. A revolve profile may be left
    open *along its axis*: SOLIDWORKS closes it against the centerline itself, and
    that is the ordinary way to draw one.

    Measured on 2026 (34.3.0): a rectangle-ish profile with a deliberate 2mm gap
    between two points that both lay on the centerline revolved without complaint.
    The test that expected a refusal is the reason this function exists - "a revolve
    needs a closed profile" was written here first and was wrong.

    So a gap only matters when it is somewhere the axis does not reach, and that is
    what comes back.
    """
    axes = [s for s in segments if s.get("construction") and s.get("endpoints")]
    if not axes:
        return list(loose_ends_mm)

    unsupported: list[list[float]] = []
    for end_mm in loose_ends_mm:
        point = (to_meters(end_mm[0]), to_meters(end_mm[1]))
        on_an_axis = False
        for axis in axes:
            start, finish = axis["endpoints"][0], axis["endpoints"][1]
            dx, dy = finish[0] - start[0], finish[1] - start[1]
            span = math.hypot(dx, dy)
            if span <= tolerance:
                continue
            # Distance to the axis as an infinite line: a centerline drawn short of
            # the gap still defines the axis the revolve will close against.
            offset = abs(dx * (point[1] - start[1]) - dy * (point[0] - start[0])) / span
            if offset <= tolerance:
                on_an_axis = True
                break
        if not on_an_axis:
            unsupported.append(end_mm)
    return unsupported
