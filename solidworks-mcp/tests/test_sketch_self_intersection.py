"""Profile crossings and arc sweep — the geometry, without SOLIDWORKS.

Closure and self-intersection are independent faults, and only closure was ever
measured. The case that forced this file: a gear tooth-space profile built with a
centre-point fillet arc whose ``direction`` named the long way round. The contour
closed to 0.0 mm, every endpoint sat exactly where it was asked for, and the extrude
that consumed it failed with a message naming neither the segment nor the reason.

Endpoints cannot detect it, because a 272 degree arc and the 88 degree one it
complements *share both endpoints*. Arc length over radius is the reading that can.
"""

from __future__ import annotations

import math

from swmcp.sketching import (
    analyze_contours,
    contour_warnings,
    find_self_intersections,
    sample_arc,
)

MM = 0.001


def seg(name: str, polyline, *, construction: bool = False, sweep=None) -> dict:
    """One segment in the shape :func:`segment_topology` hands back, in metres."""
    points = [(float(x), float(y)) for x, y in polyline]
    ends = [] if len(points) > 2 and points[0] == points[-1] else [points[0], points[-1]]
    return {
        "id": name,
        "kind": "arc" if sweep is not None else "line",
        "construction": construction,
        "endpoints": ends,
        "endpoints_read": True,
        "polyline": points,
        "sweep_rad": sweep,
    }


def square(size: float = 10 * MM) -> list[dict]:
    corners = [(0.0, 0.0), (size, 0.0), (size, size), (0.0, size)]
    return [
        seg(f"line:0:{i}", [corners[i], corners[(i + 1) % 4]])
        for i in range(4)
    ]


# --- the sampler ---------------------------------------------------------------


def test_sample_arc_follows_the_minor_turn():
    pts = sample_arc((0.0, 0.0), 1.0, (1.0, 0.0), (0.0, 1.0), math.pi / 2)
    assert all(abs(math.hypot(x, y) - 1.0) < 1e-9 for x, y in pts)
    # A quarter turn stays in the first quadrant.
    assert all(x >= -1e-9 and y >= -1e-9 for x, y in pts)


def test_sample_arc_follows_the_major_turn_between_the_same_endpoints():
    """The endpoints are identical; only the sweep separates the two arcs."""
    minor = sample_arc((0.0, 0.0), 1.0, (1.0, 0.0), (0.0, 1.0), math.pi / 2)
    major = sample_arc((0.0, 0.0), 1.0, (1.0, 0.0), (0.0, 1.0), 3 * math.pi / 2)

    assert minor[0] == major[0]
    assert math.dist(minor[-1], major[-1]) < 1e-9
    # The long way round is the one that visits the third quadrant.
    assert not any(x < -0.5 and y < -0.5 for x, y in minor)
    assert any(x < -0.5 and y < -0.5 for x, y in major)


def test_sample_arc_closes_a_full_circle():
    pts = sample_arc((0.0, 0.0), 2.0, (2.0, 0.0), None, 2 * math.pi)
    assert math.dist(pts[0], pts[-1]) < 1e-9
    assert all(abs(math.hypot(x, y) - 2.0) < 1e-9 for x, y in pts)


# --- crossings -----------------------------------------------------------------


def test_clean_square_has_no_crossings():
    assert find_self_intersections(square()) == []


def test_shared_corners_are_junctions_not_crossings():
    """Every closed profile touches at its corners; none of that is a fault."""
    contours = analyze_contours(square())
    assert contours["closed_contour_count"] == 1
    assert contours["self_intersections"] == []
    assert contour_warnings(contours) == []


def test_bowtie_is_caught():
    """Two spans that pass through each other, away from any shared endpoint."""
    crossed = [
        seg("line:0:1", [(0.0, 0.0), (10 * MM, 10 * MM)]),
        seg("line:0:2", [(0.0, 10 * MM), (10 * MM, 0.0)]),
    ]
    hits = find_self_intersections(crossed)
    assert len(hits) == 1
    assert sorted(hits[0]["segments"]) == ["line:0:1", "line:0:2"]
    assert hits[0]["at_mm"] == [5.0, 5.0]


def test_construction_geometry_is_ignored():
    """A centerline is an axis, not an edge, and crosses profiles by design."""
    with_axis = [
        *square(),
        seg("line:0:9", [(-5 * MM, 5 * MM), (15 * MM, 5 * MM)], construction=True),
    ]
    assert find_self_intersections(with_axis) == []


def test_a_closed_contour_can_still_self_intersect():
    """The fault this whole module exists for: closed *and* invalid.

    Endpoints form one clean ring; the edges cross anyway.
    """
    contours = analyze_contours(
        [
            seg("line:0:1", [(0.0, 0.0), (10 * MM, 0.0)]),
            seg("line:0:2", [(10 * MM, 0.0), (0.0, 10 * MM)]),
            seg("line:0:3", [(0.0, 10 * MM), (10 * MM, 10 * MM)]),
            seg("line:0:4", [(10 * MM, 10 * MM), (0.0, 0.0)]),
        ]
    )
    assert contours["closed_contour_count"] == 1
    assert contours["open_contour_count"] == 0
    assert contours["self_intersections"], "closure passed, so only geometry can catch this"

    warning = " ".join(contour_warnings(contours))
    assert "self-intersection" in warning


