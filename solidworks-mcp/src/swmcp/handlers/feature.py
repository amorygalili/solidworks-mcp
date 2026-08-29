"""Datum geometry, core part features, bodies, and measurement.

Every mutation here compares a :func:`swmcp.modeling.model_snapshot` taken before and
after, so "the extrude worked" means the body count and volume actually changed —
not that a COM call returned without raising.
"""

from __future__ import annotations

from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import get_com_member, normalize_sequence, null_dispatch, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.modeling import (
    area_from_m2_display,
    bodies,
    body_mass_properties,
    body_summary,
    describe_feature,
    document_density,
    document_mass_properties,
    feature_count,
    find_feature,
    latest_unused_sketch,
    model_snapshot,
    volume_to_display,
)
from swmcp.refs.capture import capture
from swmcp.refs.resolve import resolve
from swmcp.schemas.feature import (
    BodyListArgs,
    BodyListResult,
    ChamferArgs,
    DatumAxisCreateArgs,
    DatumAxisCreateResult,
    DatumCsysCreateArgs,
    DatumCsysCreateResult,
    DatumCsysTransform,
    DatumListArgs,
    DatumListResult,
    DatumPlaneCreateArgs,
    DatumPlaneCreateResult,
    DatumPointCreateArgs,
    DatumPointCreateResult,
    DraftArgs,
    DraftResult,
    EdgeFeatureResult,
    ExtrudeArgs,
    ExtrudeResult,
    FeatureDeleteArgs,
    FeatureDeleteResult,
    FeatureEditArgs,
    FeatureEditResult,
    FeatureListArgs,
    FeatureListResult,
    FilletArgs,
    HoleArgs,
    HoleResult,
    LoftArgs,
    LoftResult,
    MeasureArgs,
    MeasureResult,
    PatternArgs,
    PatternResult,
    RevolveArgs,
    RevolveResult,
    SweepArgs,
    SweepResult,
)
from swmcp.units import from_meters

_DATUM_TYPES = {
    "RefPlane": "planes",
    "RefAxis": "axes",
    "RefPoint": "points",
    "CoordSys": "coordinate_systems",
}


def _select_refs(ctx: OpContext, doc: Any, refs: list[Any], *, mark: int = 0) -> int:
    """Resolve and select a list of entity references, returning how many took.

    ``Select4`` carries no selection mark, so when a mark matters — a pattern direction,
    a revolve axis — ``Select2`` has to come first. Reversing this silently selects
    everything with mark 0, and the feature call then fails as if the reference were
    wrong rather than the selection.
    """
    selected = 0
    for ref in refs:
        resolution = resolve(ctx.session, doc, ref, max_candidates=ctx.config.max_candidates)
        entity = resolution.entity
        if mark:
            took = try_com_member(entity, "Select2", True, mark, default=False) or (
                try_com_member(entity, "Select4", True, null_dispatch(), default=False)
            )
        else:
            took = try_com_member(entity, "Select4", True, null_dispatch(), default=False) or (
                try_com_member(entity, "Select2", True, 0, default=False)
            )
        if took:
            selected += 1
    return selected


def _select_sketch(doc: Any, name: str | None) -> str:
    """Select a profile sketch by name, or the most recent unconsumed one."""
    chosen = name or latest_unused_sketch(doc)
    if not chosen:
        raise SwMcpError(
            make_error(
                "NO_PROFILE_SKETCH",
                "validation",
                "No sketch is available to use as a profile.",
                remediation=[
                    "Create a sketch first, or name one explicitly with sketch_name.",
                ],
            )
        )
    try_com_member(doc, "ClearSelection2", True, default=None)
    if not doc.Extension.SelectByID2(chosen, "SKETCH", 0, 0, 0, False, 0, null_dispatch(), 0):
        raise SwMcpError(
            make_error(
                "SKETCH_NOT_SELECTABLE",
                "reference",
                f"Could not select the sketch {chosen!r} as a profile.",
                remediation=["List the document's sketches to check the name."],
            )
        )
    return chosen


def _new_feature(doc: Any, before_names: set[str]) -> Any | None:
    """The feature that appeared since ``before_names`` was captured."""
    feature = try_com_member(doc, "FirstFeature", default=None)
    newest = None
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        name = str(try_com_member(feature, "Name", default="") or "")
        if name and name not in before_names:
            newest = feature
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return newest


def _feature_names(doc: Any) -> set[str]:
    names = set()
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        names.add(str(try_com_member(feature, "Name", default="") or ""))
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return names


def _geometry_checks(before: dict[str, Any], after: dict[str, Any], *, expect: str) -> list[Check]:
    """The invariants that make a feature operation verifiable rather than assumed."""
    volume_before = before.get("volume_m3") or 0.0
    volume_after = after.get("volume_m3") or 0.0

    if expect == "more":
        passed = volume_after > volume_before or after["body_count"] > before["body_count"]
        detail = "material was added"
    elif expect == "less":
        passed = volume_after < volume_before
        detail = "material was removed"
    else:
        passed = volume_after != volume_before or after["body_count"] != before["body_count"]
        detail = "the model changed"

    return [
        Check(
            name="geometry_changed",
            passed=passed,
            detail=(
                f"{detail}: volume {before.get('volume_mm3'):.3f} -> "
                f"{after.get('volume_mm3'):.3f} mm³, "
                f"bodies {before['body_count']} -> {after['body_count']}"
            )
            if before.get("volume_mm3") is not None and after.get("volume_mm3") is not None
            else detail,
        ),
        Check(
            name="model_has_a_body",
            passed=after["body_count"] > 0,
            detail=f"{after['body_count']} solid body(ies)",
        ),
    ]


# --- datum --------------------------------------------------------------------


