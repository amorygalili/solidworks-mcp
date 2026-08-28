"""Live cover for the reference-geometry vertical: DAT-003, DAT-004, and DAT-005.

Reference geometry is the class of feature where a call that returns cleanly proves
almost nothing. ``InsertAxis2`` answers with a bare ``True``/``False`` and leaves the
tree untouched when the selection does not describe an axis, and
``InsertCoordinateSystem`` happily builds a system at the model origin when its
selection marks are wrong — both failures look exactly like success from the return
value alone.

So a point is never checked by asserting that it was created. A coordinate system built
on it reports where it actually landed, and that position is compared against geometry
measured out of the model. That is the only read-back SOLIDWORKS offers for a reference
point, and it is what makes these tools verifiable rather than merely non-throwing.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

PLATE_X, PLATE_Y, PLATE_Z = 100.0, 60.0, 8.0
HOLE_CENTRE = (50.0, 30.0)
HOLE_RADIUS = 10.0


@pytest.fixture
def part(call, scratch_root, unique_name):
    """An empty saved scratch part."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    return target


@pytest.fixture
def plate(call, part):
    """A 100 x 60 x 8 plate with a Ø20 hole, so every coordinate below is arithmetic."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_X, PLATE_Y]}]},
    )
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": PLATE_Z, "name": "BasePlate"})

    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "circle", "center": list(HOLE_CENTRE), "radius": HOLE_RADIUS}]},
    )
    call("sw_sketch_exit")
    # The plate was extruded in +Z from the front plane, so the cut has to follow it.
    call(
        "sw_feature_extrude_cut",
        {"end_condition": "through_all", "reverse": True, "name": "Hole"},
    )
    return part


def _edges(call) -> list[dict]:
    return call("sw_probe_faces", {"entity_class": "edge", "limit": 100})["result"]["candidates"]


def _long_edge(call) -> dict:
    """One of the 100 mm straight edges, with its measured midpoint."""
    for candidate in _edges(call):
        measured = candidate["measurements"]
        length = measured.get("length_m")
        if (
            candidate["geometry_type"] == "line_edge"
            and length is not None
            and abs(length - PLATE_X / 1000.0) < 1e-9
        ):
            return candidate
    raise AssertionError(f"no {PLATE_X} mm straight edge found on the plate")


def _hole_edge(call) -> dict:
    for candidate in _edges(call):
        if candidate["geometry_type"] == "circular_edge":
            return candidate
    raise AssertionError("no circular edge found on the plate")


def _origin_of(call, point_ref: dict, name: str) -> list[float]:
    """Where a reference point actually is, read back through a coordinate system."""
    created = call("sw_datum_csys_create", {"origin": point_ref, "name": name})["result"]
    assert created["transform"] is not None
    return created["transform"]["translation_mm"]


# --- axes (DAT-003) -----------------------------------------------------------


def test_an_axis_is_created_where_two_standard_planes_intersect(call, part):
    created = call(
        "sw_datum_axis_create",
        {"method": "two_planes", "standard_planes": ["front", "right"], "name": "SpinAxis"},
    )["result"]

    assert created["axis_name"] == "SpinAxis"
    assert created["method"] == "two_planes"
    assert all(check["passed"] for check in created["verification"]["checks"])
    assert created["verification"]["after"]["type_name"] == "RefAxis"

    listed = call("sw_datum_list")["result"]
    axes = {axis["name"]: axis for axis in listed["axes"]}
    assert "SpinAxis" in axes
    assert axes["SpinAxis"]["type_name"] == "RefAxis"
    assert axes["SpinAxis"]["ref"]["label"], "a datum you cannot address is a dead end"


def test_an_axis_from_two_parallel_planes_is_refused_rather_than_invented(call, part):
    """The reason the handler does not trust ``InsertAxis2``'s return value.

    Two parallel planes never intersect, so there is no axis to create. SOLIDWORKS
    reports that by returning false and leaving the tree alone — which is exactly the
    shape of a silent success if nobody reads the tree back.
    """
    call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "front", "distance": 20, "name": "Parallel"},
    )
    listed = call("sw_datum_list")["result"]
    parallel = next(plane for plane in listed["planes"] if plane["name"] == "Parallel")
    before = len(listed["axes"])

    payload = call(
        "sw_datum_axis_create",
        {
            "method": "two_planes",
            "standard_planes": ["front"],
            "refs": [parallel["tool_args"]["ref"]],
        },
        expect_ok=False,
    )

    assert not payload["ok"]
    assert payload["error"]["code"] == "AXIS_CREATE_FAILED"
    assert payload["error"]["context"]["insert_axis_returned"] is False
    assert len(call("sw_datum_list")["result"]["axes"]) == before, "no axis may be left behind"


def test_the_axis_method_validates_its_reference_count(call, part):
    payload = call(
        "sw_datum_axis_create",
        {"method": "two_planes", "standard_planes": ["front"]},
        expect_ok=False,
    )
    assert payload["error"]["code"] == "WRONG_REFERENCE_COUNT"
    assert payload["error"]["context"]["required"] == 2
    assert payload["error"]["context"]["supplied"] == 1


# --- points (DAT-003) ---------------------------------------------------------


def test_an_arc_centre_point_lands_on_the_centre_of_the_hole(call, plate):
    """The position is checked against where the hole was sketched, not against a bool."""
    hole = _hole_edge(call)
    created = call(
        "sw_datum_point_create",
        {"method": "arc_center", "refs": [hole["tool_args"]["ref"]], "name": "HoleCentre"},
    )["result"]

    assert created["point_names"] == ["HoleCentre"]
    assert created["count"] == 1
    assert all(check["passed"] for check in created["verification"]["checks"])

    landed = _origin_of(call, created["references"][0]["tool_args"]["ref"], "AtHole")
    assert landed == pytest.approx([*HOLE_CENTRE, PLATE_Z], abs=1e-6)


def test_an_arc_centre_point_on_a_straight_edge_fails_with_a_usable_reason(call, plate):
    """SOLIDWORKS rejects a straight edge here, and the remediation must say so."""
    payload = call(
        "sw_datum_point_create",
        {"method": "arc_center", "refs": [_long_edge(call)["tool_args"]["ref"]]},
        expect_ok=False,
    )

    assert payload["error"]["code"] == "POINT_CREATE_FAILED"
    assert any("along_curve" in step for step in payload["error"]["remediation"])


def test_a_point_at_fifty_percent_lands_on_the_edge_midpoint(call, plate):
    edge = _long_edge(call)
    midpoint_mm = [value * 1000.0 for value in edge["measurements"]["point_m"]]

    created = call(
        "sw_datum_point_create",
        {
            "method": "along_curve",
            "along_curve": "percentage",
            "percent": 50,
            "refs": [edge["tool_args"]["ref"]],
            "name": "HalfWay",
        },
    )["result"]

    assert created["point_names"] == ["HalfWay"]
    landed = _origin_of(call, created["references"][0]["tool_args"]["ref"], "AtMidSpan")
    assert landed == pytest.approx(midpoint_mm, abs=1e-6)


def test_points_spaced_along_an_edge_are_all_created(call, plate):
    """``NumberOfRefPoints`` is only honoured for the evenly-distributed mode."""
    created = call(
        "sw_datum_point_create",
        {
            "method": "along_curve",
            "along_curve": "evenly",
            "count": 3,
            "refs": [_long_edge(call)["tool_args"]["ref"]],
        },
    )["result"]

    assert created["count"] == 3, "three points were asked for"
    assert len(created["point_names"]) == 3
    assert len(created["references"]) == 3
    assert created["warnings"] == []

    points = {point["name"] for point in call("sw_datum_list")["result"]["points"]}
    assert set(created["point_names"]) <= points


def test_a_face_centre_point_is_created_on_a_planar_face(call, plate):
    faces = call(
        "sw_probe_faces",
        {"geometry_type": "planar_face", "area_min_mm2": PLATE_X * PLATE_Y * 0.5},
    )["result"]["candidates"]

    created = call(
        "sw_datum_point_create",
        {"method": "face_center", "refs": [faces[0]["tool_args"]["ref"]], "name": "FaceMiddle"},
    )["result"]

    assert created["point_names"] == ["FaceMiddle"]
    assert created["references"][0]["tool_args"]["ref"]


def test_a_placement_mode_without_its_value_is_a_schema_error(call, plate):
    payload = call(
        "sw_datum_point_create",
        {
            "method": "along_curve",
            "along_curve": "distance",
            "refs": [_long_edge(call)["tool_args"]["ref"]],
        },
        expect_ok=False,
    )
    assert not payload["ok"]
    assert payload["error"]["category"] == "validation"


# --- coordinate systems (DAT-004) ---------------------------------------------


def test_a_coordinate_system_reports_the_transform_it_was_built_with(call, plate):
    """DAT-004: the transform is the evidence, and arithmetic knows the answer already.

    A system built from the wrong selection marks lands on the model origin instead of
    the requested point, which this would catch.
    """
    edge = _long_edge(call)
    midpoint_mm = [value * 1000.0 for value in edge["measurements"]["point_m"]]
    point = call(
        "sw_datum_point_create",
        {
            "method": "along_curve",
            "along_curve": "percentage",
            "percent": 50,
            "refs": [edge["tool_args"]["ref"]],
            "name": "CsysOrigin",
        },
    )["result"]

    created = call(
        "sw_datum_csys_create",
        {
            "origin": point["references"][0]["tool_args"]["ref"],
            "x_axis": edge["tool_args"]["ref"],
            "name": "Datum",
        },
    )["result"]

    assert created["csys_name"] == "Datum"
    assert all(check["passed"] for check in created["verification"]["checks"])

    transform = created["transform"]
    assert transform is not None
    assert transform["scale"] == pytest.approx(1.0)
    assert transform["translation_mm"] == pytest.approx(midpoint_mm, abs=1e-6)
    assert transform["translation_mm"] != [0.0, 0.0, 0.0], "that would be the model origin"

    for row in transform["rotation"]:
        assert sum(value * value for value in row) == pytest.approx(1.0, abs=1e-9), (
            "each rotation row must be a unit vector"
        )

    listed = call("sw_datum_list")["result"]
    assert "Datum" in {csys["name"] for csys in listed["coordinate_systems"]}


def test_a_coordinate_system_with_no_references_is_refused(call, plate):
    """Nothing selected builds a system at the model origin, which would verify fine."""
    payload = call("sw_datum_csys_create", {}, expect_ok=False)
    assert not payload["ok"]
    assert payload["error"]["category"] == "validation"


# --- datum management (DAT-005) -----------------------------------------------


def _datum(call, bucket: str, name: str) -> dict | None:
    listed = call("sw_datum_list")["result"]
    return next((item for item in listed[bucket] if item["name"] == name), None)


def test_a_datum_plane_can_be_renamed_suppressed_and_deleted(call, part):
    """DAT-005 across the three verbs, each read back out of the datum listing."""
    call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "front", "distance": 15, "name": "Working"},
    )
    assert _datum(call, "planes", "Working") is not None

    renamed = call("sw_feature_edit", {"feature_name": "Working", "rename_to": "Deck"})["result"]
    assert renamed["feature_name"] == "Deck"
    assert _datum(call, "planes", "Working") is None
    assert _datum(call, "planes", "Deck") is not None

    suppressed = call("sw_feature_edit", {"feature_name": "Deck", "suppress": True})["result"]
    assert suppressed["suppressed"] is True
    assert _datum(call, "planes", "Deck")["suppressed"] is True

    unsuppressed = call("sw_feature_edit", {"feature_name": "Deck", "suppress": False})["result"]
    assert unsuppressed["suppressed"] is False
    assert _datum(call, "planes", "Deck")["suppressed"] is False

    deleted = call("sw_feature_delete", {"feature_name": "Deck", "confirm": True})["result"]
    assert deleted["deleted"] is True
    assert _datum(call, "planes", "Deck") is None


def test_a_datum_axis_stays_addressable_across_a_rename(call, part):
    """A persistent reference that stops resolving after a rename is not persistent."""
    created = call(
        "sw_datum_axis_create",
        {"method": "two_planes", "standard_planes": ["top", "right"], "name": "Original"},
    )["result"]
    reference = created["reference"]["tool_args"]["ref"]

    call("sw_feature_edit", {"feature_name": "Original", "rename_to": "Renamed"})

    resolved = call("sw_ref_resolve", {"ref": reference})["result"]
    assert resolved["refreshed"], "the reference must still resolve to something"
    assert _datum(call, "axes", "Renamed") is not None

    call("sw_feature_delete", {"feature_name": "Renamed", "confirm": True})
    assert _datum(call, "axes", "Renamed") is None
