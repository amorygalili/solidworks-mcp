"""Sketch-text and surface logic that needs no SOLIDWORKS.

Gate 1 in `CLAUDE.md`. The result-shape test at the bottom exists because a handler
passing a field its result model did not declare cost a live run to diagnose: the
failure surfaced one test downstream, as a sketch that would not open.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.handlers.sketch import _TEXT_ALIGNMENT
from swmcp.handlers.surface import _SHEET_BODY, _SOLID_BODY
from swmcp.schemas.sketch import SketchTextArgs, SketchTextResult
from swmcp.schemas.surface import SurfaceCreateArgs, SurfaceCreateResult

REF = {"kind": "face", "document": {"path": r"C:\cad\part.SLDPRT"}}


# --- sketch text --------------------------------------------------------------


def test_alignment_values_match_what_insertsketchtext_documents():
    """0 left, 1 centre, 2 right, 3 fully justified."""
    assert _TEXT_ALIGNMENT == {"left": 0, "center": 1, "right": 2, "justified": 3}


def test_the_alignment_map_covers_exactly_the_schema_literals():
    literals = set(SketchTextArgs.model_fields["alignment"].annotation.__args__)
    assert set(_TEXT_ALIGNMENT) == literals


def test_alignment_without_a_path_is_rejected():
    """SOLIDWORKS ignores alignment for horizontal text, so accepting it would mislead."""
    with pytest.raises(ValidationError, match="only applies to text on a path"):
        SketchTextArgs(text="HELLO", alignment="center")


def test_flip_without_a_path_is_rejected():
    with pytest.raises(ValidationError, match="only applies to text on a path"):
        SketchTextArgs(text="HELLO", flip_vertical=True)


def test_alignment_is_allowed_once_a_path_is_given():
    args = SketchTextArgs(text="HELLO", path_segment_id="0:1", alignment="justified")
    assert args.alignment == "justified"
    assert _TEXT_ALIGNMENT[args.alignment] == 3


def test_left_alignment_is_fine_without_a_path():
    assert SketchTextArgs(text="HELLO").alignment == "left"


def test_text_cannot_be_empty():
    with pytest.raises(ValidationError):
        SketchTextArgs(text="")


@pytest.mark.parametrize(("field", "bad"), [("width_factor", 5), ("width_factor", 1668),
                                            ("char_spacing", 0), ("char_spacing", 10001)])
def test_width_and_spacing_stay_inside_the_documented_range(field, bad):
    """InsertSketchText documents 6-1667 and 1-10000; outside that it misbehaves."""
    with pytest.raises(ValidationError):
        SketchTextArgs(text="HELLO", **{field: bad})


def test_the_text_result_declares_sketch_state():
    """The regression: the handler passes it, so the model must accept it.

    A strict model rejecting a field the handler sends aborts the operation *after*
    SOLIDWORKS has already done the work, which is the worst shape of failure here.
    """
    assert "sketch_state" in SketchTextResult.model_fields


# --- surfaces -----------------------------------------------------------------


def test_the_body_type_constants_are_the_solidworks_ones():
    """swBodyType_e: 0 solid, 1 sheet, 2 wire. Confusing these counts the wrong bodies."""
    assert _SOLID_BODY == 0
    assert _SHEET_BODY == 1


def test_offset_needs_faces_and_a_distance():
    with pytest.raises(ValidationError, match="needs face_refs"):
        SurfaceCreateArgs(method="offset", distance=5)
    with pytest.raises(ValidationError, match="needs a distance"):
        SurfaceCreateArgs(method="offset", face_refs=[REF])


def test_a_zero_offset_is_allowed_because_it_copies_faces():
    """Zero is the documented way to turn faces into their own surface body."""
    assert SurfaceCreateArgs(method="offset", face_refs=[REF], distance=0).distance == 0


def test_extend_needs_edges_and_a_distance():
    with pytest.raises(ValidationError, match="needs edge_refs"):
        SurfaceCreateArgs(method="extend", distance=5)
    with pytest.raises(ValidationError, match="needs a distance"):
        SurfaceCreateArgs(method="extend", edge_refs=[REF])


def test_knit_needs_two_surfaces():
    with pytest.raises(ValidationError, match="at least two"):
        SurfaceCreateArgs(method="knit", face_refs=[REF])
    assert SurfaceCreateArgs(method="knit", face_refs=[REF, REF])


def test_planar_needs_nothing_because_it_finds_the_newest_sketch():
    assert SurfaceCreateArgs(method="planar").sketch_name is None


def test_the_surface_result_reports_both_body_kinds():
    """A surface operation that quietly made a solid would otherwise look identical."""
    for field in ("sheet_bodies_before", "sheet_bodies_after", "solid_bodies_after"):
        assert field in SurfaceCreateResult.model_fields