# --- the gear tooth space that actually failed ---------------------------------

#: Five consecutive segments of the m=2 z=20 spur tooth space, in millimetres,
#: verbatim from the profile that would not cut: a radial flank, the root fillet,
#: the root land, the mirrored fillet, and the opposite flank. Closed back on itself
#: so the contour reads exactly as SOLIDWORKS reported it - one closed ring.
_ROOT_REGION = [
    ("line", (18.71186, 1.75362), (18.16458, 1.70233), None),
    ("arc", (18.16458, 1.70233), (17.34059, 2.35667), (18.09367, 2.45902)),
    ("arc", (17.34059, 2.35667), (17.22013, 3.11721), (0.0, 0.0)),
    ("arc", (17.22013, 3.11721), (17.80159, 3.99415), (17.96798, 3.25259)),
    ("line", (17.80159, 3.99415), (18.33794, 4.11449), None),
    ("line", (18.33794, 4.11449), (18.71186, 1.75362), None),
]


def _root_region(*, long_way_round: bool) -> list[dict]:
    """The profile above, with the two root fillets swept either way.

    ``long_way_round`` reproduces the bug: the fillets were emitted with a
    ``direction`` naming the major arc, so each 0.76 mm fillet swept 272 degrees
    instead of 88. Their endpoints are unchanged, which is why nothing else noticed.
    """
    built: list[dict] = []
    for index, (kind, a, b, centre) in enumerate(_ROOT_REGION):
        start = (a[0] * MM, a[1] * MM)
        finish = (b[0] * MM, b[1] * MM)
        if kind == "line":
            built.append(seg(f"line:0:{index}", [start, finish]))
            continue
        origin = (centre[0] * MM, centre[1] * MM)
        radius = math.dist(origin, start)
        a0 = math.atan2(start[1] - origin[1], start[0] - origin[0])
        a1 = math.atan2(finish[1] - origin[1], finish[0] - origin[0])
        sweep = (a1 - a0) % (2 * math.pi)
        sweep = min(sweep, 2 * math.pi - sweep)  # as drawn: the minor arc
        is_fillet = radius < 1.0 * MM
        if long_way_round and is_fillet:
            sweep = 2 * math.pi - sweep
        polyline = sample_arc(origin, radius, start, finish, sweep)
        entry = seg(f"arc:0:{index}", polyline, sweep=sweep)
        entry["endpoints"] = [start, finish]
        built.append(entry)
    return built


def test_the_real_tooth_space_is_clean_as_drawn():
    """The false-positive guard, on geometry known to cut successfully."""
    contours = analyze_contours(_root_region(long_way_round=False))
    assert contours["self_intersections"] == []
    assert contours["major_arc_segment_ids"] == []
    assert not contour_warnings(contours)


def test_the_major_fillets_are_caught_on_the_real_profile():
    """Closed, every endpoint exact, and geometrically impossible.

    This is the report the server gave for the profile that failed to extrude:
    one closed contour, zero deviation, no complaint. The crossing is the only
    thing that distinguishes it.
    """
    contours = analyze_contours(_root_region(long_way_round=True))

    assert contours["closed_contour_count"] == 1
    assert contours["open_contour_count"] == 0
    assert contours["self_intersections"], "closure passed, so only geometry can catch this"
    assert set(contours["major_arc_segment_ids"]) == {"arc:0:1", "arc:0:3"}
    # Both fillets loop back over each other and over the closing edge. Asserting
    # containment rather than equality: every extra segment named here is a real
    # crossing with the same two arcs, and pinning the exact set would only make the
    # test brittle to how much of the profile the fixture carries.
    assert {"arc:0:1", "arc:0:3"} <= set(contours["self_intersecting_segment_ids"])


def test_major_arc_hint_names_the_direction_field():
    """The diagnosis has to be actionable, not just 'something is wrong'."""
    warning = " ".join(contour_warnings(analyze_contours(_root_region(long_way_round=True))))
    assert "self-intersection" in warning
    assert "180 degrees" in warning
    assert "direction" in warning


def test_major_arc_alone_is_not_reported_as_a_fault():
    """Building a major arc is legitimate; only a crossing makes it worth naming."""
    lone = [
        seg(
            "arc:0:9",
            sample_arc((0.0, 0.0), 5 * MM, (5 * MM, 0.0), (0.0, 5 * MM), 3 * math.pi / 2),
            sweep=3 * math.pi / 2,
        )
    ]
    contours = analyze_contours(lone)
    assert contours["major_arc_segment_ids"] == ["arc:0:9"]
    assert contours["self_intersections"] == []
    assert not any("180 degrees" in w for w in contour_warnings(contours))


def test_unreadable_segments_are_skipped_not_guessed():
    """A segment that would not report its geometry cannot be tested for crossings."""
    silent = [
        *square(),
        {
            "id": "spline:0:1",
            "kind": "spline",
            "construction": False,
            "endpoints": [],
            "endpoints_read": False,
            "polyline": [],
            "sweep_rad": None,
        },
    ]
    assert find_self_intersections(silent) == []


def test_crossing_search_is_bounded():
    """A pathological profile must not return an unbounded report."""
    fan = [
        seg(f"line:0:{i}", [(-10 * MM, i * MM), (10 * MM, (20 - i) * MM)])
        for i in range(20)
    ]
    assert len(find_self_intersections(fan)) <= 12
