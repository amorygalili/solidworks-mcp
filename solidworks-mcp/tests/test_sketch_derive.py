"""Restating a segment as a spec, and moving that spec to another plane.

The bevel gear is why this exists. Its loft needs an outer section and that same
section scaled by 0.717 on a plane 8mm behind it - geometrically one input, but with
no way to derive one sketch from another it had to be generated and transmitted twice,
160 entities each, at 101s and 114s.

Two halves, both testable without SOLIDWORKS attached. :func:`segment_to_entity` is
the inverse of the create handlers' ``_create_entity``, and reads through the same
type-gated helpers the rest of the module uses. :class:`SketchTransform` is pure
arithmetic on the spec that comes out.
"""

from __future__ import annotations

import math

import pytest

from swmcp.sketching import (
    SketchTransform,
    arc_direction,
    segment_to_entity,
)

MM = 0.001

#: swSketchSegments_e, as SOLIDWORKS reports it from GetType.
LINE, ARC, ELLIPSE, SPLINE, TEXT, PARABOLA = 0, 1, 2, 3, 4, 5


class FakePoint:
    def __init__(self, x: float, y: float) -> None:
        self.X, self.Y, self.Z = x, y, 0.0


class FakeSegment:
    """Only the members the real read path asks for, in metres.

    Deliberately raises AttributeError for anything else, because that is the failure
    the type gating in ``arc_frame`` and ``_spline_polyline`` exists to avoid: asking
    a spline for ``GetCenterPoint2`` is a call into an interface it does not implement.
    """

    def __init__(self, kind: int, *, construction: bool = False, **members) -> None:
        self.GetType = kind
        self.ConstructionGeometry = construction
        for name, value in members.items():
            setattr(self, name, value)


def line(start, end, *, construction: bool = False) -> FakeSegment:
    return FakeSegment(
        LINE,
        construction=construction,
        GetStartPoint2=FakePoint(start[0] * MM, start[1] * MM),
        GetEndPoint2=FakePoint(end[0] * MM, end[1] * MM),
    )


def arc(centre, start, end, radius, length, *, construction: bool = False) -> FakeSegment:
    return FakeSegment(
        ARC,
        construction=construction,
        GetCenterPoint2=FakePoint(centre[0] * MM, centre[1] * MM),
        GetRadius=radius * MM,
        GetLength=length * MM,
        GetStartPoint2=FakePoint(start[0] * MM, start[1] * MM),
        GetEndPoint2=FakePoint(end[0] * MM, end[1] * MM),
    )


def circle(centre, radius) -> FakeSegment:
    """A circle is an ISketchArc whose two endpoints coincide."""
    point = FakePoint(centre[0] * MM + radius * MM, centre[1] * MM)
    return FakeSegment(
        ARC,
        GetCenterPoint2=FakePoint(centre[0] * MM, centre[1] * MM),
        GetRadius=radius * MM,
        GetLength=2 * math.pi * radius * MM,
        GetStartPoint2=point,
        GetEndPoint2=FakePoint(point.X, point.Y),
    )


def spline(points) -> FakeSegment:
    flat = []
    for x, y in points:
        flat.extend([x * MM, y * MM, 0.0])
    return FakeSegment(SPLINE, GetPoints=flat)


# --- restating a segment as a spec ---------------------------------------------


def test_a_line_comes_back_as_a_line():
    entity = segment_to_entity(line((0, 0), (10, 5)))
    assert entity == {
        "type": "line",
        "start": [0.0, 0.0],
        "end": [10.0, 5.0],
        "construction": False,
    }


def test_construction_geometry_stays_construction():
    """A centerline that came back as profile geometry would change what a revolve does."""
    assert segment_to_entity(line((0, 0), (0, 10), construction=True))["construction"] is True


def test_a_circle_is_recognised_by_its_coincident_ends():
    entity = segment_to_entity(circle((3, 4), 5))
    assert entity["type"] == "circle"
    assert entity["center"] == [3.0, 4.0]
    assert entity["radius"] == pytest.approx(5.0)
    assert "start" not in entity


def test_an_arc_carries_the_direction_its_sweep_implies():
    """A quarter turn counterclockwise: length is r*pi/2, not the complement's."""
    quarter = arc((0, 0), (10, 0), (0, 10), 10, 10 * math.pi / 2)
    entity = segment_to_entity(quarter)
    assert entity["type"] == "arc_center"
    assert entity["direction"] == "counterclockwise"
    assert entity["center"] == [0.0, 0.0]
    assert entity["start"] == [10.0, 0.0]
    assert entity["end"] == [0.0, 10.0]


def test_the_major_arc_between_the_same_endpoints_is_restated_as_major():
    """The 272-degree fault, in reverse: rebuilding must not silently take the short way.

    Both arcs share a centre, a radius and both endpoints. Only the length separates
    them, so only the length can decide what spec is written back out.
    """
    major = arc((0, 0), (10, 0), (0, 10), 10, 10 * 3 * math.pi / 2)
    assert segment_to_entity(major)["direction"] == "clockwise"


