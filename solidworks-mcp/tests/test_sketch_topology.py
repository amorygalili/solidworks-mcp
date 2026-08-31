"""Contour topology and coordinate fidelity — the arithmetic, without SOLIDWORKS.

Every function here works on the plain data :func:`segment_topology` produces, which is
the whole point of that split: whether a profile closes is decided by geometry, and
geometry can be checked at unit-test speed.

The cases are the ones that actually bit. A revolve profile whose segments *look*
joined but are a millimetre apart reports as fully drawn and refuses to revolve; a
sketch batch that snapped onto its neighbours passed every check it had while modelling
something the caller never asked for.
"""

from __future__ import annotations

import typing

import pytest

from swmcp.handlers.feature import revolve_findings
from swmcp.handlers.sketch import _ENTITY_ANCHORS, _InferenceOff
from swmcp.schemas.sketch import SketchAddGeometryArgs, SketchEntity
from swmcp.sketching import (
    analyze_contours,
    anchor_deviation,
    cluster_points,
    coincident_axis_segments,
    straddling_axes,
    unsupported_loose_ends,
)
from swmcp.units import COORDINATE_TOLERANCE_M

MM = 0.001


def seg(name: str, start, end, *, construction: bool = False) -> dict:
    """One segment in the shape :func:`segment_topology` hands back, in metres."""
    return {
        "id": name,
        "kind": "line",
        "construction": construction,
        "endpoints": [
            (start[0] * MM, start[1] * MM),
            (end[0] * MM, end[1] * MM),
        ],
    }


def ring(name: str) -> dict:
    """A circle: closed, and with no endpoints to join to anything."""
    return {"id": name, "kind": "circle", "construction": False, "endpoints": []}


def square(prefix: str = "s") -> list[dict]:
    return [
        seg(f"{prefix}1", (0, 0), (10, 0)),
        seg(f"{prefix}2", (10, 0), (10, 10)),
        seg(f"{prefix}3", (10, 10), (0, 10)),
        seg(f"{prefix}4", (0, 10), (0, 0)),
    ]


# --- anchor deviation ---------------------------------------------------------


def test_geometry_placed_where_it_was_asked_for_reports_no_gap():
    assert anchor_deviation([(0.0, 0.0), (0.01, 0.0)], [(0.0, 0.0), (0.01, 0.0)]) == 0.0


def test_the_gap_is_measured_to_the_nearest_end_not_the_matching_one():
    """SOLIDWORKS returns a segment's ends in either order, so position means nothing."""
    requested = [(0.0, 0.0), (0.01, 0.0)]
    assert anchor_deviation(requested, [(0.01, 0.0), (0.0, 0.0)]) == 0.0


def test_a_snapped_endpoint_shows_up_as_its_real_distance():
    """The rook's bore moved 1mm when inference snapped it; that has to be visible."""
    gap = anchor_deviation([(0.007, 0.042)], [(0.008, 0.042)])
    assert gap == pytest.approx(0.001)
    assert gap > COORDINATE_TOLERANCE_M


def test_nothing_to_compare_is_none_rather_than_zero():
    """A circle has no checkable anchors. Reporting 0.0 would claim it was verified."""
    assert anchor_deviation([], [(0.0, 0.0)]) is None
    assert anchor_deviation([(0.0, 0.0)], []) is None


# --- point clustering ---------------------------------------------------------


def test_points_within_tolerance_become_one_vertex():
    centres, index = cluster_points([(0.0, 0.0), (1e-9, 0.0), (0.01, 0.0)])
    assert len(centres) == 2
    assert index == [0, 0, 1]


def test_points_beyond_tolerance_stay_apart():
    centres, _ = cluster_points([(0.0, 0.0), (0.001, 0.0)])
    assert len(centres) == 2


# --- contour topology ---------------------------------------------------------


def test_a_closed_square_is_one_closed_contour():
    result = analyze_contours(square())
    assert result["closed_contour_count"] == 1
    assert result["open_contour_count"] == 0
    assert result["loose_ends_mm"] == []


