"""Assembly mates (MATE-001 to MATE-008).

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
    out_dispatch,
    out_long,
    try_com_member,
)
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error
from swmcp.handlers.assembly import _components
from swmcp.refs.model import EntityRef
from swmcp.refs.probes import ProbeFilters, probe_entities
from swmcp.refs.resolve import resolve
from swmcp.schemas.mate import (
    InterferenceCheckArgs,
    InterferenceCheckResult,
    MateAddArgs,
    MateAddResult,
    MateDeleteArgs,
    MateDeleteResult,
    MateDofArgs,
    MateDofResult,
    MateEditArgs,
    MateEditResult,
    MateListArgs,
    MateListResult,
    MateProbeArgs,
    MateProbeResult,
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


# --- probing and degrees of freedom ---------------------------------------------

#: How a captured geometry type behaves when SOLIDWORKS builds a mate from it.
#:
#: The names on the right are this module's own vocabulary, not ``swMateEntityType_e``.
#: That enum can only be read back off a mate that already exists — ``IMateEntity2`` is
#: reachable through ``IMate2::MateEntity`` and nowhere else — which is precisely what a
#: probe cannot do. So the classification is derived from the geometry the capture
#: already measured, and the prediction built on it is labelled as one.
_ENTITY_CLASS = {
    "planar_face": "plane",
    "plane": "plane",
    "cylindrical_face": "cylinder",
    "conical_face": "cone",
    "spherical_face": "sphere",
    "toroidal_face": "torus",
    "line_edge": "line",
    "axis": "line",
    "circular_edge": "circle",
    "vertex": "point",
    "point": "point",
}

_CURVED = frozenset({"cylinder", "cone", "sphere", "torus"})

#: For each mate: the classes both entities must belong to, and a set at least one of
#: them must come from. ``None`` means no restriction — a lock mate takes any two
#: entities, because it constrains the components rather than the geometry.
_MATE_RULES: dict[str, tuple[frozenset[str] | None, frozenset[str] | None]] = {
    "coincident": (frozenset({"plane", "line", "point", "circle"}), None),
    "concentric": (frozenset({"cylinder", "cone", "sphere", "circle", "line"}), None),
    "parallel": (frozenset({"plane", "line", "cylinder", "cone"}), None),
    "perpendicular": (frozenset({"plane", "line", "cylinder", "cone"}), None),
    "tangent": (frozenset({"plane", "line"}) | _CURVED, _CURVED),
    "distance": (
        frozenset({"plane", "line", "point", "circle", "cylinder", "sphere"}),
        None,
    ),
    "angle": (frozenset({"plane", "line", "cylinder", "cone"}), None),
    "lock": (None, None),
}

_CONSTRAINED_NAMES = {
    swconst.value("swConstrainedStatus_e", member): name
    for member, name in (
        ("swUnknownConstraint", "unknown"),
        ("swUnderConstrained", "under_constrained"),
        ("swFullyConstrained", "fully_constrained"),
        ("swOverConstrained", "over_constrained"),
        ("swNoSolution", "no_solution"),
        ("swInvalidSolution", "invalid_solution"),
        ("swAutosolveOff", "autosolve_off"),
    )
}


def _entity_class(ref: EntityRef) -> str:
    """The mate class of a captured reference, falling back to its kind."""
    return _ENTITY_CLASS.get(ref.semantic.geometry_type) or _ENTITY_CLASS.get(ref.kind, "unknown")


def _mate_types_for(entity_class: str) -> list[str]:
    """Every mate type this class could take, paired with something suitable."""
    return sorted(
        name
        for name, (allowed, _) in _MATE_RULES.items()
        if allowed is None or entity_class in allowed
    )


def _pair_reasons(mate_type: str, first: str, second: str) -> list[str]:
    """Why this mate is predicted to fail for these two entity classes."""
    allowed, requires_one = _MATE_RULES[mate_type]
    reasons: list[str] = []

    if allowed is not None and [c for c in (first, second) if c not in allowed]:
        reasons.append(
            f"a {mate_type} mate is built from {', '.join(sorted(allowed))} entities; "
            f"this pair is {first} and {second}"
        )
    if requires_one is not None and not ({first, second} & requires_one):
        reasons.append(
            f"a {mate_type} mate needs at least one curved entity "
            f"({', '.join(sorted(requires_one))}); both of these are flat"
        )
    return reasons


def _component_of(ref: EntityRef) -> str:
    """The component instance name, as sw_asm_tree reports it."""
    return "/".join(ref.semantic.component_path)


def _resolve_for_probe(
    ctx: OpContext, doc: Any, ref: EntityRef
) -> tuple[EntityRef | None, str | None]:
    """Resolve without raising: a probe reports a bad reference, it does not fail on one."""
    try:
        resolution = resolve(ctx.session, doc, ref, max_candidates=ctx.config.max_candidates)
    except SwMcpError as exc:
        return None, f"{exc.envelope.code}: {exc.envelope.message}"
    return resolution.refreshed, None


@op(
    name="sw_mate_probe",
    tier="core",
    domains=("assembly",),
    tags=("mate", "assembly", "probe", "dry-run", "candidates"),
    summary=(
        "List the entities in an assembly that could take a given mate, or judge one "
        "pair before creating it. The verdict is a prediction from geometry, not a "
        "SOLIDWORKS ruling."
    ),
    safety=ReadSafety(),
    satisfies=("REF-005",),
    partially_satisfies=("MATE-005",),
    precondition="assembly",
    idempotent=True,
    timeout_s=300.0,
)
def mate_probe(ctx: OpContext, args: MateProbeArgs) -> MateProbeResult:
    """MATE-005, and the candidate-mate-entity half of REF-005.

    Two things are measured and one is predicted, and the result keeps them apart.
    Measured: whether each reference still resolves, and which component each entity
    belongs to — a mate between two faces of one component is refused by SOLIDWORKS,
    and that is the failure this catches for certain. Predicted: whether the geometry
    can take the mate, from the entity classes the capture already measured.

    There is no honest way to make the second half conclusive. ``AddMate5`` has no
    dry-run flag, ``ForPositioningOnly`` moves the component, and ``IMateEntity2`` —
    where SOLIDWORKS keeps its own answer — exists only on a mate that has already been
    built. So ``proven`` is always false, and ``sw_safe_execute`` is the tool that gets
    a conclusive answer by building the mate and rolling it back.
    """
    doc = ctx.require_doc()

    if args.refs is not None:
        return _probe_pair(ctx, doc, args)
    return _probe_candidates(ctx, doc, args)


def _probe_pair(ctx: OpContext, doc: Any, args: MateProbeArgs) -> MateProbeResult:
    if args.mate_type is None:
        raise SwMcpError(
            make_error(
                "MATE_TYPE_REQUIRED",
                "validation",
                "Judging a pair needs a mate_type; there is nothing to judge without one.",
                remediation=[
                    "Pass mate_type, or omit refs to list candidate entities instead.",
                ],
            )
        )

    reasons: list[str] = []
    entities: list[dict[str, Any]] = []
    classes: list[str] = []
    components: list[str] = []

    for index, ref in enumerate(args.refs or []):
        refreshed, failure = _resolve_for_probe(ctx, doc, ref)
        if refreshed is None:
            reasons.append(f"reference {index + 1} does not resolve — {failure}")
            entities.append({"index": index, "resolved": False, "detail": failure})
            continue
        entity_class = _entity_class(refreshed)
        component = _component_of(refreshed)
        classes.append(entity_class)
        components.append(component)
        entities.append(
            {
                "index": index,
                "resolved": True,
                "label": refreshed.label,
                "geometry_type": refreshed.semantic.geometry_type,
                "entity_class": entity_class,
                "component": component,
                "mate_types": _mate_types_for(entity_class),
            }
        )

    resolved = len(classes) == 2
    different = None
    also_possible: list[str] = []
    if resolved:
        # Two entities on one component is the one failure that is certain rather than
        # predicted: a mate joins components, so SOLIDWORKS refuses it outright.
        different = not (components[0] and components[0] == components[1])
        if not different:
            reasons.append(
                f"both entities are on component {components[0]!r}; a mate joins two "
                f"different components"
            )
        reasons.extend(_pair_reasons(args.mate_type, classes[0], classes[1]))
        also_possible = [
            name
            for name in sorted(_MATE_RULES)
            if name != args.mate_type and not _pair_reasons(name, classes[0], classes[1])
        ]

    return MateProbeResult(
        mode="pair",
        mate_type=args.mate_type,
        feasible=resolved and not reasons,
        resolved=resolved,
        different_components=different,
        reasons=reasons,
        entities=entities,
        also_possible=also_possible,
        matched=len(classes),
        warnings=[
            "feasible is predicted from entity geometry, not ruled on by SOLIDWORKS. "
            "Use sw_safe_execute to build the mate under a checkpoint for a certain "
            "answer."
        ],
    )


def _probe_candidates(ctx: OpContext, doc: Any, args: MateProbeArgs) -> MateProbeResult:
    found, examined = probe_entities(
        ctx.session,
        doc,
        entity_class=args.entity_class,
        filters=ProbeFilters(),
        limit=ctx.config.max_candidates,
    )

    wanted = set(args.components or [])
    candidates: list[dict[str, Any]] = []
    for ref in found:
        component = _component_of(ref)
        if wanted and component not in wanted:
            continue
        entity_class = _entity_class(ref)
        mate_types = _mate_types_for(entity_class)
        if args.mate_type is not None and args.mate_type not in mate_types:
            continue
        candidates.append(
            {
                "label": ref.label,
                "component": component,
                "geometry_type": ref.semantic.geometry_type,
                "entity_class": entity_class,
                "mate_types": mate_types,
                "measurements": ref.semantic.measurements.model_dump(
                    mode="json", exclude_none=True
                ),
                "tool_args": ref.tool_args(),
            }
        )

    matched = len(candidates)
    warnings: list[str] = []
    if wanted:
        missing = sorted(wanted - {c["component"] for c in candidates})
        if missing:
            warnings.append(
                f"no candidate entities were found on {', '.join(missing)}; check the "
                f"instance names with sw_asm_tree."
            )
    if matched > args.limit:
        warnings.append(
            f"{matched} entities matched and the first {args.limit} are listed; narrow "
            f"with components or mate_type rather than assuming the first is correct."
        )

    return MateProbeResult(
        mode="candidates",
        mate_type=args.mate_type,
        candidates=candidates[: args.limit],
        examined=examined,
        matched=matched,
        warnings=warnings,
    )


def _remaining_dofs(component: Any) -> tuple[int | None, str | None]:
    """``GetRemainingDOFs``, which answers ``Unavailable`` on this build.

    Probed on SOLIDWORKS 2026 across every state that could plausibly matter — no
    mates, after a forced rebuild, after a mate, with the component selected and
    unselected, for a fixed root component and a free one — it returned
    ``swRemainingDofs_Unavailable`` every time, with all twelve ``[out]`` slots
    untouched. That is SOLIDWORKS answering, not a marshalling mistake: the same call
    through ``InvokeTypes`` with the parameters declared ``[out]`` returns the identical
    tuple, and the fixed root component never reports the ``RootComponent`` value the
    enum reserves for it.

    It is still called rather than assumed dead, so a build that does answer starts
    being reported without a code change.
    """
    r1_status, r1_point = out_long(0), out_dispatch()
    r1_dir_status, r1_dir = out_long(0), out_dispatch()
    r2_status, r2_point = out_long(0), out_dispatch()
    r2_dir_status, r2_dir = out_long(0), out_dispatch()
    t1_status, t1_dir = out_long(0), out_dispatch()
    t2_status, t2_dir = out_long(0), out_dispatch()
    slots = (
        r1_status,
        r1_point,
        r1_dir_status,
        r1_dir,
        r2_status,
        r2_point,
        r2_dir_status,
        r2_dir,
        t1_status,
        t1_dir,
        t2_status,
        t2_dir,
    )
    try:
        raw, _outs = call_with_outparams(
            component.GetRemainingDOFs,
            r1_status,
            r1_point,
            r1_dir_status,
            r1_dir,
            r2_status,
            r2_point,
            r2_dir_status,
            r2_dir,
            t1_status,
            t1_dir,
            t2_status,
            t2_dir,
            outparams=slots,
        )
    except Exception:
        return None, None
    if not isinstance(raw, int):
        return None, None
    return raw, swconst.name_of("swRemainingDofs_e", raw)


@op(
    name="sw_mate_dof",
    tier="core",
    domains=("assembly",),
    tags=("mate", "assembly", "dof", "constrained", "review"),
    summary=(
        "Report how constrained each component is and which mates hold it, so an "
        "under-constrained component is named rather than discovered when it moves."
    ),
    safety=ReadSafety(),
    partially_satisfies=("MATE-007",),
    precondition="assembly",
    idempotent=True,
    timeout_s=300.0,
)
def mate_dof(ctx: OpContext, args: MateDofArgs) -> MateDofResult:
    """MATE-007, as far as this build allows.

    ``IComponent2::GetConstrainedStatus`` answers reliably and is what the report is
    built on. The per-axis detail — which rotations and translations remain, and about
    what point — would come from ``GetRemainingDOFs``, which does not answer here; see
    :func:`_remaining_dofs` for what was tried. The result says so in
    ``remaining_dofs_available`` rather than reporting six zeroed axes as though they
    were a measurement.
    """
    doc = ctx.require_doc()
    wanted = set(args.components or [])

    # Mates are read once and attributed to components, rather than asking each
    # component for its own mates: sw_mate_list already describes a mate exactly this
    # way, and two readings of the same mate could disagree.
    mates = [_describe_mate(feature) for feature in _mate_features(doc)]

    described: list[dict[str, Any]] = []
    counts = {"fully_constrained": 0, "under_constrained": 0, "over_constrained": 0}
    under: list[str] = []
    any_dofs = False

    for component in _components(doc):
        name = str(try_com_member(component, "Name2", default="") or "")
        if wanted and name not in wanted:
            continue

        raw_status = try_com_member(component, "GetConstrainedStatus", default=None)
        status = _CONSTRAINED_NAMES.get(raw_status, f"unknown({raw_status})")
        holding = [m["name"] for m in mates if name in m["components"]]
        dof_raw, dof_name = _remaining_dofs(component)
        if dof_name is not None and dof_name != "swRemainingDofs_Unavailable":
            any_dofs = True

        if status in counts:
            counts[status] += 1
        if status == "under_constrained":
            under.append(name)

        described.append(
            {
                "name": name,
                "constrained_status": status,
                "fixed": bool(try_com_member(component, "IsFixed", default=False)),
                "suppressed": bool(try_com_member(component, "IsSuppressed", default=False)),
                "mate_count": len(holding),
                "mates": holding,
                "remaining_dofs_status": dof_name,
                "remaining_dofs_raw": dof_raw,
            }
        )

    warnings: list[str] = []
    if described and not any_dofs:
        warnings.append(
            "IComponent2::GetRemainingDOFs answered swRemainingDofs_Unavailable for "
            "every component, so which axes remain free is not reported. The "
            "constrained status is measured and is unaffected."
        )
    if under:
        warnings.append(
            f"{len(under)} component(s) are under-constrained and can still move: "
            f"{', '.join(under)}."
        )

    return MateDofResult(
        component_count=len(described),
        components=described,
        fully_constrained=counts["fully_constrained"],
        under_constrained=counts["under_constrained"],
        over_constrained=counts["over_constrained"],
        under_constrained_components=under,
        remaining_dofs_available=any_dofs,
        warnings=warnings,
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
