"""Live cover for shell, rib, and the composed primitives.

Each primitive is checked against its own closed-form volume, which is the only check
that distinguishes "a solid appeared" from "the solid I asked for appeared" — a sphere
built from half a profile is a perfectly healthy hemisphere.
"""

from __future__ import annotations

import math

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]


@pytest.fixture
def part(call, scratch_root, unique_name):
    for stale in scratch_root.glob(f"{unique_name}*"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    return target


def _volume(call) -> float:
    return call("sw_measure")["result"]["mass_properties"]["volume_mm3"]


# --- primitives ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({"kind": "box", "width": 40, "depth": 30, "height": 20}, 40 * 30 * 20),
        ({"kind": "cylinder", "radius": 15, "height": 50}, math.pi * 15**2 * 50),
        ({"kind": "sphere", "radius": 20}, 4 / 3 * math.pi * 20**3),
        ({"kind": "cone", "radius": 18, "height": 40}, math.pi * 18**2 * 40 / 3),
        (
            {"kind": "frustum", "radius": 20, "top_radius": 10, "height": 30},
            math.pi * 30 / 3 * (20**2 + 20 * 10 + 10**2),
        ),
        (
            {"kind": "torus", "radius": 30, "tube_radius": 8},
            2 * math.pi**2 * 30 * 8**2,
        ),
        ({"kind": "wedge", "width": 40, "depth": 30, "height": 25}, 0.5 * 40 * 30 * 25),
        (
            {"kind": "prism", "radius": 20, "sides": 6, "height": 15},
            0.5 * 6 * 20**2 * math.sin(2 * math.pi / 6) * 15,
        ),
    ],
    ids=["box", "cylinder", "sphere", "cone", "frustum", "torus", "wedge", "prism"],
)
def test_a_primitive_measures_what_its_formula_says(call, part, args, expected):
    """FEAT-014."""
    built = call("sw_body_primitive", args)["result"]

    assert built["kind"] == args["kind"]
    assert built["body_count_before"] == 0
    assert built["body_count_after"] == 1
    assert built["expected_volume_mm3"] == pytest.approx(expected, rel=1e-9)
    assert built["volume_mm3_after"] == pytest.approx(expected, rel=1e-3), (
        f"{args['kind']} measured {built['volume_mm3_after']}, formula says {expected}"
    )
    assert built["volume_error_ratio"] < 0.01
    assert all(check["passed"] for check in built["verification"]["checks"])


def test_a_primitive_missing_a_dimension_is_refused_by_the_schema(call, part):
    refused = call("sw_body_primitive", {"kind": "cylinder", "radius": 10}, expect_ok=False)
    assert refused["error"]["code"] == "INVALID_ARGUMENTS"


def test_a_torus_thicker_than_its_own_radius_is_refused(call, part):
    refused = call(
        "sw_body_primitive", {"kind": "torus", "radius": 10, "tube_radius": 12}, expect_ok=False
    )
    assert refused["error"]["code"] == "INVALID_ARGUMENTS"


def test_two_primitives_can_share_a_document(call, part):
    """Each primitive is an ordinary sketch and boss, so they compose."""
    call("sw_body_primitive", {"kind": "box", "width": 40, "depth": 30, "height": 20})
    call(
        "sw_body_primitive",
        {"kind": "cylinder", "radius": 8, "height": 40, "at": [60, 0], "name": "Post"},
    )

    expected = 40 * 30 * 20 + math.pi * 8**2 * 40
    assert _volume(call) == pytest.approx(expected, rel=1e-3)
    names = [f["name"] for f in call("sw_feature_list")["result"]["features"]]
    assert "Post" in names


# --- shell --------------------------------------------------------------------


def test_shelling_a_box_leaves_the_walls_it_was_asked_for(call, part):
    """FEAT-009: a closed box shelled to t leaves an outer minus inner volume."""
    call("sw_body_primitive", {"kind": "box", "width": 40, "depth": 30, "height": 20})
    before = _volume(call)

    shelled = call("sw_feature_shell", {"thickness": 2, "name": "Wall"})["result"]

    expected = 40 * 30 * 20 - (40 - 4) * (30 - 4) * (20 - 4)
    assert shelled["feature_name"] == "Wall"
    assert shelled["faces_removed"] == 0
    assert shelled["thickness_mm"] == pytest.approx(2.0)
    assert shelled["volume_mm3_after"] == pytest.approx(expected, rel=1e-6)
    assert shelled["volume_mm3_after"] < before
    assert shelled["face_count_after"] > shelled["face_count_before"]
    assert all(check["passed"] for check in shelled["verification"]["checks"])


def test_shelling_with_a_face_removed_opens_the_box(call, part):
    call("sw_body_primitive", {"kind": "box", "width": 40, "depth": 30, "height": 20})
    top = call(
        "sw_probe_faces", {"geometry_type": "planar_face", "area_min_mm2": 40 * 30 * 0.99}
    )["result"]["candidates"][0]

    shelled = call(
        "sw_feature_shell", {"thickness": 2, "face_refs": [top["tool_args"]["ref"]]}
    )["result"]

    assert shelled["faces_removed"] == 1
    # An open box keeps five walls rather than six, so it holds less material.
    closed = 40 * 30 * 20 - (40 - 4) * (30 - 4) * (20 - 4)
    assert shelled["volume_mm3_after"] < closed
    assert all(check["passed"] for check in shelled["verification"]["checks"])


def test_a_wall_thicker_than_the_solid_fails_with_advice(call, part):
    call("sw_body_primitive", {"kind": "box", "width": 20, "depth": 20, "height": 20})
    refused = call("sw_feature_shell", {"thickness": 40}, expect_ok=False)

    assert refused["error"]["code"] == "SHELL_FAILED"
    assert refused["error"]["remediation"]
    assert call("sw_body_list")["result"]["count"] == 1, "the solid must be untouched"


# --- rib ----------------------------------------------------------------------


def test_a_rib_adds_material_between_two_walls(call, part):
    """FEAT-011."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    # One closed L, not two rectangles sharing an edge: overlapping contours give
    # SOLIDWORKS a self-intersecting profile rather than the shape that was meant.
    call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "line", "start": [0, 0], "end": [60, 0]},
                {"type": "line", "start": [60, 0], "end": [60, 5]},
                {"type": "line", "start": [60, 5], "end": [5, 5]},
                {"type": "line", "start": [5, 5], "end": [5, 40]},
                {"type": "line", "start": [5, 40], "end": [0, 40]},
                {"type": "line", "start": [0, 40], "end": [0, 0]},
            ]
        },
    )
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": 20, "name": "LShape"})
    before = _volume(call)

    # The rib profile goes on a plane that cuts through the solid, not on the face it
    # was extruded from: a coplanar profile gives SOLIDWORKS nothing to thicken into.
    call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "front", "distance": 10, "name": "RibPlane"},
    )
    call("sw_sketch_start", {"on": {"plane_name": "RibPlane"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "line", "start": [5, 30], "end": [40, 5]}]},
    )
    call("sw_sketch_exit")

    ribbed = call("sw_feature_rib", {"thickness": 4, "name": "Stiffener"})["result"]

    assert ribbed["feature_name"] == "Stiffener"
    assert ribbed["thickness_mm"] == pytest.approx(4.0)
    assert ribbed["volume_mm3_after"] > before, "a rib that missed the body adds nothing"
    assert all(check["passed"] for check in ribbed["verification"]["checks"])