def test_a_square_with_a_gap_is_open_and_names_where():
    """The failure mode that matters: it looks drawn, and it will not revolve."""
    segments = square()
    segments[3] = seg("s4", (0, 10), (0, 1))  # stops 1mm short of the start
    result = analyze_contours(segments)

    assert result["closed_contour_count"] == 0
    assert result["open_contour_count"] == 1
    assert sorted(result["loose_ends_mm"]) == [[0.0, 0.0], [0.0, 1.0]]
    assert set(result["open_segment_ids"]) == {"s1", "s2", "s3", "s4"}


def test_a_circle_closes_on_its_own():
    result = analyze_contours([ring("c1")])
    assert result["closed_contour_count"] == 1
    assert result["open_contour_count"] == 0


def test_two_separate_loops_are_counted_separately():
    inner = [
        seg("i1", (2, 2), (4, 2)),
        seg("i2", (4, 2), (4, 4)),
        seg("i3", (4, 4), (2, 4)),
        seg("i4", (2, 4), (2, 2)),
    ]
    result = analyze_contours(square() + inner)
    assert result["closed_contour_count"] == 2


def test_construction_geometry_is_not_part_of_the_profile():
    """A centerline is an axis. Counting it would report every revolve sketch as broken."""
    segments = [*square(), seg("axis", (-5, -5), (-5, 20), construction=True)]
    result = analyze_contours(segments)

    assert result["profile_segment_count"] == 4
    assert result["closed_contour_count"] == 1
    assert result["loose_ends_mm"] == []


def test_a_branching_profile_is_open_even_though_nothing_is_loose():
    """Three edges at a corner still will not revolve, so degree 2 is the real test."""
    segments = [*square(), seg("spur", (10, 0), (20, 0))]
    result = analyze_contours(segments)

    assert result["open_contour_count"] == 1
    assert result["branch_points_mm"] == [[10.0, 0.0]]


def test_an_empty_sketch_reports_nothing_rather_than_failing():
    assert analyze_contours([])["closed_contour_count"] == 0


# --- axis findings ------------------------------------------------------------


def test_a_centerline_lying_on_a_profile_edge_is_reported():
    """The queen's finial: axis and closing edge spanning the same two points."""
    segments = [
        *square(),
        seg("axis", (0, 10), (0, 0), construction=True),
    ]
    found = coincident_axis_segments(segments)
    assert found == [{"centerline": "axis", "segment": "s4"}]


def test_a_centerline_longer_than_the_edge_is_left_alone():
    """The fix for the above is to extend it, so extending must not stay flagged."""
    segments = [*square(), seg("axis", (0, -5), (0, 15), construction=True)]
    assert coincident_axis_segments(segments) == []


def test_a_profile_touching_the_axis_is_not_crossing_it():
    """Every revolve profile closed along its centerline touches. That is normal."""
    segments = [*square(), seg("axis", (0, -5), (0, 15), construction=True)]
    assert straddling_axes(segments) == []


def test_a_profile_with_material_both_sides_is_crossing():
    segments = [
        seg("p1", (-5, 0), (5, 0)),
        seg("p2", (5, 0), (5, 10)),
        seg("p3", (5, 10), (-5, 10)),
        seg("p4", (-5, 10), (-5, 0)),
        seg("axis", (0, -5), (0, 15), construction=True),
    ]
    assert straddling_axes(segments) == ["axis"]


def test_a_degenerate_centerline_is_skipped_rather_than_dividing_by_zero():
    segments = [*square(), seg("axis", (0, 0), (0, 0), construction=True)]
    assert straddling_axes(segments) == []


# --- gaps the axis can close for you ------------------------------------------


def test_a_gap_lying_on_the_axis_is_not_held_against_the_profile():
    """Measured: SOLIDWORKS revolves this. A revolve closes its profile on the axis."""
    axis = seg("axis", (0, -5), (0, 35), construction=True)
    assert unsupported_loose_ends([[0.0, 0.0], [0.0, 2.0]], [axis]) == []


