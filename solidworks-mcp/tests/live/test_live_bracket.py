"""The end-to-end acceptance build: model a bracket and verify it against arithmetic.

This is the test that says the whole stack works. It builds real geometry, checks the
measured volume and bounding box against values computed by hand, finds the holes by
probing the B-Rep rather than by trusting the feature succeeded, and finishes by
proving a checkpoint restore actually rolls the model back.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

PLATE_X, PLATE_Y, PLATE_Z = 100.0, 60.0, 8.0
HOLE_DIAMETER = 6.6
PLATE_VOLUME_MM3 = PLATE_X * PLATE_Y * PLATE_Z


@pytest.fixture
def bracket(call, scratch_root, unique_name):
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    try:
        yield target
    finally:
        # The autouse fixture closes the document and removes the file, in that order.
        pass


def _base_plate(call) -> dict:
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_X, PLATE_Y]}]},
    )
    call("sw_sketch_exit")
    return call("sw_feature_extrude_boss", {"depth": PLATE_Z, "name": "BasePlate"})["result"]


def test_the_base_plate_measures_what_arithmetic_says(call, bracket):
    extruded = _base_plate(call)

    assert extruded["feature_name"] == "BasePlate"
    assert extruded["body_count_before"] == 0
    assert extruded["body_count_after"] == 1
    assert extruded["volume_mm3_after"] == pytest.approx(PLATE_VOLUME_MM3, rel=1e-6)
    assert all(check["passed"] for check in extruded["verification"]["checks"]), (
        f"failed checks: {[c for c in extruded['verification']['checks'] if not c['passed']]}"
    )

    measured = call("sw_measure")["result"]
    assert measured["mass_properties"]["volume_mm3"] == pytest.approx(PLATE_VOLUME_MM3, rel=1e-6)
    assert measured["bounding_box"]["size_mm"] == pytest.approx(
        [PLATE_X, PLATE_Y, PLATE_Z], rel=1e-6
    )
    assert measured["topology"] == {
        **measured["topology"],
        "body_count": 1,
        "face_count": 6,
        "edge_count": 12,
    }
    assert measured["validity"]["has_volume"] is True
    assert measured["validity"]["features_in_error"] == []


def test_a_cut_removes_the_volume_it_should(call, bracket):
    _base_plate(call)
    side = 20.0

    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [10, 10], "opposite": [10 + side, 10 + side]}]},
    )
    call("sw_sketch_exit")

    # The plate was extruded in +Z from the front plane, so a cut sketched on that same
    # plane has to point the same way to reach material.
    cut = call(
        "sw_feature_extrude_cut",
        {"end_condition": "through_all", "reverse": True, "name": "Pocket"},
    )["result"]
    expected = PLATE_VOLUME_MM3 - side * side * PLATE_Z
    assert cut["volume_mm3_after"] == pytest.approx(expected, rel=1e-6)
    assert all(check["passed"] for check in cut["verification"]["checks"])


def test_a_hole_is_verified_by_finding_it_in_the_geometry(call, bracket):
    """FEAT-012: the feature returning success is not the evidence; the B-Rep is."""
    _base_plate(call)

    top = call(
        "sw_probe_faces",
        {"geometry_type": "planar_face", "area_min_mm2": PLATE_X * PLATE_Y * 0.99},
    )["result"]["candidates"][0]

    drilled = call(
        "sw_feature_hole",
        {
            "face_ref": top["tool_args"]["ref"],
            "kind": "simple",
            "at": [20, 20, PLATE_Z],
            "diameter": HOLE_DIAMETER,
            "through_all": True,
            "name": "MountingHole",
        },
    )["result"]

    assert drilled["strategy_used"] in {"simple_hole", "cut_extrude"}
    assert drilled["holes_found"] >= 1, "the hole must be findable as a cylindrical face"
    assert drilled["volume_mm3_after"] < drilled["volume_mm3_before"]

    found = call(
        "sw_probe_faces",
        {
            "geometry_type": "cylindrical_face",
            "radius_min": HOLE_DIAMETER / 2 - 0.05,
            "radius_max": HOLE_DIAMETER / 2 + 0.05,
        },
    )["result"]
    assert found["matched"] >= 1
    assert found["candidates"][0]["measurements"]["radius_m"] == pytest.approx(
        HOLE_DIAMETER / 2000.0, rel=1e-4
    )


def test_a_fillet_rounds_the_edges_it_was_given(call, bracket):
    _base_plate(call)

    before = call("sw_measure")["result"]["mass_properties"]["volume_mm3"]
    edges = call("sw_probe_faces", {"entity_class": "edge", "geometry_type": "line_edge"})["result"]
    assert edges["matched"] >= 4

    vertical = [
        candidate
        for candidate in edges["candidates"]
        if candidate["measurements"].get("length_m")
        and abs(candidate["measurements"]["length_m"] - PLATE_Z / 1000.0) < 1e-9
    ][:4]
    assert len(vertical) == 4, "a plate has four short corner edges"

    rounded = call(
        "sw_feature_fillet",
        {"refs": [candidate["tool_args"]["ref"] for candidate in vertical], "radius": 5},
    )["result"]

    assert rounded["edges_selected"] == 4
    assert rounded["volume_mm3_after"] < before, "rounding a corner removes material"
    assert all(check["passed"] for check in rounded["verification"]["checks"])


def test_feature_tree_and_bodies_read_back_consistently(call, bracket):
    _base_plate(call)

    features = call("sw_feature_list")["result"]
    names = [feature["name"] for feature in features["features"]]
    assert "BasePlate" in names
    assert all(feature["error_code"] == 0 for feature in features["features"])

    listed = call("sw_body_list")["result"]
    assert listed["count"] == 1
    body = listed["bodies"][0]
    assert body["face_count"] == 6
    assert body["edge_count"] == 12
    assert body["volume_m3"] == pytest.approx(PLATE_VOLUME_MM3 / 1e9, rel=1e-6)
    assert "BasePlate" in body["owning_features"]


def test_rolling_back_a_deleted_feature_restores_the_model(call, bracket, scratch_root):
    """The whole safety story in one test: checkpoint, destroy, restore, re-measure."""
    _base_plate(call)
    call("sw_doc_save", {"output_path": str(bracket), "overwrite": "allow", "confirm": True})

    snapshot = call("sw_checkpoint_create")["result"]["checkpoint"]
    assert snapshot["method"] in {"save_as_copy", "file_copy"}
    original_volume = call("sw_measure")["result"]["mass_properties"]["volume_mm3"]
    assert original_volume == pytest.approx(PLATE_VOLUME_MM3, rel=1e-6)

    removed = call(
        "sw_feature_delete", {"feature_name": "BasePlate", "confirm": True, "delete_children": True}
    )["result"]
    assert removed["deleted"] is True
    assert call("sw_body_list")["result"]["count"] == 0, "the model should now be empty"

    call("sw_doc_save", {"output_path": str(bracket), "overwrite": "allow", "confirm": True})
    restored = call(
        "sw_checkpoint_restore",
        {"checkpoint_path": snapshot["checkpoint_path"], "confirm": True},
    )["result"]

    assert restored["pre_restore_checkpoint"], "restoring must itself be reversible"
    assert restored["reopened"] is True

    recovered = call("sw_measure")["result"]["mass_properties"]["volume_mm3"]
    assert recovered == pytest.approx(original_volume, rel=1e-6), (
        "the restored model must measure the same as before the delete"
    )


def test_deleting_a_feature_requires_confirmation(call, bracket):
    _base_plate(call)
    refused = call("sw_feature_delete", {"feature_name": "BasePlate"}, expect_ok=False)
    assert refused["error"]["code"] == "CONFIRM_REQUIRED"
    assert call("sw_body_list")["result"]["count"] == 1, "the body must still be there"


def test_renaming_and_suppressing_a_feature_is_read_back(call, bracket):
    _base_plate(call)

    renamed = call("sw_feature_edit", {"feature_name": "BasePlate", "rename_to": "Plate"})["result"]
    assert renamed["feature_name"] == "Plate"
    assert all(check["passed"] for check in renamed["verification"]["checks"])

    suppressed = call("sw_feature_edit", {"feature_name": "Plate", "suppress": True})["result"]
    assert suppressed["suppressed"] is True
    assert call("sw_body_list")["result"]["count"] == 0, "a suppressed feature has no body"

    call("sw_feature_edit", {"feature_name": "Plate", "suppress": False})
    assert call("sw_body_list")["result"]["count"] == 1
