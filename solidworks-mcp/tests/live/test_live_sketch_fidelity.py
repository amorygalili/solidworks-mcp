"""Live proof that coordinates land where they were asked for, and that a refused
revolve says why (SK-003, CON-005, FEAT-003).

These are the cases behind the change, taken from a session that built a chess set and
did not notice what had happened until the parts were measured:

* A revolve profile of lines and arcs came back with several segments the wrong length.
  SOLIDWORKS' sketch inference had snapped their endpoints onto neighbouring geometry,
  and every check the server made still passed - one rook's bore moved a whole
  millimetre, thinning its wall from 3mm to 2mm, and the tool reported success.
* A revolve was refused with a bare "could not revolve" whose remediation listed two
  causes, neither of which applied. The real cause was a centerline drawn exactly on
  top of the profile's closing edge.

The module builds its own documents rather than sharing one, because two of the tests
want a clean feature tree and the parts are small enough that the isolation is cheap.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


#: A profile shaped like the pawn that provoked the snapping: short segments meeting at
#: shallow angles, which is exactly what inference reaches for. Coordinates in mm.
SNAP_PRONE_PROFILE = [
    {"type": "centerline", "start": [0, -4], "end": [0, 46]},
    {"type": "line", "start": [0, 0], "end": [11, 0]},
    {"type": "line", "start": [11, 0], "end": [11, 3.5]},
    {"type": "line", "start": [11, 3.5], "end": [9.5, 5.5]},
    {"type": "arc_3pt", "start": [9.5, 5.5], "end": [4.2, 20], "through": [5.8, 11.5]},
    {"type": "line", "start": [4.2, 20], "end": [4.2, 22]},
    {"type": "line", "start": [4.2, 22], "end": [7, 24.5]},
    {"type": "line", "start": [7, 24.5], "end": [7, 26]},
    {"type": "line", "start": [7, 26], "end": [2.6, 28.5]},
    {"type": "line", "start": [2.6, 28.5], "end": [0, 42]},
    {"type": "line", "start": [0, 42], "end": [0, 0]},
]


@pytest.fixture
def part(call, scratch_root, unique_name):
    """A saved scratch part, so the automatic checkpoint has somewhere to go."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(scratch_root / f"{unique_name}.SLDPRT")})


def test_turning_inference_off_places_every_point_exactly_as_written(call, part):
    """The load-bearing claim: auto_relations=false means what it says.

    Asserted against the arithmetic the test knew in advance - each requested point,
    compared with where SOLIDWORKS actually put it - rather than against the call
    having returned.
    """
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {"entities": SNAP_PRONE_PROFILE, "auto_relations": False},
    )["result"]

    assert added["failed"] == []
    assert added["max_deviation_mm"] == 0.0, (
        "inference was suspended, so nothing should have moved: "
        f"{added['max_deviation_mm']} mm"
    )

    checks = {check["name"]: check for check in added["verification"]["checks"]}
    assert checks["coordinates_as_requested"]["passed"] is True
    assert not [w for w in added["warnings"] if "placed away" in w]


def test_the_placement_check_is_actually_measuring_something(call, part):
    """A check that cannot fail proves nothing, so pin that real numbers are read back.

    The default path keeps SOLIDWORKS' inference, and what it does with this profile is
    its business - so the assertion is that every measurable entity got measured, not
    that it moved.
    """
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call("sw_sketch_add_geometry", {"entities": SNAP_PRONE_PROFILE})["result"]

    assert added["failed"] == []
    assert added["max_deviation_mm"] is not None
    measured = [e for e in added["created"] if "deviation_mm" in e]
    # Every entity in this profile is a line, an arc, or a centerline: all checkable.
    assert len(measured) == len(added["created"])
    assert all(isinstance(entry["deviation_mm"], (int, float)) for entry in measured)