def test_a_spline_comes_back_through_its_own_points():
    entity = segment_to_entity(spline([(0, 0), (5, 8), (10, 0)]))
    assert entity["type"] == "spline"
    assert entity["points"] == [[0.0, 0.0], [5.0, 8.0], [10.0, 0.0]]


@pytest.mark.parametrize("kind", [ELLIPSE, PARABOLA, TEXT])
def test_shapes_with_no_lossless_spec_are_refused_not_guessed(kind):
    """None means 'say so'. A silently dropped segment is a hole in the derived sketch."""
    assert segment_to_entity(FakeSegment(kind)) is None


def test_a_segment_that_will_not_report_its_geometry_is_refused():
    assert segment_to_entity(FakeSegment(LINE)) is None


# --- the transform ---------------------------------------------------------------


def test_the_identity_transform_changes_nothing():
    entity = segment_to_entity(line((2, 3), (7, 11)))
    assert SketchTransform().entity(entity) == entity


def test_scale_moves_points_and_scales_radius():
    """The bevel case: one section, and the same section at k=0.717."""
    scaled = SketchTransform(scale=0.717).entity(segment_to_entity(circle((10, 0), 5)))
    assert scaled["center"] == [pytest.approx(7.17), 0.0]
    assert scaled["radius"] == pytest.approx(3.585)


def test_scale_about_a_point_holds_that_point_still():
    held = SketchTransform(scale=2.0, about=(10, 10)).entity(
        segment_to_entity(line((10, 10), (20, 10)))
    )
    assert held["start"] == [10.0, 10.0]
    assert held["end"] == [30.0, 10.0]


def test_rotation_turns_the_plane():
    turned = SketchTransform(rotate_deg=90).entity(segment_to_entity(line((0, 0), (10, 0))))
    assert turned["end"][0] == pytest.approx(0.0, abs=1e-9)
    assert turned["end"][1] == pytest.approx(10.0)


def test_translation_is_applied_after_the_rest():
    moved = SketchTransform(scale=2.0, translate=(5, 0)).entity(
        segment_to_entity(line((0, 0), (10, 0)))
    )
    assert moved["start"] == [5.0, 0.0]
    assert moved["end"] == [25.0, 0.0]


def test_a_mirror_reverses_every_arc():
    """Mirroring without flipping the direction rebuilds the complement.

    That is exactly the 272-degree fault, reintroduced by the transform rather than by
    the caller - and just as invisible, because the endpoints still line up.
    """
    quarter = segment_to_entity(arc((0, 0), (10, 0), (0, 10), 10, 10 * math.pi / 2))
    assert quarter["direction"] == "counterclockwise"

    mirrored = SketchTransform(mirror="x").entity(quarter)
    assert mirrored["direction"] == "clockwise"
    assert mirrored["end"] == [0.0, -10.0]


def test_a_scale_alone_does_not_reverse_an_arc():
    """The false-positive guard: only a handedness change flips the direction."""
    quarter = segment_to_entity(arc((0, 0), (10, 0), (0, 10), 10, 10 * math.pi / 2))
    assert SketchTransform(scale=3.0).entity(quarter)["direction"] == "counterclockwise"


def test_a_mirrored_arc_still_sweeps_the_same_angle():
    """Mirroring is a rigid motion up to handedness: the arc must not change size."""
    original = segment_to_entity(arc((0, 0), (10, 0), (0, 10), 10, 10 * math.pi / 2))
    mirrored = SketchTransform(mirror="y").entity(original)

    def sweep(entity):
        cx, cy = entity["center"]
        a0 = math.atan2(entity["start"][1] - cy, entity["start"][0] - cx)
        a1 = math.atan2(entity["end"][1] - cy, entity["end"][0] - cx)
        turn = (a1 - a0) % (2 * math.pi)
        return turn if entity["direction"] == "counterclockwise" else 2 * math.pi - turn

    assert sweep(mirrored) == pytest.approx(sweep(original))


def test_spline_points_all_move_together():
    moved = SketchTransform(translate=(100, 0)).entity(
        segment_to_entity(spline([(0, 0), (5, 8), (10, 0)]))
    )
    assert moved["points"] == [[100.0, 0.0], [105.0, 8.0], [110.0, 0.0]]


# --- the direction rule on its own ------------------------------------------------


def test_arc_direction_falls_back_to_the_minor_arc_without_a_sweep():
    """No length to go on: assume the short way, which is what a caller usually means."""
    assert arc_direction((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), None) == "counterclockwise"
    assert arc_direction((0.0, 0.0), (0.0, 1.0), (1.0, 0.0), None) == "clockwise"
