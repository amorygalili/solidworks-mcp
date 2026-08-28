"""Live cover for neutral-format export (IO-002, IO-003).

Every assertion here is made against the bytes on disk. ``SaveAs`` reporting no error
is not evidence that a STEP file is a STEP file, and a truncated binary STL passes
every check except the one that compares its triangle count to its length.
"""

from __future__ import annotations

import struct

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

PLATE_X, PLATE_Y, PLATE_Z = 100.0, 60.0, 8.0


@pytest.fixture
def plate(call, scratch_root, unique_name):
    for stale in scratch_root.glob(f"{unique_name}*"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"

    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_X, PLATE_Y]}]},
    )
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": PLATE_Z, "name": "Plate"})
    return target


def test_a_step_export_is_a_real_step_file(call, plate, scratch_root, unique_name):
    """IO-002."""
    target = scratch_root / f"{unique_name}.step"
    target.unlink(missing_ok=True)

    exported = call(
        "sw_export", {"output_path": str(target), "step_protocol": "ap214"}
    )["result"]

    assert exported["format"] == "step"
    assert exported["signature_verified"] is True, exported["signature_detail"]
    assert exported["settings"]["step_protocol"] == "ap214"
    assert exported["size_bytes"] > 500

    text = target.read_text(encoding="utf-8", errors="replace")
    assert text.lstrip().startswith("ISO-10303-21")
    assert "END-ISO-10303-21" in text, "a truncated STEP file would still have a header"
    assert exported["artifacts"][0]["sha256"]


def test_a_binary_stl_triangle_count_matches_its_file_size(call, plate, scratch_root, unique_name):
    """IO-003: the check that catches a truncated mesh."""
    target = scratch_root / f"{unique_name}.stl"
    target.unlink(missing_ok=True)

    exported = call(
        "sw_export",
        {"output_path": str(target), "stl_binary": True, "stl_quality": "fine"},
    )["result"]

    assert exported["format"] == "stl"
    assert exported["signature_verified"] is True, exported["signature_detail"]
    assert exported["settings"]["stl_binary"] is True
    assert exported["settings"]["stl_quality"] == "fine"

    data = target.read_bytes()
    (triangles,) = struct.unpack("<I", data[80:84])
    assert len(data) == 84 + 50 * triangles
    assert triangles >= 12, "a box tessellates to at least twelve triangles"


def test_an_ascii_stl_is_written_when_asked_for(call, plate, scratch_root, unique_name):
    target = scratch_root / f"{unique_name}_ascii.stl"
    target.unlink(missing_ok=True)

    exported = call(
        "sw_export", {"output_path": str(target), "stl_binary": False}
    )["result"]

    assert exported["signature_verified"] is True, exported["signature_detail"]
    assert exported["settings"]["stl_binary"] is False
    text = target.read_text(encoding="utf-8", errors="replace")
    assert text.lstrip().lower().startswith("solid")
    assert "facet normal" in text


def test_the_mesh_unit_setting_changes_the_coordinates(call, plate, scratch_root, unique_name):
    """IO-003's unit clause, checked by measuring the mesh rather than trusting a flag."""
    in_mm = scratch_root / f"{unique_name}_mm.stl"
    in_m = scratch_root / f"{unique_name}_m.stl"
    for path in (in_mm, in_m):
        path.unlink(missing_ok=True)

    call("sw_export", {"output_path": str(in_mm), "stl_binary": False, "mesh_unit": "mm"})
    call("sw_export", {"output_path": str(in_m), "stl_binary": False, "mesh_unit": "m"})

    def extent(path):
        values = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if parts and parts[0] == "vertex":
                values.extend(abs(float(value)) for value in parts[1:4])
        return max(values)

    millimetres, metres = extent(in_mm), extent(in_m)
    assert millimetres == pytest.approx(PLATE_X, rel=1e-3)
    assert metres == pytest.approx(PLATE_X / 1000.0, rel=1e-3)


def test_coarse_and_fine_tessellation_differ(call, plate, scratch_root, unique_name):
    """A quality setting that changes nothing is a setting that is not being applied."""
    coarse = scratch_root / f"{unique_name}_coarse.stl"
    fine = scratch_root / f"{unique_name}_fine.stl"
    for path in (coarse, fine):
        path.unlink(missing_ok=True)

    # A cylinder, because a flat plate tessellates identically at any quality.
    call("sw_sketch_start", {"on": {"standard_plane": "top"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "circle", "center": [200, 0], "radius": 20}]},
    )
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": 30, "name": "Post"})

    call("sw_export", {"output_path": str(coarse), "stl_quality": "coarse"})
    call("sw_export", {"output_path": str(fine), "stl_quality": "fine"})

    def triangles(path):
        data = path.read_bytes()
        return struct.unpack("<I", data[80:84])[0]

    assert triangles(fine) > triangles(coarse), (
        f"fine produced {triangles(fine)} triangles, coarse {triangles(coarse)}"
    )