def test_a_gap_away_from_the_axis_is_reported():
    axis = seg("axis", (0, -5), (0, 35), construction=True)
    stranded = unsupported_loose_ends([[12.0, 20.0], [12.0, 25.0]], [axis])
    assert stranded == [[12.0, 20.0], [12.0, 25.0]]


def test_a_short_centerline_still_defines_the_whole_axis():
    """The axis is the infinite line, not the drawn segment, so a gap past its end counts."""
    axis = seg("axis", (0, 0), (0, 1), construction=True)
    assert unsupported_loose_ends([[0.0, 30.0]], [axis]) == []


def test_with_no_centerline_at_all_every_loose_end_stands():
    assert unsupported_loose_ends([[0.0, 0.0]], square()) == [[0.0, 0.0]]


# --- what a refused revolve tells the caller ----------------------------------


def findings(segments, *, axis_given: bool = False) -> dict:
    return revolve_findings(segments, "Sketch1", axis_given=axis_given)


def test_a_sketch_with_no_axis_at_all_is_told_so_first():
    result = findings(square())
    assert "nothing to revolve about" in result["remediation"][0]
    assert result["context"]["centerline_count"] == 0


def test_naming_an_axis_ref_answers_the_missing_centerline_complaint():
    result = findings(square(), axis_given=True)
    assert not any("nothing to revolve about" in step for step in result["remediation"])


def test_an_off_axis_gap_is_named_with_its_coordinates():
    segments = [
        seg("p1", (0, 0), (12, 0)),
        seg("p2", (12, 0), (12, 20)),
        seg("p3", (10, 25), (12, 30)),
        seg("p4", (12, 30), (0, 30)),
        seg("p5", (0, 30), (0, 0)),
        seg("axis", (0, -5), (0, 35), construction=True),
    ]
    result = findings(segments)

    assert sorted(result["context"]["loose_ends_the_axis_cannot_close_mm"]) == [
        [10.0, 25.0],
        [12.0, 20.0],
    ]
    assert any("not on the axis" in step for step in result["remediation"])


def test_a_gap_on_the_axis_is_explicitly_ruled_out_rather_than_blamed():
    """Measured behaviour: this revolves. Saying otherwise sends the caller nowhere."""
    segments = [
        seg("p1", (0, 0), (12, 0)),
        seg("p2", (12, 0), (12, 30)),
        seg("p3", (12, 30), (0, 30)),
        seg("p4", (0, 30), (0, 2)),
        seg("axis", (0, -5), (0, 35), construction=True),
    ]
    result = findings(segments)

    assert result["context"]["loose_ends_the_axis_cannot_close_mm"] == []
    assert any("probably not the cause" in step for step in result["remediation"])


def test_a_straddling_profile_is_told_which_way_to_move():
    segments = [
        seg("p1", (-5, 0), (5, 0)),
        seg("p2", (5, 0), (5, 10)),
        seg("p3", (5, 10), (-5, 10)),
        seg("p4", (-5, 10), (-5, 0)),
        seg("axis", (0, -5), (0, 15), construction=True),
    ]
    result = findings(segments)
    assert any("both sides of the axis" in step for step in result["remediation"])


def test_the_overlap_finding_is_hedged_and_never_leads():
    """It is not a known cause, so it must not read like one or come first."""
    segments = [*square(), seg("axis", (0, 10), (0, 0), construction=True)]
    steps = findings(segments)["remediation"]

    overlap = [s for s in steps if "exactly on top of a profile edge" in s]
    assert overlap, "the geometry is there and should still be reported"
    assert "not known to cause a refusal" in overlap[0]
    assert steps.index(overlap[0]) == len(steps) - 1


def test_a_sketch_with_nothing_wrong_says_so_instead_of_inventing_a_cause():
    """The honest answer when the geometry is fine is that this is not the usual cause."""
    segments = [*square(), seg("axis", (-8, -5), (-8, 15), construction=True)]
    steps = findings(segments)["remediation"]

    assert len(steps) == 1
    assert "not one of the usual causes" in steps[0]


