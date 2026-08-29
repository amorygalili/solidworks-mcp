"""Live cover for sketch text (SK-008) and surfaces (FEAT-018).

Both areas are built on calls that report nothing useful. ``InsertSketchText`` returns
an object whether or not the text landed, and every surface call is ``void`` except
``InsertPlanarRefSurface``, whose bool is true in cases where nothing reaches the tree.
So the checks here count text segments and sheet bodies rather than trusting returns.

Knit is the one that most needs a real test: two parallel sheets 10 mm apart come back
from ``InsertSewRefSurface`` looking exactly like success — no error, no feature — which
is why the tool refuses instead, and why that refusal is tested.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

PLATE_W, PLATE_H = 60.0, 40.0


@pytest.fixture(scope="module")
def text_part(dispatcher, scratch_root):
    """One document for the text tests; they only add sketch geometry."""
    target = scratch_root / "swmcp_text.SLDPRT"
    for stale in scratch_root.glob("swmcp_text*.SLDPRT"):
        stale.unlink(missing_ok=True)
    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_doc_save", {"output_path": str(target)})
    yield target.name
    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": target.name}, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def text_call(call, text_part):
    """Activate the shared document before each test, defensively.

    ``InsertSketch`` acts on whatever document is active in the SOLIDWORKS window, and
    the surface tests below create their own documents, so re-activating keeps this
    module independent of test order.

    Not, as first assumed, the reason these tests once failed: that was
    ``SketchTextResult`` rejecting a field the handler passed, which aborted the test
    before ``sw_sketch_exit`` and left a sketch open, so the *next* test's
    ``sw_sketch_start`` failed and pointed the blame one test downstream.
    """
    call("sw_doc_activate", {"document": {"title": text_part}})

    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        args = dict(arguments or {})
        args.setdefault("document", {"title": text_part})
        return call(name, args, expect_ok=expect_ok)

    return _call


# --- sketch text (SK-008) -----------------------------------------------------


def test_plain_text_is_counted_back_out_of_the_sketch(text_call):
    text_call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    written = text_call("sw_sketch_text", {"text": "ENGRAVE", "at": [0, 0]})["result"]
    text_call("sw_sketch_exit")

    assert written["text"] == "ENGRAVE"
    assert written["on_path"] is False
    assert written["text_segment_count"] >= 1
    assert written["verification"]["before"]["text_segment_count"] == 0
    assert all(check["passed"] for check in written["verification"]["checks"])


def test_text_follows_a_sketch_segment_when_one_is_given(text_call):
    text_call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = text_call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "arc_3pt", "start": [0, 60], "end": [60, 60], "through": [30, 75]}]},
    )["result"]
    segment_id = added["created"][0]["sketch_local_id"]

    written = text_call(
        "sw_sketch_text",
        {
            "text": "ALONG THE ARC",
            "path_segment_id": segment_id,
            "alignment": "center",
        },
    )["result"]
    text_call("sw_sketch_exit")

    assert written["on_path"] is True
    assert written["alignment"] == "center"
    assert written["text_segment_count"] >= 1
    assert all(check["passed"] for check in written["verification"]["checks"])


def test_alignment_without_a_path_is_refused(text_call):
    """SOLIDWORKS ignores alignment for horizontal text, so asking for it is a mistake."""
    text_call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    payload = text_call(
        "sw_sketch_text", {"text": "NOPE", "alignment": "center"}, expect_ok=False
    )
    text_call("sw_sketch_exit")

    assert payload["error"]["category"] == "validation"


def test_a_missing_path_segment_is_named(text_call):
    text_call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    payload = text_call(
        "sw_sketch_text",
        {"text": "NOPE", "path_segment_id": "0:999", "alignment": "left"},
        expect_ok=False,
    )
    text_call("sw_sketch_exit")

    assert payload["error"]["code"] == "SEGMENT_NOT_FOUND"


def test_empty_text_is_a_schema_error(text_call):
    payload = text_call("sw_sketch_text", {"text": ""}, expect_ok=False)
    assert payload["error"]["category"] == "validation"


# --- surfaces (FEAT-018) ------------------------------------------------------


@pytest.fixture
def surface_part(call, scratch_root, unique_name):
    """A fresh document holding one planar surface, ready to offset or extend."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(scratch_root / f"{unique_name}.SLDPRT")})
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_W, PLATE_H]}]},
    )
    call("sw_sketch_exit")


