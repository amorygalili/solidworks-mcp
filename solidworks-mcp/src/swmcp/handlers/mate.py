"""Assembly mates (MATE-001 to MATE-004).

``AddMate5`` reports through an ``[out]`` status rather than by returning nothing, and
that status is the trap here: ``swAddMateError_NoError`` is **1**, while **0** is
``swAddMateError_ErrorUknown``. Testing the status for zero — the reflex for a COM
error code — would read every successful mate as a failure and every unknown failure as
a success. The status is compared against the named constant instead.
"""

from __future__ import annotations

import contextlib
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import (
    call_with_outparams,
    normalize_sequence,
    null_dispatch,
    out_long,
    try_com_member,
)
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error
from swmcp.refs.resolve import resolve
from swmcp.schemas.mate import (
    InterferenceCheckArgs,
    InterferenceCheckResult,
    MateAddArgs,
    MateAddResult,
    MateDeleteArgs,
    MateDeleteResult,
    MateEditArgs,
    MateEditResult,
    MateListArgs,
    MateListResult,
)
from swmcp.units import from_meters, from_radians

_MATE_TYPES = {
    "coincident": "swMateCOINCIDENT",
    "concentric": "swMateCONCENTRIC",
    "perpendicular": "swMatePERPENDICULAR",
    "parallel": "swMatePARALLEL",
    "tangent": "swMateTANGENT",
    "distance": "swMateDISTANCE",
    "angle": "swMateANGLE",
    "lock": "swMateLOCK",
}

_ALIGNMENTS = {
    "aligned": "swMateAlignALIGNED",
    "anti_aligned": "swMateAlignANTI_ALIGNED",
    "closest": "swMateAlignCLOSEST",
}

_TYPE_NAMES = {
    swconst.value("swMateType_e", member): name for name, member in _MATE_TYPES.items()
}
_ALIGNMENT_NAMES = {
    swconst.value("swMateAlign_e", member): name for name, member in _ALIGNMENTS.items()
}


def _mate_features(doc: Any) -> list[Any]:
    """The mate features, which live as subfeatures of the MateGroup, not in the tree."""
    found: list[Any] = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 2000:
        guard += 1
        if str(try_com_member(feature, "GetTypeName2", default="") or "") == "MateGroup":
            sub = try_com_member(feature, "GetFirstSubFeature", default=None)
            inner = 0
            while sub is not None and inner < 2000:
                inner += 1
                found.append(sub)
                sub = try_com_member(sub, "GetNextSubFeature", default=None)
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return found


def _describe_mate(feature: Any) -> dict[str, Any]:
    mate = try_com_member(feature, "GetSpecificFeature2", default=None)
    raw_type = try_com_member(mate, "Type", default=None)
    raw_alignment = try_com_member(mate, "Alignment", default=None)
    count = int(try_com_member(mate, "GetMateEntityCount", default=0) or 0)

    components: list[str] = []
    for index in range(count):
        entity = try_com_member(mate, "MateEntity", index, default=None)
        component = try_com_member(entity, "ReferenceComponent", default=None)
        name = str(try_com_member(component, "Name2", default="") or "")
        if name:
            components.append(name)

    entry: dict[str, Any] = {
        "name": str(try_com_member(feature, "Name", default="") or ""),
        "type": _TYPE_NAMES.get(
            raw_type, swconst.name_of("swMateType_e", raw_type) if raw_type is not None else None
        ),
        "alignment": _ALIGNMENT_NAMES.get(raw_alignment, raw_alignment),
        "flipped": bool(try_com_member(mate, "Flipped", default=False)),
        "suppressed": bool(try_com_member(feature, "IsSuppressed", default=False)),
        "entity_count": count,
        "components": components,
        "can_be_flipped": bool(try_com_member(mate, "CanBeFlipped", default=False)),
    }

    # Limit mates carry their range here; an ordinary mate reports zeros, so the pair is
    # only reported when it describes an actual range.
    low = try_com_member(mate, "MinimumVariation", default=None)
    high = try_com_member(mate, "MaximumVariation", default=None)
    if isinstance(low, (int, float)) and isinstance(high, (int, float)) and high != low:
        entry["limit_min"] = float(low)
        entry["limit_max"] = float(high)

    # SystemValue is metres/radians; Value is whatever the document is displaying in,
    # which on this install is inches — a distance mate of 15 mm read back as 0.5906.
    # The rest of the server reads SystemValue for exactly this reason.
    dimension = try_com_member(mate, "DisplayDimension2", 0, default=None)
    value = try_com_member(
        try_com_member(dimension, "GetDimension2", 0, default=None), "SystemValue", default=None
    )
    if isinstance(value, (int, float)):
        entry["value"] = float(value)
        # An angle mate's value is radians and a distance mate's is metres, so only the
        # meaningful conversion is reported rather than both.
        if entry["type"] == "angle":
            entry["value_deg"] = round(from_radians(float(value)), 9)
        else:
            entry["value_mm"] = round(from_meters(float(value)), 9)
    return entry