def test_a_3mf_export_is_a_zip_container(call, plate, scratch_root, unique_name):
    target = scratch_root / f"{unique_name}.3mf"
    target.unlink(missing_ok=True)

    exported = call("sw_export", {"output_path": str(target)})["result"]

    assert exported["format"] == "3mf"
    assert exported["signature_verified"] is True, exported["signature_detail"]
    assert target.read_bytes()[:2] == b"PK"


def test_a_parasolid_export_carries_its_own_header(call, plate, scratch_root, unique_name):
    target = scratch_root / f"{unique_name}.x_t"
    target.unlink(missing_ok=True)

    exported = call("sw_export", {"output_path": str(target)})["result"]

    assert exported["format"] == "parasolid_text"
    assert exported["signature_verified"] is True, exported["signature_detail"]


def test_exporting_twice_versions_rather_than_replacing(call, plate, scratch_root, unique_name):
    target = scratch_root / f"{unique_name}.step"
    for stale in scratch_root.glob(f"{unique_name}*.step"):
        stale.unlink(missing_ok=True)

    first = call("sw_export", {"output_path": str(target)})["result"]
    second = call("sw_export", {"output_path": str(target)})["result"]

    assert first["overwrite_action"] == "create"
    assert second["overwrite_action"] == "versioned"
    assert second["saved_path"] != first["saved_path"]
    assert second["warnings"]


def test_an_unsupported_extension_is_refused(call, plate, scratch_root, unique_name):
    refused = call(
        "sw_export",
        {"output_path": str(scratch_root / f"{unique_name}.xyz")},
        expect_ok=False,
    )
    assert refused["error"]["code"] == "UNSUPPORTED_EXPORT_FORMAT"
    assert ".step" in refused["error"]["context"]["supported_extensions"]


def test_an_image_extension_points_at_the_capture_tool(call, plate, scratch_root, unique_name):
    """Two operations that both write PNGs would be a trap; one of them says so."""
    refused = call(
        "sw_export",
        {"output_path": str(scratch_root / f"{unique_name}.png")},
        expect_ok=False,
    )
    assert refused["error"]["code"] == "USE_VIEW_CAPTURE"
    assert any("sw_view_capture" in step for step in refused["error"]["remediation"])


def test_a_format_that_disagrees_with_the_extension_is_refused(call, plate, scratch_root, unique_name):
    refused = call(
        "sw_export",
        {"output_path": str(scratch_root / f"{unique_name}.step"), "format": "stl"},
        expect_ok=False,
    )
    assert refused["error"]["code"] == "INVALID_ARGUMENTS"


def test_the_export_path_is_root_checked(call, plate):
    refused = call(
        "sw_export",
        {"output_path": "C:\\Windows\\System32\\swmcp_export.step"},
        expect_ok=False,
    )
    assert refused["error"]["code"] == "PATH_NOT_ALLOWED"


def test_export_preferences_are_put_back_afterwards(call, plate, scratch_root, unique_name):
    """The settings belong to the user; borrowing them must not keep them."""
    before = call(
        "sw_api_invoke",
        {
            "target": "app",
            "member": "GetUserPreferenceIntegerValue",
            "args": [78],  # swSTLQuality
        },
    )["result"]["value"]

    call(
        "sw_export",
        {
            "output_path": str(scratch_root / f"{unique_name}_pref.stl"),
            "stl_quality": "coarse" if before != 1 else "fine",
        },
    )

    after = call(
        "sw_api_invoke",
        {"target": "app", "member": "GetUserPreferenceIntegerValue", "args": [78]},
    )["result"]["value"]

    assert after == before, "the STL quality preference must be restored after an export"


def test_exporting_a_configuration_leaves_the_active_one_alone(
    call, plate, scratch_root, unique_name
):
    """Exporting a variant is not a request to leave the model showing it."""
    call("sw_config_create", {"name": "Alt", "activate": False})
    before = call("sw_config_list")["result"]["active"]

    exported = call(
        "sw_export",
        {"output_path": str(scratch_root / f"{unique_name}_alt.step"), "configuration": "Alt"},
    )["result"]

    assert exported["settings"]["configuration"] == "Alt"
    assert exported["signature_verified"] is True
    assert call("sw_config_list")["result"]["active"] == before, (
        "the caller's own configuration must be put back after the export"
    )
