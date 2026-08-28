"""Live cover for the feature tools the bracket build never exercised.

Every tool here mutates geometry, which is the class where an untested operation does
the wrong thing quietly rather than failing: ``sw_feature_pattern`` shipped selecting
its direction reference with the wrong selection mark, and nothing caught it because
no test ever called it. So each check below compares a measurement against arithmetic
rather than asserting that the call returned.
"""

from __future__ import annotations

import math

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

PLATE_X, PLATE_Y, PLATE_Z = 100.0, 60.0, 8.0
PLATE_VOLUME_MM3 = PLATE_X * PLATE_Y * PLATE_Z


@pytest.fixture
def part(call, scratch_root, unique_name):
    """An empty saved scratch part."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    return target


def _plate(call) -> dict:
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_X, PLATE_Y]}]},
    )
    call("sw_sketch_exit")
    return call("sw_feature_extrude_boss", {"depth": PLATE_Z, "name": "BasePlate"})["result"]


def _edges(call, *, length_mm: float, axis: int | None = None) -> list[dict]:
    """Edges of a given length, optionally running along one positive axis."""
    found = call("sw_probe_faces", {"entity_class": "edge", "geometry_type": "line_edge"})
    picked = []
    for candidate in found["result"]["candidates"]:
        measured = candidate["measurements"]
        if measured.get("length_m") is None:
            continue
        if abs(measured["length_m"] - length_mm / 1000.0) > 1e-9:
            continue
        if axis is not None:
            direction = measured.get("direction") or [0.0, 0.0, 0.0]
            if direction[axis] < 0.9:
                continue
        picked.append(candidate)
    return picked


def _volume(call) -> float:
    return call("sw_measure")["result"]["mass_properties"]["volume_mm3"]


# --- revolve ------------------------------------------------------------------


def test_a_revolve_sweeps_the_profile_it_was_given(call, part):
    """FEAT-003. Two stacked cylinders, so the answer is closed-form."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "centerline", "start": [0, 0], "end": [70, 0]},
                {"type": "line", "start": [0, 0], "end": [0, 15]},
                {"type": "line", "start": [0, 15], "end": [40, 15]},
                {"type": "line", "start": [40, 15], "end": [40, 10]},
                {"type": "line", "start": [40, 10], "end": [70, 10]},
                {"type": "line", "start": [70, 10], "end": [70, 0]},
                {"type": "line", "start": [70, 0], "end": [0, 0]},
            ]
        },
    )
    call("sw_sketch_exit")

    revolved = call("sw_feature_revolve", {"angle": 360, "name": "Shaft"})["result"]
    expected = math.pi * (15**2 * 40 + 10**2 * 30)

    assert revolved["feature_name"] == "Shaft"
    assert revolved["mode"] == "boss"
    assert revolved["body_count_before"] == 0
    assert revolved["body_count_after"] == 1
    assert revolved["volume_mm3_after"] == pytest.approx(expected, rel=1e-6)
    assert all(check["passed"] for check in revolved["verification"]["checks"])

    measured = call("sw_measure")["result"]
    assert measured["bounding_box"]["size_mm"] == pytest.approx([70.0, 30.0, 30.0], rel=1e-6)


def test_a_partial_revolve_sweeps_only_the_angle_asked_for(call, part):
    """A 90 degree revolve must be a quarter of the full one, not a full one."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "centerline", "start": [0, 0], "end": [50, 0]},
                {"type": "rect_corner", "corner": [0, 0], "opposite": [50, 20]},
            ]
        },
    )
    call("sw_sketch_exit")

    quarter = call("sw_feature_revolve", {"angle": "90deg", "name": "Quarter"})["result"]
    expected = math.pi * 20**2 * 50 / 4

    assert quarter["volume_mm3_after"] == pytest.approx(expected, rel=1e-4)


def test_a_revolve_cut_removes_the_ring_it_describes(call, part):
    """A groove turned into a cylinder: the removed volume is a closed-form annulus."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "centerline", "start": [0, 0], "end": [0, 50]},
                {"type": "rect_corner", "corner": [0, 0], "opposite": [20, 50]},
            ]
        },
    )
    call("sw_sketch_exit")
    call("sw_feature_revolve", {"angle": 360, "name": "Barrel"})
    assert _volume(call) == pytest.approx(math.pi * 20**2 * 50, rel=1e-6)

    # A 5 mm deep, 10 mm tall groove cut into the outer wall.
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "centerline", "start": [0, 0], "end": [0, 50]},
                {"type": "rect_corner", "corner": [15, 20], "opposite": [20, 30]},
            ]
        },
    )
    call("sw_sketch_exit")

    cut = call("sw_feature_revolve", {"mode": "cut", "angle": 360, "name": "Groove"})["result"]
    removed = math.pi * (20**2 - 15**2) * 10

    assert cut["mode"] == "cut"
    assert cut["feature_name"] == "Groove"
    assert cut["volume_mm3_after"] == pytest.approx(
        cut["volume_mm3_before"] - removed, rel=1e-6
    )
    assert all(check["passed"] for check in cut["verification"]["checks"])


