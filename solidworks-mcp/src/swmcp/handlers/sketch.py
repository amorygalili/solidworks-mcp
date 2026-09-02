"""Sketch domain: start, edit, inspect, and modify sketch geometry."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import (
    array_of_doubles,
    normalize_sequence,
    null_dispatch,
    try_com_member,
)
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import (
    SwMcpError,
    make_error,
    validation_error,
    wire_safe_validation_errors,
)
from swmcp.refs.resolve import resolve
from swmcp.safety.paths import normalize_cad_path
from swmcp.schemas.sketch import (
    SketchAddGeometryArgs,
    SketchAddGeometryResult,
    SketchConvertEntitiesArgs,
    SketchConvertEntitiesResult,
    SketchCreateArgs,
    SketchCreateResult,
    SketchDeleteArgs,
    SketchDeleteResult,
    SketchEntity,
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
    compact_created,
)
from swmcp.sketching import (
    active_sketch,
    analyze_contours,
    anchor_deviation,
    contour_warnings,
    describe_segment,
    find_sketch,
    require_active_sketch,
    segment_endpoints,
    segment_topology,
    segments_by_id,
    select_segments,
    sketch_segments,
    sketch_state,
)
from swmcp.units import COORDINATE_TOLERANCE_M, from_meters


@contextlib.contextmanager
def _editing(ctx: OpContext, doc: Any, name: str | None):
    """Yield the sketch to work on, opening it for editing only if it is not already.

    ``ISketchManager::InsertSketch`` *toggles*, so closing whatever happens to be open
    and reopening the target would silently discard the caller's editing session. If a
    different sketch is open, this refuses instead - shutting someone else's sketch is
    not a side effect a delete should have.
    """
    open_now = active_sketch(doc)
    open_name = (
        str(try_com_member(open_now, "Name", default="") or "") if open_now is not None else None
    )
    if name is None:
        yield require_active_sketch(doc)
        return
    if open_name == name:
        yield open_now
        return
    if open_now is not None:
        raise SwMcpError(
            make_error(
                "SKETCH_ALREADY_OPEN",
                "validation",
                f"{open_name!r} is open for editing, so {name!r} cannot be edited too.",
                context={"open_sketch": open_name, "requested": name},
                remediation=[
                    "Exit the open sketch first, or address that one instead.",
                ],
            )
        )

    sketch = _resolve_sketch(ctx, doc, name)
    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = doc.Extension.SelectByID2(
        name, "SKETCH", 0, 0, 0, False, 0, null_dispatch(), 0
    )
    if not selected:
        raise SwMcpError(
            make_error(
                "SKETCH_NOT_SELECTABLE",
                "reference",
                f"The sketch {name!r} exists but could not be selected for editing.",
                context={"sketch": name},
                remediation=["Open it by hand, or pass its segments while it is active."],
            )
        )
    try_com_member(doc, "EditSketch", default=None)
    try:
        yield active_sketch(doc) or sketch
    finally:
        # Close it again only if this opened it, and only if it is still open.
        if active_sketch(doc) is not None:
            doc.SketchManager.InsertSketch(True)


def load_entities(args: Any) -> list[Any]:
    """The entities to draw, from the request or from the file it names.

    Validated through the same discriminated union either way, so a file cannot
    smuggle in a shape the inline route would have refused.
    """
    if not getattr(args, "entities_file", None):
        return list(args.entities)

    path = Path(normalize_cad_path(args.entities_file))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SwMcpError(
            make_error(
                "ENTITIES_FILE_NOT_FOUND",
                "validation",
                f"No entities file at {str(path)!r}.",
                context={"entities_file": str(path)},
                remediation=["Write the profile to that path, or pass entities inline."],
            )
        ) from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SwMcpError(
            make_error(
                "ENTITIES_FILE_UNREADABLE",
                "validation",
                f"Could not read {str(path)!r} as UTF-8 JSON: {exc}",
                context={"entities_file": str(path)},
                remediation=["The file must be UTF-8 JSON: a list of entities, or an "
                             "object with an 'entities' key."],
            )
        ) from exc

    if isinstance(raw, dict):
        raw = raw.get("entities")
    if not isinstance(raw, list) or not raw:
        raise SwMcpError(
            validation_error(
                "ENTITIES_FILE_EMPTY",
                f"{str(path)!r} holds no entities.",
                context={"entities_file": str(path)},
            )
        )
    if len(raw) > 500:
        raise SwMcpError(
            validation_error(
                "ENTITIES_FILE_TOO_LARGE",
                f"{str(path)!r} holds {len(raw)} entities; the limit is 500.",
                context={"entities_file": str(path), "count": len(raw)},
            )
        )

    adapter = TypeAdapter(list[SketchEntity])
    try:
        return adapter.validate_python(raw)
    except ValidationError as exc:
        raise SwMcpError(
            validation_error(
                "ENTITIES_FILE_INVALID",
                f"{str(path)!r} does not hold valid sketch entities.",
                context={
                    "entities_file": str(path),
                    "errors": wire_safe_validation_errors(exc)[:5],
                },
            )
        ) from exc


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


#: Which of an entity's declared points must come back as an actual segment endpoint.
#:
#: Only forms whose coordinates *are* ends can be checked this way. A circle's centre,
#: a polygon's centre and a spline's interior points sit on no endpoint, so those forms
#: are left unmeasured rather than measured against the wrong thing — an unchecked
#: entity reports no deviation instead of a misleading zero.
_ENTITY_ANCHORS: dict[str, tuple[str, ...]] = {
    "line": ("start", "end"),
    "centerline": ("start", "end"),
    "arc_center": ("start", "end"),
    "arc_3pt": ("start", "end"),
    "rect_corner": ("corner", "opposite"),
    "rect_center": ("corner",),
}


def _requested_anchors(entity: Any) -> list[tuple[float, float]]:
    """The points this entity promised would end up as segment ends, in metres."""
    points: list[tuple[float, float]] = []
    for field in _ENTITY_ANCHORS.get(entity.type, ()):
        value = getattr(entity, field, None)
        if value is not None and len(value) >= 2:
            points.append((float(value[0]), float(value[1])))
    return points


class _InferenceOff:
    """Suspend SOLIDWORKS' sketch inference for the duration of a batch.

    ``ISketchManager::AddToDB`` puts geometry straight into the sketch database
    without the snapping and auto-relations that a human sketcher wants — so the
    caller's flag reads ``auto_relations=False`` and the property goes *True*. The
    inversion is worth the confusion at this one site: the caller should not have to
    know the API's name for "stop helping".

    Restoring the previous value matters more than setting it. SOLIDWORKS is the
    user's live application; leaving inference off would quietly change how their next
    hand-drawn sketch behaves, with nothing on screen to say why.
    """

    def __init__(self, manager: Any, *, enabled: bool) -> None:
        self._manager = manager
        self._enabled = enabled
        self._previous: Any = None
        self._applied = False

    def __enter__(self) -> _InferenceOff:
        if self._enabled:
            self._previous = try_com_member(self._manager, "AddToDB", default=None)
            try:
                self._manager.AddToDB = True
                self._applied = True
            except Exception:
                # A build that will not accept the property falls back to inference-on,
                # which is the safe direction: the caller still gets measured deviations
                # and a warning, rather than a batch that silently did not run.
                self._applied = False
        return self

    def __exit__(self, *_exc: Any) -> None:
        # Keyed to whether the write actually happened, not to whether the read did.
        # Reading the old value can fail on its own; if it does and the write then
        # succeeds, this is the only thing standing between the user and a SOLIDWORKS
        # left with inference off for every sketch they draw afterwards.
        if self._applied:
            with contextlib.suppress(Exception):
                self._manager.AddToDB = bool(self._previous)

    @property
    def engaged(self) -> bool:
        return self._applied


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
        # CreateSpline2 reads PointData as a SAFEARRAY of doubles. A bare Python list
        # marshals as VT_ARRAY | VT_VARIANT, which SOLIDWORKS answers by returning
        # nothing at all rather than raising - so the spline just never appears.
        flattened: list[float] = []
        for point in entity.points:
            flattened.extend([point[0], point[1], 0.0])
        return normalize_sequence(manager.CreateSpline2(array_of_doubles(flattened), True))

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
    deviations: list[tuple[int, str, float]] = []

    entities = load_entities(args)
    with _InferenceOff(manager, enabled=not args.auto_relations) as inference:
        for index, entity in enumerate(entities, start=1):
            try:
                segments = [s for s in _create_entity(manager, entity) if s is not None]
            except SwMcpError as exc:
                failed.append(
                    {"index": index, "type": entity.type, "reason": exc.envelope.message}
                )
                continue
            except Exception as exc:  # one bad primitive must not lose the whole batch
                failed.append({"index": index, "type": entity.type, "reason": str(exc)})
                continue

            if not segments:
                failed.append(
                    {
                        "index": index,
                        "type": entity.type,
                        "reason": "SOLIDWORKS created no geometry",
                    }
                )
                continue

            # Measure before anything else touches the segments: what matters is where
            # SOLIDWORKS put them, and the answer is only trustworthy while it is the
            # most recent thing that happened to this geometry.
            actual_ends: list[tuple[float, float]] = []
            for segment in segments:
                actual_ends.extend(segment_endpoints(segment))
            gap = anchor_deviation(_requested_anchors(entity), actual_ends)
            if gap is not None:
                deviations.append((index, entity.type, gap))

            wants_construction = entity.construction or entity.type == "centerline"
            for segment in segments:
                if wants_construction:
                    try_com_member(segment, "ConstructionGeometry", default=None)
                    segment.ConstructionGeometry = True
                # Keep both: the primitive the caller asked for, and what SOLIDWORKS
                # actually produced. A rectangle becomes four lines, so without
                # requested_type there is no way to tell which segments came from which
                # entry in the batch.
                entry = {
                    "index": index,
                    "requested_type": entity.type,
                    **describe_segment(segment),
                }
                if gap is not None:
                    entry["deviation_mm"] = round(from_meters(gap, "mm"), 6)
                created.append(entry)

        inference_engaged = inference.engaged

    worst = max((gap for _, _, gap in deviations), default=None)
    moved = [
        (index, kind, gap)
        for index, kind, gap in deviations
        if gap > COORDINATE_TOLERANCE_M
    ]

    extra_warnings: list[str] = []
    if moved:
        worst_index, worst_type, worst_gap = max(moved, key=lambda item: item[2])
        extra_warnings.append(
            f"{len(moved)} of {len(deviations)} measured entity(ies) were placed away "
            f"from the coordinates given, by up to "
            f"{from_meters(worst_gap, 'mm'):.4f} mm "
            f"(entity {worst_index}, {worst_type}). SOLIDWORKS' sketch inference snaps "
            f"new geometry onto nearby entities; pass auto_relations=false to place it "
            f"exactly as written."
        )
    if not args.auto_relations and not inference_engaged:
        extra_warnings.append(
            "auto_relations=false was requested but this build would not accept "
            "ISketchManager::AddToDB, so inference stayed on and geometry may have "
            "snapped. The reported deviations still say whether it did."
        )

    after = segments_by_id(sketch)
    shown, compacted = compact_created(created, args.detail)
    return SketchAddGeometryResult(
        sketch_name=name,
        created=shown,
        created_total=len(created),
        created_compacted=compacted,
        failed=failed,
        sketch_state=sketch_state(sketch),
        max_deviation_mm=None if worst is None else round(from_meters(worst, "mm"), 6),
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
                    detail=f"{len(failed)} of {len(entities)} entities failed"
                    if failed
                    else "all entities created",
                ),
                # "It was created" and "it was created where I asked" are different
                # claims, and only the first one used to be made. A batch that snapped
                # onto neighbouring geometry passed every check while quietly modelling
                # something else.
                Check(
                    name="coordinates_as_requested",
                    passed=not moved,
                    detail="nothing measurable in this batch"
                    if worst is None
                    else f"worst placement gap {from_meters(worst, 'mm'):.4f} mm across "
                    f"{len(deviations)} measured entity(ies)",
                ),
            ],
        ),
        warnings=(
            [f"{len(failed)} entity(ies) could not be created."] if failed else []
        )
        + extra_warnings,
    )


@op(
    name="sw_sketch_create",
    tier="core",
    domains=("sketch",),
    tags=("sketch", "profile", "batch", "compose"),
    summary=(
        "Open a sketch on a plane, draw a profile into it, and close it - the whole "
        "cadence in one call, reporting where every point landed and whether the "
        "profile closes."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("SK-001", "SK-003", "SK-004"),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=300.0,
)
def sketch_create(ctx: OpContext, args: SketchCreateArgs) -> SketchCreateResult:
    """Compose the three sketch operations rather than reimplement them.

    Each step is the same handler a caller would have reached for, so the behaviour
    cannot drift from the individual tools: fixing a bug in sw_sketch_add_geometry
    fixes it here too. What this adds is one checkpoint instead of three, two fewer
    round trips on the serialized COM thread, and the contour analysis at the end -
    the point at which "is this profile usable?" is worth asking, because it is the
    last moment before a feature tries to consume it.
    """
    doc = ctx.require_doc()

    started = sketch_start(ctx, SketchStartArgs(on=args.on))
    # The file is handed on rather than read here, so both routes load it in exactly
    # one place and a malformed file fails the same way whichever tool was called.
    added = sketch_add_geometry(
        ctx,
        SketchAddGeometryArgs(
            entities=args.entities,
            entities_file=args.entities_file,
            sketch_name=None,
            auto_relations=args.auto_relations,
            detail=args.detail,
        ),
    )

    exited = False
    if args.exit_sketch:
        sketch_exit(ctx, SketchExitArgs(rebuild=args.rebuild))
        exited = True

    # Re-found by name: exiting the sketch invalidates nothing, but the handle came
    # from before the exit and asking the document again is cheaper than reasoning
    # about whether it survived.
    sketch = find_sketch(doc, started.sketch_name)
    contours = analyze_contours(segment_topology(sketch)) if sketch is not None else {}

    warnings = list(started.warnings) + list(added.warnings) + contour_warnings(contours)

    return SketchCreateResult(
        sketch_name=started.sketch_name,
        plane=started.plane,
        created=added.created,
        created_total=added.created_total,
        created_compacted=added.created_compacted,
        failed=added.failed,
        sketch_state=added.sketch_state,
        max_deviation_mm=added.max_deviation_mm,
        exited=exited,
        contours=contours,
        warnings=warnings,
        verification=Verification(
            read_back=True,
            before={"segment_count": 0},
            after={
                "sketch": started.sketch_name,
                "segment_count": added.created_total,
                "closed_contour_count": contours.get("closed_contour_count"),
            },
            checks=[
                Check(
                    name="sketch_created",
                    passed=bool(started.sketch_name),
                    detail=started.sketch_name or "no sketch came back",
                ),
                Check(
                    name="every_entity_created",
                    passed=not added.failed,
                    detail=f"{len(added.failed)} of "
                    f"{len(added.failed) + added.created_total} entities failed"
                    if added.failed
                    else "all entities created",
                ),
                # Carried through rather than re-derived: the sub-handler measured it
                # against the request, and restating the number here would be a second
                # place for it to be wrong.
                Check(
                    name="coordinates_as_requested",
                    passed=(
                        added.max_deviation_mm is None
                        or added.max_deviation_mm
                        <= from_meters(COORDINATE_TOLERANCE_M, "mm")
                    ),
                    detail="nothing measurable in this batch"
                    if added.max_deviation_mm is None
                    else f"worst placement gap {added.max_deviation_mm} mm",
                ),
                Check(
                    name="sketch_closed_for_editing",
                    passed=exited or not args.exit_sketch,
                    detail="left open on request" if not args.exit_sketch else "exited",
                ),
            ],
        ),
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
    deleted, missing = [], []
    absorbed = swconst.value("swDeleteSelectionOptions_e", "swDelete_Absorbed")

    with _editing(ctx, doc, args.sketch_name) as sketch:
        available = segments_by_id(sketch)
        before = len(available)

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
        state = sketch_state(sketch)
    return SketchDeleteResult(
        deleted=deleted,
        missing=missing,
        sketch_state=state,
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
                    # Requiring `deleted` to be non-empty is the point: over an empty
                    # list this passes vacuously, so a delete that removed nothing used
                    # to report all-green.
                    passed=bool(deleted)
                    and all(identifier not in after_map for identifier in deleted),
                    detail=(
                        "deleted ids are gone from the sketch"
                        if deleted
                        else f"nothing was deleted; {len(missing)} id(s) did not resolve"
                    ),
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
