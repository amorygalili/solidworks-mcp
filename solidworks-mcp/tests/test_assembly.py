"""Assembly logic that needs no SOLIDWORKS: enum mappings and schema guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.com import swconst
from swmcp.handlers.assembly import _STATE_NAMES, _SUPPRESSION_STATES
from swmcp.schemas.assembly import AsmComponentSetArgs, AsmInsertArgs, AsmTreeArgs

# --- suppression states --------------------------------------------------------


@pytest.mark.parametrize("member", sorted(_SUPPRESSION_STATES.values()))
def test_every_suppression_name_maps_to_a_real_enum_member(member):
    assert isinstance(swconst.value("swComponentSuppressionState_e", member), int)


def test_the_suppression_map_covers_exactly_the_schema_literals():
    literals = set(AsmComponentSetArgs.model_fields["suppression"].annotation.__args__[0].__args__)
    assert set(_SUPPRESSION_STATES) == literals


def test_state_names_invert_the_mapping_without_collisions():
    """Two names sharing a value would make a read-back report the wrong state."""
    values = [swconst.value("swComponentSuppressionState_e", m) for m in _SUPPRESSION_STATES.values()]
    assert len(set(values)) == len(values)
    for name, member in _SUPPRESSION_STATES.items():
        assert _STATE_NAMES[swconst.value("swComponentSuppressionState_e", member)] == name


def test_an_unknown_state_is_reported_rather_than_guessed():
    """swComponentInternalIdMismatch is real and is not one of the four this maps."""
    mismatch = swconst.value("swComponentSuppressionState_e", "swComponentInternalIdMismatch")
    assert mismatch not in _STATE_NAMES, "an unmapped state must fall through to unknown()"


# --- the two visibility enums --------------------------------------------------


def test_component_and_feature_visibility_enums_disagree():
    """The trap this pins: 1 means *visible* for a component and *hidden* for a feature.

    IComponent2::Visible is swComponentVisibilityState_e (0 hidden, 1 visible), while
    IFeature::Visible is swVisibilityState_e (1 hidden, 2 shown). Reusing one decoder
    for both would report every hidden feature as visible, and bool() is useless for
    either.
    """
    assert swconst.value("swComponentVisibilityState_e", "swComponentVisible") == 1
    assert swconst.value("swComponentVisibilityState_e", "swComponentHidden") == 0
    assert swconst.value("swVisibilityState_e", "swVisibilityStateHide") == 1
    assert swconst.value("swVisibilityState_e", "swVisibilityStateShown") == 2


# --- schema guards --------------------------------------------------------------


def test_a_component_path_is_required():
    with pytest.raises(ValidationError):
        AsmInsertArgs(component_path="")


def test_a_position_needs_three_coordinates():
    with pytest.raises(ValidationError):
        AsmInsertArgs(component_path="C:/a.SLDPRT", at=[0, 0])
    with pytest.raises(ValidationError):
        AsmInsertArgs(component_path="C:/a.SLDPRT", at=[0, 0, 0, 0])
    assert AsmInsertArgs(component_path="C:/a.SLDPRT", at=[1, 2, 3]).at == [0.001, 0.002, 0.003]


def test_the_default_position_is_the_origin_and_unfixed():
    args = AsmInsertArgs(component_path="C:/a.SLDPRT")
    assert args.at == [0.0, 0.0, 0.0]
    assert args.fixed is False
    assert args.configuration is None


def test_tree_depth_is_bounded():
    with pytest.raises(ValidationError):
        AsmTreeArgs(max_depth=0)
    with pytest.raises(ValidationError):
        AsmTreeArgs(max_depth=65)
    assert AsmTreeArgs().max_depth == 16


def test_the_tree_walks_subassemblies_by_default():
    assert AsmTreeArgs().top_level_only is False


def test_a_component_set_needs_a_name():
    with pytest.raises(ValidationError):
        AsmComponentSetArgs(component_name="", visible=False)


def test_a_component_set_may_change_nothing():
    """All four fields optional: a caller may legitimately probe without mutating."""
    args = AsmComponentSetArgs(component_name="block-1")
    assert args.suppression is None
    assert args.fixed is None
    assert args.visible is None
    assert args.configuration is None
