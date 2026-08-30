"""Drawing logic that needs no SOLIDWORKS: enum mappings and the zero-sheet guard.

The guard is the point of this file. ``NewDocument`` reads its width and height only
for ``swDwgPapersUserDefined``, so asking for that size without them builds a sheet of
zero area — and SOLIDWORKS does not reject it. It accepts it, and then pegs one core
forever the first time a view is placed, with no error and no return. Four SOLIDWORKS
restarts went into diagnosing that once. It is a schema error here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.com import swconst
from swmcp.handlers.drawing import (
    _ORIENTATIONS,
    _PAPER_NAMES,
    _PAPER_SIZES,
    _SHEET_TYPE,
    _VIEW_TYPES,
    _sheet_geometry,
)
from swmcp.schemas.drawing import DrawingNewArgs, DrawingViewAddArgs

# --- the zero-by-zero sheet ------------------------------------------------------


def test_a_custom_sheet_without_a_size_is_refused():
    """The exact call that spun: user-defined paper, no dimensions."""
    with pytest.raises(ValidationError, match="needs both width and height"):
        DrawingNewArgs(paper_size="custom")
    with pytest.raises(ValidationError, match="needs both width and height"):
        DrawingNewArgs(paper_size="custom", width=100)
    assert DrawingNewArgs(paper_size="custom", width=280, height=216)


def test_a_zero_dimension_is_refused_even_when_both_are_given():
    with pytest.raises(ValidationError):
        DrawingNewArgs(paper_size="custom", width=0, height=216)


def test_dimensions_on_a_standard_size_are_refused_rather_than_ignored():
    """SOLIDWORKS would silently drop them, which reads as the size having been applied."""
    with pytest.raises(ValidationError, match="only read for paper_size='custom'"):
        DrawingNewArgs(paper_size="a", width=280, height=216)


def test_a_standard_size_needs_nothing_else():
    args = DrawingNewArgs()
    assert args.paper_size == "a"
    assert args.width is None and args.height is None
    assert args.projection == "third_angle"


def test_the_custom_size_is_the_only_one_that_reads_dimensions():
    """Pins the asymmetry the guard exists for, straight from the enum."""
    assert _PAPER_SIZES["custom"] == "swDwgPapersUserDefined"
    assert swconst.value("swDwgPaperSizes_e", "swDwgPapersUserDefined") == 12
    others = {n: m for n, m in _PAPER_SIZES.items() if n != "custom"}
    assert "swDwgPapersUserDefined" not in others.values()


def test_a_degenerate_sheet_is_reported_as_zero_rather_than_omitted():
    """The measurement that catches it: GetProperties2 slots 5 and 6."""
    spun = _sheet_geometry(_FakeSheet((12.0, 13.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0)))
    assert spun["width_mm"] == 0.0
    assert spun["height_mm"] == 0.0
    assert spun["paper_size"] == "custom"

    good = _sheet_geometry(_FakeSheet((0.0, 13.0, 1.0, 1.0, 0.0, 0.2794, 0.2159, 1.0)))
    assert good["width_mm"] == pytest.approx(279.4)
    assert good["height_mm"] == pytest.approx(215.9)
    assert good["paper_size"] == "a"
    assert good["scale"] == [1.0, 1.0]
    assert good["first_angle"] is False


def test_the_geometry_carries_metres_for_the_api_and_millimetres_for_the_caller():
    """Both, so no second unit conversion is needed anywhere in the handler."""
    geometry = _sheet_geometry(_FakeSheet((0.0, 13.0, 1.0, 1.0, 0.0, 0.2794, 0.2159, 1.0)))
    assert geometry["width_m"] == pytest.approx(0.2794)
    assert geometry["width_mm"] == pytest.approx(279.4)


def test_a_short_property_array_is_not_guessed_at():
    assert _sheet_geometry(_FakeSheet((0.0, 13.0))) == {}
    assert _sheet_geometry(_FakeSheet(None)) == {}


class _FakeSheet:
    def __init__(self, properties):
        self._properties = properties

    def GetProperties2(self):  # noqa: N802 - the COM member's own name
        return self._properties


# --- enum mappings ---------------------------------------------------------------


@pytest.mark.parametrize("member", sorted(_PAPER_SIZES.values()))
def test_every_paper_size_names_a_real_enum_member(member):
    assert isinstance(swconst.value("swDwgPaperSizes_e", member), int)


def test_paper_names_invert_without_collisions():
    values = [swconst.value("swDwgPaperSizes_e", m) for m in _PAPER_SIZES.values()]
    assert len(set(values)) == len(values)
    for name, member in _PAPER_SIZES.items():
        assert _PAPER_NAMES[swconst.value("swDwgPaperSizes_e", member)] == name


def test_the_paper_map_covers_exactly_the_schema_literals():
    literals = set(DrawingNewArgs.model_fields["paper_size"].annotation.__args__)
    assert set(_PAPER_SIZES) == literals


def test_the_orientation_map_covers_exactly_the_schema_literals():
    literals = set(DrawingViewAddArgs.model_fields["orientation"].annotation.__args__)
    assert set(_ORIENTATIONS) == literals


def test_every_standard_view_name_carries_its_asterisk():
    """The asterisk is part of the name; without it the call fails rather than guessing."""
    for name in _ORIENTATIONS.values():
        assert name.startswith("*"), name


def test_the_sheet_masquerades_as_a_view_and_is_identified_by_type():
    """GetFirstView returns the sheet, so the type code is what tells them apart."""
    assert swconst.value("swDrawingViewTypes_e", "swDrawingSheet") == _SHEET_TYPE
    assert _VIEW_TYPES[_SHEET_TYPE] == "sheet"
    assert _VIEW_TYPES[swconst.value("swDrawingViewTypes_e", "swDrawingProjectedView")] == (
        "projected"
    )
    assert _VIEW_TYPES[swconst.value("swDrawingViewTypes_e", "swDrawingNamedView")] == "named"


# --- schema guards ----------------------------------------------------------------


def test_a_standard_three_view_will_not_take_a_position():
    """It arranges its own three views; a single position could not apply to them."""
    with pytest.raises(ValidationError, match="arranges its own three views"):
        DrawingViewAddArgs(view_type="standard_3", at=[100, 100])
    assert DrawingViewAddArgs(view_type="standard_3")


def test_a_standard_three_view_will_not_take_a_single_name():
    with pytest.raises(ValidationError, match="creates three views"):
        DrawingViewAddArgs(view_type="standard_3", name="Front")


def test_a_position_needs_exactly_two_coordinates():
    with pytest.raises(ValidationError):
        DrawingViewAddArgs(at=[100])
    with pytest.raises(ValidationError):
        DrawingViewAddArgs(at=[100, 100, 100])
    assert DrawingViewAddArgs(at=[100, 100]).at == [0.1, 0.1]


def test_a_scale_must_be_positive_in_both_parts():
    with pytest.raises(ValidationError, match="greater than zero"):
        DrawingNewArgs(scale=[1, 0])
    assert DrawingNewArgs(scale=[1, 2])


def test_the_view_tool_verifies_and_the_creation_tool_is_a_side_effect():
    """Adding a view changes a document; creating one only changes the session."""
    from swmcp.catalog.projection import project
    from swmcp.catalog.registry import load_all_ops

    ops = load_all_ops()
    assert ops["sw_drawing_view_add"].safety.kind == "model_mutation"
    assert ops["sw_drawing_new"].safety.kind == "non_model_side_effect"
    assert project(ops["sw_drawing_list"].safety).read_only is True


def test_the_drawing_tools_require_the_right_document_type():
    from swmcp.catalog.registry import load_all_ops

    ops = load_all_ops()
    assert ops["sw_drawing_new"].precondition == "none"
    assert ops["sw_drawing_view_add"].precondition == "drawing"
    assert ops["sw_drawing_list"].precondition == "drawing"
