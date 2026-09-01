"""Splines in contour analysis, and a cut that goes both ways (SK-*, FEAT-*).

Both behaviours were found while modelling a chess set. A knight's head drawn as
splines joined to lines reported contours that did not exist, and cutting a rook's
crenellations clean through had to be faked with a blind depth guessed larger than the
part.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


@pytest.fixture
def open_part(call, scratch_root, unique_name):
    """A saved scratch part, closed and cleaned up by the autouse fixture."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"

    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    yield target


def test_a_spline_reports_its_ends_rather_than_passing_for_a_circle(call, open_part):
    """``GetStartPoint2`` is not on ``ISketchSegment``; a spline needs ``GetPoints``.

    When it went unread the empty answer was taken for "no endpoints", which analysis
    reads as a closed ring - so a spline joined to two lines came back as one closed
    contour plus an open chain, on a profile that closes perfectly.
    """
    created = call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "auto_relations": False,
            "entities": [
                {"type": "spline", "points": [[0, 0], [10, 12], [24, 16], [34, 8]]},
                {"type": "line", "start": [34, 8], "end": [34, -10]},
                {"type": "line", "start": [34, -10], "end": [0, 0]},
            ],
        },
    )["result"]

    contours = created["contours"]
    assert contours["unreadable_segment_ids"] == [], (
        "a spline must report where it ends"
    )
    assert contours["closed_contour_count"] == 1
    assert contours["open_contour_count"] == 0
    assert contours["loose_ends_mm"] == []
    assert not [w for w in created["warnings"] if "do not close" in w]


def test_that_spline_profile_extrudes_because_it_really_was_closed(call, open_part):
    """The proof the old warning was wrong: SOLIDWORKS accepts the same profile."""
    call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "auto_relations": False,
            "entities": [
                {"type": "spline", "points": [[0, 0], [10, 12], [24, 16], [34, 8]]},
                {"type": "line", "start": [34, 8], "end": [34, -10]},
                {"type": "line", "start": [34, -10], "end": [0, 0]},
            ],
        },
    )
    made = call(
        "sw_feature_extrude_boss", {"end_condition": "blind", "depth": 10}
    )["result"]

    assert made["body_count_after"] == 1
    assert made["volume_mm3_after"] > 0


def test_through_all_both_cuts_clean_through_without_a_guessed_depth(call, open_part):
    """One end condition, both directions, no number to get wrong."""
    call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "entities": [{"type": "rect_center", "center": [0, 0], "corner": [20, 20]}],
        },
    )
    call("sw_feature_extrude_boss", {"end_condition": "mid_plane", "depth": 40})

    call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "entities": [{"type": "circle", "center": [0, 0], "radius": 5}],
        },
    )
    cut = call("sw_feature_extrude_cut", {"end_condition": "through_all_both"})["result"]

    # A 40mm cube with a 10mm hole bored the whole way through, not stopped inside it.
    bored = cut["volume_mm3_before"] - cut["volume_mm3_after"]
    assert bored == pytest.approx(3.14159 * 25 * 40, rel=0.02)


def test_through_all_both_ignores_a_second_direction_rather_than_arguing(call, open_part):
    """It already reaches both ways; a second blind depth would contradict it."""
    call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "entities": [{"type": "rect_center", "center": [0, 0], "corner": [20, 20]}],
        },
    )
    call("sw_feature_extrude_boss", {"end_condition": "mid_plane", "depth": 40})

    call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "entities": [{"type": "circle", "center": [0, 0], "radius": 5}],
        },
    )
    cut = call(
        "sw_feature_extrude_cut",
        {"end_condition": "through_all_both", "second_direction": True, "second_depth": 1},
    )["result"]

    bored = cut["volume_mm3_before"] - cut["volume_mm3_after"]
    assert bored == pytest.approx(3.14159 * 25 * 40, rel=0.02)