# --- chamfer ------------------------------------------------------------------


def test_a_chamfer_removes_the_wedge_its_dimensions_describe(call, part):
    """FEAT-006. A 45 degree chamfer on a plate edge is a triangular prism."""
    _plate(call)
    before = _volume(call)

    vertical = _edges(call, length_mm=PLATE_Z)
    assert len(vertical) >= 4, "a plate has four short corner edges"

    chamfered = call(
        "sw_feature_chamfer",
        {"refs": [vertical[0]["tool_args"]["ref"]], "distance": 4, "name": "CornerBreak"},
    )["result"]

    assert chamfered["feature_type"] == "Chamfer", "the locale-invariant type token"
    assert chamfered["edges_selected"] == 1
    expected = before - 0.5 * 4 * 4 * PLATE_Z
    assert chamfered["volume_mm3_after"] == pytest.approx(expected, rel=1e-6)
    assert all(check["passed"] for check in chamfered["verification"]["checks"])


def test_an_angle_distance_chamfer_uses_the_angle(call, part):
    """The two chamfer kinds must not silently produce the same geometry."""
    _plate(call)
    before = _volume(call)
    vertical = _edges(call, length_mm=PLATE_Z)

    chamfered = call(
        "sw_feature_chamfer",
        {
            "refs": [vertical[0]["tool_args"]["ref"]],
            "distance": 4,
            "angle": 30,
            "kind": "angle_distance",
        },
    )["result"]

    # A 4 mm leg at 30 degrees leaves a wedge of 0.5 * 4 * 4*tan(30) * thickness.
    expected = before - 0.5 * 4 * (4 * math.tan(math.radians(30))) * PLATE_Z
    assert chamfered["volume_mm3_after"] == pytest.approx(expected, rel=1e-4)
    assert chamfered["volume_mm3_after"] != pytest.approx(before - 0.5 * 4 * 4 * PLATE_Z, rel=1e-4)


# --- pattern ------------------------------------------------------------------


@pytest.fixture
def drilled_plate(call, part):
    """A plate with one hole near the origin corner, ready to be patterned."""
    _plate(call)
    top = call(
        "sw_probe_faces",
        {"geometry_type": "planar_face", "area_min_mm2": PLATE_X * PLATE_Y * 0.99},
    )["result"]["candidates"][0]
    call(
        "sw_feature_hole",
        {
            "face_ref": top["tool_args"]["ref"],
            "kind": "simple",
            "at": [20, 20, PLATE_Z],
            "diameter": 6.6,
            "through_all": True,
            "name": "MountingHole",
        },
    )
    return 6.6


def _holes(call, diameter: float) -> int:
    return call(
        "sw_probe_faces",
        {
            "geometry_type": "cylindrical_face",
            "radius_min": diameter / 2 - 0.05,
            "radius_max": diameter / 2 + 0.05,
        },
    )["result"]["matched"]


def test_a_one_direction_linear_pattern_makes_the_instances_it_promised(call, drilled_plate):
    """FEAT-007, and the regression for a direction selected with the wrong mark."""
    seeded = _volume(call)
    direction = _edges(call, length_mm=PLATE_X, axis=0)
    assert direction, "the plate has an edge running along +X"

    patterned = call(
        "sw_feature_pattern",
        {
            "type": "linear",
            "feature_names": ["MountingHole"],
            "direction_ref": direction[0]["tool_args"]["ref"],
            "count": 3,
            "spacing": 25,
            "name": "Row",
        },
    )["result"]

    assert patterned["pattern_type"] == "linear"
    assert patterned["instances_requested"] == 3
    assert _holes(call, drilled_plate) == 3, "the B-Rep is the evidence, not the return value"

    one_hole = math.pi * (drilled_plate / 2) ** 2 * PLATE_Z
    assert patterned["volume_mm3_after"] == pytest.approx(seeded - 2 * one_hole, rel=1e-4)


