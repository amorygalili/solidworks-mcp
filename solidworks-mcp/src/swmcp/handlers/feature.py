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
from swmcp.refs.probes import ProbeFilters, probe_entities
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
from swmcp.sketching import (
    analyze_contours,
    coincident_axis_segments,
    find_sketch,
    segment_topology,
    straddling_axes,
    unsupported_loose_ends,
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


def feature_error_check(feature: Any) -> Check:
    """FEAT-019 evidence: did SOLIDWORKS flag the feature it just built?

    A feature can be created, change the geometry, and still be in error - a fillet
    that skipped edges, a pattern with failed instances. Every op that returns a
    feature owes this check, so it is written once.
    """
    code = try_com_member(feature, "GetErrorCode2", default=0)
    return Check(name="feature_has_no_error", passed=not code, detail=str(code))


#: End conditions that reach both ways from the sketch plane. Reversing one of these
#: cannot change what it touches, so suggesting it sends the caller to re-run the same
#: failure - which is exactly what happened: two attempts spent on `reverse` and
#: `mid_plane` for a cut whose real fault was a self-intersecting profile.
_SYMMETRIC_END_CONDITIONS = frozenset({"through_all_both", "mid_plane"})


def _extrude_remediation(end_condition: str, *, cut: bool) -> list[str]:
    """What to actually try, given how this extrude was asked to end."""
    steps: list[str] = []
    if cut and end_condition not in _SYMMETRIC_END_CONDITIONS:
        steps.append(
            "A one-way cut that points away from the material removes nothing and "
            "fails. Try reverse=true."
        )
    elif cut:
        steps.append(
            f"{end_condition!r} already reaches both ways from the sketch plane, so "
            f"reverse and a larger depth cannot change what it touches. The fault is "
            f"more likely in the profile."
        )
    steps.append(
        "Run sw_sketch_diagnose on the profile. It reports self-intersections and "
        "major arcs as well as closure - a contour can close cleanly and still have "
        "edges that cross, which no feature will accept."
    )
    steps.append("The profile may also be open, or already consumed by another feature.")
    return steps


def _geometry_checks(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    expect: str,
    feature: Any = None,
) -> list[Check]:
    """The invariants that make a feature operation verifiable rather than assumed.

    ``feature`` adds the rebuild-error check. It lives here rather than at each call
    site because it was written out by hand at four of them and omitted at the rest -
    so a sweep or a loft that SOLIDWORKS had flagged came back all-green while an
    extrude in the same document did not. One place to add it is one place to forget.
    """
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

    checks = [
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
    if feature is not None:
        checks.append(feature_error_check(feature))
    return checks


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
    # Both ways from the sketch plane. Sent as through-all on a double-ended feature
    # rather than as swEndCondThroughAllBoth, which does not do what its name says from
    # here - see _extrude. Without this the only way to cut clean through a part is a
    # blind depth guessed larger than the material in each direction, and a guess that
    # comes up short still removes volume, so every check here passes on a cut that
    # stopped inside the part.
    "through_all_both": "swEndCondThroughAll",
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
    second_direction = args.second_direction
    second_end = (
        swconst.value("swEndConditions_e", "swEndCondBlind") if second_direction else 0
    )

    # "Through all - both" is not one end condition here, whatever the enum implies.
    # Passing swEndCondThroughAllBoth (9) as T1 on a single-ended cut behaves exactly
    # like swEndCondThroughAll: measured on 2026 (34.3.0), a 10mm hole through a 40mm
    # cube sketched on its mid-plane removed 1570mm3 - precisely half the 3141mm3 the
    # bore should be, so it went one way and stopped at the sketch plane. Both
    # directions means a double-ended feature with through-all on each.
    if args.end_condition == "through_all_both":
        end = second_end = swconst.value("swEndConditions_e", "swEndCondThroughAll")
        second_direction = True
    manager = doc.FeatureManager

    # FeatureExtrusion3 always adds material; the parameter that looks like a cut flag
    # is "single-ended". Removing material is a different call altogether.
    if cut:
        feature = manager.FeatureCut4(
            not second_direction,  # Sd: single-ended
            False,                      # Flip
            args.reverse,               # Dir
            end, second_end,            # T1, T2
            args.depth, args.second_depth,
            args.draft > 0, second_direction and args.draft > 0,
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
            not second_direction,
            False,
            args.reverse,
            end, second_end,
            args.depth, args.second_depth,
            args.draft > 0, second_direction and args.draft > 0,
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
                remediation=_extrude_remediation(args.end_condition, cut=cut),
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
                *_geometry_checks(before, after, expect="less" if cut else "more", feature=feature),
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


#: What the old error said, every time, whatever the sketch looked like.
_GENERIC_REVOLVE_ADVICE = [
    "A revolve needs an axis: add a centerline to the sketch, or pass axis_ref.",
    "The profile must not cross the axis.",
]


def revolve_findings(
    segments: list[dict[str, Any]], sketch_name: str, *, axis_given: bool
) -> dict[str, Any]:
    """Turn a sketch's topology into a diagnosis, with no COM in sight.

    Split out from :func:`_revolve_diagnosis` so the reasoning can be tested directly.
    The alternative was to test it through a live revolve failure, and this build turned
    out to be far harder to refuse than expected - it revolves a profile whose axis
    lies on its closing edge, one with a gap between two points on the axis, and one
    with a collinear gap in its outer wall. Three attempts at a failing fixture is
    enough of a hint that the diagnosis should not be reachable only through failure.
    """
    contours = analyze_contours(segments)
    centerlines = [s for s in segments if s.get("construction")]
    overlaps = coincident_axis_segments(segments)
    crossed = straddling_axes(segments)
    # An open contour is only a fault where the axis cannot close it. A profile
    # left open along its own centerline is the ordinary way to draw a revolve,
    # and blaming that gap would send the caller after a problem they do not have.
    stranded = unsupported_loose_ends(contours["loose_ends_mm"], segments)

    context: dict[str, Any] = {
        "sketch": sketch_name,
        "axis_ref_given": axis_given,
        "centerline_count": len(centerlines),
        "closed_contour_count": contours["closed_contour_count"],
        "open_contour_count": contours["open_contour_count"],
        "loose_ends_mm": contours["loose_ends_mm"],
        "loose_ends_the_axis_cannot_close_mm": stranded,
        "branch_points_mm": contours["branch_points_mm"],
        "centerlines_on_a_profile_edge": overlaps,
        "centerlines_the_profile_crosses": crossed,
    }

    remediation: list[str] = []
    if not centerlines and not axis_given:
        remediation.append(
            "The sketch holds no centerline and no axis_ref was passed, so there is "
            "nothing to revolve about. Add a centerline or name an axis."
        )
    if stranded or contours["branch_points_mm"]:
        where = stranded or contours["branch_points_mm"]
        remediation.append(
            f"The profile does not close, and the gap is not on the axis, so the "
            f"revolve cannot close it for you. The ends that do not meet are at "
            f"(mm): {where}."
        )
    elif contours["open_contour_count"]:
        remediation.append(
            "The profile is open, but every loose end lies on the axis, which a "
            "revolve closes by itself - so this is probably not the cause. "
            f"Loose ends (mm): {contours['loose_ends_mm']}."
        )
    if crossed:
        remediation.append(
            "The profile has material on both sides of the axis, which would sweep "
            "through itself. Keep it entirely on one side; touching the axis is "
            "fine, straddling it is not."
        )
    if overlaps:
        # Reported last and hedged on purpose: a revolve did once fail on exactly
        # this arrangement and succeed once the centerline was extended, but the
        # reproduction in tests/live/test_live_sketch_fidelity.py revolves it
        # happily. So it is worth a reader's attention and not worth their
        # confidence.
        remediation.append(
            "A centerline is drawn exactly on top of a profile edge "
            f"({overlaps}). This is not known to cause a refusal on its own - a "
            "deliberate reproduction revolves fine - so treat it as the last thing "
            "to try rather than the answer. Extending the centerline past both ends "
            "of the profile costs nothing and defines the same axis."
        )
    if not remediation:
        remediation.append(
            "The sketch looks revolvable from here: it has "
            f"{contours['closed_contour_count']} closed contour(s), "
            f"{len(centerlines)} centerline(s), and nothing crossing the axis. The "
            "refusal is therefore not one of the usual causes - check that the "
            "sketch is not already consumed by another feature, and that the angle "
            "and thin-thickness values are ones SOLIDWORKS accepts."
        )
    return {"context": context, "remediation": remediation}


def _revolve_diagnosis(doc: Any, sketch_name: str, *, axis_given: bool) -> dict[str, Any]:
    """Say why a revolve was refused, by reading the sketch it was refused on.

    ``FeatureRevolve2`` reports failure by returning ``None`` and nothing else, so the
    old error could only recite the two usual causes and leave the caller to guess
    which applied - or whether either did.

    Diagnosis must never replace the failure with a different one: any COM trouble
    while inspecting falls back to the generic advice, because a confusing error about
    the revolve beats a confident error about the diagnosis.
    """
    try:
        sketch = find_sketch(doc, sketch_name)
        if sketch is None:
            return {
                "context": {"sketch": sketch_name},
                "remediation": _GENERIC_REVOLVE_ADVICE,
            }
        return revolve_findings(
            segment_topology(sketch), sketch_name, axis_given=axis_given
        )
    except Exception as exc:  # diagnosis is a courtesy; the revolve failure is the news
        return {
            "context": {"sketch": sketch_name, "diagnosis_failed": str(exc)},
            "remediation": _GENERIC_REVOLVE_ADVICE,
        }

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
        findings = _revolve_diagnosis(doc, sketch, axis_given=args.axis_ref is not None)
        raise SwMcpError(
            make_error(
                "REVOLVE_FAILED",
                "solidworks",
                f"SOLIDWORKS could not revolve {sketch!r}.",
                context=findings["context"],
                remediation=findings["remediation"],
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
                before,
                after,
                expect="less" if args.mode == "cut" else "more",
                feature=feature,
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
            checks=_geometry_checks(before, after, expect="any", feature=feature),
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
                before,
                after,
                expect="less" if args.mode == "cut" else "more",
                feature=feature,
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
                before,
                after,
                expect="less" if args.mode == "cut" else "more",
                feature=feature,
            ),
        ),
    )


# --- edge features ------------------------------------------------------------


def _edges_for(ctx: OpContext, doc: Any, args: Any, kind: str) -> tuple[list[Any], dict[str, Any]]:
    """Resolve the edges a fillet or chamfer will act on, however they were named.

    Both routes end in the same list of references. The predicate goes through
    :func:`probe_entities` - the machinery behind sw_probe_faces - rather than walking
    edges again here, so "every edge over 2mm" selects exactly what probing for the
    same thing would have reported.
    """
    if args.edges is None:
        return list(args.refs), {}

    query = args.edges
    found, examined = probe_entities(
        ctx.session,
        doc,
        entity_class="edge",
        feature_name=query.feature_name,
        body_name=query.body_name,
        filters=ProbeFilters(
            geometry_type=query.geometry_type,
            length_min_m=query.min_length,
            length_max_m=query.max_length,
        ),
        limit=query.limit,
    )
    if not found:
        # Nothing examined and nothing matched are different failures. A feature that
        # merged into an existing body owns no edges of its own - every edge it made
        # belongs to that body - so scoping to its name searches an empty set, which is
        # not the same as a predicate that was too strict.
        nothing_examined = not examined
        remediation = [
            "Run sw_probe_faces with entity_class='edge' and the same bounds to "
            "see what is actually there.",
            "A body_name or feature_name that names nothing matches nothing; "
            "check it against sw_body_list or sw_feature_list.",
        ]
        if nothing_examined and query.feature_name:
            remediation.insert(
                0,
                f"No edges were examined at all: {query.feature_name!r} contributes none "
                f"directly. A feature merged into an existing body gives its edges to "
                f"that body, so scope by body_name instead - sw_body_list names the body "
                f"and its owning features.",
            )
        raise SwMcpError(
            make_error(
                "NO_EDGES_MATCHED",
                "reference",
                f"No edge matched the {kind} predicate, out of {examined} examined."
                if examined
                else f"No edges were examined for the {kind} predicate, so none could match.",
                context={
                    "examined": examined,
                    "body_name": query.body_name,
                    "feature_name": query.feature_name,
                    "geometry_type": query.geometry_type,
                    "min_length_m": query.min_length,
                    "max_length_m": query.max_length,
                },
                remediation=remediation,
            )
        )
    return found, {"edges_examined": examined, "edges_matched": len(found)}


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

    refs, tallies = _edges_for(ctx, doc, args, "fillet")
    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = _select_refs(ctx, doc, refs)
    if not selected:
        raise SwMcpError(
            make_error(
                "NO_EDGES_SELECTED",
                "reference",
                "None of the supplied references could be selected for a fillet.",
                context=tallies,
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
        ctx, doc, feature, before, selected=selected, kind="fillet", name=args.name,
        tallies=tallies, sizing=_edge_sizing(refs, args.radius),
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

    refs, tallies = _edges_for(ctx, doc, args, "chamfer")
    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = _select_refs(ctx, doc, refs)
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
        ctx, doc, feature, before, selected=selected, kind="chamfer", name=args.name,
        tallies=tallies, sizing=_edge_sizing(refs, args.distance),
    )


def _edge_sizing(refs: list[Any], size: float) -> dict[str, Any]:
    """Measure the selection against the radius, so a failure can name the culprits.

    A fillet needs roughly its own radius of edge to sit in, so the shortest edges are
    where one fails. Their lengths were already measured when the references were
    captured, so this costs no extra COM calls - and "which edge" is the question the
    caller is left holding when SOLIDWORKS answers only "could not create the fillet".
    """
    measured: list[tuple[float, str]] = []
    for ref in refs:
        semantic = getattr(ref, "semantic", None)
        measurements = getattr(semantic, "measurements", None)
        length = getattr(measurements, "length_m", None)
        if isinstance(length, (int, float)) and length > 0:
            measured.append((float(length), str(getattr(ref, "label", "") or "")))
    if not measured:
        return {"size_mm": round(from_meters(size), 4)}
    measured.sort()
    tight = [
        {"label": label, "length_mm": round(from_meters(length), 4)}
        for length, label in measured
        if length < size
    ]
    return {
        "size_mm": round(from_meters(size), 4),
        "shortest_edge_mm": round(from_meters(measured[0][0]), 4),
        "edges_shorter_than_size": tight[:10],
    }


def _edge_feature_result(
    ctx: OpContext,
    doc: Any,
    feature: Any,
    before: dict[str, Any],
    *,
    selected: int,
    kind: str,
    name: str | None,
    tallies: dict[str, Any] | None = None,
    sizing: dict[str, Any] | None = None,
) -> EdgeFeatureResult:
    if feature is None:
        context: dict[str, Any] = {"edges_selected": selected, **(tallies or {}), **(sizing or {})}
        remediation = [
            f"The {kind} may be too large for the geometry, or the edges may not "
            "form a valid chain.",
            "Try a smaller value, or fewer edges.",
        ]
        tight = (sizing or {}).get("edges_shorter_than_size") or []
        if tight:
            remediation.insert(
                0,
                f"{len(tight)} selected edge(s) are shorter than the {kind} size itself "
                f"(shortest {context.get('shortest_edge_mm')}mm against "
                f"{context.get('size_mm')}mm); a {kind} has nowhere to sit on those. "
                f"Exclude them with a min_length above that, or reduce the size.",
            )
        raise SwMcpError(
            make_error(
                f"{kind.upper()}_FAILED",
                "solidworks",
                f"SOLIDWORKS could not create the {kind}.",
                context=context,
                remediation=remediation,
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
        **(tallies or {}),
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
                feature_error_check(feature),
            ],
        ),
    )


# --- patterns -----------------------------------------------------------------


#: Each model axis is where two standard planes meet. Front is XY, Top is XZ, and
#: Right is YZ, so every pair intersects on exactly one of them.
_STANDARD_AXIS_PLANES = {
    "x": ("front", "top"),
    "y": ("front", "right"),
    "z": ("top", "right"),
}

#: Reference axes this server creates on the caller's behalf are named so they can be
#: found again. Without that, every pattern about Y would add another axis to the tree.
STANDARD_AXIS_PREFIX = "swmcp_axis_"


def _standard_axis_feature(ctx: OpContext, doc: Any, which: str) -> tuple[str, bool]:
    """Find or build the reference axis for a model axis; report which it was.

    SOLIDWORKS will not pattern about a bare direction: a circular pattern needs a real
    axis it can select, and the model's own X/Y/Z are not selectable entities. The two
    standard planes that meet on that axis *are* selectable, and ``InsertAxis2`` turns
    them into one - so the shorthand costs a feature in the tree.

    That is a visible change the caller did not ask for, which is why the axis is named
    and reused rather than created per call, and why the result says whether this one
    made it.
    """
    name = f"{STANDARD_AXIS_PREFIX}{which}"
    existing = find_feature(doc, name)
    if existing is not None:
        return name, False

    first, second = _STANDARD_AXIS_PLANES[which]
    before = _feature_names(doc)
    try_com_member(doc, "ClearSelection2", True, default=None)
    ctx.session.find_standard_plane(doc, first).Select2(True, 0)
    ctx.session.find_standard_plane(doc, second).Select2(True, 0)

    # InsertAxis2 answers with a bare bool and puts nothing in the tree when the
    # selection does not describe an axis, so the bool alone is not evidence.
    created = bool(try_com_member(doc, "InsertAxis2", True, default=False))
    feature = _new_feature(doc, before)
    type_name = str(try_com_member(feature, "GetTypeName2", default="") or "") if feature else ""
    if not created or feature is None or type_name != "RefAxis":
        raise SwMcpError(
            make_error(
                "STANDARD_AXIS_UNAVAILABLE",
                "solidworks",
                f"Could not build a reference axis for the {which} axis.",
                context={
                    "planes": [first, second],
                    "insert_axis_returned": created,
                    "created_type": type_name or None,
                },
                remediation=[
                    "This needs the two standard planes to exist and be unsuppressed.",
                    "Pass direction_ref with an edge or axis of your own instead.",
                ],
            )
        )
    feature.Name = name
    return name, True


def _select_pattern_direction(
    ctx: OpContext, doc: Any, args: PatternArgs, axis_name: str | None
) -> None:
    """Put the pattern's first direction on selection mark 1, however it was named."""
    if axis_name is None:
        _select_refs(ctx, doc, [args.direction_ref], mark=1)
        return
    if not doc.Extension.SelectByID2(axis_name, "AXIS", 0, 0, 0, False, 1, null_dispatch(), 0):
        raise SwMcpError(
            make_error(
                "STANDARD_AXIS_UNAVAILABLE",
                "reference",
                f"The reference axis {axis_name!r} exists but could not be selected.",
                context={"axis": axis_name, "standard_axis": args.standard_axis},
                remediation=[
                    "A feature of that name may exist without being an axis; rename or "
                    "delete it, or pass direction_ref instead.",
                ],
            )
        )


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

    if args.direction_ref is None and args.standard_axis is None:
        raise SwMcpError(
            validation_error(
                "MISSING_ARGUMENT",
                "A pattern needs a direction: pass direction_ref, or standard_axis for "
                "the model's own X, Y or Z.",
                remediation=[
                    "For a pattern about the part's centreline, standard_axis='y' needs "
                    "no probing.",
                    "Otherwise probe for a straight edge or an axis and pass its "
                    "tool_args as direction_ref.",
                ],
            )
        )

    # Resolved before the snapshot: building the axis adds a feature, and a "before"
    # taken after it would hide that from the evidence the caller reads back.
    axis_name: str | None = None
    axis_was_created = False
    if args.standard_axis is not None:
        axis_name, axis_was_created = _standard_axis_feature(ctx, doc, args.standard_axis)

    before = model_snapshot(doc)

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
    _select_pattern_direction(ctx, doc, args, axis_name)
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
        axis_name=axis_name,
        axis_was_created=axis_was_created,
        warnings=(
            [
                f"Added the reference axis {axis_name!r} to the feature tree to pattern "
                f"about {args.standard_axis}. Later patterns about the same axis reuse it."
            ]
            if axis_was_created
            else []
        ),
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
                feature_error_check(feature),
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
                feature_error_check(feature),
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

    before_names = _feature_names(doc)
    before = len(before_names)
    try_com_member(doc, "ClearSelection2", True, default=None)
    try_com_member(feature, "Select2", False, 0, default=False)

    # swDelete_Children (1) and swDelete_Absorbed (2) are independent bits, not a
    # choice between two modes. Sending Children alone deleted the dependent features
    # but *kept* the profile sketch the feature had absorbed, which then sat in the
    # tree as an orphan and drew itself over the model. Deleting a feature should take
    # the sketch it consumed with it, so delete_children means both bits.
    absorbed = swconst.value("swDeleteSelectionOptions_e", "swDelete_Absorbed")
    children = swconst.value("swDeleteSelectionOptions_e", "swDelete_Children")
    doc.Extension.DeleteSelection2(absorbed | children if args.delete_children else absorbed)

    after_names = _feature_names(doc)
    after = len(after_names)
    still_there = find_feature(doc, args.feature_name) is not None
    also_removed = sorted(set(before_names) - set(after_names) - {args.feature_name})

    return FeatureDeleteResult(
        feature_name=args.feature_name,
        deleted=not still_there,
        features_before=before,
        features_after=after,
        also_removed=also_removed,
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
                # Naming what else went is the difference between a delete the caller
                # can reason about and one they have to go and look at.
                Check(
                    name="collateral_named",
                    passed=True,
                    detail=f"also removed: {also_removed}" if also_removed else "nothing else",
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


#: The six axis directions a tight box needs, paired with the slot of the returned
#: point that is extreme in that direction and whether it is a maximum.
_EXTREME_DIRECTIONS = (
    ((1.0, 0.0, 0.0), 0, True), ((-1.0, 0.0, 0.0), 0, False),
    ((0.0, 1.0, 0.0), 1, True), ((0.0, -1.0, 0.0), 1, False),
    ((0.0, 0.0, 1.0), 2, True), ((0.0, 0.0, -1.0), 2, False),
)


def tight_body_box(body: Any) -> list[float] | None:
    """A bounding box measured on the body itself, in metres, or ``None``.

    ``IBody2::GetBodyBox`` is cheap and, on anything spline-shaped, *loose*: it bounds
    the underlying surface definition rather than the trimmed material. Measured on
    2026 (34.3.0), a spline body whose true height is exactly 10.000mm reported
    10.843mm - 0.84mm of material that is not there. The same call is exact on
    analytic geometry: a cylinder and a box both agreed to the micron.

    ``IBody2::GetExtremePoint`` answers the real question, one direction at a time, and
    six calls give the axis-aligned box. It returns four values through pywin32 - the
    method's own success flag followed by the point - so the coordinates are slots 1-3.

    ``IModelDocExtension::GetBoundingBox`` would be the obvious alternative and is
    simply not available on this build: it returned ``None`` for every option value.
    """
    low: list[float] = []
    high: list[float] = []
    for direction, axis, is_max in _EXTREME_DIRECTIONS:
        raw = normalize_sequence(try_com_member(body, "GetExtremePoint", *direction))
        if len(raw) != 4:
            return None
        try:
            value = float(raw[1 + axis])
        except (TypeError, ValueError):
            return None
        (high if is_max else low).append(value)
    if len(low) != 3 or len(high) != 3:
        return None
    return [*low, *high]


def _aggregate_bodies(
    chosen: list[Any], density: float, *, tight: bool = False
) -> dict[str, Any]:
    """Sum volume, area, mass, bounding box, and topology over the chosen bodies.

    Only solid bodies carry a volume and a mass. A sheet body contributes its area and
    nothing else, and is counted separately so the caller can be told that a volume of
    zero means "these are surfaces", not "the measurement failed".

    ``tight`` swaps the box for one measured with :func:`tight_body_box`. It is opt-in
    because it costs six extra COM calls per body against one, and ``sw_measure`` is
    already among the slower reads.
    """
    total_volume = total_area = total_mass = 0.0
    weighted_center = [0.0, 0.0, 0.0]
    box: list[float] | None = None
    fast_box: list[float] | None = None
    unmeasured = 0
    faces = edges = 0
    volumeless = 0

    def union(current: list[float] | None, values: list[float] | None) -> list[float] | None:
        if values is None:
            return current
        if current is None:
            return list(values)
        return [
            *[min(a, b) for a, b in zip(current[0:3], values[0:3], strict=True)],
            *[max(a, b) for a, b in zip(current[3:6], values[3:6], strict=True)],
        ]

    for body in chosen:
        properties = body_mass_properties(body, density)
        volumeless += properties.get("volume_m3") is None
        volume = properties.get("volume_m3") or 0.0
        total_volume += volume
        total_area += properties.get("surface_area_m2") or 0.0
        mass = properties.get("mass_kg") or 0.0
        total_mass += mass
        center = properties.get("center_of_mass_m") or [0.0, 0.0, 0.0]
        for index in range(3):
            weighted_center[index] += center[index] * (mass or volume or 1.0)

        raw_box = normalize_sequence(try_com_member(body, "GetBodyBox", default=None))
        fast_values = [float(v) for v in raw_box] if len(raw_box) == 6 else None
        fast_box = union(fast_box, fast_values)

        values = fast_values
        if tight:
            measured = tight_body_box(body)
            if measured is None:
                # Fall back to the loose box rather than dropping the body out of the
                # union entirely - a box missing a body is worse than a box that is
                # slightly large, and the count says which happened.
                unmeasured += 1
            else:
                values = measured
        box = union(box, values)
        faces += len(normalize_sequence(get_com_member(body, "GetFaces", default=None)))
        edges += len(normalize_sequence(get_com_member(body, "GetEdges", default=None)))

    divisor = total_mass or total_volume or 1.0
    return {
        "volume_m3": total_volume,
        "surface_area_m2": total_area,
        "mass_kg": total_mass,
        "volumeless_body_count": volumeless,
        "center_of_mass_m": [value / divisor for value in weighted_center],
        "box": box,
        "fast_box": fast_box,
        "box_method": "extreme_point" if tight and not unmeasured else "body_box",
        "box_unmeasured_bodies": unmeasured,
        "face_count": faces,
        "edge_count": edges,
    }


def _overshoot(totals: dict[str, Any], unit: str) -> dict[str, Any]:
    """How much the cheap box overstated, once there is a tight one to compare it to.

    Reported as evidence rather than as a claim: it is the difference between two
    readings taken on the same bodies in the same call, which is the only way a caller
    can see that the default reading would have been wrong for them.
    """
    box, fast = totals.get("box"), totals.get("fast_box")
    if totals.get("box_method") != "extreme_point" or not box or not fast:
        return {}
    return {
        f"fast_box_overstated_{unit}": [
            round(
                from_meters((fast[i + 3] - fast[i]) - (box[i + 3] - box[i]), unit),
                9,
            )
            for i in range(3)
        ]
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

    totals = _aggregate_bodies(chosen, density, tight=args.bounding_box == "tight")
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
    if totals["volumeless_body_count"]:
        warnings.append(
            f"{totals['volumeless_body_count']} of {len(chosen)} bodies enclose no "
            "volume - a sheet body has an area and a perimeter but no volume or mass, "
            "so neither is included in the totals."
        )
    if totals["box_unmeasured_bodies"]:
        warnings.append(
            f"{totals['box_unmeasured_bodies']} of {len(chosen)} bodies would not "
            "report an extreme point, so the bounding box falls back to the "
            "approximate GetBodyBox reading for those and is reported as approximate."
        )
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
            # Never leave the caller to guess which reading they got: the two differ by
            # nearly a millimetre on spline geometry, which is enough to mislead a
            # clearance check either way.
            "method": totals["box_method"],
            "approximate": totals["box_method"] != "extreme_point",
            **_overshoot(totals, unit),
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
