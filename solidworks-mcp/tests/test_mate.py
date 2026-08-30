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


# --- mate editing and interference ---------------------------------------------


def test_editing_and_deleting_are_separate_tools():
    """Folding them together forced a confirmation onto renaming.

    A single tool with a `delete` flag has to be declared destructive, and the safety
    layer then demands `confirm=true` for every call — including a rename, which
    destroys nothing. The split keeps the confirmation where the risk is.
    """
    from swmcp.catalog.projection import project
    from swmcp.catalog.registry import load_all_ops

    ops = load_all_ops()
    assert project(ops["sw_mate_edit"].safety).confirm_required is False
    assert project(ops["sw_mate_delete"].safety).confirm_required is True


def test_a_mate_edit_must_change_something():
    from swmcp.schemas.mate import MateEditArgs

    with pytest.raises(ValidationError, match="nothing to do"):
        MateEditArgs(mate_name="Coincident1")
    assert MateEditArgs(mate_name="Coincident1", rename_to="Butt")
    assert MateEditArgs(mate_name="Coincident1", suppressed=True)


def test_suppression_actions_map_to_the_real_enum():
    from swmcp.handlers.mate import _SUPPRESS_ACTIONS

    assert swconst.value("swFeatureSuppressionAction_e", _SUPPRESS_ACTIONS[True]) == 0
    assert swconst.value("swFeatureSuppressionAction_e", _SUPPRESS_ACTIONS[False]) == 1


def test_interference_flags_name_real_manager_members():
    """Each flag must match both a schema field and an IInterferenceDetectionMgr member."""
    import json
    from pathlib import Path

    from swmcp.handlers.mate import _INTERFERENCE_FLAGS
    from swmcp.schemas.mate import InterferenceCheckArgs

    root = Path(__file__).resolve().parent.parent
    members = json.loads(
        (root / "src" / "swmcp" / "generated" / "swapi.json").read_text(encoding="utf-8")
    )["interfaces"]["IInterferenceDetectionMgr"]

    for member, field in _INTERFERENCE_FLAGS:
        assert member in members, f"{member} is not on IInterferenceDetectionMgr"
        assert field in InterferenceCheckArgs.model_fields, f"{field} is not a schema field"


def test_interference_defaults_match_solidworks_own():
    """Measured defaults: every option off. Silently changing them would surprise."""
    from swmcp.schemas.mate import InterferenceCheckArgs

    args = InterferenceCheckArgs()
    assert args.treat_coincidence_as_interference is False
    assert args.ignore_hidden_bodies is False
    assert args.treat_subassemblies_as_components is False
    assert args.include_multibody_part_interferences is False


# --- probing a mate before building it (MATE-005) --------------------------------


def test_every_mate_type_has_a_compatibility_rule():
    """A mate the schema offers but the rules do not know would be judged as unknown."""
    from swmcp.handlers.mate import _MATE_RULES, _MATE_TYPES

    assert set(_MATE_RULES) == set(_MATE_TYPES)


def test_the_entity_classes_used_by_the_rules_are_all_reachable():
    """A rule naming a class no geometry maps to could never match anything."""
    from swmcp.handlers.mate import _ENTITY_CLASS, _MATE_RULES

    reachable = set(_ENTITY_CLASS.values())
    for mate_type, (allowed, requires_one) in _MATE_RULES.items():
        for group in (allowed, requires_one):
            if group is None:
                continue
            unreachable = set(group) - reachable
            assert not unreachable, f"{mate_type} allows unreachable classes {unreachable}"


def test_captured_geometry_types_are_classified():
    """Every surface and curve type a capture can emit must map to a mate class.

    An unmapped type falls through to "unknown", which no rule allows — so a perfectly
    mateable cylindrical face would be reported as unable to take a concentric mate.
    """
    from swmcp.handlers.mate import _ENTITY_CLASS
    from swmcp.refs.capture import _SURFACE_TYPE

    mateable = {"planar_face", "cylindrical_face", "conical_face", "spherical_face"}
    for geometry_type in mateable:
        assert geometry_type in _SURFACE_TYPE.values(), f"{geometry_type} is not a capture output"
        assert geometry_type in _ENTITY_CLASS, f"{geometry_type} has no mate class"


