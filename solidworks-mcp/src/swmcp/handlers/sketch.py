"""Sketch domain: start, edit, inspect, and modify sketch geometry."""

from __future__ import annotations

from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import normalize_sequence, null_dispatch, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.refs.resolve import resolve
from swmcp.schemas.sketch import (
    SketchAddGeometryArgs,
    SketchAddGeometryResult,
    SketchConvertEntitiesArgs,
    SketchConvertEntitiesResult,
    SketchDeleteArgs,
    SketchDeleteResult,
    SketchExitArgs,
    SketchExitResult,
    SketchListArgs,
    SketchListResult,
    SketchModifyArgs,
    SketchModifyResult,
    SketchSetConstructionArgs,
    SketchSetConstructionResult,
    SketchStartArgs,
    SketchStartResult,
    SketchTextArgs,
    SketchTextResult,
)
from swmcp.sketching import (
    active_sketch,
    describe_segment,
    find_sketch,
    require_active_sketch,
    segments_by_id,
    select_segments,
    sketch_segments,
    sketch_state,
)


def _resolve_sketch(ctx: OpContext, doc: Any, name: str | None) -> Any:
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
    _ = ctx
    return sketch


# --- geometry creation --------------------------------------------------------


_SLOT_LENGTH_TYPES = {"center_to_center": 0, "overall": 1}

#: ``swSketchSlotCreationType_e``. Each form reads the three points differently, which
#: is why they are separate entity types rather than one type with flags.
_SLOT_CREATION_TYPES = {
    "slot_straight": 0,
    "slot_centerpoint": 1,
    "slot_arc": 2,
    "slot_3point_arc": 3,
}


def _create_slot(manager: Any, entity: Any, kind: str) -> list[Any]:
    """Drive ``CreateSketchSlot`` and return the segments it actually added.

    Points the chosen form does not use are passed as zeros, which SOLIDWORKS ignores.
    ``CenterArcDirection`` is only read for the centre-point arc slot.

    The call hands back one ``ISketchSlot`` rather than the arcs and lines it built, and
    describing that wrapper produced a "created" entry with no type and no length while
    the sketch really held three or four new segments. So the sketch is diffed either
    side of the call and the new segments are what gets reported.
    """
    direction = 1
    if kind == "slot_straight":
        first, second, third = entity.start, entity.end, (0.0, 0.0)
    elif kind == "slot_centerpoint":
        first, second, third = entity.center, entity.end, (0.0, 0.0)
    elif kind == "slot_arc":
        first, second, third = entity.center, entity.start, entity.end
        direction = -1 if entity.direction == "clockwise" else 1
    else:  # slot_3point_arc
        first, second, third = entity.start, entity.end, entity.through

    sketch = try_com_member(manager, "ActiveSketch", default=None)
    before = set(segments_by_id(sketch)) if sketch is not None else set()

    made = manager.CreateSketchSlot(
        _SLOT_CREATION_TYPES[kind],
        _SLOT_LENGTH_TYPES[entity.length_type],
        entity.width,
        first[0], first[1], 0.0,
        second[0], second[1], 0.0,
        third[0], third[1], 0.0,
        direction,
        False,
    )
    if sketch is None:
        return normalize_sequence(made)

    after = segments_by_id(sketch)
    fresh = [segment for key, segment in after.items() if key not in before]
    # If the diff finds nothing but the call returned something, report the wrapper
    # rather than claiming the slot failed.
    return fresh or normalize_sequence(made)