def test_a_two_direction_pattern_uses_both_directions(call, drilled_plate):
    """The second direction has to be selected with mark 2 or the feature fails."""
    seeded = _volume(call)
    first = _edges(call, length_mm=PLATE_X, axis=0)
    second = _edges(call, length_mm=PLATE_Y, axis=1)
    assert first and second

    patterned = call(
        "sw_feature_pattern",
        {
            "type": "linear",
            "feature_names": ["MountingHole"],
            "direction_ref": first[0]["tool_args"]["ref"],
            "count": 2,
            "spacing": 60,
            "second_direction_ref": second[0]["tool_args"]["ref"],
            "second_count": 2,
            "second_spacing": 20,
            "name": "Grid",
        },
    )["result"]

    assert patterned["instances_requested"] == 4, "count x second_count, not count"
    assert _holes(call, drilled_plate) == 4

    one_hole = math.pi * (drilled_plate / 2) ** 2 * PLATE_Z
    assert patterned["volume_mm3_after"] == pytest.approx(seeded - 3 * one_hole, rel=1e-4)


def test_a_second_direction_count_without_a_reference_is_refused(call, drilled_plate):
    """Rejected in the schema layer, before SOLIDWORKS is asked to fail."""
    direction = _edges(call, length_mm=PLATE_X, axis=0)
    refused = call(
        "sw_feature_pattern",
        {
            "type": "linear",
            "feature_names": ["MountingHole"],
            "direction_ref": direction[0]["tool_args"]["ref"],
            "count": 2,
            "spacing": 20,
            "second_count": 2,
        },
        expect_ok=False,
    )

    assert refused["error"]["code"] == "MISSING_ARGUMENT"
    assert _holes(call, drilled_plate) == 1, "the model must be untouched"


def test_a_circular_pattern_repeats_around_an_axis(call, part):
    """The circular branch takes a different COM call, so it needs its own proof."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call("sw_sketch_add_geometry", {"entities": [{"type": "circle", "center": [0, 0], "radius": 40}]})
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": 10, "name": "Disc"})

    top = call(
        "sw_probe_faces", {"geometry_type": "planar_face", "area_min_mm2": math.pi * 40**2 * 0.9}
    )["result"]["candidates"][0]
    call(
        "sw_feature_hole",
        {
            "face_ref": top["tool_args"]["ref"],
            "kind": "simple",
            "at": [25, 0, 10],
            "diameter": 5,
            "through_all": True,
            "name": "BoltHole",
        },
    )
    assert _holes(call, 5.0) == 1

    axis = call("sw_probe_faces", {"geometry_type": "cylindrical_face", "radius_min": 39.9})
    assert axis["result"]["matched"] >= 1, "the disc's outer face gives the pattern axis"

    patterned = call(
        "sw_feature_pattern",
        {
            "type": "circular",
            "feature_names": ["BoltHole"],
            "direction_ref": axis["result"]["candidates"][0]["tool_args"]["ref"],
            "count": 4,
            "angle": 360,
            "equal_spacing": True,
            "name": "BoltCircle",
        },
    )["result"]

    assert patterned["pattern_type"] == "circular"
    assert _holes(call, 5.0) == 4


# --- datum geometry -----------------------------------------------------------


def test_an_offset_datum_plane_is_created_where_it_was_asked_for(call, part):
    """DAT-002."""
    created = call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "front", "distance": 25, "name": "Raised"},
    )["result"]

    assert created["plane_name"] == "Raised"
    assert created["method"] == "offset"
    assert all(check["passed"] for check in created["verification"]["checks"])

    listed = call("sw_datum_list")["result"]
    names = [plane["name"] for plane in listed["planes"]]
    assert "Raised" in names
    assert len(listed["planes"]) >= 4, "three standard planes plus the new one"
    assert listed["origin"] is not None


def test_a_new_datum_plane_can_be_sketched_on(call, part):
    """A plane nobody can sketch on is not a usable plane."""
    call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "front", "distance": 30, "name": "Deck"},
    )
    started = call("sw_sketch_start", {"on": {"plane_name": "Deck"}})["result"]
    assert started["sketch_name"]

    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [20, 20]}]},
    )
    call("sw_sketch_exit")
    extruded = call("sw_feature_extrude_boss", {"depth": 5, "name": "OnDeck"})["result"]

    assert extruded["body_count_after"] == 1
    assert extruded["volume_mm3_after"] == pytest.approx(20 * 20 * 5, rel=1e-6)


def test_datum_list_reports_locale_invariant_type_tokens(call, part):
    """DAT-001 and SYS-007: the tree is read by type token, never by display name."""
    listed = call("sw_datum_list")["result"]

    assert len(listed["planes"]) >= 3
    for plane in listed["planes"]:
        assert plane["type_name"] == "RefPlane"
        assert plane["ref"]["label"], "every datum must come back capture-ready"
    assert listed["origin"]["type_name"] == "OriginProfileFeature"