@op(
    name="sw_datum_list",
    tier="core",
    domains=("datum", "reference"),
    tags=("datum", "plane", "axis", "point", "origin"),
    summary=(
        "List the document's reference geometry — planes, axes, points, and coordinate "
        "systems — with their locale-invariant type tokens and capture-ready references."
    ),
    safety=ReadSafety(),
    satisfies=("DAT-001", "DAT-005"),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def datum_list(ctx: OpContext, args: DatumListArgs) -> DatumListResult:
    _ = args
    doc = ctx.require_doc()
    buckets: dict[str, list[dict[str, Any]]] = {
        "planes": [],
        "axes": [],
        "points": [],
        "coordinate_systems": [],
    }
    origin = None
    standard = {p["name"]: p for p in ctx.session.standard_planes(doc)}

    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        type_name = str(try_com_member(feature, "GetTypeName2", default="") or "")
        name = str(try_com_member(feature, "Name", default="") or "")
        if type_name == "OriginProfileFeature":
            origin = {"name": name, "type_name": type_name}
        bucket = _DATUM_TYPES.get(type_name)
        if bucket:
            # The summary promises capture-ready references, so every datum carries one:
            # listing datums you then cannot address would make the tool a dead end.
            reference = capture(ctx.session, doc, feature)
            entry = {
                "name": name,
                "type_name": type_name,
                "suppressed": bool(try_com_member(feature, "IsSuppressed", default=False)),
                "ref": reference.model_dump(mode="json", exclude_none=True),
                "tool_args": reference.tool_args(),
            }
            if type_name == "RefPlane" and name in standard:
                entry["standard"] = standard[name]["standard"]
                entry["index"] = standard[name]["index"]
            buckets[bucket].append(entry)
        feature = try_com_member(feature, "GetNextFeature", default=None)

    return DatumListResult(origin=origin, **buckets)


@op(
    name="sw_datum_plane_create",
    tier="core",
    domains=("datum",),
    tags=("datum", "plane", "offset", "angle", "midplane"),
    summary=(
        "Create a reference plane by offset, angle, midplane, three points, or tangency, "
        "and read back the plane that was actually created."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("DAT-002",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def datum_plane_create(ctx: OpContext, args: DatumPlaneCreateArgs) -> DatumPlaneCreateResult:
    doc = ctx.require_doc()
    needed = {"offset": 1, "angle": 2, "mid": 2, "three_point": 3, "tangent": 2}[args.method]
    supplied = len(args.refs) + (1 if args.standard_plane else 0)
    if supplied != needed:
        raise SwMcpError(
            validation_error(
                "WRONG_REFERENCE_COUNT",
                f"The {args.method!r} method needs {needed} reference(s), got {supplied}.",
                context={"method": args.method, "required": needed, "supplied": supplied},
            )
        )
    if args.method == "offset" and args.distance is None:
        raise SwMcpError(
            validation_error("MISSING_ARGUMENT", "An offset plane needs a distance.")
        )
    if args.method == "angle" and args.angle is None:
        raise SwMcpError(validation_error("MISSING_ARGUMENT", "An angled plane needs an angle."))

    before = _feature_names(doc)
    try_com_member(doc, "ClearSelection2", True, default=None)

    if args.standard_plane:
        plane = ctx.session.find_standard_plane(doc, args.standard_plane)
        plane.Select2(True, 0)
    _select_refs(ctx, doc, args.refs)

    manager = doc.FeatureManager
    def _constraint(member: str) -> int:
        return swconst.value("swRefPlaneReferenceConstraints_e", member)

    constraint = _constraint("swRefPlaneReferenceConstraint_Distance")
    by_method = {
        "angle": "swRefPlaneReferenceConstraint_Angle",
        "mid": "swRefPlaneReferenceConstraint_MidPlane",
        "tangent": "swRefPlaneReferenceConstraint_Tangent",
        "three_point": "swRefPlaneReferenceConstraint_Coincident",
    }
    if args.method in by_method:
        constraint = _constraint(by_method[args.method])

    value = args.distance if args.method == "offset" else (args.angle or 0.0)
    if args.flip:
        constraint |= _constraint("swRefPlaneReferenceConstraint_OptionFlip")

    feature = manager.InsertRefPlane(constraint, value, 0, 0, 0, 0)
    if feature is None:
        raise SwMcpError(
            make_error(
                "PLANE_CREATE_FAILED",
                "solidworks",
                f"SOLIDWORKS could not create a {args.method} plane from those references.",
                remediation=[
                    "Check that the references suit the method: an offset needs one plane "
                    "or planar face, a midplane needs two.",
                ],
            )
        )

    if args.name:
        feature.Name = args.name
    name = str(try_com_member(feature, "Name", default="") or "")
    after = _feature_names(doc)
    reference = capture(ctx.session, doc, feature)

    return DatumPlaneCreateResult(
        plane_name=name,
        method=args.method,
        reference={
            **reference.model_dump(mode="json", exclude_none=True),
            "tool_args": reference.tool_args(),
        },
        verification=Verification(
            read_back=True,
            before={"feature_count": len(before)},
            after={"feature_count": len(after)},
            checks=[
                Check(name="plane_created", passed=bool(name), detail=name or "no plane returned"),
                Check(
                    name="feature_tree_grew",
                    passed=len(after) > len(before),
                    detail=f"{len(before)} -> {len(after)} features",
                ),
            ],
        ),
    )


_AXIS_REFERENCE_COUNT = {
    "one_line": 1,
    "two_planes": 2,
    "two_points": 2,
    "cyl_face": 1,
    "point_and_plane": 2,
}

_REF_POINT_TYPES = {
    "along_curve": "swRefPointAlongCurve",
    # swRefPointCenterEdge is the *arc* centre: SOLIDWORKS rejects a straight edge for
    # it, which probing found the hard way. The schema name says so.
    "arc_center": "swRefPointCenterEdge",
    "face_center": "swRefPointFaceCenter",
    "face_vertex_projection": "swRefPointFaceVertexProjection",
    "intersection": "swRefPointIntersection",
    "sketch_point": "swRefPointSketchPoint",
}

_ALONG_CURVE_TYPES = {
    "distance": "swRefPointAlongCurveDistance",
    "percentage": "swRefPointAlongCurvePercentage",
    "evenly": "swRefPointAlongCurveEvenlyDistributed",
}

#: ``InsertCoordinateSystem`` reads its references from selection *marks*, not from
#: argument order: 1 origin, 2 X, 4 Y, 8 Z. Selecting them all with mark 0 produces a
#: system at the model origin rather than an error, so the mark is the whole contract.
_CSYS_MARKS = {"origin": 1, "x_axis": 2, "y_axis": 4, "z_axis": 8}


def _select_marked(ctx: OpContext, doc: Any, ref: Any, mark: int) -> bool:
    """Select one reference under a specific mark.

    ``Select4`` cannot carry a mark, so this goes through ``Select2`` and appends
    rather than replacing: a coordinate system needs up to four marked selections
    live at the same time.
    """
    resolution = resolve(ctx.session, doc, ref, max_candidates=ctx.config.max_candidates)
    return bool(try_com_member(resolution.entity, "Select2", True, mark, default=False))


def _datum_checks(before: set[str], after: set[str], name: str, kind: str) -> list[Check]:
    return [
        Check(
            name=f"{kind}_created",
            passed=bool(name),
            detail=name or f"no {kind} came back from SOLIDWORKS",
        ),
        Check(
            name="feature_tree_grew",
            passed=len(after) > len(before),
            detail=f"{len(before)} -> {len(after)} features",
        ),
    ]


@op(
    name="sw_datum_axis_create",
    tier="core",
    domains=("datum",),
    tags=("datum", "axis", "reference"),
    summary=(
        "Create a reference axis from one line, two planes, two points, a cylindrical "
        "face, or a point and a plane, and read back the axis that was actually made."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("DAT-003",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def datum_axis_create(ctx: OpContext, args: DatumAxisCreateArgs) -> DatumAxisCreateResult:
    doc = ctx.require_doc()
    needed = _AXIS_REFERENCE_COUNT[args.method]
    supplied = len(args.refs) + len(args.standard_planes)
    if supplied != needed:
        raise SwMcpError(
            validation_error(
                "WRONG_REFERENCE_COUNT",
                f"The {args.method!r} method needs {needed} reference(s), got {supplied}.",
                context={"method": args.method, "required": needed, "supplied": supplied},
            )
        )

    before = _feature_names(doc)
    try_com_member(doc, "ClearSelection2", True, default=None)
    for which in args.standard_planes:
        ctx.session.find_standard_plane(doc, which).Select2(True, 0)
    _select_refs(ctx, doc, args.refs)

    # InsertAxis2 answers with a bare bool and puts nothing in the tree when the
    # selection does not describe an axis, so the bool alone is not evidence.
    created = bool(try_com_member(doc, "InsertAxis2", args.auto_size, default=False))
    feature = _new_feature(doc, before)
    type_name = str(try_com_member(feature, "GetTypeName2", default="") or "") if feature else ""

    if not created or feature is None or type_name != "RefAxis":
        raise SwMcpError(
            make_error(
                "AXIS_CREATE_FAILED",
                "solidworks",
                f"SOLIDWORKS could not create a {args.method} axis from those references.",
                context={
                    "method": args.method,
                    "insert_axis_returned": created,
                    "created_type": type_name or None,
                },
                remediation=[
                    "Check the references suit the method: 'two_planes' needs two "
                    "non-parallel planes, 'cyl_face' one cylindrical or conical face.",
                    "Use sw_probe_faces to pick the face or edge precisely.",
                ],
            )
        )

    if args.name:
        feature.Name = args.name
    name = str(try_com_member(feature, "Name", default="") or "")
    after = _feature_names(doc)
    reference = capture(ctx.session, doc, feature)

    return DatumAxisCreateResult(
        axis_name=name,
        method=args.method,
        reference={
            **reference.model_dump(mode="json", exclude_none=True),
            "tool_args": reference.tool_args(),
        },
        verification=Verification(
            read_back=True,
            before={"feature_count": len(before)},
            after={"feature_count": len(after), "type_name": type_name},
            checks=_datum_checks(before, after, name, "axis"),
        ),
    )


@op(
    name="sw_datum_point_create",
    tier="core",
    domains=("datum",),
    tags=("datum", "point", "reference"),
    summary=(
        "Create reference points at a face centre, an edge centre, an intersection, a "
        "projected vertex, a sketch point, or spaced along a curve by distance, "
        "percentage, or even division."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("DAT-003",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def datum_point_create(ctx: OpContext, args: DatumPointCreateArgs) -> DatumPointCreateResult:
    doc = ctx.require_doc()
    before = _feature_names(doc)

    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = _select_refs(ctx, doc, args.refs)
    if selected != len(args.refs):
        raise SwMcpError(
            make_error(
                "REFERENCE_NOT_SELECTABLE",
                "reference",
                f"Only {selected} of {len(args.refs)} references could be selected.",
                remediation=["Re-capture the references; the model may have changed."],
            )
        )

    # Distance arrives in metres already; percentage passes straight through, and
    # 'evenly' ignores the value entirely and reads the count instead.
    if args.along_curve == "distance":
        placement = float(args.distance or 0.0)
    elif args.along_curve == "percentage":
        placement = float(args.percent or 0.0)
    else:
        placement = 0.0
    evenly = args.method == "along_curve" and args.along_curve == "evenly"
    count = args.count if evenly else 1

    raw = try_com_member(
        doc.FeatureManager,
        "InsertReferencePoint",
        swconst.value("swRefPointType_e", _REF_POINT_TYPES[args.method]),
        swconst.value("swRefPointAlongCurveType_e", _ALONG_CURVE_TYPES[args.along_curve]),
        placement,
        count,
        default=None,
    )
    # pywin32 hands this one back as a one-element tuple rather than the IFeature the
    # documentation describes. Treating the tuple as a feature makes every call look
    # successful until `.Name` raises, so it is unwrapped here, once.
    feature = next(iter(normalize_sequence(raw)), None)

    created = {name for name in _feature_names(doc) - before if name}
    if feature is None or not created:
        raise SwMcpError(
            make_error(
                "POINT_CREATE_FAILED",
                "solidworks",
                f"SOLIDWORKS could not create a {args.method} reference point.",
                context={"method": args.method, "along_curve": args.along_curve},
                remediation=[
                    "'arc_center' needs a circular edge; for the midpoint of a straight "
                    "edge use 'along_curve' with along_curve='percentage' and percent=50.",
                    "'face_center' needs a face, 'along_curve' needs an edge, and "
                    "'intersection' needs entities that actually cross.",
                ],
            )
        )

    names = sorted(created)
    if args.name and len(names) == 1:
        feature.Name = args.name
        names = [args.name]

    after = _feature_names(doc)
    references = []
    for name in names:
        found = find_feature(doc, name)
        if found is None:
            continue
        ref = capture(ctx.session, doc, found)
        references.append(
            {
                "name": name,
                **ref.model_dump(mode="json", exclude_none=True),
                "tool_args": ref.tool_args(),
            }
        )

    return DatumPointCreateResult(
        point_names=names,
        count=len(names),
        method=args.method,
        references=references,
        verification=Verification(
            read_back=True,
            before={"feature_count": len(before)},
            after={"feature_count": len(after), "points_created": len(names)},
            checks=[
                *_datum_checks(before, after, ", ".join(names), "point"),
                Check(
                    name="every_point_is_addressable",
                    passed=len(references) == len(names),
                    detail=f"{len(references)} of {len(names)} came back capture-ready",
                ),
            ],
        ),
        warnings=(
            [f"{args.name!r} was ignored: {len(names)} points were created, not one."]
            if args.name and len(names) != 1
            else []
        ),
    )


@op(
    name="sw_datum_csys_create",
    tier="core",
    domains=("datum",),
    tags=("datum", "coordinate-system", "transform", "reference"),
    summary=(
        "Create a coordinate system from an origin and axis references, and return the "
        "transform SOLIDWORKS actually built: rotation, origin position, and scale."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("DAT-004",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def datum_csys_create(ctx: OpContext, args: DatumCsysCreateArgs) -> DatumCsysCreateResult:
    doc = ctx.require_doc()
    before = _feature_names(doc)

    try_com_member(doc, "ClearSelection2", True, default=None)
    unresolved = []
    for field, mark in _CSYS_MARKS.items():
        ref = getattr(args, field)
        if ref is not None and not _select_marked(ctx, doc, ref, mark):
            unresolved.append(field)
    if unresolved:
        raise SwMcpError(
            make_error(
                "REFERENCE_NOT_SELECTABLE",
                "reference",
                f"These references could not be selected: {', '.join(unresolved)}.",
                context={"unresolved": unresolved},
                remediation=["Re-capture the references; the model may have changed."],
            )
        )

    feature = try_com_member(
        doc.FeatureManager,
        "InsertCoordinateSystem",
        args.flip_x,
        args.flip_y,
        args.flip_z,
        default=None,
    )
    created = _new_feature(doc, before)
    if feature is None or created is None:
        raise SwMcpError(
            make_error(
                "CSYS_CREATE_FAILED",
                "solidworks",
                "SOLIDWORKS could not create a coordinate system from those references.",
                remediation=[
                    "The origin must be a vertex, sketch point, or reference point, and "
                    "each axis an edge, reference axis, or sketch line.",
                ],
            )
        )

    if args.name:
        created.Name = args.name
    name = str(try_com_member(created, "Name", default="") or "")
    after = _feature_names(doc)
    transform = _read_csys_transform(doc, name)
    reference = capture(ctx.session, doc, created)

    return DatumCsysCreateResult(
        csys_name=name,
        transform=transform,
        reference={
            **reference.model_dump(mode="json", exclude_none=True),
            "tool_args": reference.tool_args(),
        },
        verification=Verification(
            read_back=True,
            before={"feature_count": len(before)},
            after={
                "feature_count": len(after),
                "translation_mm": transform.translation_mm if transform else None,
            },
            checks=[
                *_datum_checks(before, after, name, "coordinate_system"),
                Check(
                    name="transform_read_back",
                    passed=transform is not None,
                    detail=(
                        f"origin at {transform.translation_mm} mm"
                        if transform
                        else "SOLIDWORKS returned no transform for the new system"
                    ),
                ),
            ],
        ),
        warnings=(
            []
            if transform
            else ["The coordinate system was created but its transform could not be read."]
        ),
    )


def _read_csys_transform(doc: Any, name: str) -> DatumCsysTransform | None:
    """Decode ``IMathTransform.ArrayData`` for a named coordinate system.

    The array is sixteen doubles: nine row-major rotation terms, three translation
    terms in metres, a uniform scale, and three unused. Anything shorter means
    SOLIDWORKS did not hand back a transform, and reporting a partly-filled one as
    fact would be worse than reporting none.
    """
    if not name:
        return None
    math_transform = try_com_member(
        doc.Extension, "GetCoordinateSystemTransformByName", name, default=None
    )
    data = normalize_sequence(try_com_member(math_transform, "ArrayData", default=None))
    if len(data) < 13:
        return None
    values = [float(item) for item in data]
    return DatumCsysTransform(
        rotation=[values[0:3], values[3:6], values[6:9]],
        translation_mm=[round(from_meters(value), 9) for value in values[9:12]],
        scale=values[12],
    )


# --- extrudes -----------------------------------------------------------------


_END_CONDITION = {
    "blind": "swEndCondBlind",
    "through_all": "swEndCondThroughAll",
    "up_to_next": "swEndCondUpToNext",
    "up_to_vertex": "swEndCondUpToVertex",
    "up_to_surface": "swEndCondUpToSurface",
    "offset_from_surface": "swEndCondOffsetFromSurface",
    "mid_plane": "swEndCondMidPlane",
    "up_to_body": "swEndCondUpToBody",
}


def _extrude(ctx: OpContext, args: ExtrudeArgs, *, cut: bool) -> ExtrudeResult:
    doc = ctx.require_doc()
    sketch = _select_sketch(doc, args.sketch_name)
    before = model_snapshot(doc)

    end = swconst.value("swEndConditions_e", _END_CONDITION[args.end_condition])
    second_end = (
        swconst.value("swEndConditions_e", "swEndCondBlind") if args.second_direction else 0
    )
    manager = doc.FeatureManager

    # FeatureExtrusion3 always adds material; the parameter that looks like a cut flag
    # is "single-ended". Removing material is a different call altogether.
    if cut:
        feature = manager.FeatureCut4(
            not args.second_direction,  # Sd: single-ended
            False,                      # Flip
            args.reverse,               # Dir
            end, second_end,            # T1, T2
            args.depth, args.second_depth,
            args.draft > 0, args.second_direction and args.draft > 0,
            args.draft_outward, args.draft_outward,
            args.draft, args.draft,
            False, False,               # offset reverse
            False, False,               # translate surface
            False,                      # NormalCut
            True, True,                 # UseFeatScope, UseAutoSelect
            True, True, False,          # assembly scope, auto-select, propagate
            0, 0.0, False,              # start condition
            False,                      # OptimizeGeometry
        )
    else:
        feature = manager.FeatureExtrusion3(
            not args.second_direction,
            False,
            args.reverse,
            end, second_end,
            args.depth, args.second_depth,
            args.draft > 0, args.second_direction and args.draft > 0,
            args.draft_outward, args.draft_outward,
            args.draft, args.draft,
            False, False,
            False, False,
            args.merge_result,
            True, True,
            0, 0.0,
            False,
        )

    if feature is None:
        raise SwMcpError(
            make_error(
                "EXTRUDE_FAILED",
                "solidworks",
                f"SOLIDWORKS could not create the extrude from {sketch!r}.",
                context={"sketch": sketch, "end_condition": args.end_condition},
                remediation=(
                    [
                        "A through-all cut that points away from the material creates "
                        "nothing and fails. Try reverse=true.",
                        "The profile may be open, self-intersecting, or already consumed.",
                    ]
                    if cut
                    else [
                        "The profile may be open, self-intersecting, or already consumed.",
                        "Check the sketch is closed and fully contained.",
                    ]
                ),
            )
        )

    if args.name:
        feature.Name = args.name

    after = model_snapshot(doc)
    name = str(try_com_member(feature, "Name", default="") or "")

    return ExtrudeResult(
        feature_name=name,
        feature_type=str(try_com_member(feature, "GetTypeName2", default="") or ""),
        body_count_before=before["body_count"],
        body_count_after=after["body_count"],
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=[
                Check(name="feature_created", passed=bool(name), detail=name),
                *_geometry_checks(before, after, expect="less" if cut else "more"),
                Check(
                    name="feature_has_no_error",
                    passed=not try_com_member(feature, "GetErrorCode2", default=0),
                    detail=str(try_com_member(feature, "GetErrorCode2", default=0)),
                ),
            ],
        ),

    )


@op(
    name="sw_feature_extrude_boss",
    tier="core",
    domains=("feature",),
    tags=("extrude", "boss", "pad", "solid"),
    summary=(
        "Create a boss or base extrude from a sketch profile, with blind, through-all, "
        "up-to, or mid-plane end conditions, draft, and merge control. Verifies the "
        "body count and volume actually changed."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-001",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_extrude_boss(ctx: OpContext, args: ExtrudeArgs) -> ExtrudeResult:
    return _extrude(ctx, args, cut=False)


@op(
    name="sw_feature_extrude_cut",
    tier="core",
    domains=("feature",),
    tags=("extrude", "cut", "pocket"),
    summary=(
        "Cut material with an extruded sketch profile, with the same end conditions as "
        "a boss extrude. Verifies that volume actually decreased."
    ),
    # Removing material is not destructive in the safety sense: the cut is a feature in
    # the tree, undone by deleting it or restoring the automatic checkpoint. Demanding
    # confirmation for every pocket would put friction where there is no real risk.
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-002",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_extrude_cut(ctx: OpContext, args: ExtrudeArgs) -> ExtrudeResult:
    return _extrude(ctx, args, cut=True)


@op(
    name="sw_feature_revolve",
    tier="core",
    domains=("feature",),
    tags=("revolve", "boss", "cut", "axis"),
    summary=(
        "Revolve a sketch profile about an axis to add or remove material. Boss and cut "
        "share one tool because their option sets are identical."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-003",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_revolve(ctx: OpContext, args: RevolveArgs) -> RevolveResult:
    doc = ctx.require_doc()
    sketch = _select_sketch(doc, args.sketch_name)
    before = model_snapshot(doc)

    if args.axis_ref is not None:
        _select_refs(ctx, doc, [args.axis_ref], mark=4)

    feature = doc.FeatureManager.FeatureRevolve2(
        True,
        True,
        False,
        args.mode == "cut",
        False,
        False,
        swconst.value("swEndConditions_e", "swEndCondBlind"),
        0,
        args.angle,
        0.0,
        False, False,
        0.0, 0.0,
        args.thin_thickness or 0.0,
        0.0, 0.0,
        True,
        True,
        args.merge_result,
    )
    if feature is None:
        raise SwMcpError(
            make_error(
                "REVOLVE_FAILED",
                "solidworks",
                f"SOLIDWORKS could not revolve {sketch!r}.",
                remediation=[
                    "A revolve needs an axis: add a centerline to the sketch, "
                    "or pass axis_ref.",
                    "The profile must not cross the axis.",
                ],
            )
        )

    if args.name:
        feature.Name = args.name
    after = model_snapshot(doc)

    return RevolveResult(
        feature_name=str(try_com_member(feature, "Name", default="") or ""),
        mode=args.mode,
        body_count_before=before["body_count"],
        body_count_after=after["body_count"],
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=_geometry_checks(
                before, after, expect="less" if args.mode == "cut" else "more"
            ),
        ),
    )


# --- draft --------------------------------------------------------------------

#: ``InsertMultiFaceDraft`` reads its three roles from selection marks, like sweep and
#: the coordinate system: 1 the neutral plane or pull direction, 2 the faces to draft,
#: 4 the parting-line edges.
_DRAFT_MARK_NEUTRAL = 1
_DRAFT_MARK_FACE = 2
_DRAFT_MARK_EDGE = 4

_DRAFT_PROPAGATION = {
    "none": "swFacePropNone",
    "tangent": "swFacePropTangent",
    "all_loops": "swFacePropAllLoops",
    "inner_loops": "swFacePropInnerLoops",
    "outer_loops": "swFacePropOuterLoops",
}


@op(
    name="sw_feature_draft",
    tier="core",
    domains=("feature",),
    tags=("draft", "taper", "mold", "parting-line"),
    summary=(
        "Taper faces by a draft angle from a neutral plane, a parting line, or as a step "
        "draft, verified by measuring the material the taper added or removed."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-010",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_draft(ctx: OpContext, args: DraftArgs) -> DraftResult:
    """FEAT-010.

    The draft direction is worth stating because it is the opposite of what most people
    expect: with ``flip`` false SOLIDWORKS tapers *outward*, so a box drafted on all four
    sides gains material. Measured against the closed form for a drafted prism,
    ``W*D*h + tan(a)*(W+D)*h^2 + (4/3)*tan(a)^2*h^3``, it agreed to twelve significant
    figures — so this is the documented behaviour rather than a quirk of one model.
    """
    doc = ctx.require_doc()
    before = model_snapshot(doc)

    try_com_member(doc, "ClearSelection2", True, default=None)
    if args.neutral_standard_plane:
        plane = ctx.session.find_standard_plane(doc, args.neutral_standard_plane)
        plane.Select2(True, _DRAFT_MARK_NEUTRAL)
    elif _select_refs(ctx, doc, [args.neutral_ref], mark=_DRAFT_MARK_NEUTRAL) != 1:
        raise SwMcpError(
            make_error(
                "REFERENCE_NOT_SELECTABLE",
                "reference",
                "The neutral reference could not be selected.",
                remediation=["Re-capture the face or plane; the model may have changed."],
            )
        )

    faces = _select_refs(ctx, doc, args.face_refs, mark=_DRAFT_MARK_FACE)
    edges = _select_refs(ctx, doc, args.edge_refs, mark=_DRAFT_MARK_EDGE)
    if faces != len(args.face_refs) or edges != len(args.edge_refs):
        raise SwMcpError(
            make_error(
                "REFERENCE_NOT_SELECTABLE",
                "reference",
                f"Selected {faces} of {len(args.face_refs)} faces and {edges} of "
                f"{len(args.edge_refs)} edges.",
                remediation=["Re-capture the references with sw_probe_faces."],
            )
        )

    feature = try_com_member(
        doc.FeatureManager,
        "InsertMultiFaceDraft",
        float(args.angle),
        args.flip,
        args.method == "parting_line",
        swconst.value("swDraftFacePropagationType_e", _DRAFT_PROPAGATION[args.propagation]),
        args.method == "step",
        args.body_draft,
        default=None,
    )
    if feature is None:
        try_com_member(doc, "ClearSelection2", True, default=None)
        raise SwMcpError(
            make_error(
                "DRAFT_FAILED",
                "solidworks",
                f"SOLIDWORKS could not apply a {args.method} draft.",
                context={
                    "method": args.method,
                    "faces": faces,
                    "edges": edges,
                    "propagation": args.propagation,
                },
                remediation=[
                    "The neutral reference must be planar, and the drafted faces must "
                    "meet it rather than lie parallel to it.",
                    "An angle steep enough to collapse a face will refuse to build; try "
                    "a smaller one.",
                ],
            )
        )

    if args.name:
        feature.Name = args.name
    after = model_snapshot(doc)
    reference = capture(ctx.session, doc, feature)

    return DraftResult(
        feature_name=str(try_com_member(feature, "Name", default="") or ""),
        method=args.method,
        faces_drafted=faces,
        edges_used=edges,
        body_count_before=before["body_count"],
        body_count_after=after["body_count"],
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        reference={
            **reference.model_dump(mode="json", exclude_none=True),
            "tool_args": reference.tool_args(),
        },
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            # A draft adds material one way and removes it the other, so "changed" is
            # the honest invariant; the caller sees which way from the volumes.
            checks=_geometry_checks(before, after, expect="any"),
        ),
    )


# --- sweep and loft -----------------------------------------------------------

#: Selection marks are the entire contract for both features: SOLIDWORKS reads the
#: role of each selection from its mark, not from argument order. Getting one wrong
#: does not raise - it builds the wrong shape, or silently builds nothing.
_SWEEP_MARK_PROFILE = 1
_SWEEP_MARK_GUIDE = 2
_SWEEP_MARK_PATH = 4

_LOFT_MARK_PROFILE = 1
_LOFT_MARK_GUIDE = 2
_LOFT_MARK_CENTERLINE = 4

_SWEEP_ORIENTATION = {
    "follow_path": "swTwistControlFollowPath",
    "keep_normal_constant": "swTwistControlKeepNormalConstant",
    "follow_path_and_first_guide": "swTwistControlFollowPathFirstGuideCurve",
    "follow_first_and_second_guide": "swTwistControlFollowFirstSecondGuideCurves",
    "constant_twist_along_path": "swTwistControlConstantTwistAlongPath",
}

#: Which side of the profile a thin wall is added to. swThinWallOneDirection grows the
#: wall *outward*: a 1 mm wall on a circle of r=5 measured as the annulus between r=5
#: and r=6, not r=4 and r=5. That was found by measuring, not by reading.
_THIN_WALL_TYPES = {
    "outward": "swThinWallOneDirection",
    "inward": "swThinWallOppDirection",
    "mid_plane": "swThinWallMidPlane",
    "both": "swThinWallTwoDirection",
}

_SWEEP_DIRECTION = {
    "forward": "swSweepDirection1",
    "reverse": "swSweepDirection2",
    "bidirectional": "swSweepBidirectional",
}

#: Loft's StartMatchingType/EndMatchingType are documented as a plain 0-4 scale rather
#: than as swTangencyType_e, and the two do not agree beyond 0. They are spelled out
#: here so the mismatch is recorded rather than rediscovered.
_LOFT_TANGENCY = {
    "none": 0,
    "normal_to_profile": 1,
    "direction_vector": 2,
    "all_faces": 3,
}


def _select_sketch_marked(doc: Any, name: str, mark: int, *, append: bool) -> bool:
    return bool(
        doc.Extension.SelectByID2(name, "SKETCH", 0, 0, 0, append, mark, null_dispatch(), 0)
    )


def _select_named_sketches(
    doc: Any, names: list[str], mark: int, *, append: bool, role: str
) -> list[str]:
    """Select each sketch under one mark, returning the names that would not select."""
    missing = []
    for name in names:
        if not _select_sketch_marked(doc, name, mark, append=append):
            missing.append(name)
        append = True
    if missing:
        raise SwMcpError(
            make_error(
                "SKETCH_NOT_SELECTABLE",
                "reference",
                f"These {role} sketches could not be selected: {', '.join(missing)}.",
                context={"role": role, "missing": missing},
                remediation=[
                    "List the document's sketches to check the exact names.",
                    "A sketch already consumed by another feature cannot be reused.",
                ],
            )
        )
    return names


@op(
    name="sw_feature_sweep",
    tier="core",
    domains=("feature",),
    tags=("sweep", "boss", "cut", "path", "guide"),
    summary=(
        "Sweep a closed profile along a path, with optional guide curves, profile "
        "orientation, twist, and thin-wall options, verified by measuring the result."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-004",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_sweep(ctx: OpContext, args: SweepArgs) -> SweepResult:
    """FEAT-004, built on the post-2018 sweep architecture.

    ``IFeatureManager::InsertProtrusionSwept4`` still works on this build and was
    measured exact, but the API help marks it obsolete from 2018 in favour of
    ``CreateDefinition(swFmSweep)`` -> ``ISweepFeatureData`` -> ``CreateFeature``. The
    supported route is also the faster one here - 12.9s against 23.2s for the same
    solid - so it is the one used, and ``ISweepFeatureData`` was added to the curated
    interface list so its properties are arity-checked like everything else.
    """
    doc = ctx.require_doc()
    before = model_snapshot(doc)

    try_com_member(doc, "ClearSelection2", True, default=None)
    _select_named_sketches(
        doc, [args.profile_sketch], _SWEEP_MARK_PROFILE, append=False, role="profile"
    )
    if args.path_sketch is not None:
        _select_named_sketches(doc, [args.path_sketch], _SWEEP_MARK_PATH, append=True, role="path")
        path_label = args.path_sketch
    else:
        if _select_refs(ctx, doc, [args.path_ref], mark=_SWEEP_MARK_PATH) != 1:
            raise SwMcpError(
                make_error(
                    "REFERENCE_NOT_SELECTABLE",
                    "reference",
                    "The sweep path reference could not be selected.",
                    remediation=["Re-capture the edge; the model may have changed."],
                )
            )
        path_label = "path_ref"

    _select_named_sketches(doc, args.guide_sketches, _SWEEP_MARK_GUIDE, append=True, role="guide")
    guides = len(args.guide_sketches)
    if args.guide_refs:
        guides += _select_refs(ctx, doc, args.guide_refs, mark=_SWEEP_MARK_GUIDE)

    manager = doc.FeatureManager
    kind = "swFmSweepCut" if args.mode == "cut" else "swFmSweep"
    definition = try_com_member(
        manager, "CreateDefinition", swconst.value("swFeatureNameID_e", kind), default=None
    )
    if definition is None:
        raise SwMcpError(
            make_error(
                "SWEEP_DEFINITION_FAILED",
                "solidworks",
                f"SOLIDWORKS would not create a {args.mode} sweep definition.",
                context={"feature_type": kind},
            )
        )

    definition.TwistControlType = swconst.value(
        "swTwistControlType_e", _SWEEP_ORIENTATION[args.orientation]
    )
    definition.PathAlignmentType = swconst.value("swTangencyType_e", "swTangencyNone")
    if args.twist_angle is not None:
        # Angles reach handlers already in radians, which is what SOLIDWORKS wants.
        try_com_member(definition, "SetTwistAngle", float(args.twist_angle), default=None)
    definition.Direction = swconst.value("swSweepDirection_e", _SWEEP_DIRECTION[args.direction])
    definition.Merge = args.merge_result
    definition.MergeSmoothFaces = args.merge_smooth_faces
    definition.AlignWithEndFaces = args.align_with_end_faces
    definition.TangentPropagation = args.tangent_propagation
    if args.thin_thickness is not None:
        definition.ThinFeature = True
        definition.ThinWallType = swconst.value(
            "swThinWallType_e", _THIN_WALL_TYPES[args.thin_direction]
        )
        try_com_member(
            definition, "SetWallThickness", True, float(args.thin_thickness), default=None
        )

    feature = try_com_member(manager, "CreateFeature", definition, default=None)
    if feature is None:
        try_com_member(doc, "ClearSelection2", True, default=None)
        raise SwMcpError(
            make_error(
                "SWEEP_FAILED",
                "solidworks",
                f"SOLIDWORKS could not sweep {args.profile_sketch!r} along {path_label!r}.",
                context={"mode": args.mode, "guide_curves": guides},
                remediation=[
                    "The path must start on the plane of the profile for a one-directional "
                    "sweep.",
                    "A boss sweep needs a closed profile, and each guide curve must touch "
                    "the profile or a point on it.",
                    "A cut sweep needs existing material along the path to remove.",
                ],
            )
        )

    if args.name:
        feature.Name = args.name
    after = model_snapshot(doc)
    reference = capture(ctx.session, doc, feature)

    return SweepResult(
        feature_name=str(try_com_member(feature, "Name", default="") or ""),
        mode=args.mode,
        profile_sketch=args.profile_sketch,
        path=path_label,
        guide_curve_count=guides,
        body_count_before=before["body_count"],
        body_count_after=after["body_count"],
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        reference={
            **reference.model_dump(mode="json", exclude_none=True),
            "tool_args": reference.tool_args(),
        },
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=_geometry_checks(
                before, after, expect="less" if args.mode == "cut" else "more"
            ),
        ),
    )


@op(
    name="sw_feature_loft",
    tier="core",
    domains=("feature",),
    tags=("loft", "boss", "cut", "profile", "guide"),
    summary=(
        "Loft between two or more closed profiles in the order given, with optional "
        "guide curves, a centerline, a closed loop, and start/end tangency."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("FEAT-005",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_loft(ctx: OpContext, args: LoftArgs) -> LoftResult:
    """FEAT-005 for loft. The boundary feature is a different API and is not built here.

    Note for anyone writing a test against this: a loft between two circles is *not*
    an exact frustum. SOLIDWORKS builds a B-spline surface through the sections, and
    the measured volume came out 0.0036% under the closed-form figure. Compare with a
    relative tolerance; asserting exact equality here would be asserting something that
    is not true.
    """
    doc = ctx.require_doc()
    before = model_snapshot(doc)

    try_com_member(doc, "ClearSelection2", True, default=None)
    # Order is the shape: SOLIDWORKS lofts through the profiles in selection order.
    _select_named_sketches(
        doc, args.profile_sketches, _LOFT_MARK_PROFILE, append=False, role="profile"
    )
    _select_named_sketches(doc, args.guide_sketches, _LOFT_MARK_GUIDE, append=True, role="guide")
    if args.centerline_sketch is not None:
        _select_named_sketches(
            doc, [args.centerline_sketch], _LOFT_MARK_CENTERLINE, append=True, role="centerline"
        )

    thin = args.thin_thickness is not None
    thickness = float(args.thin_thickness or 0.0)
    thin_type = swconst.value("swThinWallType_e", "swThinWallOneDirection")
    start_tangency = _LOFT_TANGENCY[args.start_tangency]
    end_tangency = _LOFT_TANGENCY[args.end_tangency]
    manager = doc.FeatureManager

    if args.mode == "cut":
        feature = try_com_member(
            manager, "InsertCutBlend",
            args.closed, args.keep_tangency, False, 1.0,
            start_tangency, end_tangency,
            thin, thickness, 0.0, thin_type,
            True, True,
            default=None,
        )
    else:
        feature = try_com_member(
            manager, "InsertProtrusionBlend2",
            args.closed, args.keep_tangency, False, 1.0,
            start_tangency, end_tangency,
            0.0, 0.0, True, True,
            thin, thickness, 0.0, thin_type,
            args.merge_result, True, True,
            swconst.value("swGuideCurveInfluence_e", "swGuideCurveInfluenceNextGuide"),
            default=None,
        )

    if feature is None:
        try_com_member(doc, "ClearSelection2", True, default=None)
        raise SwMcpError(
            make_error(
                "LOFT_FAILED",
                "solidworks",
                f"SOLIDWORKS could not loft through {len(args.profile_sketches)} profiles.",
                context={"mode": args.mode, "profiles": args.profile_sketches},
                remediation=[
                    "A solid loft needs closed profiles, listed in the order the loft "
                    "should run through them.",
                    "Profiles that cross each other, or a guide curve that misses a "
                    "profile, will refuse to build.",
                    "A cut loft needs existing material between the profiles to remove.",
                ],
            )
        )

    if args.name:
        feature.Name = args.name
    after = model_snapshot(doc)
    reference = capture(ctx.session, doc, feature)

    return LoftResult(
        feature_name=str(try_com_member(feature, "Name", default="") or ""),
        mode=args.mode,
        profile_sketches=list(args.profile_sketches),
        guide_curve_count=len(args.guide_sketches),
        centerline=args.centerline_sketch,
        body_count_before=before["body_count"],
        body_count_after=after["body_count"],
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        reference={
            **reference.model_dump(mode="json", exclude_none=True),
            "tool_args": reference.tool_args(),
        },
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=_geometry_checks(
                before, after, expect="less" if args.mode == "cut" else "more"
            ),
        ),
    )


# --- edge features ------------------------------------------------------------


@op(
    name="sw_feature_fillet",
    tier="core",
    domains=("feature",),
    tags=("fillet", "round", "edge"),
    summary=(
        "Round edges or faces with a constant-radius fillet, addressing them through "
        "stable entity references rather than whatever happens to be selected."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-006",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_fillet(ctx: OpContext, args: FilletArgs) -> EdgeFeatureResult:
    doc = ctx.require_doc()
    before = model_snapshot(doc)

    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = _select_refs(ctx, doc, args.refs)
    if not selected:
        raise SwMcpError(
            make_error(
                "NO_EDGES_SELECTED",
                "reference",
                "None of the supplied references could be selected for a fillet.",
                remediation=["Probe for the edges first and pass their tool_args."],
            )
        )

    feature = doc.FeatureManager.FeatureFillet3(
        195 if args.propagate else 194,
        args.radius,
        0, 0, 0, 0, 0,
        None, None, None, None, None, None, None,
    )
    return _edge_feature_result(
        ctx, doc, feature, before, selected=selected, kind="fillet", name=args.name
    )


@op(
    name="sw_feature_chamfer",
    tier="core",
    domains=("feature",),
    tags=("chamfer", "bevel", "edge"),
    summary=(
        "Bevel edges or faces with an equal-distance or angle-distance chamfer, using "
        "stable entity references."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-006",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_chamfer(ctx: OpContext, args: ChamferArgs) -> EdgeFeatureResult:
    doc = ctx.require_doc()
    before = model_snapshot(doc)

    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = _select_refs(ctx, doc, args.refs)
    if not selected:
        raise SwMcpError(
            make_error(
                "NO_EDGES_SELECTED",
                "reference",
                "None of the supplied references could be selected for a chamfer.",
                remediation=["Probe for the edges first and pass their tool_args."],
            )
        )

    # swChamferEqualDistance belongs to the chamfer *feature data* interface, not to
    # InsertFeatureChamfer: passing it creates a Chamfer feature that removes nothing
    # and reports no error. An equal-distance chamfer is distance-distance with the
    # same distance twice.
    if args.kind == "equal_distance":
        chamfer_type = swconst.value("swChamferType_e", "swChamferDistanceDistance")
        other_distance = args.distance
    else:
        chamfer_type = swconst.value("swChamferType_e", "swChamferAngleDistance")
        other_distance = 0.0

    feature = doc.FeatureManager.InsertFeatureChamfer(
        4 if args.propagate else 0,
        chamfer_type,
        args.distance,
        args.angle,
        other_distance,
        0, 0, 0,
    )
    return _edge_feature_result(
        ctx, doc, feature, before, selected=selected, kind="chamfer", name=args.name
    )


def _edge_feature_result(
    ctx: OpContext,
    doc: Any,
    feature: Any,
    before: dict[str, Any],
    *,
    selected: int,
    kind: str,
    name: str | None,
) -> EdgeFeatureResult:
    if feature is None:
        raise SwMcpError(
            make_error(
                f"{kind.upper()}_FAILED",
                "solidworks",
                f"SOLIDWORKS could not create the {kind}.",
                remediation=[
                    f"The {kind} may be too large for the geometry, or the edges may not "
                    "form a valid chain.",
                    "Try a smaller value, or fewer edges.",
                ],
            )
        )
    if name:
        feature.Name = name

    after = model_snapshot(doc)
    _ = ctx
    return EdgeFeatureResult(
        feature_name=str(try_com_member(feature, "Name", default="") or ""),
        feature_type=str(try_com_member(feature, "GetTypeName2", default="") or ""),
        edges_selected=selected,
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=[
                Check(
                    name="feature_created",
                    passed=True,
                    detail=str(try_com_member(feature, "Name", default="")),
                ),
                Check(
                    name="geometry_changed",
                    passed=after["volume_m3"] != before["volume_m3"]
                    or after["face_count"] != before["face_count"],
                    detail=(
                        f"faces {before['face_count']} -> {after['face_count']}, "
                        f"volume {before['volume_mm3']:.3f} -> {after['volume_mm3']:.3f} mm³"
                    ),
                ),
                Check(
                    name="feature_has_no_error",
                    passed=not try_com_member(feature, "GetErrorCode2", default=0),
                    detail=str(try_com_member(feature, "GetErrorCode2", default=0)),
                ),
            ],
        ),
    )


# --- patterns -----------------------------------------------------------------


@op(
    name="sw_feature_pattern",
    tier="core",
    domains=("feature",),
    tags=("pattern", "linear", "circular", "array"),
    summary=(
        "Repeat features in a linear or circular pattern. Other pattern families are "
        "rejected by the schema rather than failing at runtime, so the tool never "
        "advertises coverage it does not have."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("FEAT-007",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_pattern(ctx: OpContext, args: PatternArgs) -> PatternResult:
    doc = ctx.require_doc()
    before = model_snapshot(doc)

    if args.direction_ref is None:
        raise SwMcpError(
            validation_error(
                "MISSING_ARGUMENT",
                "A pattern needs direction_ref: an edge, axis, or planar face.",
                remediation=["Probe for a straight edge or an axis and pass its tool_args."],
            )
        )

    if args.second_count > 1 and args.second_direction_ref is None:
        raise SwMcpError(
            validation_error(
                "MISSING_ARGUMENT",
                "second_count is greater than 1, so second_direction_ref is required.",
                context={"second_count": args.second_count},
                remediation=["Probe for an edge perpendicular to the first direction."],
            )
        )

    try_com_member(doc, "ClearSelection2", True, default=None)
    _select_refs(ctx, doc, [args.direction_ref], mark=1)
    if args.second_direction_ref is not None:
        _select_refs(ctx, doc, [args.second_direction_ref], mark=2)

    for feature_name in args.feature_names:
        if not doc.Extension.SelectByID2(
            feature_name, "BODYFEATURE", 0, 0, 0, True, 4, null_dispatch(), 0
        ):
            raise SwMcpError(
                make_error(
                    "FEATURE_NOT_FOUND",
                    "reference",
                    f"Could not select the feature {feature_name!r} to pattern.",
                    remediation=["List the document's features to check the name."],
                )
            )

    manager = doc.FeatureManager
    if args.type == "linear":
        # FeatureLinearPattern4(Num1, Spacing1, Num2, Spacing2, FlipDir1, FlipDir2,
        # DName1, DName2, GeometryPattern, VaryInstance, HasOffset1, HasOffset2,
        # CtrlByNum1, CtrlByNum2, FromCentroid1, FromCentroid2, RevOffset1, RevOffset2,
        # Offset1, Offset2). The two offsets are distances, so they must be doubles.
        feature = manager.FeatureLinearPattern4(
            args.count, args.spacing,
            args.second_count, args.second_spacing,
            args.reverse, False,
            "NULL", "NULL",
            False, False, False, False, False, False,
            False, False, False, False, 0.0, 0.0,
        )
    else:
        # FeatureCircularPattern5(Number, Spacing, FlipDirection, DName, GeometryPattern,
        # EqualSpacing, VaryInstance, SyncSubAssemblies, BDir2, BSymmetric, Number2,
        # Spacing2, DName2, EqualSpacing2) — 14 arguments. Passing 13 raises
        # "Parameter not optional" rather than anything that names the real problem.
        feature = manager.FeatureCircularPattern5(
            args.count, args.angle, args.reverse, "NULL",
            False, args.equal_spacing, False, False,
            False, False, 1, 0.0, "NULL", False,
        )

    if feature is None:
        raise SwMcpError(
            make_error(
                "PATTERN_FAILED",
                "solidworks",
                f"SOLIDWORKS could not create the {args.type} pattern.",
                context={"features": args.feature_names, "count": args.count},
                remediation=[
                    "Check that direction_ref is a straight edge or axis.",
                    "Instances that fall off the body cause the pattern to fail; "
                    "reduce the count or spacing.",
                ],
            )
        )
    if args.name:
        feature.Name = args.name

    after = model_snapshot(doc)
    return PatternResult(
        feature_name=str(try_com_member(feature, "Name", default="") or ""),
        pattern_type=args.type,
        # A two-direction pattern makes count x second_count instances, so reporting
        # only count would understate what was asked for.
        instances_requested=args.count * args.second_count,
        body_count_before=before["body_count"],
        body_count_after=after["body_count"],
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=[
                Check(
                    name="pattern_created",
                    passed=True,
                    detail=str(try_com_member(feature, "Name", default="")),
                ),
                Check(
                    name="model_changed",
                    passed=after["face_count"] != before["face_count"]
                    or after["volume_m3"] != before["volume_m3"],
                    detail=f"faces {before['face_count']} -> {after['face_count']}",
                ),
                Check(
                    name="feature_has_no_error",
                    passed=not try_com_member(feature, "GetErrorCode2", default=0),
                    detail=str(try_com_member(feature, "GetErrorCode2", default=0)),
                ),
            ],
        ),
    )


# --- holes --------------------------------------------------------------------


@op(
    name="sw_feature_hole",
    tier="core",
    domains=("feature",),
    tags=("hole", "drill", "counterbore", "countersink", "tapped"),
    summary=(
        "Place a hole on a face. Reports which strategy was actually used, and never "
        "silently downgrades a tapped or counterbored hole to a plain cut when Hole "
        "Wizard is unavailable. Counts the resulting cylindrical faces as evidence."
    ),
    # Like a cut extrude, a hole is a reversible tree feature rather than lost work.
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-012",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_hole(ctx: OpContext, args: HoleArgs) -> HoleResult:
    doc = ctx.require_doc()
    before = model_snapshot(doc)

    resolution = resolve(ctx.session, doc, args.face_ref, max_candidates=ctx.config.max_candidates)
    try_com_member(doc, "ClearSelection2", True, default=None)
    try_com_member(resolution.entity, "Select4", True, null_dispatch(), default=False)

    strategy, feature, warnings = _place_hole(ctx, doc, args)
    if feature is None:
        raise SwMcpError(
            make_error(
                "HOLE_FAILED",
                "solidworks",
                f"SOLIDWORKS could not create the {args.kind} hole.",
                context={"strategy": strategy, "kind": args.kind},
                remediation=[
                    "Check that the point lies on the selected face.",
                    "A through hole needs material below the face.",
                ],
            )
        )
    if args.name:
        feature.Name = args.name

    after = model_snapshot(doc)
    radius_m = args.diameter / 2.0
    matching = _count_cylindrical_faces(ctx, doc, radius_m)

    return HoleResult(
        feature_name=str(try_com_member(feature, "Name", default="") or ""),
        strategy_used=strategy,
        kind=args.kind,
        holes_found=matching,
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=[
                Check(
                    name="material_removed",
                    passed=(after["volume_m3"] or 0) < (before["volume_m3"] or 0),
                    detail=(
                        f"volume {before['volume_mm3']:.3f} -> {after['volume_mm3']:.3f} mm³"
                    ),
                ),
                Check(
                    name="hole_is_present_in_geometry",
                    passed=matching > 0,
                    detail=(
                        f"{matching} cylindrical face(s) at radius "
                        f"{from_meters(radius_m, 'mm'):.3f} mm"
                    ),
                ),
                Check(
                    name="feature_has_no_error",
                    passed=not try_com_member(feature, "GetErrorCode2", default=0),
                    detail=str(try_com_member(feature, "GetErrorCode2", default=0)),
                ),
            ],
        ),
        warnings=warnings,
    )


def _place_hole(ctx: OpContext, doc: Any, args: HoleArgs) -> tuple[str, Any, list[str]]:
    """Try the requested strategy, falling back only where the result is equivalent."""
    warnings: list[str] = []
    manager = doc.FeatureManager
    depth = args.depth if args.depth is not None else 0.0
    through = args.through_all or args.depth is None

    wants_wizard = args.kind in {"counterbore", "countersink", "tapped"}
    if args.strategy in {"auto", "hole_wizard"} and wants_wizard:
        feature = _try_hole_wizard(manager, args, through, depth)
        if feature is not None:
            return "hole_wizard", feature, warnings
        if args.strategy == "hole_wizard":
            return "hole_wizard", None, warnings
        raise SwMcpError(
            make_error(
                "HOLE_WIZARD_UNAVAILABLE",
                "solidworks",
                f"A {args.kind} hole needs Hole Wizard, which is not available here.",
                context={"kind": args.kind},
                remediation=[
                    "Confirm SOLIDWORKS Toolbox is installed and its hole database is set.",
                    "Or model the feature explicitly with strategy='cut_extrude' — "
                    "note that this produces a plain hole, not a "
                    f"{args.kind} one.",
                ],
            )
        )

    # SimpleHole2 takes no coordinates — it places the hole from the selection, so it
    # cannot honour the `at` position this tool promises. A sketched circle cut through
    # the face is the only strategy that puts the hole where the caller asked for it.
    if args.strategy == "simple_hole":
        feature = try_com_member(
            manager,
            "SimpleHole2",
            args.diameter,
            True, False, False,
            swconst.value(
                "swEndConditions_e", "swEndCondThroughAll" if through else "swEndCondBlind"
            ),
            0, depth, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False,
            True, True, True, True, False,
            default=None,
        )
        if feature is not None:
            warnings.append(
                "SimpleHole2 positions the hole from the selection, not from `at`; "
                "check where it landed."
            )
            return "simple_hole", feature, warnings

    return "cut_extrude", _hole_by_cut(ctx, doc, args, through, depth), warnings


def _try_hole_wizard(manager: Any, args: HoleArgs, through: bool, depth: float) -> Any | None:
    if args.kind != "counterbore":
        return None
    standard = swconst.value("swWzdGeneralHoleTypes_e", "swWzdCounterBore")
    return try_com_member(
        manager,
        "HoleWizard5",
        standard, 0, 0, "", 0,
        args.diameter,
        0.0 if through else depth,
        args.counterbore_diameter or args.diameter * 1.6,
        args.counterbore_depth or args.diameter * 0.6,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        False, False, False, False, False, False,
        default=None,
    )


def _hole_by_cut(ctx: OpContext, doc: Any, args: HoleArgs, through: bool, depth: float) -> Any:
    """Sketch a circle at the requested point on the selected face, and cut through it."""
    from swmcp.sketching import active_sketch

    doc.SketchManager.InsertSketch(True)
    sketch = active_sketch(doc)
    if sketch is None:
        return None
    sketch_name = str(try_com_member(sketch, "Name", default="") or "")
    doc.SketchManager.CreateCircleByRadius(args.at[0], args.at[1], args.at[2], args.diameter / 2.0)
    doc.SketchManager.InsertSketch(True)

    try_com_member(doc, "ClearSelection2", True, default=None)
    doc.Extension.SelectByID2(sketch_name, "SKETCH", 0, 0, 0, False, 0, null_dispatch(), 0)

    end = swconst.value(
        "swEndConditions_e", "swEndCondThroughAll" if through else "swEndCondBlind"
    )
    _ = ctx
    return doc.FeatureManager.FeatureCut4(
        True, False, False, end, 0, depth, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, False,
        True, True, True, True, False,
        0, 0.0, False, False,
    )


def _count_cylindrical_faces(
    ctx: OpContext, doc: Any, radius_m: float, tolerance: float = 1e-5
) -> int:
    count = 0
    for body in bodies(doc):
        for face in normalize_sequence(get_com_member(body, "GetFaces", default=None)):
            ref = capture(ctx.session, doc, face)
            found = ref.semantic.measurements.radius_m
            if (
                ref.semantic.geometry_type == "cylindrical_face"
                and found is not None
                and abs(found - radius_m) <= tolerance
            ):
                count += 1
    return count


# --- feature lifecycle --------------------------------------------------------


@op(
    name="sw_feature_list",
    tier="core",
    domains=("feature",),
    tags=("feature", "list", "tree", "inspect"),
    summary=(
        "List the feature tree in order, with each feature's locale-invariant type "
        "token, suppression state, and decoded error, if any."
    ),
    safety=ReadSafety(),
    satisfies=("FEAT-015",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def feature_list(ctx: OpContext, args: FeatureListArgs) -> FeatureListResult:
    doc = ctx.require_doc()
    found = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        described = describe_feature(feature)
        if (args.include_suppressed or not described["suppressed"]) and (
            not args.types or described["type"] in args.types
        ):
            described["order"] = guard
            found.append(described)
        feature = try_com_member(feature, "GetNextFeature", default=None)

    errored = [f["name"] for f in found if f["error_code"]]
    return FeatureListResult(
        count=len(found),
        features=found,
        warnings=[f"{len(errored)} feature(s) are in error: {errored[:5]}"] if errored else [],
    )


@op(
    name="sw_feature_edit",
    tier="extended",
    domains=("feature",),
    tags=("feature", "rename", "suppress"),
    summary="Rename a feature or change its suppression state, verified by reading it back.",
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-015", "DAT-005"),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def feature_edit(ctx: OpContext, args: FeatureEditArgs) -> FeatureEditResult:
    doc = ctx.require_doc()
    feature = find_feature(doc, args.feature_name)
    if feature is None:
        raise SwMcpError(
            make_error(
                "FEATURE_NOT_FOUND",
                "validation",
                f"There is no feature named {args.feature_name!r}.",
                remediation=["List the document's features to see the exact names."],
            )
        )

    before = describe_feature(feature)
    if args.rename_to:
        feature.Name = args.rename_to
    if args.suppress is not None:
        try_com_member(doc, "ClearSelection2", True, default=None)
        try_com_member(feature, "Select2", False, 0, default=False)
        get_com_member(doc, "EditSuppress2" if args.suppress else "EditUnsuppress2")

    resolved = find_feature(doc, args.rename_to or args.feature_name)
    after = describe_feature(resolved) if resolved is not None else before

    return FeatureEditResult(
        feature_name=after["name"],
        renamed_to=args.rename_to,
        suppressed=after["suppressed"],
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=[
                Check(
                    name="rename_applied",
                    passed=after["name"] == (args.rename_to or args.feature_name),
                    detail=f"{before['name']} -> {after['name']}",
                ),
                Check(
                    name="suppression_applied",
                    passed=args.suppress is None or after["suppressed"] == args.suppress,
                    detail=f"suppressed={after['suppressed']}",
                ),
            ],
        ),
    )


@op(
    name="sw_feature_delete",
    tier="extended",
    domains=("feature",),
    tags=("feature", "delete", "remove"),
    summary=(
        "Delete a feature, optionally with its dependents, and verify it is gone from "
        "the tree."
    ),
    safety=ModelMutation(destructive=True),
    satisfies=("FEAT-015", "DAT-005"),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def feature_delete(ctx: OpContext, args: FeatureDeleteArgs) -> FeatureDeleteResult:
    doc = ctx.require_doc()
    feature = find_feature(doc, args.feature_name)
    if feature is None:
        raise SwMcpError(
            make_error(
                "FEATURE_NOT_FOUND",
                "validation",
                f"There is no feature named {args.feature_name!r}.",
                remediation=["List the document's features to see the exact names."],
            )
        )

    before = feature_count(doc)
    try_com_member(doc, "ClearSelection2", True, default=None)
    try_com_member(feature, "Select2", False, 0, default=False)
    doc.Extension.DeleteSelection2(
        swconst.value("swDeleteSelectionOptions_e", "swDelete_Children")
        if args.delete_children
        else swconst.value("swDeleteSelectionOptions_e", "swDelete_Absorbed")
    )

    after = feature_count(doc)
    still_there = find_feature(doc, args.feature_name) is not None

    return FeatureDeleteResult(
        feature_name=args.feature_name,
        deleted=not still_there,
        features_before=before,
        features_after=after,
        verification=Verification(
            read_back=True,
            before={"feature_count": before},
            after={"feature_count": after},
            checks=[
                Check(
                    name="feature_removed",
                    passed=not still_there,
                    detail=f"{args.feature_name} is gone"
                    if not still_there
                    else "the feature is still in the tree",
                ),
                Check(
                    name="tree_shrank",
                    passed=after < before,
                    detail=f"{before} -> {after} features",
                ),
            ],
        ),
    )


# --- bodies and measurement ---------------------------------------------------


@op(
    name="sw_body_list",
    tier="core",
    domains=("body", "feature"),
    tags=("body", "solid", "list", "mass"),
    summary=(
        "List the solid and surface bodies with their owning features, material, "
        "visibility, face and edge counts, and mass properties."
    ),
    safety=ReadSafety(),
    satisfies=("FEAT-016",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=300.0,
)
def body_list(ctx: OpContext, args: BodyListArgs) -> BodyListResult:
    _ = args
    doc = ctx.require_doc()
    density = document_density(doc) or 1.0
    summaries = [body_summary(body, density) for body in bodies(doc)]
    return BodyListResult(count=len(summaries), bodies=summaries)


def _aggregate_bodies(chosen: list[Any], density: float) -> dict[str, Any]:
    """Sum volume, area, mass, bounding box, and topology over the chosen bodies."""
    total_volume = total_area = total_mass = 0.0
    weighted_center = [0.0, 0.0, 0.0]
    box: list[float] | None = None
    faces = edges = 0

    for body in chosen:
        properties = body_mass_properties(body, density)
        volume = properties.get("volume_m3") or 0.0
        total_volume += volume
        total_area += properties.get("surface_area_m2") or 0.0
        mass = properties.get("mass_kg") or 0.0
        total_mass += mass
        center = properties.get("center_of_mass_m") or [0.0, 0.0, 0.0]
        for index in range(3):
            weighted_center[index] += center[index] * (mass or volume or 1.0)

        raw_box = normalize_sequence(try_com_member(body, "GetBodyBox", default=None))
        if len(raw_box) == 6:
            values = [float(v) for v in raw_box]
            if box is None:
                box = values
            else:
                box = [
                    *[min(a, b) for a, b in zip(box[0:3], values[0:3], strict=True)],
                    *[max(a, b) for a, b in zip(box[3:6], values[3:6], strict=True)],
                ]
        faces += len(normalize_sequence(get_com_member(body, "GetFaces", default=None)))
        edges += len(normalize_sequence(get_com_member(body, "GetEdges", default=None)))

    divisor = total_mass or total_volume or 1.0
    return {
        "volume_m3": total_volume,
        "surface_area_m2": total_area,
        "mass_kg": total_mass,
        "center_of_mass_m": [value / divisor for value in weighted_center],
        "box": box,
        "face_count": faces,
        "edge_count": edges,
    }


def _mass_caveats(
    whole_document: dict[str, Any], density: float, *, measuring_everything: bool
) -> list[str]:
    """Say when a reported mass is not the model's real mass.

    ``IBody2::GetMassProperties`` computes ``volume * density`` from the density handed
    to it, so it knows nothing about the assigned material: before this, a steel part
    and an aluminium one of the same size both reported the same mass and a density of
    1.0. The document figure comes from ``IModelDocExtension::GetMassProperties``, which
    uses the material, and anything short of that is flagged here rather than presented
    as fact.
    """
    if not whole_document:
        return [
            "SOLIDWORKS did not return document mass properties, so mass assumes a "
            "density of 1.0 kg/m3 and is not the model's real mass."
        ]
    if not measuring_everything:
        return [
            f"Mass is volume x {density:.6g} kg/m3, the density of the whole document. "
            "If bodies carry different materials, this subset's mass is approximate."
        ]
    return []


@op(
    name="sw_measure",
    tier="core",
    domains=("measure", "body"),
    tags=("measure", "volume", "mass", "bounding-box", "inertia"),
    summary=(
        "Measure the model, a body, a feature, or a single face: bounding box, volume, "
        "surface area, mass, centre of mass, topology counts, and rebuild validity."
    ),
    safety=ReadSafety(),
    satisfies=("FEAT-019",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=300.0,
)
def measure(ctx: OpContext, args: MeasureArgs) -> MeasureResult:
    doc = ctx.require_doc()
    scope = args.scope
    unit = args.unit

    if scope.ref is not None:
        resolution = resolve(ctx.session, doc, scope.ref, max_candidates=ctx.config.max_candidates)
        ref = resolution.refreshed
        measurements = ref.semantic.measurements
        return MeasureResult(
            unit=unit,
            scope="entity",
            entity={
                "label": ref.label,
                "geometry_type": ref.semantic.geometry_type,
                "area_mm2": area_from_m2_display(measurements.area_m2),
                "length_mm": from_meters(measurements.length_m, unit)
                if measurements.length_m is not None
                else None,
                "radius_mm": from_meters(measurements.radius_m, unit)
                if measurements.radius_m is not None
                else None,
                "point_mm": [from_meters(v, unit) for v in measurements.point_m]
                if measurements.point_m
                else None,
            },
        )

    chosen = bodies(doc)
    described = "document"
    if scope.body_name:
        chosen = [
            b for b in chosen if str(try_com_member(b, "Name", default="")) == scope.body_name
        ]
        described = f"body {scope.body_name}"
    elif scope.feature_name:
        feature = find_feature(doc, scope.feature_name)
        faces = (
            normalize_sequence(get_com_member(feature, "GetFaces", default=None))
            if feature
            else []
        )
        owned = {
            str(try_com_member(try_com_member(f, "GetBody", default=None), "Name", default=""))
            for f in faces
        }
        chosen = [b for b in chosen if str(try_com_member(b, "Name", default="")) in owned]
        described = f"feature {scope.feature_name}"

    if not chosen:
        raise SwMcpError(
            make_error(
                "NOTHING_TO_MEASURE",
                "validation",
                f"No bodies matched the requested scope ({described}).",
                remediation=["List the document's bodies to see what exists."],
            )
        )

    # The material's density, not the 1.0 IBody2::GetMassProperties assumes.
    whole_document = document_mass_properties(doc)
    density = whole_document.get("density_kg_m3") or 1.0
    measuring_everything = len(chosen) == len(bodies(doc))

    totals = _aggregate_bodies(chosen, density)
    total_volume = totals["volume_m3"]
    total_area = totals["surface_area_m2"]
    total_mass = totals["mass_kg"]
    box = totals["box"]
    faces, edges = totals["face_count"], totals["edge_count"]
    center_of_mass = totals["center_of_mass_m"]

    # Measuring the whole document has an exact answer straight from SOLIDWORKS, so
    # prefer it over the per-body sum. A subset has to be summed, and its mass is only
    # right while every body shares the document's material - which is said out loud
    # rather than left for the caller to discover.
    warnings = _mass_caveats(whole_document, density, measuring_everything=measuring_everything)
    if measuring_everything and whole_document:
        total_mass = whole_document["mass_kg"]
        center_of_mass = whole_document["center_of_mass_m"]

    return MeasureResult(
        unit=unit,
        scope=described,
        mass_properties={
            "volume_m3": total_volume,
            f"volume_{unit}3": volume_to_display(total_volume, unit),
            "surface_area_m2": total_area,
            f"surface_area_{unit}2": area_from_m2_display(total_area, unit),
            "mass_kg": total_mass,
            "density_kg_m3": (total_mass / total_volume) if total_volume else None,
            f"center_of_mass_{unit}": [from_meters(v, unit) for v in center_of_mass],
        },
        bounding_box={
            f"min_{unit}": [from_meters(v, unit) for v in box[0:3]] if box else None,
            f"max_{unit}": [from_meters(v, unit) for v in box[3:6]] if box else None,
            f"size_{unit}": [from_meters(box[i + 3] - box[i], unit) for i in range(3)]
            if box
            else None,
        },
        topology={
            "body_count": len(chosen),
            "face_count": faces,
            "edge_count": edges,
            "feature_count": feature_count(doc),
        },
        validity={
            "has_volume": total_volume > 0,
            "features_in_error": _errored_feature_names(doc),
        },
        warnings=[
            *warnings,
            *(["The model has zero volume."] if total_volume <= 0 else []),
        ],
    )


def _errored_feature_names(doc: Any) -> list[str]:
    """Feature names whose GetErrorCode2 is non-zero (FEAT-019 validity evidence)."""
    names = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        described = describe_feature(feature)
        if described["error_code"]:
            names.append(described["name"])
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return names
