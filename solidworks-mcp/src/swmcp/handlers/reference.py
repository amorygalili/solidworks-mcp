"""Selection and entity references: capture, resolve, and probe."""

from __future__ import annotations

from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import NonModelSideEffect, ReadSafety
from swmcp.com.marshal import null_dispatch, try_com_member
from swmcp.context import OpContext
from swmcp.errors import SwMcpError, make_error
from swmcp.refs.capture import capture
from swmcp.refs.probes import ProbeFilters, probe_entities
from swmcp.refs.resolve import resolve
from swmcp.schemas.reference import (
    ProbeFacesArgs,
    ProbeFacesResult,
    ProbeRayArgs,
    ProbeRayResult,
    RefCaptureArgs,
    RefCaptureResult,
    RefResolveArgs,
    RefResolveResult,
    SelectionGetArgs,
    SelectionGetResult,
    SelectionSetArgs,
    SelectionSetResult,
)
from swmcp.units import area_to_m2


def _selection_manager(doc: Any) -> Any:
    manager = try_com_member(doc, "SelectionManager", default=None)
    if manager is None:
        raise SwMcpError(
            make_error(
                "NO_SELECTION_MANAGER",
                "worker",
                "This document does not expose a selection manager.",
            )
        )
    return manager


def _selected_entities(doc: Any) -> list[tuple[int, Any, int]]:
    """``(index, entity, mark)`` for each current selection."""
    manager = _selection_manager(doc)
    count = int(try_com_member(manager, "GetSelectedObjectCount2", -1, default=0) or 0)
    found = []
    for index in range(1, count + 1):
        entity = try_com_member(manager, "GetSelectedObject6", index, -1, default=None)
        if entity is None:
            continue
        mark = int(try_com_member(manager, "GetSelectedObjectMark", index, default=0) or 0)
        found.append((index, entity, mark))
    return found


@op(
    name="sw_selection_get",
    tier="core",
    domains=("selection", "reference"),
    tags=("selection", "inspect", "pick"),
    summary=(
        "Report what is currently selected in SOLIDWORKS, capturing a full reference "
        "for each item so the user can point at geometry instead of naming it."
    ),
    safety=ReadSafety(),
    satisfies=("REF-001",),
    precondition="any",
    idempotent=True,
)
def selection_get(ctx: OpContext, args: SelectionGetArgs) -> SelectionGetResult:
    doc = ctx.require_doc()
    selections = []
    for index, entity, mark in _selected_entities(doc):
        entry: dict[str, Any] = {"index": index, "mark": mark}
        if args.capture_references:
            ref = capture(ctx.session, doc, entity)
            entry.update(
                {
                    "label": ref.label,
                    "kind": ref.kind,
                    "reference": ref.model_dump(mode="json", exclude_none=True),
                    "tool_args": ref.tool_args(),
                }
            )
        selections.append(entry)
    return SelectionGetResult(count=len(selections), selections=selections)


@op(
    name="sw_selection_set",
    tier="core",
    domains=("selection", "reference"),
    tags=("selection", "clear", "select"),
    summary=(
        "Set or clear the SOLIDWORKS selection from entity references or typed names. "
        "An empty reference list with clear_first simply clears the selection."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Changes the selection set shown in the SOLIDWORKS user interface. No model "
            "data is created, changed, or removed."
        ),
    ),
    satisfies=("REF-001",),
    precondition="any",
    idempotent=True,
    timeout_s=180.0,
)
def selection_set(ctx: OpContext, args: SelectionSetArgs) -> SelectionSetResult:
    doc = ctx.require_doc()
    if args.clear_first:
        try_com_member(doc, "ClearSelection2", True, default=None)

    selected = 0
    failed: list[dict[str, Any]] = []

    for position, ref in enumerate(args.refs, start=1):
        try:
            resolution = resolve(
                ctx.session, doc, ref, max_candidates=ctx.config.max_candidates
            )
            if try_com_member(resolution.entity, "Select4", True, null_dispatch(), default=False):
                selected += 1
            else:
                failed.append({"index": position, "reason": "SOLIDWORKS refused the selection"})
        except SwMcpError as exc:
            failed.append(
                {
                    "index": position,
                    "reason": exc.envelope.code,
                    "message": exc.envelope.message,
                }
            )

    for name in args.names:
        ok = doc.Extension.SelectByID2(
            name, args.name_type, 0, 0, 0, True, args.mark, null_dispatch(), 0
        )
        if ok:
            selected += 1
        else:
            failed.append({"name": name, "reason": "SelectByID2 returned false"})

    return SelectionSetResult(
        selected=selected,
        failed=failed,
        selection=[
            {"index": index, "mark": mark, "label": capture(ctx.session, doc, entity).label}
            for index, entity, mark in _selected_entities(doc)
        ],
        warnings=[f"{len(failed)} item(s) could not be selected."] if failed else [],
    )


