"""Constraint domain: sketch relations, dimensions, and solver diagnosis.

Every relation and dimension result carries ``sketch_state``. CON-005 asks for the
under/over-defined state to be validated after every constraint batch, and putting it
in the result schema is what makes that unskippable — an agent that forgets to check
still receives the answer.
"""

from __future__ import annotations

from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import get_com_member, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.modeling import configuration_names
from swmcp.schemas.sketch import (
    DimensionListArgs,
    DimensionListResult,
    DimensionSetArgs,
    DimensionSetResult,
    SketchAddDimensionsArgs,
    SketchAddDimensionsResult,
    SketchAddRelationsArgs,
    SketchAddRelationsResult,
    SketchAutoDimensionArgs,
    SketchAutoDimensionResult,
    SketchDiagnoseArgs,
    SketchDiagnoseResult,
)
from swmcp.sketching import (
    RELATION_ARITY,
    RELATION_TOKENS,
    analyze_contours,
    contour_warnings,
    find_sketch,
    require_active_sketch,
    segment_topology,
    segments_by_id,
    select_segments,
    sketch_segments,
    sketch_state,
    under_defined_count,
)
from swmcp.units import from_meters, to_meters


def _is_driving(dimension: Any) -> bool:
    """swDimensionDriving is 2; swDimensionDriven (a reference dimension) is 1."""
    state = try_com_member(dimension, "DrivenState", default=None)
    return state == swconst.value("swDimensionDrivenState_e", "swDimensionDriving")

#: Our dimension names -> how many entities must be selected.
_DIMENSION_ARITY = {
    "distance": (1, 2),
    "horizontal_distance": (1, 2),
    "vertical_distance": (1, 2),
    "radius": (1, 1),
    "diameter": (1, 1),
    "angle": (2, 3),
    "arc_length": (1, 1),
}


def _resolve_sketch(doc: Any, name: str | None) -> Any:
    if name is None:
        return require_active_sketch(doc)
    sketch = find_sketch(doc, name)
    if sketch is None:
        raise SwMcpError(
            make_error(
                "SKETCH_NOT_FOUND",
                "validation",
                f"There is no sketch named {name!r} in this document.",
                remediation=["List the document's sketches to see what exists."],
            )
        )
    return sketch


def _collect(available: dict[str, Any], ids: list[str]) -> tuple[list[Any], list[str]]:
    found, missing = [], []
    for identifier in ids:
        segment = available.get(identifier)
        if segment is None:
            missing.append(identifier)
        else:
            found.append(segment)
    return found, missing


def _check_arity(kind: str, count: int, table: dict[str, tuple[int, int]]) -> str | None:
    bounds = table.get(kind)
    if bounds is None:
        return f"{kind!r} is not supported"
    low, high = bounds
    if not (low <= count <= high):
        return f"{kind!r} needs {low}-{high} entities, got {count}"
    return None