def _create_entity(manager: Any, entity: Any) -> list[Any]:
    """Create one primitive, returning the segments SOLIDWORKS produced."""
    kind = entity.type

    if kind in {"line", "centerline"}:
        (sx, sy), (ex, ey) = entity.start, entity.end
        maker = manager.CreateLine if kind == "line" else manager.CreateCenterLine
        return normalize_sequence(maker(sx, sy, 0.0, ex, ey, 0.0))

    if kind == "point":
        return normalize_sequence(manager.CreatePoint(entity.at[0], entity.at[1], 0.0))

    if kind == "rect_corner":
        (cx, cy), (ox, oy) = entity.corner, entity.opposite
        return normalize_sequence(manager.CreateCornerRectangle(cx, cy, 0.0, ox, oy, 0.0))

    if kind == "rect_center":
        (cx, cy), (ox, oy) = entity.center, entity.corner
        return normalize_sequence(manager.CreateCenterRectangle(cx, cy, 0.0, ox, oy, 0.0))

    if kind == "circle":
        cx, cy = entity.center
        return normalize_sequence(
            manager.CreateCircleByRadius(cx, cy, 0.0, entity.radius)
        )

    if kind == "arc_center":
        (cx, cy), (sx, sy), (ex, ey) = entity.center, entity.start, entity.end
        direction = 1 if entity.direction == "counterclockwise" else -1
        return normalize_sequence(
            manager.CreateArc(cx, cy, 0.0, sx, sy, 0.0, ex, ey, 0.0, direction)
        )

    if kind == "arc_3pt":
        (sx, sy), (ex, ey), (tx, ty) = entity.start, entity.end, entity.through
        return normalize_sequence(
            manager.Create3PointArc(sx, sy, 0.0, ex, ey, 0.0, tx, ty, 0.0)
        )

    if kind == "ellipse":
        (cx, cy), (mx, my), (nx, ny) = (
            entity.center,
            entity.major_axis_point,
            entity.minor_axis_point,
        )
        return normalize_sequence(
            manager.CreateEllipse(cx, cy, 0.0, mx, my, 0.0, nx, ny, 0.0)
        )

    if kind == "polygon":
        cx, cy = entity.center
        return normalize_sequence(
            manager.CreatePolygon(
                cx, cy, 0.0, cx + entity.circumradius, cy, 0.0, entity.sides, entity.inscribed
            )
        )

    if kind.startswith("slot_"):
        return _create_slot(manager, entity, kind)

    if kind == "spline":
        flattened: list[float] = []
        for point in entity.points:
            flattened.extend([point[0], point[1], 0.0])
        return normalize_sequence(manager.CreateSpline2(flattened, True))

    raise SwMcpError(
        validation_error("UNSUPPORTED_SKETCH_ENTITY", f"{kind!r} is not a supported primitive.")
    )