def test_the_diagnosis_never_repeats_the_old_boilerplate_verbatim():
    """The whole point was to stop answering every refusal with the same two lines."""
    for segments in (square(), [*square(), seg("a", (0, -5), (0, 15), construction=True)]):
        steps = findings(segments)["remediation"]
        assert "The profile must not cross the axis." not in steps


# --- the anchor map matches the schema ----------------------------------------


def _entity_classes() -> dict[str, type]:
    members = typing.get_args(typing.get_args(SketchEntity)[0])
    return {
        typing.get_args(cls.model_fields["type"].annotation)[0]: cls for cls in members
    }


def test_every_anchor_names_a_field_that_exists_on_its_entity():
    """A renamed schema field would otherwise silently stop being checked."""
    classes = _entity_classes()
    for kind, fields in _ENTITY_ANCHORS.items():
        assert kind in classes, f"{kind} is not a SketchEntity member"
        for field in fields:
            assert field in classes[kind].model_fields, f"{kind}.{field} does not exist"


def test_forms_whose_points_are_not_endpoints_are_deliberately_unchecked():
    """Measuring a circle's centre against an endpoint would compare the wrong things."""
    for kind in ("circle", "polygon", "ellipse", "spline", "point", "slot_straight"):
        assert kind not in _ENTITY_ANCHORS


# --- the flag itself ----------------------------------------------------------


def test_inference_stays_on_unless_it_is_turned_off():
    """Existing callers keep SOLIDWORKS' sketching behaviour; the fix is opt-in."""
    args = SketchAddGeometryArgs(entities=[{"type": "point", "at": [0, 0]}])
    assert args.auto_relations is True


def test_inference_can_be_turned_off():
    args = SketchAddGeometryArgs(
        entities=[{"type": "point", "at": [0, 0]}], auto_relations=False
    )
    assert args.auto_relations is False


# --- putting the user's SOLIDWORKS back the way it was ------------------------


class _FakeSketchManager:
    """Just enough of ``ISketchManager`` to exercise the toggle's failure modes."""

    def __init__(self, *, initial: bool = False, readable: bool = True,
                 writable: bool = True) -> None:
        self.value = initial
        self.writes: list[bool] = []
        self._readable = readable
        self._writable = writable

    def __getattr__(self, name: str):
        if name == "AddToDB":
            if not self._readable:
                raise AttributeError("AddToDB is not readable on this build")
            return self.__dict__["value"]
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name == "AddToDB":
            if not self.__dict__["_writable"]:
                raise AttributeError("AddToDB is not writable on this build")
            self.__dict__["writes"].append(value)
            self.__dict__["value"] = value
            return
        object.__setattr__(self, name, value)


def test_inference_is_left_alone_when_the_caller_did_not_ask():
    manager = _FakeSketchManager()
    with _InferenceOff(manager, enabled=False) as toggle:
        assert toggle.engaged is False
    assert manager.writes == []


def test_inference_is_suspended_and_then_restored():
    manager = _FakeSketchManager(initial=False)
    with _InferenceOff(manager, enabled=True) as toggle:
        assert toggle.engaged is True
        assert manager.value is True
    assert manager.value is False


def test_a_session_that_already_had_it_set_keeps_that_setting():
    manager = _FakeSketchManager(initial=True)
    with _InferenceOff(manager, enabled=True):
        assert manager.value is True
    assert manager.value is True


def test_an_unreadable_property_is_still_restored_after_a_successful_write():
    """The dangerous case: read fails, write works, and nothing puts it back.

    Leaving AddToDB True would change how every sketch the user draws by hand behaves
    afterwards, with nothing on screen to say why.
    """
    manager = _FakeSketchManager(initial=False, readable=False)
    with _InferenceOff(manager, enabled=True) as toggle:
        assert toggle.engaged is True
        assert manager.value is True
    assert manager.value is False


def test_a_build_that_refuses_the_property_reports_that_it_did_not_engage():
    manager = _FakeSketchManager(writable=False)
    with _InferenceOff(manager, enabled=True) as toggle:
        assert toggle.engaged is False
    assert manager.writes == []