def test_two_planar_faces_can_take_a_coincident_mate_but_not_a_concentric_one():
    from swmcp.handlers.mate import _pair_reasons

    assert _pair_reasons("coincident", "plane", "plane") == []
    assert _pair_reasons("concentric", "plane", "plane")


def test_a_tangent_mate_needs_one_curved_entity():
    """The rule that needs a second clause: both sides are allowed, yet the pair is not."""
    from swmcp.handlers.mate import _pair_reasons

    assert _pair_reasons("tangent", "plane", "cylinder") == []
    reasons = _pair_reasons("tangent", "plane", "plane")
    assert reasons and "curved" in reasons[0]


def test_a_lock_mate_accepts_any_pair():
    """Lock constrains the components, not the geometry, so no pair is refused."""
    from swmcp.handlers.mate import _ENTITY_CLASS, _pair_reasons

    for entity_class in set(_ENTITY_CLASS.values()):
        assert _pair_reasons("lock", entity_class, entity_class) == []


def test_a_cylindrical_face_offers_concentric_and_a_planar_face_does_not():
    from swmcp.handlers.mate import _mate_types_for

    assert "concentric" in _mate_types_for("cylinder")
    assert "concentric" not in _mate_types_for("plane")
    assert "coincident" in _mate_types_for("plane")


def test_the_probe_never_claims_its_verdict_is_proven():
    """MATE-005 is declared partial precisely because this field cannot become true."""
    from swmcp.schemas.mate import MateProbeResult

    assert MateProbeResult(mode="pair", feasible=True).proven is False
    assert MateProbeResult(mode="candidates").proven is False


def test_probing_a_pair_needs_exactly_two_references():
    from swmcp.schemas.mate import MateProbeArgs

    with pytest.raises(ValidationError):
        MateProbeArgs(refs=[REF])
    with pytest.raises(ValidationError):
        MateProbeArgs(refs=[REF, REF, REF])
    assert MateProbeArgs(refs=[REF, REF], mate_type="coincident")


def test_listing_candidates_needs_no_references_at_all():
    from swmcp.schemas.mate import MateProbeArgs

    args = MateProbeArgs()
    assert args.refs is None
    assert args.mate_type is None
    assert args.entity_class == "face"
    assert args.limit == 25


def test_the_probe_is_read_only():
    """It must not be a side effect: it resolves references but never selects them.

    An earlier draft selected both entities to prove they were selectable, which is a
    UI change and would have made the tool a non_model_side_effect owing artifact
    evidence it has none of.
    """
    from swmcp.catalog.projection import project
    from swmcp.catalog.registry import load_all_ops

    ops = load_all_ops()
    assert project(ops["sw_mate_probe"].safety).read_only is True
    assert project(ops["sw_mate_dof"].safety).read_only is True


# --- degrees of freedom (MATE-007) ----------------------------------------------


def test_constrained_statuses_map_to_real_enum_members_without_collisions():
    from swmcp.handlers.mate import _CONSTRAINED_NAMES

    assert len(set(_CONSTRAINED_NAMES.values())) == len(_CONSTRAINED_NAMES)
    assert _CONSTRAINED_NAMES[swconst.value("swConstrainedStatus_e", "swFullyConstrained")] == (
        "fully_constrained"
    )
    assert _CONSTRAINED_NAMES[swconst.value("swConstrainedStatus_e", "swUnderConstrained")] == (
        "under_constrained"
    )


def test_the_constrained_map_covers_the_whole_enum():
    """An unmapped status would be reported as unknown(4) rather than over-constrained."""
    from swmcp.com.swconst import members
    from swmcp.handlers.mate import _CONSTRAINED_NAMES

    assert set(members("swConstrainedStatus_e").values()) == set(_CONSTRAINED_NAMES)


def test_remaining_dofs_is_called_with_the_arity_the_type_library_declares():
    """Twelve pure-out parameters; the type library accepts none or all of them."""
    from swmcp.com import apiver

    assert apiver.arities("GetRemainingDOFs") == {0, 12}
    assert apiver.interfaces_declaring("GetRemainingDOFs") == ("IComponent2",)


def test_an_unavailable_dof_answer_is_not_reported_as_available():
    from swmcp.schemas.mate import MateDofResult

    assert MateDofResult(component_count=0).remaining_dofs_available is False


def test_a_dof_report_defaults_to_every_component():
    from swmcp.schemas.mate import MateDofArgs

    assert MateDofArgs().components is None