@op(
    name="sw_ref_capture",
    tier="core",
    domains=("reference",),
    tags=("reference", "capture", "persist"),
    summary=(
        "Capture durable references to the selected entities, emitting the persistent "
        "reference, a semantic geometry fallback, and paste-ready arguments together."
    ),
    safety=ReadSafety(),
    satisfies=("REF-002", "REF-003", "REF-004", "REF-007"),
    precondition="any",
    idempotent=True,
)
def ref_capture(ctx: OpContext, args: RefCaptureArgs) -> RefCaptureResult:
    doc = ctx.require_doc()
    selections = _selected_entities(doc)
    if args.selection_index is not None:
        selections = [item for item in selections if item[0] == args.selection_index]
        if not selections:
            raise SwMcpError(
                make_error(
                    "SELECTION_INDEX_MISSING",
                    "validation",
                    f"There is no selection at index {args.selection_index}.",
                    context={"selected_count": len(_selected_entities(doc))},
                    remediation=["Select the entity in SOLIDWORKS, then retry."],
                )
            )
    if not selections:
        raise SwMcpError(
            make_error(
                "NO_SELECTION",
                "validation",
                "Nothing is selected in SOLIDWORKS.",
                remediation=[
                    "Select the geometry in SOLIDWORKS, or use a face probe to find it "
                    "by its properties instead.",
                ],
            )
        )

    references = []
    for index, entity, mark in selections:
        ref = capture(ctx.session, doc, entity)
        references.append(
            {
                "index": index,
                "mark": mark,
                "label": ref.label,
                "reference": ref.model_dump(mode="json", exclude_none=True),
                "tool_args": ref.tool_args(),
            }
        )
    return RefCaptureResult(references=references)


@op(
    name="sw_ref_resolve",
    tier="core",
    domains=("reference",),
    tags=("reference", "resolve", "stale", "ambiguous"),
    summary=(
        "Resolve a stored entity reference against the current model. Reports whether "
        "it resolved exactly or was healed by geometry matching, and returns every "
        "candidate rather than guessing when the match is ambiguous."
    ),
    safety=ReadSafety(),
    satisfies=("REF-002", "REF-003", "REF-004", "REF-006", "REF-007"),
    precondition="any",
    idempotent=True,
    timeout_s=180.0,
)
def ref_resolve(ctx: OpContext, args: RefResolveArgs) -> RefResolveResult:
    doc = ctx.require_doc()
    resolution = resolve(ctx.session, doc, args.ref, max_candidates=ctx.config.max_candidates)

    if args.select:
        try_com_member(doc, "ClearSelection2", True, default=None)
        try_com_member(resolution.entity, "Select4", True, null_dispatch(), default=False)

    return RefResolveResult(
        via=resolution.via,
        score=resolution.score,
        drift=resolution.drift.model_dump(mode="json", exclude_none=True)
        if resolution.drift
        else None,
        refreshed=resolution.refreshed.model_dump(mode="json", exclude_none=True),
        tool_args=resolution.refreshed.tool_args(),
        warnings=resolution.warnings,
    )


@op(
    name="sw_probe_faces",
    tier="core",
    domains=("reference",),
    tags=("probe", "face", "edge", "search", "geometry"),
    summary=(
        "Find faces or edges by their geometry — type, radius, area, normal direction, "
        "or a point they contain — and return ranked references. This is how to narrow "
        "an ambiguous reference down to exactly one entity before acting on it."
    ),
    safety=ReadSafety(),
    satisfies=("REF-006",),
    partially_satisfies=("REF-005",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=300.0,
)
def probe_faces(ctx: OpContext, args: ProbeFacesArgs) -> ProbeFacesResult:
    doc = ctx.require_doc()
    # Length fields arrive already normalized to metres; areas convert through units.py.
    filters = ProbeFilters(
        geometry_type=args.geometry_type,
        radius_min_m=args.radius_min,
        radius_max_m=args.radius_max,
        area_min_m2=area_to_m2(args.area_min_mm2) if args.area_min_mm2 is not None else None,
        area_max_m2=area_to_m2(args.area_max_mm2) if args.area_max_mm2 is not None else None,
        normal=tuple(args.normal) if args.normal else None,
        normal_within_deg=args.normal_within_deg,
        contains_point_m=tuple(args.contains_point) if args.contains_point else None,
        contains_tolerance_m=args.contains_tolerance,
    )
    found, examined = probe_entities(
        ctx.session,
        doc,
        entity_class=args.entity_class,
        feature_name=args.feature_name,
        body_name=args.body_name,
        filters=filters,
        limit=args.limit,
    )

    return ProbeFacesResult(
        examined=examined,
        matched=len(found),
        candidates=[
            {
                "label": ref.label,
                "geometry_type": ref.semantic.geometry_type,
                "measurements": ref.semantic.measurements.model_dump(
                    mode="json", exclude_none=True
                ),
                "reference": ref.model_dump(mode="json", exclude_none=True),
                "tool_args": ref.tool_args(),
            }
            for ref in found
        ],
        warnings=(
            [f"{len(found)} entities matched; add a filter to narrow it to one."]
            if len(found) > 1
            else []
        ),
    )


@op(
    name="sw_probe_ray",
    tier="extended",
    domains=("reference",),
    tags=("probe", "ray", "pick"),
    summary=(
        "Cast a ray into the model and capture a reference to the first face it hits. "
        "Useful when a face is easier to describe by where it is than by what it is."
    ),
    safety=ReadSafety(),
    partially_satisfies=("REF-005",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def probe_ray(ctx: OpContext, args: ProbeRayArgs) -> ProbeRayResult:
    doc = ctx.require_doc()
    origin = args.origin  # already metres

    try_com_member(doc, "ClearSelection2", True, default=None)
    hit = doc.Extension.SelectByRay(
        origin[0],
        origin[1],
        origin[2],
        args.direction[0],
        args.direction[1],
        args.direction[2],
        args.radius,
        2,  # swSelectType_e.swSelFACES
        False,
        0,
        0,
    )
    if not hit:
        return ProbeRayResult(
            hit=False,
            warnings=["The ray did not hit a face. Check the origin and direction."],
        )

    selections = _selected_entities(doc)
    if not selections:
        return ProbeRayResult(hit=False, warnings=["The ray reported a hit but selected nothing."])

    ref = capture(ctx.session, doc, selections[0][1])
    return ProbeRayResult(
        hit=True,
        reference=ref.model_dump(mode="json", exclude_none=True),
        tool_args=ref.tool_args(),
    )
