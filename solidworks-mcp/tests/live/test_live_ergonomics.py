"""Live checks for the shorthands: composed sketches, axis patterns, edge predicates.

Every one of these drives a COM path that had not been probed before it was written -
``InsertAxis2`` from two standard planes and then patterning about the result,
``DeleteSelection2`` with two option bits ORed together, and ``probe_entities`` walking
edges rather than faces. The unit tests pin the arithmetic and the schemas; only this
module can say whether SOLIDWORKS agrees.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


@pytest.fixture
def part(call, scratch_root, unique_name):
    """A saved scratch part, so the automatic checkpoint has somewhere to go."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(scratch_root / f"{unique_name}.SLDPRT")})


def _plate(call, half: float = 30.0, thickness: float = 10.0) -> None:
    """A square plate centred on the origin, extruded along Y.

    Sketched on the Top plane so the material straddles the Y axis, which is what makes
    a circular pattern about Y land its instances back inside the body.
    """
    call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "top"},
            "entities": [
                {"type": "rect_center", "center": [0, 0], "corner": [half, half]}
            ],
            "auto_relations": False,
        },
    )
    call("sw_feature_extrude_boss", {"depth": thickness, "name": "Plate"})


# --- one call for a profile ---------------------------------------------------


def test_a_profile_takes_one_call_instead_of_three(call, part):
    result = call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "entities": [
                {"type": "line", "start": [0, 0], "end": [20, 0]},
                {"type": "line", "start": [20, 0], "end": [20, 15]},
                {"type": "line", "start": [20, 15], "end": [0, 15]},
                {"type": "line", "start": [0, 15], "end": [0, 0]},
            ],
            "auto_relations": False,
        },
    )["result"]

    assert result["sketch_name"]
    assert result["plane"] == "front"
    assert result["failed"] == []
    assert len(result["created"]) == 4
    assert result["exited"] is True
    assert result["max_deviation_mm"] == 0.0
    # The reason to compose them: the profile's usability is known before anything
    # tries to consume it.
    assert result["contours"]["closed_contour_count"] == 1
    assert result["contours"]["open_contour_count"] == 0


def test_a_composed_sketch_can_be_left_open(call, part):
    result = call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "entities": [{"type": "circle", "center": [0, 0], "radius": 10}],
            "exit_sketch": False,
        },
    )["result"]
    assert result["exited"] is False

    # Still the active sketch, so the diagnose default resolves to it.
    diagnosed = call("sw_sketch_diagnose")["result"]
    assert diagnosed["sketch_name"] == result["sketch_name"]
    call("sw_sketch_exit")


# --- patterning about the model's own axis ------------------------------------


def test_a_circular_pattern_can_just_name_the_y_axis(call, part):
    """The shorthand's whole point: no probe, no captured reference, no datum first."""
    _plate(call)
    call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "top"},
            "entities": [{"type": "circle", "center": [20, 0], "radius": 3}],
            "auto_relations": False,
        },
    )
    # Mid-plane rather than through-all: the plate straddles the Top plane in only one
    # direction, and a through-all cut that picks the other one removes nothing at all.
    call(
        "sw_feature_extrude_cut",
        {"end_condition": "mid_plane", "depth": 100, "name": "Hole"},
    )

    before = call("sw_body_list")["result"]
    patterned = call(
        "sw_feature_pattern",
        {
            "type": "circular",
            "feature_names": ["Hole"],
            "count": 4,
            "angle": 360,
            "equal_spacing": True,
            "standard_axis": "y",
            "name": "Holes",
        },
    )["result"]

    assert patterned["axis_name"] == "swmcp_axis_y"
    assert patterned["axis_was_created"] is True
    assert any("reference axis" in w for w in patterned["warnings"])
    # Four holes rather than one: the pattern removed material it did not before.
    assert patterned["volume_mm3_after"] < patterned["volume_mm3_before"]
    assert before is not None


def test_the_axis_is_made_once_and_reused(call, part):
    """Creating one per call would litter the tree of anyone patterning repeatedly."""
    _plate(call)
    for index, radius in enumerate((20.0, 12.0)):
        call(
            "sw_sketch_create",
            {
                "on": {"standard_plane": "top"},
                "entities": [{"type": "circle", "center": [radius, 0], "radius": 2.5}],
                "auto_relations": False,
            },
        )
        call(
            "sw_feature_extrude_cut",
            {"end_condition": "mid_plane", "depth": 100, "name": f"Hole{index}"},
        )
        patterned = call(
            "sw_feature_pattern",
            {
                "type": "circular",
                "feature_names": [f"Hole{index}"],
                "count": 3,
                "angle": 360,
                "equal_spacing": True,
                "standard_axis": "y",
                "name": f"Ring{index}",
            },
        )["result"]

        assert patterned["axis_name"] == "swmcp_axis_y"
        assert patterned["axis_was_created"] is (index == 0), (
            "the first pattern builds the axis and every later one reuses it"
        )

    axes = [
        f["name"]
        for f in call("sw_feature_list", {"types": ["RefAxis"]})["result"]["features"]
    ]
    assert axes.count("swmcp_axis_y") == 1


def test_a_pattern_still_refuses_when_no_direction_is_given(call, part):
    _plate(call)
    payload = call(
        "sw_feature_pattern",
        {"type": "circular", "feature_names": ["Plate"], "count": 4},
        expect_ok=False,
    )
    assert not payload.get("ok")
    assert payload["error"]["code"] == "MISSING_ARGUMENT"
    assert any("standard_axis" in step for step in payload["error"]["remediation"])


# --- edges chosen by what they are --------------------------------------------


def test_a_fillet_can_choose_its_own_edges(call, part):
    """The knight's head case: round everything on the body without naming any of it."""
    _plate(call, half=20.0, thickness=8.0)

    filleted = call(
        "sw_feature_fillet",
        {"edges": {"min_length": 5}, "radius": 1.5, "name": "Rounded"},
    )["result"]

    assert filleted["edges_matched"] >= 8, "a box has twelve edges over 5mm"
    assert filleted["edges_examined"] >= filleted["edges_matched"]
    assert filleted["edges_selected"] > 0
    assert filleted["volume_mm3_after"] < filleted["volume_mm3_before"]


def test_a_predicate_that_matches_nothing_says_how_many_it_looked_at(call, part):
    """'No edges' and 'no edges over a metre' are different problems."""
    _plate(call, half=20.0, thickness=8.0)

    payload = call(
        "sw_feature_fillet",
        {"edges": {"min_length": 1000}, "radius": 1.0},
        expect_ok=False,
    )
    assert not payload.get("ok")
    assert payload["error"]["code"] == "NO_EDGES_MATCHED"
    assert payload["error"]["context"]["examined"] > 0


# --- a delete that takes what it consumed -------------------------------------


def test_deleting_a_feature_takes_the_sketch_it_absorbed(call, part):
    """swDelete_Children alone left the profile behind, drawing itself over the model."""
    sketch = call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "entities": [
                {"type": "rect_corner", "corner": [0, 0], "opposite": [20, 15]}
            ],
            "auto_relations": False,
        },
    )["result"]["sketch_name"]
    call("sw_feature_extrude_boss", {"depth": 5, "name": "Block"})

    deleted = call(
        "sw_feature_delete",
        {"feature_name": "Block", "delete_children": True, "confirm": True},
    )["result"]

    assert deleted["deleted"] is True
    assert sketch in deleted["also_removed"], (
        "the profile the extrude absorbed should go with it, not linger as an orphan"
    )

    names = [f["name"] for f in call("sw_feature_list")["result"]["features"]]
    assert sketch not in names
    assert "Block" not in names
