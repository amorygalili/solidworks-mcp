"""Mate logic that needs no SOLIDWORKS: enum mappings and schema guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.com import swconst
from swmcp.handlers.mate import _ALIGNMENT_NAMES, _ALIGNMENTS, _MATE_TYPES, _TYPE_NAMES
from swmcp.schemas.mate import MateAddArgs

REF = {"kind": "face", "document": {"path": r"C:\cad\part.SLDPRT"}}


def _refs() -> list[dict]:
    return [REF, REF]


# --- the inverted success code -------------------------------------------------


def test_no_error_is_one_not_zero():
    """The trap in AddMate5: zero means *unknown error*, not success.

    Testing an out-status for zero is the reflex for COM error codes, and here it would
    call every successful mate a failure and every unknown failure a success.
    """
    assert swconst.value("swAddMateError_e", "swAddMateError_NoError") == 1
    assert swconst.value("swAddMateError_e", "swAddMateError_ErrorUknown") == 0


def test_the_documented_failure_reasons_all_exist():
    """The handler's remediation names these, so they must be real."""
    for member in (
        "swAddMateError_IncorrectSelections",
        "swAddMateError_IncorrectAlignment",
        "swAddMateError_OverDefinedAssembly",
    ):
        assert isinstance(swconst.value("swAddMateError_e", member), int)


# --- enum mappings --------------------------------------------------------------


@pytest.mark.parametrize("member", sorted(_MATE_TYPES.values()))
def test_every_mate_type_names_a_real_enum_member(member):
    assert isinstance(swconst.value("swMateType_e", member), int)


@pytest.mark.parametrize("member", sorted(_ALIGNMENTS.values()))
def test_every_alignment_names_a_real_enum_member(member):
    assert isinstance(swconst.value("swMateAlign_e", member), int)


def test_the_type_map_covers_exactly_the_schema_literals():
    literals = set(MateAddArgs.model_fields["mate_type"].annotation.__args__)
    assert set(_MATE_TYPES) == literals


def test_the_alignment_map_covers_exactly_the_schema_literals():
    literals = set(MateAddArgs.model_fields["alignment"].annotation.__args__)
    assert set(_ALIGNMENTS) == literals


def test_type_names_invert_without_collisions():
    """Two mate types sharing a value would make a read-back report the wrong one."""
    values = [swconst.value("swMateType_e", m) for m in _MATE_TYPES.values()]
    assert len(set(values)) == len(values)
    for name, member in _MATE_TYPES.items():
        assert _TYPE_NAMES[swconst.value("swMateType_e", member)] == name


def test_alignment_names_invert_without_collisions():
    """swMateAlign_e has two overlapping families; only the swMateAlign* ones are used."""
    values = [swconst.value("swMateAlign_e", m) for m in _ALIGNMENTS.values()]
    assert len(set(values)) == len(values)
    for name, member in _ALIGNMENTS.items():
        assert _ALIGNMENT_NAMES[swconst.value("swMateAlign_e", member)] == name


def test_unsupported_mate_types_are_absent_from_the_schema():
    """Width, gear, cam and friends need more than two selections; the schema says no."""
    literals = set(MateAddArgs.model_fields["mate_type"].annotation.__args__)
    for unsupported in ("width", "symmetric", "gear", "cam", "slot", "path", "screw"):
        assert unsupported not in literals


# --- schema guards ---------------------------------------------------------------


def test_a_mate_needs_exactly_two_references():
    with pytest.raises(ValidationError):
        MateAddArgs(mate_type="coincident", refs=[REF])
    with pytest.raises(ValidationError):
        MateAddArgs(mate_type="coincident", refs=[REF, REF, REF])
    assert MateAddArgs(mate_type="coincident", refs=_refs())


def test_a_distance_mate_needs_a_distance():
    with pytest.raises(ValidationError, match="needs a distance"):
        MateAddArgs(mate_type="distance", refs=_refs())


def test_an_angle_mate_needs_an_angle():
    with pytest.raises(ValidationError, match="needs an angle"):
        MateAddArgs(mate_type="angle", refs=_refs())


def test_limits_must_be_given_as_a_pair():
    with pytest.raises(ValidationError, match="both distance_min and distance_max"):
        MateAddArgs(mate_type="distance", refs=_refs(), distance=10, distance_min=5)
    with pytest.raises(ValidationError, match="both angle_min and angle_max"):
        MateAddArgs(mate_type="angle", refs=_refs(), angle=30, angle_max=45)


def test_a_reversed_limit_range_is_rejected():
    with pytest.raises(ValidationError, match="must not exceed"):
        MateAddArgs(
            mate_type="distance", refs=_refs(), distance=10, distance_min=40, distance_max=5
        )


def test_a_plain_mate_needs_no_value():
    args = MateAddArgs(mate_type="coincident", refs=_refs())
    assert args.distance is None
    assert args.angle is None
    assert args.alignment == "closest"
    assert args.flip is False
    assert args.for_positioning_only is False


def test_lengths_and_angles_reach_the_handler_in_api_units():
    args = MateAddArgs(mate_type="distance", refs=_refs(), distance=15)
    assert args.distance == pytest.approx(0.015)
    angled = MateAddArgs(mate_type="angle", refs=_refs(), angle=45)
    assert angled.angle == pytest.approx(0.7853981633974483)
