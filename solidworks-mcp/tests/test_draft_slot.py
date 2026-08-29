"""Draft and slot logic that needs no SOLIDWORKS: enum mappings and schema guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.com import swconst
from swmcp.handlers.feature import _DRAFT_PROPAGATION
from swmcp.handlers.sketch import _SLOT_CREATION_TYPES, _SLOT_LENGTH_TYPES
from swmcp.schemas.feature import DraftArgs
from swmcp.schemas.sketch import (
    SlotArc3PointEntity,
    SlotArcEntity,
    SlotCenterpointEntity,
    SlotStraightEntity,
)

REF = {"kind": "face", "document": {"path": r"C:\cad\part.SLDPRT"}}


# --- draft --------------------------------------------------------------------


@pytest.mark.parametrize("member", sorted(_DRAFT_PROPAGATION.values()))
def test_every_propagation_names_a_real_enum_member(member):
    assert isinstance(swconst.value("swDraftFacePropagationType_e", member), int)


def test_the_propagation_map_covers_exactly_the_schema_literals():
    literals = set(DraftArgs.model_fields["propagation"].annotation.__args__)
    assert set(_DRAFT_PROPAGATION) == literals


def test_the_propagation_values_match_what_the_api_documents():
    """InsertMultiFaceDraft documents PropType 0-4; the enum agrees, so pin both."""
    assert swconst.value("swDraftFacePropagationType_e", "swFacePropNone") == 0
    assert swconst.value("swDraftFacePropagationType_e", "swFacePropTangent") == 1
    assert swconst.value("swDraftFacePropagationType_e", "swFacePropAllLoops") == 2
    assert swconst.value("swDraftFacePropagationType_e", "swFacePropInnerLoops") == 3
    assert swconst.value("swDraftFacePropagationType_e", "swFacePropOuterLoops") == 4


def test_a_draft_needs_a_neutral_reference():
    with pytest.raises(ValidationError, match="neutral_ref or neutral_standard_plane"):
        DraftArgs(angle=5, face_refs=[REF])


def test_a_draft_refuses_two_neutral_references():
    """Naming both would leave the handler quietly preferring one of them."""
    with pytest.raises(ValidationError, match="not both"):
        DraftArgs(
            angle=5, neutral_ref=REF, neutral_standard_plane="top", face_refs=[REF]
        )


def test_parting_line_drafting_needs_edges():
    with pytest.raises(ValidationError, match="needs edge_refs"):
        DraftArgs(method="parting_line", angle=5, neutral_standard_plane="top")


def test_neutral_plane_drafting_needs_faces_or_a_body():
    with pytest.raises(ValidationError, match="needs face_refs"):
        DraftArgs(method="neutral_plane", angle=5, neutral_standard_plane="top")

    assert DraftArgs(
        method="neutral_plane", angle=5, neutral_standard_plane="top", body_draft=True
    ).body_draft


def test_a_draft_angle_reaches_the_handler_in_radians():
    assert DraftArgs(
        angle=45, neutral_standard_plane="top", face_refs=[REF]
    ).angle == pytest.approx(0.7853981633974483)


def test_the_draft_default_is_the_unflipped_outward_direction():
    """Unflipped adds material — measured, and the opposite of the obvious guess."""
    assert DraftArgs(angle=5, neutral_standard_plane="top", face_refs=[REF]).flip is False


# --- slots --------------------------------------------------------------------


def test_slot_creation_types_match_the_solidworks_enum():
    for name, value in (
        ("slot_straight", "swSketchSlotCreationType_line"),
        ("slot_centerpoint", "swSketchSlotCreationType_center_line"),
        ("slot_arc", "swSketchSlotCreationType_arc"),
        ("slot_3point_arc", "swSketchSlotCreationType_3pointarc"),
    ):
        assert _SLOT_CREATION_TYPES[name] == swconst.value("swSketchSlotCreationType_e", value)


def test_slot_length_types_match_the_solidworks_enum():
    assert _SLOT_LENGTH_TYPES["center_to_center"] == swconst.value(
        "swSketchSlotLengthType_e", "swSketchSlotLengthType_CenterCenter"
    )
    assert _SLOT_LENGTH_TYPES["overall"] == swconst.value(
        "swSketchSlotLengthType_e", "swSketchSlotLengthType_FullLength"
    )


def test_every_slot_form_defaults_to_no_dimension():
    """length_type only becomes observable once a dimension is added; default is off."""
    straight = SlotStraightEntity(start=[0, 0], end=[10, 0], width=4)
    centre = SlotCenterpointEntity(center=[0, 0], end=[5, 0], width=4)
    arc = SlotArcEntity(center=[0, 0], start=[5, 0], end=[0, 5], width=3)
    three = SlotArc3PointEntity(start=[0, 0], end=[10, 0], through=[5, 3], width=3)

    for entity in (straight, centre, arc, three):
        assert entity.add_dimension is False
        assert entity.length_type == "center_to_center"


def test_a_slot_width_must_be_positive():
    for build in (
        lambda w: SlotStraightEntity(start=[0, 0], end=[10, 0], width=w),
        lambda w: SlotCenterpointEntity(center=[0, 0], end=[5, 0], width=w),
        lambda w: SlotArcEntity(center=[0, 0], start=[5, 0], end=[0, 5], width=w),
        lambda w: SlotArc3PointEntity(start=[0, 0], end=[10, 0], through=[5, 3], width=w),
    ):
        with pytest.raises(ValidationError):
            build(0)


def test_the_arc_slot_carries_a_sweep_direction():
    """CenterArcDirection is only read for the centre-point arc slot, so only it has one."""
    assert SlotArcEntity(
        center=[0, 0], start=[5, 0], end=[0, 5], width=3
    ).direction == "counterclockwise"
    assert not hasattr(SlotStraightEntity(start=[0, 0], end=[1, 0], width=1), "direction")