@op(
    name="sw_sketch_add_relations",
    tier="core",
    domains=("constraint", "sketch"),
    tags=("relation", "constraint", "horizontal", "vertical", "coincident", "tangent"),
    summary=(
        "Add geometric relations to sketch segments in one batch. Reports each relation "
        "individually and always returns the resulting solver state, so an over-defined "
        "sketch is visible immediately rather than at the next rebuild."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("CON-001", "CON-005"),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=300.0,
)
def sketch_add_relations(
    ctx: OpContext, args: SketchAddRelationsArgs
) -> SketchAddRelationsResult:
    doc = ctx.require_doc()
    sketch = _resolve_sketch(doc, args.sketch_name)
    available = segments_by_id(sketch)

    before_state = sketch_state(sketch)
    before_undefined = under_defined_count(sketch)

    planned, failed = [], []
    for index, relation in enumerate(args.relations, start=1):
        segments, missing = _collect(available, relation.segment_ids)
        problem = _check_arity(relation.type, len(segments), RELATION_ARITY)
        if missing:
            failed.append(
                {"index": index, "type": relation.type, "reason": f"unknown ids {missing}"}
            )
        elif problem:
            failed.append({"index": index, "type": relation.type, "reason": problem})
        else:
            planned.append((index, relation, segments))

    if args.preflight:
        return SketchAddRelationsResult(
            applied=0,
            failed=failed,
            sketch_state=before_state,
            verification=Verification(
                read_back=True,
                before={"relation_count": before_state["relation_count"]},
                after={"relation_count": before_state["relation_count"]},
                checks=[Check(name="preflight_only", passed=True, detail="nothing was applied")],
            ),
            warnings=[
                f"Preflight only: {len(planned)} relation(s) would apply, "
                f"{len(failed)} would fail."
            ],
        )

    # A merge fuses two points into one. It leaves no relation behind to count, so the
    # before/after relation tally cannot speak for it and the profile topology has to:
    # read it only when a merge is actually in the batch, since it walks every segment.
    merges_planned = sum(1 for _, relation, _ in planned if relation.type == "merge")
    before_contours = analyze_contours(segment_topology(sketch)) if merges_planned else {}

    applied = 0
    merges_applied = 0
    for index, relation, segments in planned:
        select_segments(doc, segments)
        try:
            doc.SketchAddConstraints(RELATION_TOKENS[relation.type])
            applied += 1
            if relation.type == "merge":
                merges_applied += 1
        except Exception as exc:  # one bad relation must not lose the batch
            failed.append({"index": index, "type": relation.type, "reason": str(exc)})

    try_com_member(doc, "ClearSelection2", True, default=None)
    after_state = sketch_state(sketch)
    after_undefined = under_defined_count(sketch)
    after_contours = analyze_contours(segment_topology(sketch)) if merges_applied else {}

    return SketchAddRelationsResult(
        applied=applied,
        failed=failed,
        sketch_state=after_state,
        verification=Verification(
            read_back=True,
            before={
                "relation_count": before_state["relation_count"],
                "under_defined_segments": before_undefined,
                "status": before_state["status"],
            },
            after={
                "relation_count": after_state["relation_count"],
                "under_defined_segments": after_undefined,
                "status": after_state["status"],
            },
            checks=[
                Check(
                    name="relations_added",
                    # Merges are excluded deliberately. They delete a point rather than
                    # add a relation, so a batch of nothing but merges cannot move this
                    # count, and reporting that as a failure called a working operation
                    # broken.
                    passed=after_state["relation_count"] > before_state["relation_count"]
                    if applied - merges_applied
                    else True,
                    detail=(
                        f"{before_state['relation_count']} -> "
                        f"{after_state['relation_count']} relations"
                        + (
                            f" ({merges_applied} merge(s) add none by design)"
                            if merges_applied
                            else ""
                        )
                    ),
                ),
                *(
                    [
                        Check(
                            name="points_merged",
                            passed=_points_were_merged(before_contours, after_contours),
                            detail=_merge_detail(before_contours, after_contours),
                        )
                    ]
                    if merges_applied
                    else []
                ),
                Check(
                    name="sketch_not_over_defined",
                    passed=not after_state["over_defined"],
                    detail=after_state["status"],
                ),
                Check(
                    name="no_dangling_relations",
                    passed=not after_state["dangling_relations"],
                    detail=f"{len(after_state['dangling_relations'])} dangling",
                ),
            ],
        ),
        warnings=_relation_warnings(failed, after_state),
    )


def _loose_end_count(contours: dict[str, Any]) -> int:
    return len(contours.get("loose_ends_mm") or ())


def _points_were_merged(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Did fusing points actually join the profile up?

    Fewer loose ends is the direct evidence. A merge on a profile that had none to
    begin with - joining two points mid-chain, say - changes nothing measurable here,
    and passes rather than claiming a failure it cannot see.
    """
    if not before or not after:
        return True
    if _loose_end_count(before) == 0:
        return True
    return _loose_end_count(after) < _loose_end_count(before) or after.get(
        "open_contour_count", 0
    ) < before.get("open_contour_count", 0)


def _merge_detail(before: dict[str, Any], after: dict[str, Any]) -> str:
    return (
        f"{_loose_end_count(before)} -> {_loose_end_count(after)} loose ends, "
        f"{before.get('open_contour_count', 0)} -> {after.get('open_contour_count', 0)} "
        f"open contour(s)"
    )


def _relation_warnings(failed: list[dict[str, Any]], state: dict[str, Any]) -> list[str]:
    warnings = []
    if failed:
        warnings.append(f"{len(failed)} relation(s) could not be applied.")
    if state["over_defined"]:
        warnings.append("The sketch is now over-defined. Remove a conflicting relation.")
    if state["dangling_relations"]:
        warnings.append(
            f"{len(state['dangling_relations'])} relation(s) are dangling and will not solve."
        )
    return warnings


@op(
    name="sw_sketch_add_dimensions",
    tier="core",
    domains=("constraint", "sketch"),
    tags=("dimension", "constraint", "distance", "radius", "angle"),
    summary=(
        "Add driving dimensions to sketch segments in one batch and optionally set their "
        "values. Always returns the resulting solver state, so reaching fully defined is "
        "verifiable rather than assumed."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("CON-002", "CON-005"),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=300.0,
)
def sketch_add_dimensions(
    ctx: OpContext, args: SketchAddDimensionsArgs
) -> SketchAddDimensionsResult:
    doc = ctx.require_doc()
    sketch = _resolve_sketch(doc, args.sketch_name)
    available = segments_by_id(sketch)

    before_state = sketch_state(sketch)
    before_undefined = under_defined_count(sketch)

    planned, failed = [], []
    for index, spec in enumerate(args.dimensions, start=1):
        segments, missing = _collect(available, spec.segment_ids)
        problem = _check_arity(spec.type, len(segments), _DIMENSION_ARITY)
        if missing:
            failed.append({"index": index, "type": spec.type, "reason": f"unknown ids {missing}"})
        elif problem:
            failed.append({"index": index, "type": spec.type, "reason": problem})
        else:
            planned.append((index, spec, segments))

    if args.preflight:
        return SketchAddDimensionsResult(
            created=[
                {"index": index, "type": spec.type, "would_create": True}
                for index, spec, _ in planned
            ],
            failed=failed,
            sketch_state=before_state,
            verification=Verification(
                read_back=True,
                before={"status": before_state["status"]},
                after={"status": before_state["status"]},
                checks=[Check(name="preflight_only", passed=True, detail="nothing was created")],
            ),
            warnings=["Preflight only: no dimensions were created."],
        )

    created = []
    for index, spec, segments in planned:
        try:
            entry = _add_one_dimension(doc, spec, segments)
            created.append({"index": index, **entry})
        except Exception as exc:  # one bad dimension must not lose the batch
            failed.append({"index": index, "type": spec.type, "reason": str(exc)})

    try_com_member(doc, "ClearSelection2", True, default=None)
    after_state = sketch_state(sketch)
    after_undefined = under_defined_count(sketch)

    return SketchAddDimensionsResult(
        created=created,
        failed=failed,
        sketch_state=after_state,
        verification=Verification(
            read_back=True,
            before={
                "under_defined_segments": before_undefined,
                "status": before_state["status"],
            },
            after={
                "under_defined_segments": after_undefined,
                "status": after_state["status"],
            },
            checks=[
                Check(
                    name="dimensions_created",
                    passed=bool(created) or not planned,
                    detail=f"{len(created)} of {len(planned)} dimensions created",
                ),
                Check(
                    name="constraint_progress",
                    passed=after_undefined <= before_undefined,
                    detail=(
                        f"{before_undefined} -> {after_undefined} under-defined segments"
                    ),
                ),
                Check(
                    name="sketch_not_over_defined",
                    passed=not after_state["over_defined"],
                    detail=after_state["status"],
                ),
            ],
        ),
        warnings=_relation_warnings(failed, after_state),
    )


def _add_one_dimension(doc: Any, spec: Any, segments: list[Any]) -> dict[str, Any]:
    """Select the entities, place the dimension, then drive it if a value was given."""
    select_segments(doc, segments)

    place = spec.place_at or [0.0, 0.0, 0.0]
    display = doc.AddDimension2(place[0], place[1], place[2])
    if display is None:
        raise RuntimeError("SOLIDWORKS did not create a dimension for this selection")

    dimension = try_com_member(display, "GetDimension", default=None)
    if dimension is None:
        raise RuntimeError("the dimension was created but could not be read back")

    name = str(try_com_member(dimension, "FullName", default="") or "")
    before_value = try_com_member(dimension, "SystemValue", default=None)

    target = spec.angle_value if spec.type == "angle" else spec.value
    if target is not None:
        dimension.SystemValue = target

    if spec.name:
        try_com_member(dimension, "Name", default=None)
        dimension.Name = spec.name

    after_value = try_com_member(dimension, "SystemValue", default=None)
    return {
        "type": spec.type,
        "name": str(try_com_member(dimension, "FullName", default=name) or name),
        "before_value_m": before_value,
        "after_value_m": after_value,
        "driving": _is_driving(dimension),
    }


@op(
    name="sw_sketch_diagnose",
    tier="core",
    domains=("constraint", "sketch"),
    tags=("diagnose", "constraint", "solver", "defined"),
    summary=(
        "Report a sketch's solver state and its profile topology: fully or under "
        "defined, over-defining relations, dangling relations, how many segments are "
        "still free, and how many closed contours the sketch actually holds — with the "
        "coordinates of any gap that stops one closing."
    ),
    safety=ReadSafety(),
    satisfies=("CON-005",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def sketch_diagnose(ctx: OpContext, args: SketchDiagnoseArgs) -> SketchDiagnoseResult:
    doc = ctx.require_doc()
    sketch = _resolve_sketch(doc, args.sketch_name)
    name = str(try_com_member(sketch, "Name", default="") or "")
    state = sketch_state(sketch)
    contours = analyze_contours(segment_topology(sketch))

    warnings = []
    if state["over_defined"]:
        warnings.append("The sketch is over-defined and will not solve as drawn.")
    if state["dangling_relations"]:
        warnings.append(f"{len(state['dangling_relations'])} relation(s) are dangling.")
    # The solver is content with a profile that has a gap in it, so this is the only
    # place a caller finds out before a feature refuses the sketch. Stated as what was
    # measured rather than as a prediction: an extrude does need this closed, but a
    # revolve closes a profile against its own axis, so an open contour whose ends sit
    # on the centerline revolves perfectly well.
    warnings.extend(contour_warnings(contours))

    return SketchDiagnoseResult(
        sketch_name=name,
        sketch_state=state,
        segment_count=len(sketch_segments(sketch)),
        contours=contours,
        warnings=warnings,
    )


def _find_dimension(doc: Any, name: str) -> Any | None:
    """Locate a dimension by its full name.

    ``IModelDoc2.Parameter`` looks like the direct route but does not marshal reliably
    through late binding here — it resolves to a value rather than a callable — so the
    dimension is found by walking the tree that ``sw_dimension_list`` already walks.
    """
    for _owner, dimension in _iter_dimensions(doc, None):
        if str(try_com_member(dimension, "FullName", default="") or "") == name:
            return dimension
    return None


def _iter_dimensions(doc: Any, sketch_name: str | None):
    """Walk the feature tree yielding ``(feature_name, IDimension)`` pairs.

    A sketch dimension is reported twice — once by the sketch that owns it and once by
    the feature that consumed the sketch — so each is yielded only the first time its
    full name is seen. Without that, a parameter table lists every driving dimension
    twice and an import applies each change twice.
    """
    seen: set[str] = set()
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        name = str(try_com_member(feature, "Name", default="") or "")
        if sketch_name is None or name == sketch_name:
            dimension = try_com_member(feature, "GetFirstDisplayDimension", default=None)
            inner_guard = 0
            while dimension is not None and inner_guard < 500:
                inner_guard += 1
                actual = try_com_member(dimension, "GetDimension", default=None)
                if actual is not None:
                    full_name = str(try_com_member(actual, "FullName", default="") or "")
                    if not full_name or full_name not in seen:
                        if full_name:
                            seen.add(full_name)
                        yield name, actual
                dimension = try_com_member(
                    feature, "GetNextDisplayDimension", dimension, default=None
                )
        feature = try_com_member(feature, "GetNextFeature", default=None)


@op(
    name="sw_dimension_list",
    tier="core",
    domains=("constraint", "sketch"),
    tags=("dimension", "list", "parameters"),
    summary=(
        "List driving dimensions with their names and values in the requested unit, "
        "optionally as they stand in one configuration, so a parametric change can "
        "address a dimension by name rather than by position."
    ),
    safety=ReadSafety(),
    satisfies=("CON-003", "PAR-001"),
    partially_satisfies=("PAR-004",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def dimension_list(ctx: OpContext, args: DimensionListArgs) -> DimensionListResult:
    doc = ctx.require_doc()
    warnings: list[str] = []
    if args.configuration:
        known = configuration_names(doc)
        if args.configuration not in known:
            raise SwMcpError(
                validation_error(
                    "CONFIGURATION_NOT_FOUND",
                    f"No configuration named {args.configuration!r}.",
                    context={"existing": known},
                    remediation=["List the document's configurations to see what exists."],
                )
            )

    found = []
    for owner, dimension in _iter_dimensions(doc, args.sketch_name):
        value_m = try_com_member(dimension, "SystemValue", default=None)
        if args.configuration:
            # GetSystemValue2 reads one named configuration's value, which can differ
            # from the active one; that difference is the whole point of PAR-004.
            scoped = try_com_member(
                dimension, "GetSystemValue2", args.configuration, default=None
            )
            if isinstance(scoped, (int, float)):
                value_m = scoped
        entry: dict[str, Any] = {
            "name": str(try_com_member(dimension, "FullName", default="") or ""),
            "owner": owner,
            "value_m": value_m,
            "driving": _is_driving(dimension),
            "applies_to_all_configurations": try_com_member(
                dimension, "IsAppliedToAllConfigurations", default=None
            ),
            "tolerance_type": try_com_member(dimension, "GetToleranceType", default=None),
        }
        if isinstance(value_m, (int, float)):
            entry[f"value_{args.unit}"] = from_meters(float(value_m), args.unit)
        found.append(entry)

    return DimensionListResult(
        unit=args.unit,
        configuration=args.configuration,
        dimensions=found,
        warnings=warnings,
    )





def _dimension_scope(doc: Any, args: DimensionSetArgs) -> tuple[int | None, Any]:
    """``(swInConfigurationOpts_e, names)``, or ``(None, None)`` for a plain write.

    A single-configuration part is the common case, and writing its one configuration
    through the scoped API buys nothing, so that path stays on the simple assignment.
    """
    known = configuration_names(doc)
    if args.configuration_scope == "specify":
        if not args.configurations:
            raise SwMcpError(
                validation_error(
                    "MISSING_ARGUMENT",
                    "configuration_scope='specify' needs at least one configuration name.",
                )
            )
        unknown = [name for name in args.configurations if name not in known]
        if unknown:
            raise SwMcpError(
                validation_error(
                    "CONFIGURATION_NOT_FOUND",
                    f"No configuration named {unknown[0]!r}.",
                    context={"unknown": unknown, "existing": known},
                )
            )
        return (
            swconst.value("swInConfigurationOpts_e", "swSpecifyConfiguration"),
            list(args.configurations),
        )

    if len(known) <= 1:
        return None, None
    member = "swThisConfiguration" if args.configuration_scope == "this" else "swAllConfiguration"
    return swconst.value("swInConfigurationOpts_e", member), None


@op(
    name="sw_dimension_set",
    tier="core",
    domains=("constraint", "sketch"),
    tags=("dimension", "parametric", "set", "value"),
    summary=(
        "Change a named driving dimension in the active configuration, in all of them, "
        "or in named ones, reporting the value before and after plus any rebuild errors "
        "the change caused."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("CON-003", "PAR-001"),
    partially_satisfies=("PAR-004",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=300.0,
)
def dimension_set(ctx: OpContext, args: DimensionSetArgs) -> DimensionSetResult:
    doc = ctx.require_doc()
    dimension = _find_dimension(doc, args.name)
    if dimension is None:
        known = [
            str(try_com_member(d, "FullName", default=""))
            for _owner, d in _iter_dimensions(doc, None)
        ]
        raise SwMcpError(
            make_error(
                "DIMENSION_NOT_FOUND",
                "validation",
                f"No dimension named {args.name!r}.",
                context={"known_dimensions": known[:50]},
                remediation=[
                    "List the document's dimensions to see the exact names, "
                    "which usually look like 'D1@Sketch1'.",
                ],
            )
        )

    before_m = try_com_member(dimension, "SystemValue", default=None)
    if not isinstance(before_m, (int, float)):
        raise SwMcpError(
            validation_error(
                "DIMENSION_NOT_READABLE",
                f"{args.name!r} did not report a numeric value.",
            )
        )

    scope, names = _dimension_scope(doc, args)
    if scope is None:
        dimension.SystemValue = args.value
    else:
        # SetSystemValue3 returns swSetValueReturnStatus_e; a non-zero code means the
        # value was refused, which must not be reported as a successful change.
        status = try_com_member(
            dimension, "SetSystemValue3", args.value, scope, names, default=None
        )
        if isinstance(status, int) and status != 0:
            raise SwMcpError(
                make_error(
                    "DIMENSION_NOT_SET",
                    "solidworks",
                    f"SOLIDWORKS refused the new value for {args.name!r} (status {status}).",
                    context={"status": status, "configuration_scope": args.configuration_scope},
                    remediation=[
                        "A driven or design-table dimension cannot be set directly.",
                        "Check that every named configuration exists.",
                    ],
                )
            )

    rebuild_errors: list[str] = []
    # EditRebuild3 is another property-or-method member; call it through the shim.
    if args.rebuild and not get_com_member(doc, "EditRebuild3"):
        rebuild_errors.append("EditRebuild3 reported failure")

    after_m = try_com_member(dimension, "SystemValue", default=before_m)
    return DimensionSetResult(
        name=args.name,
        before_mm=from_meters(float(before_m), "mm"),
        after_mm=from_meters(float(after_m), "mm"),
        requested_mm=from_meters(args.value, "mm"),
        configuration_scope=args.configuration_scope,
        configurations=list(args.configurations),
        rebuild_errors=rebuild_errors,
        verification=Verification(
            read_back=True,
            before={"value_mm": from_meters(float(before_m), "mm")},
            after={"value_mm": from_meters(float(after_m), "mm")},
            checks=[
                Check(
                    name="value_applied",
                    passed=abs(float(after_m) - args.value) < to_meters(0.0001),
                    detail=(
                        f"requested {from_meters(args.value, 'mm'):.4f} mm, "
                        f"model reports {from_meters(float(after_m), 'mm'):.4f} mm"
                    ),
                ),
                Check(
                    name="rebuild_clean",
                    passed=not rebuild_errors,
                    detail="; ".join(rebuild_errors) or "no rebuild errors",
                ),
            ],
        ),
    )


@op(
    name="sw_sketch_auto_dimension",
    tier="advanced",
    domains=("constraint", "sketch"),
    tags=("dimension", "auto", "fully-define"),
    summary=(
        "Fully define a sketch automatically under an explicit policy, reporting every "
        "dimension it created. The policy has no default because auto-dimensioning adds "
        "constraints the caller did not choose."
    ),
    safety=ModelMutation(destructive=True),
    satisfies=("CON-004",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=300.0,
)
def sketch_auto_dimension(
    ctx: OpContext, args: SketchAutoDimensionArgs
) -> SketchAutoDimensionResult:
    doc = ctx.require_doc()
    sketch = _resolve_sketch(doc, args.sketch_name)
    name = str(try_com_member(sketch, "Name", default="") or "")

    before = [
        str(try_com_member(d, "FullName", default="")) for _o, d in _iter_dimensions(doc, name)
    ]
    before_state = sketch_state(sketch)

    scheme = {"baseline": 0, "chain": 1, "ordinate": 2}[args.policy]
    ok = try_com_member(
        sketch,
        "FullyDefine",
        doc,
        1,  # apply to the whole sketch
        True,  # add relations as well as dimensions
        0,
        scheme,
        scheme,
        None,
        None,
        None,
        None,
        default=False,
    )

    after_pairs = list(_iter_dimensions(doc, name))
    after = [str(try_com_member(d, "FullName", default="")) for _o, d in after_pairs]
    after_state = sketch_state(sketch)
    created = [
        {
            "name": full_name,
            "value_m": try_com_member(dimension, "SystemValue", default=None),
        }
        for full_name, (_owner, dimension) in zip(after, after_pairs, strict=True)
        if full_name not in before
    ]

    return SketchAutoDimensionResult(
        sketch_name=name,
        dimensions_before=len(before),
        dimensions_after=len(after),
        created=created,
        sketch_state=after_state,
        verification=Verification(
            read_back=True,
            before={"dimension_count": len(before), "status": before_state["status"]},
            after={"dimension_count": len(after), "status": after_state["status"]},
            checks=[
                Check(
                    name="auto_dimension_ran",
                    passed=bool(ok) or len(after) > len(before),
                    detail=f"{len(created)} dimension(s) created",
                ),
                Check(
                    name="sketch_fully_defined",
                    passed=after_state["fully_defined"],
                    detail=after_state["status"],
                ),
            ],
        ),
        warnings=(
            []
            if after_state["fully_defined"]
            else ["The sketch is still not fully defined; add dimensions manually."]
        ),
    )