@op(
    name="sw_mate_add",
    tier="core",
    domains=("assembly",),
    tags=("mate", "assembly", "constraint"),
    summary=(
        "Mate two entities with a coincident, concentric, parallel, perpendicular, "
        "tangent, distance, angle, or lock mate, verified by reading the mate back."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("MATE-001", "MATE-002", "MATE-003"),
    precondition="assembly",
    idempotent=False,
    timeout_s=300.0,
)
def mate_add(ctx: OpContext, args: MateAddArgs) -> MateAddResult:
    doc = ctx.require_doc()
    before = _mate_features(doc)
    before_names = {str(try_com_member(f, "Name", default="") or "") for f in before}

    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = 0
    for ref in args.refs:
        resolution = resolve(ctx.session, doc, ref, max_candidates=ctx.config.max_candidates)
        if try_com_member(resolution.entity, "Select4", True, null_dispatch(), default=False):
            selected += 1
    if selected != 2:
        try_com_member(doc, "ClearSelection2", True, default=None)
        raise SwMcpError(
            make_error(
                "REFERENCE_NOT_SELECTABLE",
                "reference",
                f"Selected {selected} of 2 mate references.",
                remediation=[
                    "Both entities must still exist; re-capture them with sw_probe_faces.",
                    "A mate needs entities on two different components.",
                ],
            )
        )

    status = out_long(0)
    mate, outs = call_with_outparams(
        doc.AddMate5,
        swconst.value("swMateType_e", _MATE_TYPES[args.mate_type]),
        swconst.value("swMateAlign_e", _ALIGNMENTS[args.alignment]),
        args.flip,
        float(args.distance or 0.0),
        float(args.distance_max or 0.0),
        float(args.distance_min or 0.0),
        1.0,
        1.0,
        float(args.angle or 0.0),
        float(args.angle_max or 0.0),
        float(args.angle_min or 0.0),
        args.for_positioning_only,
        args.lock_rotation,
        0,
        status,
        outparams=[status],
    )
    try_com_member(doc, "ClearSelection2", True, default=None)

    code = outs[0] if outs else None
    no_error = swconst.value("swAddMateError_e", "swAddMateError_NoError")
    after = _mate_features(doc)

    if mate is None or code != no_error:
        raise SwMcpError(
            make_error(
                "MATE_FAILED",
                "solidworks",
                f"SOLIDWORKS refused the {args.mate_type} mate: "
                f"{swconst.name_of('swAddMateError_e', code) or code}.",
                context={
                    "mate_type": args.mate_type,
                    "alignment": args.alignment,
                    "error_status": code,
                    "error_name": swconst.name_of("swAddMateError_e", code),
                },
                remediation=[
                    "IncorrectSelections means the two entities cannot take this mate — "
                    "a concentric mate needs cylindrical faces or axes, for example.",
                    "IncorrectAlignment means the mate is possible but not the way round "
                    "that was asked; try alignment='closest'.",
                    "OverDefinedAssembly means the components are already fully "
                    "constrained by existing mates.",
                ],
            )
        )

    fresh = [
        f
        for f in after
        if str(try_com_member(f, "Name", default="") or "") not in before_names
    ]
    feature = fresh[-1] if fresh else None
    if args.name and feature is not None:
        feature.Name = args.name

    described = _describe_mate(feature) if feature is not None else {}
    return MateAddResult(
        mate_name=described.get("name", ""),
        mate_type=described.get("type") or args.mate_type,
        alignment=str(described.get("alignment", args.alignment)),
        flipped=bool(described.get("flipped", False)),
        entity_count=int(described.get("entity_count", 0)),
        components=described.get("components", []),
        mates_before=len(before),
        mates_after=len(after),
        verification=Verification(
            read_back=True,
            before={"mate_count": len(before)},
            after={"mate_count": len(after), **described},
            checks=[
                Check(
                    name="mate_reported_no_error",
                    passed=code == no_error,
                    detail=f"{swconst.name_of('swAddMateError_e', code)} ({code})",
                ),
                Check(
                    name="mate_is_in_the_tree",
                    # for_positioning_only moves the component and deliberately leaves
                    # no mate behind, so the tree is not expected to grow then.
                    passed=(len(after) > len(before)) or args.for_positioning_only,
                    detail=f"{len(before)} -> {len(after)} mate(s)",
                ),
                Check(
                    name="mate_type_reads_back",
                    passed=described.get("type") == args.mate_type
                    if described
                    else args.for_positioning_only,
                    detail=f"{described.get('type')!r} vs requested {args.mate_type!r}",
                ),
            ],
        ),
        warnings=(
            ["for_positioning_only was set, so the component moved but no mate was kept."]
            if args.for_positioning_only
            else []
        ),
    )


@op(
    name="sw_mate_list",
    tier="core",
    domains=("assembly",),
    tags=("mate", "assembly", "inspect"),
    summary=(
        "List the assembly's mates with type, alignment, flip, suppression, the "
        "components they join, and any limit range or driving value."
    ),
    safety=ReadSafety(),
    satisfies=("MATE-004",),
    precondition="assembly",
    idempotent=True,
    timeout_s=300.0,
)
def mate_list(ctx: OpContext, args: MateListArgs) -> MateListResult:
    _ = args
    doc = ctx.require_doc()
    mates = [_describe_mate(feature) for feature in _mate_features(doc)]
    return MateListResult(
        mate_count=len(mates),
        mates=mates,
        suppressed_count=sum(1 for mate in mates if mate["suppressed"]),
    )


# --- editing and interference --------------------------------------------------

_SUPPRESS_ACTIONS = {True: "swSuppressFeature", False: "swUnSuppressFeature"}

#: The interference manager's options, paired with the schema field that drives each.
_INTERFERENCE_FLAGS = (
    ("TreatCoincidenceAsInterference", "treat_coincidence_as_interference"),
    ("IgnoreHiddenBodies", "ignore_hidden_bodies"),
    ("TreatSubAssembliesAsComponents", "treat_subassemblies_as_components"),
    ("IncludeMultibodyPartInterferences", "include_multibody_part_interferences"),
)


def _find_mate(doc: Any, name: str) -> Any | None:
    for feature in _mate_features(doc):
        if str(try_com_member(feature, "Name", default="") or "") == name:
            return feature
    return None


@op(
    name="sw_mate_edit",
    tier="extended",
    domains=("assembly",),
    tags=("mate", "assembly", "rename", "suppress"),
    summary=(
        "Rename a mate or change its suppression, verified by reading the mate list "
        "back rather than trusting the call."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("MATE-006",),
    precondition="assembly",
    idempotent=True,
    timeout_s=300.0,
)
def mate_edit(ctx: OpContext, args: MateEditArgs) -> MateEditResult:
    """MATE-006's non-destructive half.

    A mate is a *subfeature* of the MateGroup rather than a top-level feature, which is
    why sw_feature_edit cannot reach it — that walks the tree, and a mate is not on it.

    Deleting lives in sw_mate_delete instead of behind a flag here. Folding both into
    one tool meant marking the whole thing destructive, and then renaming a mate
    demanded a confirmation it had no business demanding.
    """
    doc = ctx.require_doc()
    before = _mate_features(doc)
    feature = _find_mate(doc, args.mate_name)
    if feature is None:
        raise SwMcpError(
            make_error(
                "MATE_NOT_FOUND",
                "validation",
                f"This assembly has no mate named {args.mate_name!r}.",
                remediation=["Use sw_mate_list to see the mate names."],
            )
        )

    renamed_to = None
    if args.rename_to:
        feature.Name = args.rename_to
        renamed_to = args.rename_to
        feature = _find_mate(doc, args.rename_to) or feature

    if args.suppressed is not None:
        try_com_member(
            feature,
            "SetSuppression2",
            swconst.value("swFeatureSuppressionAction_e", _SUPPRESS_ACTIONS[args.suppressed]),
            swconst.value("swInConfigurationOpts_e", "swThisConfiguration"),
            null_dispatch(),
            default=None,
        )

    final_name = renamed_to or args.mate_name
    after = _mate_features(doc)
    surviving = _find_mate(doc, final_name)
    suppressed = (
        bool(try_com_member(surviving, "IsSuppressed", default=False))
        if surviving is not None
        else False
    )

    checks = [
        Check(name="mate_still_present", passed=surviving is not None, detail=final_name)
    ]
    if args.rename_to:
        checks.append(
            Check(
                name="rename_applied",
                passed=surviving is not None,
                detail=f"{args.mate_name} -> {args.rename_to}",
            )
        )
    if args.suppressed is not None:
        checks.append(
            Check(
                name="suppression_applied",
                passed=suppressed == args.suppressed,
                detail=f"suppressed={suppressed}",
            )
        )

    return MateEditResult(
        mate_name=final_name,
        suppressed=suppressed,
        renamed_to=renamed_to,
        mates_before=len(before),
        mates_after=len(after),
        verification=Verification(
            read_back=True,
            before={"mate_count": len(before), "name": args.mate_name},
            after={"mate_count": len(after), "name": final_name, "suppressed": suppressed},
            checks=checks,
        ),
    )


@op(
    name="sw_mate_delete",
    tier="extended",
    domains=("assembly",),
    tags=("mate", "assembly", "delete"),
    summary=(
        "Delete one mate and verify it is gone from the mate list. Removing a mate can "
        "let components move, so it requires confirmation."
    ),
    safety=ModelMutation(destructive=True),
    partially_satisfies=("MATE-006",),
    precondition="assembly",
    idempotent=False,
    timeout_s=300.0,
)
def mate_delete(ctx: OpContext, args: MateDeleteArgs) -> MateDeleteResult:
    doc = ctx.require_doc()
    before = _mate_features(doc)
    feature = _find_mate(doc, args.mate_name)
    if feature is None:
        raise SwMcpError(
            make_error(
                "MATE_NOT_FOUND",
                "validation",
                f"This assembly has no mate named {args.mate_name!r}.",
                remediation=["Use sw_mate_list to see the mate names."],
            )
        )

    try_com_member(doc, "ClearSelection2", True, default=None)
    if not try_com_member(feature, "Select2", False, 0, default=False):
        raise SwMcpError(
            make_error(
                "MATE_NOT_SELECTABLE",
                "reference",
                f"Could not select {args.mate_name!r} to delete it.",
            )
        )
    try_com_member(
        doc.Extension,
        "DeleteSelection2",
        swconst.value("swDeleteSelectionOptions_e", "swDelete_Absorbed"),
        default=None,
    )
    try_com_member(doc, "ClearSelection2", True, default=None)

    after = _mate_features(doc)
    gone = _find_mate(doc, args.mate_name) is None

    return MateDeleteResult(
        mate_name=args.mate_name,
        deleted=gone,
        mates_before=len(before),
        mates_after=len(after),
        verification=Verification(
            read_back=True,
            before={"mate_count": len(before)},
            after={"mate_count": len(after)},
            checks=[
                Check(
                    name="mate_removed",
                    passed=gone,
                    detail=f"{args.mate_name} is gone"
                    if gone
                    else "the mate is still in the assembly",
                ),
                Check(
                    name="mate_count_fell",
                    passed=len(after) < len(before),
                    detail=f"{len(before)} -> {len(after)} mate(s)",
                ),
            ],
        ),
    )


@op(
    name="sw_interference_check",
    tier="core",
    domains=("assembly",),
    tags=("interference", "clearance", "assembly", "review"),
    summary=(
        "Find where components overlap, reporting each interference's volume and the "
        "components involved rather than a pass/fail verdict."
    ),
    safety=ReadSafety(),
    partially_satisfies=("MATE-008",),
    precondition="assembly",
    idempotent=True,
    timeout_s=600.0,
)
def interference_check(
    ctx: OpContext, args: InterferenceCheckArgs
) -> InterferenceCheckResult:
    """MATE-008 for interference. Clearance verification is a different manager.

    The volume is the point: a boolean "they interfere" tells a caller nothing about
    whether it is a rounding artefact or a real collision. Two 30 x 20 x 10 blocks
    overlapping by 10 mm report 2000 mm3 exactly, which is what the live test checks.
    """
    doc = ctx.require_doc()
    manager = try_com_member(doc, "InterferenceDetectionManager", default=None)
    if manager is None:
        raise SwMcpError(
            make_error(
                "INTERFERENCE_UNAVAILABLE",
                "solidworks",
                "SOLIDWORKS did not provide an interference detection manager.",
                remediation=["Interference detection needs an assembly document."],
            )
        )

    settings: dict[str, bool] = {}
    for member, field in _INTERFERENCE_FLAGS:
        wanted = bool(getattr(args, field))
        # An option this build refuses to set is reported as it actually reads back,
        # rather than echoing what the caller asked for.
        with contextlib.suppress(Exception):
            setattr(manager, member, wanted)
        settings[field] = bool(try_com_member(manager, member, default=wanted))

    count = int(try_com_member(manager, "GetInterferenceCount", default=0) or 0)
    found = normalize_sequence(try_com_member(manager, "GetInterferences", default=None))

    interferences = []
    total = 0.0
    for item in found:
        volume = try_com_member(item, "Volume", default=None)
        volume_m3 = float(volume) if isinstance(volume, (int, float)) else 0.0
        total += volume_m3
        interferences.append(
            {
                "volume_m3": volume_m3,
                "volume_mm3": round(volume_m3 * 1e9, 6),
                "component_count": int(try_com_member(item, "GetComponentCount", default=0) or 0),
                "components": [
                    str(try_com_member(component, "Name2", default="") or "")
                    for component in normalize_sequence(
                        try_com_member(item, "Components", default=None)
                    )
                ],
                # A "possible" interference is one SOLIDWORKS could not decide on, which
                # is not the same as a real overlap and is reported separately.
                "possible_only": bool(
                    try_com_member(item, "IsPossibleInterference", default=False)
                ),
                "is_fastener": bool(try_com_member(item, "IsFastener", default=False)),
            }
        )

    # Done() releases the manager's UI state; skipping it leaves the assembly in
    # interference-detection mode.
    try_com_member(manager, "Done", default=None)

    warnings = []
    if count != len(interferences):
        warnings.append(
            f"SOLIDWORKS reported {count} interference(s) but returned "
            f"{len(interferences)}; the listing may be incomplete."
        )

    return InterferenceCheckResult(
        interference_count=len(interferences),
        total_volume_mm3=round(total * 1e9, 6),
        interferences=interferences,
        settings=settings,
        warnings=warnings,
    )