@op(
    name="sw_sketch_start",
    tier="core",
    domains=("sketch",),
    tags=("sketch", "plane", "edit"),
    summary=(
        "Open a new sketch on a standard plane, a named plane, or a planar face. "
        "Standard planes resolve by tree position, so a non-English SOLIDWORKS works."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("SK-001",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def sketch_start(ctx: OpContext, args: SketchStartArgs) -> SketchStartResult:
    doc = ctx.require_doc()
    target = args.on
    given = [f for f in (target.standard_plane, target.plane_name, target.ref) if f]
    if len(given) != 1:
        raise SwMcpError(
            validation_error(
                "AMBIGUOUS_SKETCH_PLANE",
                "Give exactly one of standard_plane, plane_name, or ref.",
                context={"given": len(given)},
            )
        )

    try_com_member(doc, "ClearSelection2", True, default=None)
    selected: Any = None
    if target.standard_plane:
        plane = ctx.session.find_standard_plane(doc, target.standard_plane)
        selected = plane.Select2(False, 0)
        described = target.standard_plane
    elif target.plane_name:
        selected = doc.Extension.SelectByID2(
            target.plane_name, "PLANE", 0, 0, 0, False, 0, null_dispatch(), 0
        )
        if not selected:
            raise SwMcpError(
                make_error(
                    "PLANE_NOT_FOUND",
                    "reference",
                    f"No plane named {target.plane_name!r} could be selected.",
                    remediation=["List the document's datum features to see what exists."],
                )
            )
        described = target.plane_name
    else:
        resolution = resolve(
            ctx.session, doc, target.ref, max_candidates=ctx.config.max_candidates
        )
        selected = try_com_member(
            resolution.entity, "Select4", True, null_dispatch(), default=False
        )
        described = resolution.refreshed.label

    before = _sketch_names(doc)
    # InsertSketch is declared void, so there is no return value worth keeping: whether
    # a sketch opened is answered by asking the document, not by what came back.
    doc.SketchManager.InsertSketch(True)
    sketch = active_sketch(doc)
    if sketch is None:
        # An empty context here would leave the caller guessing which half failed, so
        # say whether the plane was selected and what the toggle actually did.
        selection_count = try_com_member(
            doc.SelectionManager, "GetSelectedObjectCount2", -1, default=None
        )
        raise SwMcpError(
            make_error(
                "SKETCH_NOT_STARTED",
                "solidworks",
                "SOLIDWORKS did not open a sketch on the selected plane.",
                context={
                    "target": described,
                    "selection_succeeded": bool(selected),
                    "selected_object_count": selection_count,
                    "sketches_before": len(before),
                    "sketches_after": len(_sketch_names(doc)),
                    "user_control": try_com_member(
                        ctx.session.app, "UserControl", default=None
                    ),
                    "command_in_progress": try_com_member(
                        ctx.session.app, "CommandInProgress", default=None
                    ),
                },
                remediation=[
                    "Confirm the target is planar and not suppressed.",
                    "If selected_object_count is 0 the plane was not selected; if it is 1 "
                    "the sketch toggle itself was refused, which usually means the "
                    "document is not the active one in the SOLIDWORKS window.",
                ],
            )
        )

    name = str(try_com_member(sketch, "Name", default="") or "")
    after = _sketch_names(doc)
    return SketchStartResult(
        sketch_name=name,
        plane=described,
        verification=Verification(
            read_back=True,
            before={"sketch_count": len(before)},
            after={"sketch_count": len(after), "active_sketch": name},
            checks=[
                Check(
                    name="sketch_is_active",
                    passed=bool(name),
                    detail=name or "no active sketch",
                ),
                Check(
                    name="sketch_was_created",
                    passed=len(after) >= len(before),
                    detail=f"{len(before)} -> {len(after)} sketches",
                ),
            ],
        ),
    )


def _sketch_names(doc: Any) -> list[str]:
    names = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        if str(try_com_member(feature, "GetTypeName2", default="")) == "ProfileFeature":
            names.append(str(try_com_member(feature, "Name", default="")))
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return names


@op(
    name="sw_sketch_exit",
    tier="core",
    domains=("sketch",),
    tags=("sketch", "exit", "close"),
    summary="Close the sketch currently open for editing and optionally rebuild the model.",
    safety=ModelMutation(destructive=False),
    satisfies=("SK-001",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def sketch_exit(ctx: OpContext, args: SketchExitArgs) -> SketchExitResult:
    doc = ctx.require_doc()
    sketch = active_sketch(doc)
    name = str(try_com_member(sketch, "Name", default="") or "") if sketch is not None else None

    if sketch is not None:
        doc.SketchManager.InsertSketch(args.rebuild)

    still_open = active_sketch(doc) is not None
    return SketchExitResult(
        exited=not still_open,
        sketch_name=name,
        verification=Verification(
            read_back=True,
            before={"active_sketch": name},
            after={"active_sketch": None if not still_open else name},
            checks=[
                Check(
                    name="no_sketch_open_for_editing",
                    passed=not still_open,
                    detail="editing finished" if not still_open else "a sketch is still open",
                )
            ],
        ),
        warnings=[] if sketch is not None else ["No sketch was open for editing."],
    )


@op(
    name="sw_sketch_list",
    tier="core",
    domains=("sketch",),
    tags=("sketch", "list", "inspect"),
    summary=(
        "List the document's sketches with their solver state, segment counts, and "
        "which one is currently open for editing."
    ),
    safety=ReadSafety(),
    satisfies=("SK-002",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def sketch_list(ctx: OpContext, args: SketchListArgs) -> SketchListResult:
    doc = ctx.require_doc()
    active = active_sketch(doc)
    active_name = str(try_com_member(active, "Name", default="") or "") if active else None

    sketches = []
    for name in _sketch_names(doc):
        sketch = find_sketch(doc, name)
        if sketch is None:
            continue
        segments = sketch_segments(sketch)
        entry: dict[str, Any] = {
            "name": name,
            "segment_count": len(segments),
            "construction_count": sum(
                1 for s in segments if try_com_member(s, "ConstructionGeometry", default=False)
            ),
            "state": sketch_state(sketch),
            "is_active": name == active_name,
        }
        if args.include_geometry:
            entry["segments"] = [describe_segment(s) for s in segments]
        sketches.append(entry)

    return SketchListResult(active_sketch=active_name, sketches=sketches)


@op(
    name="sw_sketch_add_geometry",
    tier="core",
    domains=("sketch",),
    tags=("sketch", "line", "circle", "arc", "rectangle", "polygon", "slot", "spline"),
    summary=(
        "Create sketch primitives in one batch — lines, centerlines, points, rectangles, "
        "circles, arcs, ellipses, polygons, slots, and splines. Each created segment "
        "comes back with a stable id for use in relations, dimensions, and deletes."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("SK-003", "SK-004"),
    partially_satisfies=("FEAT-013",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=300.0,
)
def sketch_add_geometry(ctx: OpContext, args: SketchAddGeometryArgs) -> SketchAddGeometryResult:
    doc = ctx.require_doc()
    sketch = _resolve_sketch(ctx, doc, args.sketch_name)
    name = str(try_com_member(sketch, "Name", default="") or "")
    manager = doc.SketchManager

    before_ids = set(segments_by_id(sketch))

    if args.preflight:
        return SketchAddGeometryResult(
            sketch_name=name,
            created=[
                {"index": index, "type": entity.type, "would_create": True}
                for index, entity in enumerate(args.entities, start=1)
            ],
            sketch_state=sketch_state(sketch),
            verification=Verification(
                read_back=True,
                before={"segment_count": len(before_ids)},
                after={"segment_count": len(before_ids)},
                checks=[
                    Check(name="preflight_only", passed=True, detail="nothing was created")
                ],
            ),
            warnings=["Preflight only: no geometry was created."],
        )

    created: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for index, entity in enumerate(args.entities, start=1):
        try:
            segments = [s for s in _create_entity(manager, entity) if s is not None]
        except SwMcpError as exc:
            failed.append({"index": index, "type": entity.type, "reason": exc.envelope.message})
            continue
        except Exception as exc:  # one bad primitive must not lose the whole batch
            failed.append({"index": index, "type": entity.type, "reason": str(exc)})
            continue

        if not segments:
            failed.append(
                {"index": index, "type": entity.type, "reason": "SOLIDWORKS created no geometry"}
            )
            continue

        wants_construction = entity.construction or entity.type == "centerline"
        for segment in segments:
            if wants_construction:
                try_com_member(segment, "ConstructionGeometry", default=None)
                segment.ConstructionGeometry = True
            # Keep both: the primitive the caller asked for, and what SOLIDWORKS
            # actually produced. A rectangle becomes four lines, so without
            # requested_type there is no way to tell which segments came from which
            # entry in the batch.
            created.append(
                {
                    "index": index,
                    "requested_type": entity.type,
                    **describe_segment(segment),
                }
            )

    after = segments_by_id(sketch)
    return SketchAddGeometryResult(
        sketch_name=name,
        created=created,
        failed=failed,
        sketch_state=sketch_state(sketch),
        verification=Verification(
            read_back=True,
            before={"segment_count": len(before_ids)},
            after={"segment_count": len(after)},
            checks=[
                Check(
                    name="segments_created",
                    passed=len(after) > len(before_ids) if args.entities else True,
                    detail=f"{len(before_ids)} -> {len(after)} segments",
                ),
                Check(
                    name="every_entity_created",
                    passed=not failed,
                    detail=f"{len(failed)} of {len(args.entities)} entities failed"
                    if failed
                    else "all entities created",
                ),
            ],
        ),
        warnings=[f"{len(failed)} entity(ies) could not be created."] if failed else [],
    )


@op(
    name="sw_sketch_set_construction",
    tier="extended",
    domains=("sketch",),
    tags=("sketch", "construction"),
    summary="Toggle segments between construction geometry and profile geometry.",
    safety=ModelMutation(destructive=False),
    satisfies=("SK-004",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def sketch_set_construction(
    ctx: OpContext, args: SketchSetConstructionArgs
) -> SketchSetConstructionResult:
    doc = ctx.require_doc()
    sketch = require_active_sketch(doc)
    available = segments_by_id(sketch)

    changed, missing = [], []
    before = sum(
        1 for s in available.values() if try_com_member(s, "ConstructionGeometry", default=False)
    )

    for identifier in args.segment_ids:
        segment = available.get(identifier)
        if segment is None:
            missing.append(identifier)
            continue
        segment.ConstructionGeometry = args.construction
        changed.append(identifier)

    after = sum(
        1
        for s in segments_by_id(sketch).values()
        if try_com_member(s, "ConstructionGeometry", default=False)
    )
    return SketchSetConstructionResult(
        changed=changed,
        missing=missing,
        verification=Verification(
            read_back=True,
            before={"construction_count": before},
            after={"construction_count": after},
            checks=[
                Check(
                    name="all_segments_found",
                    passed=not missing,
                    detail=f"unknown segment ids: {missing}" if missing else "all ids resolved",
                ),
                Check(
                    name="construction_state_changed",
                    passed=after != before or not changed,
                    detail=f"{before} -> {after} construction segments",
                ),
            ],
        ),
        warnings=[f"{len(missing)} segment id(s) were not found."] if missing else [],
    )


@op(
    name="sw_sketch_delete",
    tier="extended",
    domains=("sketch",),
    tags=("sketch", "delete"),
    summary="Delete sketch segments by their stable ids, reporting which ones were removed.",
    safety=ModelMutation(destructive=True),
    satisfies=("SK-006",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def sketch_delete(ctx: OpContext, args: SketchDeleteArgs) -> SketchDeleteResult:
    doc = ctx.require_doc()
    sketch = require_active_sketch(doc)
    available = segments_by_id(sketch)
    before = len(available)

    deleted, missing = [], []
    absorbed = swconst.value("swDeleteSelectionOptions_e", "swDelete_Absorbed")
    for identifier in args.segment_ids:
        segment = available.get(identifier)
        if segment is None:
            missing.append(identifier)
            continue
        select_segments(doc, [segment])
        try_com_member(doc.Extension, "DeleteSelection2", absorbed, default=None)
        # Trust the model, not the return value: SOLIDWORKS reports deletion
        # inconsistently, so the evidence is that the id no longer resolves.
        if identifier in segments_by_id(sketch):
            missing.append(identifier)
        else:
            deleted.append(identifier)

    after_map = segments_by_id(sketch)
    return SketchDeleteResult(
        deleted=deleted,
        missing=missing,
        sketch_state=sketch_state(sketch),
        verification=Verification(
            read_back=True,
            before={"segment_count": before},
            after={"segment_count": len(after_map)},
            checks=[
                Check(
                    name="segments_removed",
                    passed=len(after_map) == before - len(deleted),
                    detail=f"{before} -> {len(after_map)} segments, {len(deleted)} deleted",
                ),
                Check(
                    name="no_deleted_id_remains",
                    passed=all(identifier not in after_map for identifier in deleted),
                    detail="deleted ids are gone from the sketch",
                ),
            ],
        ),
        warnings=[f"{len(missing)} segment id(s) could not be deleted."] if missing else [],
    )


@op(
    name="sw_sketch_convert_entities",
    tier="extended",
    domains=("sketch",),
    tags=("sketch", "convert", "project"),
    summary=(
        "Project existing edges or faces into the active sketch, returning stable ids "
        "for the segments that were created."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("SK-005",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def sketch_convert_entities(
    ctx: OpContext, args: SketchConvertEntitiesArgs
) -> SketchConvertEntitiesResult:
    doc = ctx.require_doc()
    sketch = require_active_sketch(doc)
    name = str(try_com_member(sketch, "Name", default="") or "")
    before = set(segments_by_id(sketch))

    try_com_member(doc, "ClearSelection2", True, default=None)
    for ref in args.refs:
        resolution = resolve(ctx.session, doc, ref, max_candidates=ctx.config.max_candidates)
        try_com_member(resolution.entity, "Select4", True, null_dispatch(), default=False)

    doc.SketchManager.SketchUseEdge3(args.inner_loops, False)

    after = segments_by_id(sketch)
    created = [describe_segment(segment) for key, segment in after.items() if key not in before]
    return SketchConvertEntitiesResult(
        sketch_name=name,
        created=created,
        verification=Verification(
            read_back=True,
            before={"segment_count": len(before)},
            after={"segment_count": len(after)},
            checks=[
                Check(
                    name="entities_converted",
                    passed=bool(created),
                    detail=f"{len(created)} segment(s) projected into {name}",
                )
            ],
        ),
        warnings=[] if created else ["No geometry was projected; check the references."],
    )


@op(
    name="sw_sketch_modify",
    tier="extended",
    domains=("sketch",),
    tags=("sketch", "move", "rotate", "scale", "mirror", "offset", "trim"),
    summary=(
        "Move, rotate, scale, mirror, offset, or trim sketch geometry, reporting how "
        "many segments the operation affected and the resulting solver state."
    ),
    safety=ModelMutation(destructive=True),
    partially_satisfies=("SK-007",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def sketch_modify(ctx: OpContext, args: SketchModifyArgs) -> SketchModifyResult:
    doc = ctx.require_doc()
    sketch = require_active_sketch(doc)
    manager = doc.SketchManager
    available = segments_by_id(sketch)

    chosen = [available[i] for i in args.segment_ids if i in available]
    missing = [i for i in args.segment_ids if i not in available]
    before_count = len(available)
    selected = select_segments(doc, chosen) if chosen else 0

    # None of ISketchManager's members do this: SketchMove, SketchRotate and SketchScale
    # are on no interface in the type library. The transforms live on IModelDoc2 and
    # IModelDocExtension, and they are not interchangeable — SketchModifyScale returns
    # True and changes nothing, while Extension.ScaleOrCopy does the work.
    if args.keep_original and args.operation == "rotate":
        raise SwMcpError(
            validation_error(
                "UNSUPPORTED_OPTION",
                "The rotate API turns the selected geometry in place; it cannot leave a "
                "copy behind.",
                context={"operation": args.operation, "keep_original": True},
                remediation=["Drop keep_original, or mirror the geometry instead."],
            )
        )

    if args.operation == "move":
        _require(args.delta, "delta", "move")
        if args.keep_original:
            doc.Extension.MoveOrCopy(
                True, 1, False, 0.0, 0.0, 0.0, args.delta[0], args.delta[1], 0.0
            )
        else:
            # SketchModifyTranslate takes a from-point and a to-point, so the delta is
            # expressed as a move away from the origin.
            doc.SketchModifyTranslate(0.0, 0.0, args.delta[0], args.delta[1])
    elif args.operation == "rotate":
        _require(args.angle, "angle", "rotate")
        _require(args.about, "about", "rotate")
        doc.SketchModifyRotate(args.about[0], args.about[1], args.angle)
    elif args.operation == "scale":
        _require(args.factor, "factor", "scale")
        about = args.about or [0.0, 0.0]
        doc.Extension.ScaleOrCopy(
            args.keep_original, 1, about[0], about[1], 0.0, args.factor
        )
    elif args.operation == "mirror":
        _require(args.mirror_axis_id, "mirror_axis_id", "mirror")
        axis = available.get(args.mirror_axis_id)
        if axis is None:
            raise SwMcpError(
                validation_error(
                    "SEGMENT_NOT_FOUND",
                    f"No sketch segment with id {args.mirror_axis_id!r} to mirror about.",
                )
            )
        try_com_member(axis, "Select2", True, 0, default=False)
        doc.SketchMirror()
    elif args.operation == "offset":
        _require(args.distance, "distance", "offset")
        manager.SketchOffset2(args.distance, False, True, 0, 0, False)
    else:  # trim
        manager.SketchTrim(0, 0.0, 0.0, 0.0)

    after = segments_by_id(sketch)
    return SketchModifyResult(
        operation=args.operation,
        affected=selected,
        sketch_state=sketch_state(sketch),
        verification=Verification(
            read_back=True,
            before={"segment_count": before_count, "selected": selected},
            after={"segment_count": len(after)},
            checks=[
                Check(
                    name="segments_resolved",
                    passed=not missing,
                    detail=f"unknown segment ids: {missing}" if missing else "all ids resolved",
                ),
                Check(
                    name="sketch_still_solvable",
                    passed=sketch_state(sketch)["status"]
                    not in {"no_solution", "invalid_solution"},
                    detail=sketch_state(sketch)["status"],
                ),
            ],
        ),
        warnings=[f"{len(missing)} segment id(s) were not found."] if missing else [],
    )


def _require(value: Any, field: str, operation: str) -> None:
    if value is None:
        raise SwMcpError(
            validation_error(
                "MISSING_ARGUMENT",
                f"{field!r} is required for the {operation!r} operation.",
                context={"operation": operation, "missing": field},
            )
        )


_TEXT_ALIGNMENT = {"left": 0, "center": 1, "right": 2, "justified": 3}


@op(
    name="sw_sketch_text",
    tier="core",
    domains=("sketch",),
    tags=("text", "engrave", "emboss", "sketch"),
    summary=(
        "Draw sketch text, optionally running along a sketch segment, so engraving and "
        "embossing do not need a macro. Verified by counting the text back out."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("SK-008",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def sketch_text(ctx: OpContext, args: SketchTextArgs) -> SketchTextResult:
    """SK-008.

    Font is not an argument, and that is a limitation rather than an oversight:
    ``InsertSketchText`` takes no font, and SOLIDWORKS reads it from the *document's*
    text-format preference. Exposing it here would mean changing a document-wide setting
    as a side effect of drawing one string, and leaving it changed afterwards. So the
    text is drawn in whatever font the document uses, and the limitation is declared.

    Alignment and flip only apply when a path is selected — with mark 1, which is why
    the segment is selected rather than passed as an argument.
    """
    doc = ctx.require_doc()
    sketch = _resolve_sketch(ctx, doc, args.sketch_name)
    name = str(try_com_member(sketch, "Name", default="") or "")
    before = len(normalize_sequence(
        try_com_member(sketch, "GetSketchTextSegments", default=None)
    ))

    try_com_member(doc, "ClearSelection2", True, default=None)
    on_path = False
    if args.path_segment_id is not None:
        segment = segments_by_id(sketch).get(args.path_segment_id)
        if segment is None:
            raise SwMcpError(
                make_error(
                    "SEGMENT_NOT_FOUND",
                    "validation",
                    f"Sketch {name!r} has no segment {args.path_segment_id!r}.",
                    remediation=["List the sketch to see the ids it actually holds."],
                )
            )
        # Mark 1 is the whole contract for a text path; anything else and SOLIDWORKS
        # silently lays the text out horizontally instead.
        on_path = bool(try_com_member(segment, "Select2", True, 1, default=False))
        if not on_path:
            raise SwMcpError(
                make_error(
                    "SEGMENT_NOT_SELECTABLE",
                    "reference",
                    f"Could not select {args.path_segment_id!r} as the text path.",
                )
            )

    made = try_com_member(
        doc,
        "InsertSketchText",
        float(args.at[0]),
        float(args.at[1]),
        0.0,
        args.text,
        _TEXT_ALIGNMENT[args.alignment],
        int(args.flip_vertical),
        int(args.mirror_horizontal),
        args.width_factor,
        args.char_spacing,
        default=None,
    )
    try_com_member(doc, "ClearSelection2", True, default=None)

    after = len(normalize_sequence(
        try_com_member(sketch, "GetSketchTextSegments", default=None)
    ))
    if made is None or after <= before:
        raise SwMcpError(
            make_error(
                "SKETCH_TEXT_FAILED",
                "solidworks",
                f"SOLIDWORKS did not add the text to {name!r}.",
                context={"text": args.text, "on_path": on_path},
                remediation=[
                    "A sketch must be open; start one first.",
                    "Text on a path needs a segment in the same sketch.",
                ],
            )
        )

    return SketchTextResult(
        sketch_name=name,
        text=args.text,
        on_path=on_path,
        text_segment_count=after,
        alignment=args.alignment,
        sketch_state=sketch_state(sketch),
        verification=Verification(
            read_back=True,
            before={"text_segment_count": before},
            after={"text_segment_count": after},
            checks=[
                Check(
                    name="text_added",
                    passed=after > before,
                    detail=f"{before} -> {after} text segment(s)",
                ),
                Check(
                    name="path_selected_when_requested",
                    passed=on_path == (args.path_segment_id is not None),
                    detail="text follows the given segment" if on_path else "horizontal text",
                ),
            ],
        ),
    )
