"""Sweep and loft logic that needs no SOLIDWORKS: enum mappings and schema guards.

Gate 1 in `CLAUDE.md`. Every name in the three mapping tables is resolved against the
generated constants here, so a typo in an enum member is a 6-second failure rather than
something found minutes into a live run — or, worse, at runtime in a user's session.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.com import swconst
from swmcp.handlers.feature import (
    _LOFT_TANGENCY,
    _SWEEP_DIRECTION,
    _SWEEP_ORIENTATION,
    _THIN_WALL_TYPES,
)
from swmcp.schemas.feature import LoftArgs, SweepArgs

REF = {"kind": "edge", "document": {"path": r"C:\cad\part.SLDPRT"}}


# --- the enum mappings --------------------------------------------------------


@pytest.mark.parametrize("member", sorted(_SWEEP_ORIENTATION.values()))
def test_every_orientation_names_a_real_twist_control(member):
    assert isinstance(swconst.value("swTwistControlType_e", member), int)


@pytest.mark.parametrize("member", sorted(_SWEEP_DIRECTION.values()))
def test_every_direction_names_a_real_sweep_direction(member):
    assert isinstance(swconst.value("swSweepDirection_e", member), int)


@pytest.mark.parametrize("member", sorted(_THIN_WALL_TYPES.values()))
def test_every_thin_direction_names_a_real_wall_type(member):
    assert isinstance(swconst.value("swThinWallType_e", member), int)


def test_the_mappings_cover_exactly_what_the_schema_offers():
    """A literal the schema accepts but the handler cannot map is a KeyError at runtime."""
    fields = SweepArgs.model_fields
    assert set(_SWEEP_ORIENTATION) == set(fields["orientation"].annotation.__args__)
    assert set(_SWEEP_DIRECTION) == set(fields["direction"].annotation.__args__)
    assert set(_THIN_WALL_TYPES) == set(fields["thin_direction"].annotation.__args__)
    assert set(_LOFT_TANGENCY) == set(
        LoftArgs.model_fields["start_tangency"].annotation.__args__
    )


def test_loft_tangency_is_not_the_swTangencyType_enum():
    """Loft documents a plain 0-4 scale that disagrees with swTangencyType_e past 0.

    Pinning the disagreement stops someone "fixing" the table by pointing it at the
    enum whose names happen to match.
    """
    assert _LOFT_TANGENCY["normal_to_profile"] == 1
    assert _LOFT_TANGENCY["direction_vector"] == 2
    assert swconst.value("swTangencyType_e", "swTangencyDirectionVector") == 2
    assert swconst.value("swTangencyType_e", "swTangencyNormalToProfile") == 1
    # They agree here, but the sweep path uses the enum and loft uses the literal scale;
    # the two are only interchangeable by coincidence, so neither reads the other's table.
    assert _LOFT_TANGENCY["all_faces"] == 3


# --- sweep schema guards ------------------------------------------------------


def test_a_sweep_needs_exactly_one_path():
    with pytest.raises(ValidationError, match="exactly one of path_sketch or path_ref"):
        SweepArgs(profile_sketch="Profile")
    with pytest.raises(ValidationError, match="exactly one of path_sketch or path_ref"):
        SweepArgs(profile_sketch="Profile", path_sketch="Path", path_ref=REF)


def test_either_path_form_is_accepted_on_its_own():
    assert SweepArgs(profile_sketch="P", path_sketch="Path").path_sketch == "Path"
    assert SweepArgs(profile_sketch="P", path_ref=REF).path_ref is not None


def test_a_constant_twist_without_an_angle_is_rejected():
    """Otherwise the twist silently becomes zero and the sweep looks merely wrong."""
    with pytest.raises(ValidationError, match="needs a twist_angle"):
        SweepArgs(
            profile_sketch="P", path_sketch="Path", orientation="constant_twist_along_path"
        )


def test_a_constant_twist_with_an_angle_is_accepted():
    args = SweepArgs(
        profile_sketch="P",
        path_sketch="Path",
        orientation="constant_twist_along_path",
        twist_angle=45,
    )
    assert args.twist_angle == pytest.approx(0.7853981633974483)


def test_the_thin_wall_default_is_the_measured_one():
    """SOLIDWORKS grows a one-direction wall outward; the default says so out loud."""
    assert SweepArgs(profile_sketch="P", path_sketch="Path").thin_direction == "outward"
    assert _THIN_WALL_TYPES["outward"] == "swThinWallOneDirection"
    assert _THIN_WALL_TYPES["inward"] == "swThinWallOppDirection"


def test_a_sweep_profile_cannot_be_blank():
    with pytest.raises(ValidationError):
        SweepArgs(profile_sketch="", path_sketch="Path")


# --- loft schema guards -------------------------------------------------------


def test_a_loft_needs_at_least_two_profiles():
    with pytest.raises(ValidationError):
        LoftArgs(profile_sketches=["Only"])


def test_a_loft_rejects_a_repeated_profile():
    """The same sketch twice cannot define two sections, and SOLIDWORKS will not say so."""
    with pytest.raises(ValidationError, match="must not repeat"):
        LoftArgs(profile_sketches=["A", "B", "A"])


def test_a_loft_keeps_the_profile_order_it_was_given():
    """Order is the shape: SOLIDWORKS lofts in selection order, not tree order."""
    args = LoftArgs(profile_sketches=["Top", "Middle", "Bottom"])
    assert args.profile_sketches == ["Top", "Middle", "Bottom"]


def test_loft_defaults_are_the_conservative_ones():
    args = LoftArgs(profile_sketches=["A", "B"])
    assert args.closed is False
    assert args.keep_tangency is True
    assert args.start_tangency == "none"
    assert args.end_tangency == "none"
    assert args.merge_result is True
    assert args.thin_thickness is None
