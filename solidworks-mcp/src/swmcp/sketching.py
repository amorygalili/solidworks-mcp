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
    return {
        "sketch_local_id": segment_id(segment),
        "type": segment_kind(segment),
        "construction": bool(try_com_member(segment, "ConstructionGeometry", default=False)),
        "length_m": try_com_member(segment, "GetLength", default=None),
    }


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


def segment_endpoints(segment: Any) -> list[Point]:
    """The segment's two ends in metres, or ``[]`` when it has none.

    A circle and a full ellipse have no ends: SOLIDWORKS either refuses the call or
    answers the same point twice. Both come back as an empty list, so a caller can
    read "no endpoints" as the closed case rather than as a failure to read them.
    """
    start = point_of(try_com_member(segment, "GetStartPoint2", default=None))
    end = point_of(try_com_member(segment, "GetEndPoint2", default=None))
    if start is None or end is None:
        return []
    if distance(start, end) <= COORDINATE_TOLERANCE_M:
        return []
    return [start, end]


def segment_topology(sketch: Any) -> list[dict[str, Any]]:
    """Plain data for every segment: id, kind, construction flag, and endpoints.

    This is the only part of contour analysis that touches COM. Everything that
    decides whether a profile closes works on what this returns, so the topology can
    be tested without SOLIDWORKS attached.
    """
    return [
        {
            "id": segment_id(segment),
            "kind": segment_kind(segment),
            "construction": bool(
                try_com_member(segment, "ConstructionGeometry", default=False)
            ),
            "endpoints": segment_endpoints(segment),
        }
        for segment in sketch_segments(sketch)
    ]


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
    rings = [s for s in profile if not s.get("endpoints")]
    chained = [s for s in profile if s.get("endpoints")]

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

    return {
        "profile_segment_count": len(profile),
        "closed_contour_count": closed,
        "open_contour_count": open_count,
        "loose_ends_mm": [_to_mm(centres[v]) for v, n in sorted(degree.items()) if n == 1],
        "branch_points_mm": [_to_mm(centres[v]) for v, n in sorted(degree.items()) if n > 2],
        "open_segment_ids": sorted(set(unjoined)),
    }


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
