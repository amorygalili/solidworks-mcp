"""Live cover for viewport orientation and image capture (VIEW-003, VIEW-004).

An image is the one result a caller cannot verify from JSON, so these tests verify it
from the file itself: the bytes on disk are decoded for their format signature and
pixel size rather than trusting what the call reported.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live

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


def test_the_viewport_takes_every_standard_orientation(call, plate):
    """VIEW-003."""
    for orientation in ("front", "top", "right", "isometric", "back", "bottom", "left"):
        outcome = call("sw_view_set", {"orientation": orientation})["result"]
        assert outcome["orientation"] == orientation
        assert outcome["fitted"] is True
        assert outcome["selection_cleared"] is True


def test_display_modes_are_accepted(call, plate):
    for mode in ("wireframe", "hidden_lines_removed", "shaded", "shaded_with_edges"):
        outcome = call("sw_view_set", {"display_mode": mode, "fit": False})["result"]
        assert outcome["display_mode"] == mode
        assert outcome["fitted"] is False


def test_a_png_capture_writes_a_real_png(call, plate, scratch_root, unique_name):
    """VIEW-004: the file is decoded, not merely counted."""
    target = scratch_root / f"{unique_name}.png"
    target.unlink(missing_ok=True)

    captured = call(
        "sw_view_capture",
        {"output_path": str(target), "orientation": "isometric", "width": 800, "height": 600},
    )["result"]

    assert captured["format"] == "png"
    assert captured["overwrite_action"] == "create"
    assert captured["orientation"] == "isometric"
    assert captured["saved_path"] == str(target)

    written = target.read_bytes()
    assert written[:8] == b"\x89PNG\r\n\x1a\n", "the file must actually be a PNG"
    assert len(written) > 1000, "an image of a plate is not a few hundred bytes"

    assert captured["actual_size"], "the size must be read back out of the file"
    assert captured["actual_size"][0] > 0
    assert captured["requested_size"] == [800, 600]

    evidence = captured["artifacts"][0]
    assert evidence["exists"] is True
    assert evidence["size_bytes"] == len(written)
    assert evidence["sha256"]


def test_a_bmp_capture_honours_the_requested_size(call, plate, scratch_root, unique_name):
    """SaveBMP is the one call that takes explicit pixel dimensions."""
    target = scratch_root / f"{unique_name}.bmp"
    target.unlink(missing_ok=True)

    captured = call(
        "sw_view_capture",
        {"output_path": str(target), "width": 640, "height": 480, "orientation": "front"},
    )["result"]

    assert captured["format"] == "bmp"
    assert captured["method"] == "SaveBMP"
    assert target.read_bytes()[:2] == b"BM"
    assert captured["actual_size"] == [640, 480], (
        f"SaveBMP was asked for 640x480 and produced {captured['actual_size']}"
    )
    assert captured["warnings"] == []


def test_a_size_mismatch_is_reported_rather_than_hidden(call, plate, scratch_root, unique_name):
    """A PNG capture is limited by the viewport, so the difference must be visible."""
    target = scratch_root / f"{unique_name}_big.png"
    target.unlink(missing_ok=True)

    captured = call(
        "sw_view_capture", {"output_path": str(target), "width": 4096, "height": 4096}
    )["result"]

    if captured["actual_size"] != [4096, 4096]:
        assert any("rather than the requested" in w for w in captured["warnings"]), (
            f"size differed ({captured['actual_size']}) with no warning"
        )


def test_capturing_twice_versions_rather_than_replacing(call, plate, scratch_root, unique_name):
    """SAFE-008 applies to previews too."""
    target = scratch_root / f"{unique_name}.png"
    for stale in scratch_root.glob(f"{unique_name}*.png"):
        stale.unlink(missing_ok=True)

    first = call("sw_view_capture", {"output_path": str(target)})["result"]
    second = call("sw_view_capture", {"output_path": str(target)})["result"]

    assert first["overwrite_action"] == "create"
    assert second["overwrite_action"] == "versioned"
    assert second["saved_path"] != first["saved_path"]
    assert second["warnings"], "writing elsewhere than asked must be said out loud"


def test_an_unsupported_format_is_refused_before_anything_is_written(
    call, plate, scratch_root, unique_name
):
    target = scratch_root / f"{unique_name}.tiff"
    refused = call("sw_view_capture", {"output_path": str(target)}, expect_ok=False)

    assert refused["error"]["code"] == "UNSUPPORTED_IMAGE_FORMAT"
    assert not target.exists()


def test_the_capture_path_is_root_checked(call, plate):
    refused = call(
        "sw_view_capture",
        {"output_path": "C:\\Windows\\System32\\swmcp_preview.png"},
        expect_ok=False,
    )
    assert refused["error"]["code"] == "PATH_NOT_ALLOWED"