def _sheet_faces(call) -> list[dict]:
    return call(
        "sw_probe_faces", {"geometry_type": "planar_face", "limit": 50}
    )["result"]["candidates"]


def test_a_planar_surface_fills_a_closed_sketch(call, surface_part):
    made = call("sw_surface_create", {"method": "planar", "name": "Skin"})["result"]

    assert made["feature_name"] == "Skin"
    assert made["method"] == "planar"
    assert made["sheet_bodies_before"] == 0
    assert made["sheet_bodies_after"] == 1
    assert made["solid_bodies_after"] == 0, "a surface must not produce a solid"
    assert all(check["passed"] for check in made["verification"]["checks"])


def test_offsetting_a_surface_adds_a_second_sheet(call, surface_part):
    call("sw_surface_create", {"method": "planar", "name": "Skin"})
    face = _sheet_faces(call)[0]

    offset = call(
        "sw_surface_create",
        {
            "method": "offset",
            "face_refs": [face["tool_args"]["ref"]],
            "distance": 10,
            "name": "Shifted",
        },
    )["result"]

    assert offset["sheet_bodies_before"] == 1
    assert offset["sheet_bodies_after"] == 2
    assert all(check["passed"] for check in offset["verification"]["checks"])


def test_a_zero_offset_copies_the_face_in_place(call, surface_part):
    """The documented way to convert faces into their own surface body."""
    call("sw_surface_create", {"method": "planar", "name": "Skin"})
    face = _sheet_faces(call)[0]

    copied = call(
        "sw_surface_create",
        {"method": "offset", "face_refs": [face["tool_args"]["ref"]], "distance": 0},
    )["result"]

    assert copied["sheet_bodies_after"] == 2


def test_extending_a_surface_edge_keeps_one_sheet(call, surface_part):
    call("sw_surface_create", {"method": "planar", "name": "Skin"})
    edges = call(
        "sw_probe_faces", {"entity_class": "edge", "geometry_type": "line_edge", "limit": 20}
    )["result"]["candidates"]

    extended = call(
        "sw_surface_create",
        {
            "method": "extend",
            "edge_refs": [edges[0]["tool_args"]["ref"]],
            "distance": 5,
            "name": "Longer",
        },
    )["result"]

    assert extended["feature_name"] == "Longer"
    assert extended["sheet_bodies_after"] == 1, "extending reshapes a sheet, it does not add one"
    assert all(check["passed"] for check in extended["verification"]["checks"])


def test_knitting_parallel_sheets_is_refused_rather_than_silently_doing_nothing(
    call, surface_part
):
    """The failure this tool exists to catch.

    ``InsertSewRefSurface`` is void, and two sheets 10 mm apart cannot be sewn: it
    returns exactly as it does on success, adds no feature, and leaves both bodies in
    place. Trusting the call would report a knit that never happened.
    """
    call("sw_surface_create", {"method": "planar", "name": "Skin"})
    face = _sheet_faces(call)[0]
    call(
        "sw_surface_create",
        {"method": "offset", "face_refs": [face["tool_args"]["ref"]], "distance": 10},
    )

    faces = _sheet_faces(call)
    assert len(faces) >= 2

    payload = call(
        "sw_surface_create",
        {"method": "knit", "face_refs": [f["tool_args"]["ref"] for f in faces[:2]]},
        expect_ok=False,
    )

    assert payload["error"]["code"] == "SURFACE_FAILED"
    assert any("touch" in step for step in payload["error"]["remediation"])


def test_offset_without_a_distance_is_a_schema_error(call, surface_part):
    payload = call(
        "sw_surface_create",
        {"method": "offset", "face_refs": [{"kind": "face", "document": {"title": "x"}}]},
        expect_ok=False,
    )
    assert payload["error"]["category"] == "validation"


def test_knit_needs_at_least_two_surfaces(call, surface_part):
    payload = call(
        "sw_surface_create",
        {"method": "knit", "face_refs": [{"kind": "face", "document": {"title": "x"}}]},
        expect_ok=False,
    )
    assert payload["error"]["category"] == "validation"