def test_a_gap_in_a_profile_is_reported_with_its_coordinates(call, part):
    """The solver calls this sketch fine; only the contour walk knows it will not close.

    ``sw_sketch_diagnose`` is asked for the sketch by name: after ``sw_sketch_exit``
    there is no active sketch, and defaulting to one would fail here rather than
    diagnose anything.
    """
    started = call("sw_sketch_start", {"on": {"standard_plane": "front"}})["result"]
    call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "line", "start": [0, 0], "end": [10, 0]},
                {"type": "line", "start": [10, 0], "end": [10, 10]},
                {"type": "line", "start": [10, 10], "end": [0, 10]},
                {"type": "line", "start": [0, 10], "end": [0, 1]},
            ],
            "auto_relations": False,
        },
    )
    call("sw_sketch_exit")

    diagnosed = call(
        "sw_sketch_diagnose", {"sketch_name": started["sketch_name"]}
    )["result"]
    contours = diagnosed["contours"]

    assert contours["closed_contour_count"] == 0
    assert contours["open_contour_count"] == 1
    assert sorted(contours["loose_ends_mm"]) == [[0.0, 0.0], [0.0, 1.0]]
    assert any("do not close" in warning for warning in diagnosed["warnings"])


def test_a_closed_profile_reports_one_contour_and_no_warning(call, part):
    started = call("sw_sketch_start", {"on": {"standard_plane": "front"}})["result"]
    call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "rect_corner", "corner": [0, 0], "opposite": [40, 25]},
                {"type": "centerline", "start": [0, -5], "end": [0, 30]},
            ]
        },
    )
    call("sw_sketch_exit")

    contours = call(
        "sw_sketch_diagnose", {"sketch_name": started["sketch_name"]}
    )["result"]["contours"]
    assert contours["closed_contour_count"] == 1
    assert contours["open_contour_count"] == 0
    # The centerline is an axis, not a side of the rectangle.
    assert contours["profile_segment_count"] == 4
    assert contours["loose_ends_mm"] == []


#: Profiles that were each expected to be refused, and were not.
#:
#: Three attempts at a failing revolve fixture, three surprises. They are kept as a
#: single parametrised finding because what they collectively establish - that this
#: build closes far more than the documentation implies - is worth more than any one of
#: them, and because a future build that *does* refuse one should announce itself here
#: rather than in somebody's model.
FORGIVEN_PROFILES = {
    "axis_on_the_closing_edge": [
        {"type": "centerline", "start": [0, 50], "end": [0, 64]},
        {"type": "line", "start": [0, 50], "end": [2.2, 50]},
        {"type": "line", "start": [2.2, 50], "end": [2.2, 56.66]},
        {"type": "line", "start": [2.2, 56.66], "end": [0, 64]},
        {"type": "line", "start": [0, 64], "end": [0, 50]},
    ],
    "gap_between_two_points_on_the_axis": [
        {"type": "centerline", "start": [0, -5], "end": [0, 35]},
        {"type": "line", "start": [0, 0], "end": [12, 0]},
        {"type": "line", "start": [12, 0], "end": [12, 30]},
        {"type": "line", "start": [12, 30], "end": [0, 30]},
        {"type": "line", "start": [0, 30], "end": [0, 2]},
    ],
    "collinear_gap_in_the_outer_wall": [
        {"type": "centerline", "start": [0, -5], "end": [0, 35]},
        {"type": "line", "start": [0, 0], "end": [12, 0]},
        {"type": "line", "start": [12, 0], "end": [12, 20]},
        {"type": "line", "start": [12, 25], "end": [12, 30]},
        {"type": "line", "start": [12, 30], "end": [0, 30]},
        {"type": "line", "start": [0, 30], "end": [0, 0]},
    ],
}


@pytest.mark.parametrize("shape", sorted(FORGIVEN_PROFILES))
def test_solidworks_revolves_profiles_that_look_like_it_should_not(call, part, shape):
    """A record of what this build forgives, written the way round it actually behaves.

    Each of these was first written as ``assert the revolve fails``, on the strength of
    a real failure or of what "a revolve needs a closed profile" plainly implies. Each
    one passed instead. The beliefs they disproved have been taken out of the
    diagnosis: an on-axis gap is now explicitly ruled *out* as a cause rather than
    blamed, and the centerline-overlap finding is hedged and reported last.

    Asserting success is not a way of turning a red test green here - it is the finding.
    If a later build refuses one of these, the diagnosis it produces becomes checkable
    and this test is where that conversation starts.
    """
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": FORGIVEN_PROFILES[shape], "auto_relations": False},
    )
    call("sw_sketch_exit")

    payload = call("sw_feature_revolve", {"angle": 360}, expect_ok=False)
    assert payload.get("ok"), (
        f"{shape} was refused. That is new: it revolved when this test was written, "
        "and the revolve diagnosis was hedged on the strength of that. Check what "
        "error['context'] now says and tighten the wording it earned."
    )
    assert payload["result"]["volume_mm3_after"] > 0
