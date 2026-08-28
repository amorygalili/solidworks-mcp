"""Shell, rib, and composed primitives.

The primitives are built by calling the sketch and boss handlers directly. They are
plain ``(ctx, args)`` functions, so composing them costs nothing and inherits their
read-back verification — a ``sw_body_primitive`` result carries the same evidence the
equivalent hand-built sequence would.

Every primitive also reports the closed-form volume its dimensions imply and the ratio
between that and the measured volume. A sphere that comes out as a hemisphere is a
plausible-looking success under any other check.

Mirror (FEAT-008) and combine (FEAT-017) are **not here**, and the reason is recorded
so the next attempt starts ahead rather than repeating it. On SOLIDWORKS 2026 SP3.0:

* ``InsertMirrorFeature2`` returns ``None`` for every combination tried — mirroring a
  body or a feature, ``BGeometryPattern``/``BMerge``/``BKnit`` either way, the plane at
  selection mark 2 with the item at mark 1 and the reverse. The one shape that *does*
  return a feature (plane at mark 2, ``BODYFEATURE`` at mark 1) creates a Mirror feature
  that adds no material at all.
* ``InsertCombineFeature`` returns ``None`` for every combination tried: both
  ``swCombineBodiesOperationType_e`` (0/1/2) and ``swBodyOperationType_e`` (15901-3);
  bodies from ``IPartDoc::GetBodies2`` and from walking faces (they are the same
  bodies, checked); the tool list as a Python list, as a ``VT_ARRAY|VT_DISPATCH``
  VARIANT, and omitted with the bodies pre-selected.

A ``None`` return is not, by itself, evidence of failure — which is why the two
removals above rest on the measured volume rather than on the return value.
``IFeatureManager::InsertRib`` is declared ``void`` (see
``reference/swapi-docs/types/IFeatureManager/InsertRib.md``), so returning nothing is
its signature rather than a complaint; this module finds the feature by diffing the
tree instead. Read as a failure, it produced ``RIB_FAILED`` for a rib that had built
correctly and measured 9,500 → 11,250 mm³.

One real bug did come out of that investigation and is worth remembering: ``IBody2``
does not share ``IEntity``'s selection signature. ``IEntity::Select2(Append, Mark)``
takes a mark, but ``IBody2::Select2(Append, Data)`` takes a ``SelectData`` object, so
passing an integer silently returns False and nothing is selected. ``IBody2::Select``
is the one that takes a mark. The arity check in ``tests/test_api_versions.py`` cannot
see this — both members take two arguments.
"""

from __future__ import annotations

import math
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation
from swmcp.com.marshal import null_dispatch, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.modeling import model_snapshot, volume_to_display
from swmcp.refs.resolve import resolve
from swmcp.schemas.solid import (
    PrimitiveArgs,
    PrimitiveResult,
    RibArgs,
    RibResult,
    ShellArgs,
    ShellResult,
)
from swmcp.units import from_meters


def _volume_checks(before: dict[str, Any], after: dict[str, Any], *, expect: str) -> list[Check]:
    volume_before = before.get("volume_m3") or 0.0
    volume_after = after.get("volume_m3") or 0.0
    if expect == "more":
        passed, detail = volume_after > volume_before, "material was added"
    elif expect == "less":
        passed, detail = volume_after < volume_before, "material was removed"
    else:
        passed, detail = volume_after != volume_before, "the model changed"

    return [
        Check(
            name="geometry_changed",
            passed=passed,
            detail=(
                f"{detail}: volume {before.get('volume_mm3', 0):.3f} -> "
                f"{after.get('volume_mm3', 0):.3f} mm³"
            ),
        ),
        Check(
            name="model_has_a_body",
            passed=after["body_count"] > 0,
            detail=f"{after['body_count']} solid body(ies)",
        ),
    ]


def _new_feature(doc: Any, before: set[str]) -> Any | None:
    from swmcp.handlers.feature import _new_feature as found

    return found(doc, before)


def _feature_names(doc: Any) -> set[str]:
    from swmcp.handlers.feature import _feature_names as names

    return names(doc)


def _select_feature(doc: Any, name: str, mark: int) -> None:
    if not doc.Extension.SelectByID2(
        name, "BODYFEATURE", 0, 0, 0, True, mark, null_dispatch(), 0
    ):
        raise SwMcpError(
            make_error(
                "FEATURE_NOT_FOUND",
                "reference",
                f"Could not select the feature {name!r}.",
                remediation=["List the document's features to check the name."],
            )
        )


# --- shell --------------------------------------------------------------------


@op(
    name="sw_feature_shell",
    tier="core",
    domains=("feature",),
    tags=("shell", "hollow", "wall", "thickness"),
    summary=(
        "Hollow a solid to a wall thickness, optionally opening it by removing named "
        "faces, and verify that material was actually removed."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("FEAT-009",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_shell(ctx: OpContext, args: ShellArgs) -> ShellResult:
    doc = ctx.require_doc()
    before = model_snapshot(doc)
    if before["body_count"] == 0:
        raise SwMcpError(
            validation_error(
                "NO_BODY_TO_SHELL",
                "There is no solid body in this document to shell.",
                remediation=["Create a feature first."],
            )
        )

    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = 0
    for ref in args.face_refs:
        resolution = resolve(ctx.session, doc, ref, max_candidates=ctx.config.max_candidates)
        if try_com_member(resolution.entity, "Select4", True, null_dispatch(), default=False):
            selected += 1

    if args.face_refs and selected != len(args.face_refs):
        raise SwMcpError(
            make_error(
                "FACES_NOT_SELECTED",
                "reference",
                f"Only {selected} of {len(args.face_refs)} faces could be selected.",
                remediation=["Probe for the faces again; the model may have changed."],
            )
        )

    before_names = _feature_names(doc)
    ok = try_com_member(doc, "InsertFeatureShell", args.thickness, args.outward, default=None)
    feature = _new_feature(doc, before_names)
    if feature is not None and args.name:
        feature.Name = args.name
    name = str(try_com_member(feature, "Name", default="") or "") if feature else ""
    after = model_snapshot(doc)

    if not name:
        raise SwMcpError(
            make_error(
                "SHELL_FAILED",
                "solidworks",
                "SOLIDWORKS did not add a shell feature.",
                context={"returned": repr(ok), "thickness_mm": from_meters(args.thickness, "mm")},
                remediation=[
                    "The wall may be thicker than the thinnest part of the solid.",
                    "Removing every face of a body leaves nothing to shell.",
                ],
            )
        )

    return ShellResult(
        feature_name=name,
        faces_removed=selected,
        thickness_mm=from_meters(args.thickness, "mm"),
        outward=args.outward,
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        face_count_before=before["face_count"],
        face_count_after=after["face_count"],
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=[
                *_volume_checks(before, after, expect="less" if not args.outward else "any"),
                Check(
                    name="wall_created",
                    passed=after["face_count"] > before["face_count"],
                    detail=(
                        f"faces {before['face_count']} -> {after['face_count']}; a shell "
                        "adds inner faces"
                    ),
                ),
            ],
        ),
    )


# --- rib ----------------------------------------------------------------------


@op(
    name="sw_feature_rib",
    tier="extended",
    domains=("feature",),
    tags=("rib", "stiffener", "thicken"),
    summary=(
        "Thicken an open sketch into a rib against the existing solid, reporting the "
        "material it added so a rib that missed the body is visible immediately."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("FEAT-011",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def feature_rib(ctx: OpContext, args: RibArgs) -> RibResult:
    from swmcp.handlers.feature import _select_sketch

    doc = ctx.require_doc()
    before = model_snapshot(doc)
    sketch = _select_sketch(doc, args.sketch_name)

    drafted = args.draft_angle is not None
    before_names = _feature_names(doc)
    # InsertRib is declared void, so there is no return value to test - the feature is
    # found by comparing the tree. Trusting what came back reported RIB_FAILED for a
    # rib that was sitting in the tree, measured at 9500 -> 11250 mm3.
    doc.FeatureManager.InsertRib(
        args.both_sides,
        args.reverse_thickness,
        args.thickness,
        0,  # reference edge index; 0 is the first edge of the profile
        args.reverse_material,
        drafted,
        args.draft_outward,
        args.draft_angle or 0.0,
        args.normal_to_sketch,
        False,  # draft from the wall rather than the sketch
    )
    feature = _new_feature(doc, before_names)
    if feature is None:
        raise SwMcpError(
            make_error(
                "RIB_FAILED",
                "solidworks",
                f"SOLIDWORKS could not build a rib from {sketch!r}.",
                context={"sketch": sketch, "thickness_mm": from_meters(args.thickness, "mm")},
                remediation=[
                    "A rib needs an open profile whose ends reach the existing solid.",
                    "If the profile is placed correctly, try reverse_material=true.",
                ],
            )
        )

    if args.name:
        feature.Name = args.name
    after = model_snapshot(doc)

    return RibResult(
        feature_name=str(try_com_member(feature, "Name", default="") or ""),
        thickness_mm=from_meters(args.thickness, "mm"),
        volume_mm3_before=before["volume_mm3"],
        volume_mm3_after=after["volume_mm3"],
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=_volume_checks(before, after, expect="more"),
        ),
    )


# --- primitives ---------------------------------------------------------------


def _m(value: float) -> dict[str, Any]:
    """One length, in metres, said out loud.

    Every ``Length`` on the arguments has already been normalised to metres, but a bare
    number inside a sketch entity means *millimetres* — that is the documented input
    convention. Passing a normalised value straight through would therefore build a
    primitive a thousand times too small, and it would still be a perfectly valid solid,
    so nothing downstream would notice. Naming the unit removes the ambiguity.
    """
    return {"value": value, "unit": "m"}


def _point(x: float, y: float) -> list[dict[str, Any]]:
    return [_m(x), _m(y)]


def _primitive_profile(args: PrimitiveArgs) -> tuple[list[dict[str, Any]], str, float]:
    """``(sketch entities, method, expected volume in m³)`` for one primitive."""
    x, y = args.at
    kind = args.kind

    if kind == "box":
        half_w, half_d = args.width / 2, args.depth / 2
        return (
            [
                {
                    "type": "rect_corner",
                    "corner": _point(x - half_w, y - half_d),
                    "opposite": _point(x + half_w, y + half_d),
                }
            ],
            "extrude",
            args.width * args.depth * args.height,
        )

    if kind == "cylinder":
        return (
            [{"type": "circle", "center": _point(x, y), "radius": _m(args.radius)}],
            "extrude",
            math.pi * args.radius**2 * args.height,
        )

    if kind == "prism":
        return (
            [
                {
                    "type": "polygon",
                    "center": _point(x, y),
                    "circumradius": _m(args.radius),
                    "sides": args.sides,
                    "inscribed": True,
                }
            ],
            "extrude",
            0.5 * args.sides * args.radius**2 * math.sin(2 * math.pi / args.sides) * args.height,
        )

    if kind == "wedge":
        half_w, half_d = args.width / 2, args.depth / 2
        low_left = _point(x - half_w, y - half_d)
        low_right = _point(x + half_w, y - half_d)
        high_left = _point(x - half_w, y + half_d)
        return (
            [
                {"type": "line", "start": low_left, "end": low_right},
                {"type": "line", "start": low_right, "end": high_left},
                {"type": "line", "start": high_left, "end": low_left},
            ],
            "extrude",
            0.5 * args.width * args.depth * args.height,
        )

    if kind == "sphere":
        # A semicircle and its centerline, and deliberately no closing line. Closing
        # the profile with a line over the centerline makes FeatureRevolve2 return
        # None: measured for both arc directions and for a two-quarter-arc profile.
        # Left open, SOLIDWORKS closes the profile against the axis of revolution
        # itself and the result measures 4/3 pi r^3 to the last digit. Note this is
        # not a general rule about revolves - the cone below closes itself with a
        # line along its own axis and builds without complaint.
        radius = args.radius
        return (
            [
                {
                    "type": "centerline",
                    "start": _point(x, y - radius),
                    "end": _point(x, y + radius),
                },
                {
                    "type": "arc_center",
                    "center": _point(x, y),
                    "start": _point(x, y - radius),
                    "end": _point(x, y + radius),
                    "direction": "counterclockwise",
                },
            ],
            "revolve",
            4 / 3 * math.pi * radius**3,
        )

    if kind in ("cone", "frustum"):
        top_radius = args.top_radius if kind == "frustum" else 0.0
        axis_bottom = _point(x, y)
        axis_top = _point(x, y + args.height)
        rim = _point(x + args.radius, y)
        entities: list[dict[str, Any]] = [
            {"type": "centerline", "start": axis_bottom, "end": axis_top},
            {"type": "line", "start": axis_bottom, "end": rim},
        ]
        if top_radius > 0:
            shoulder = _point(x + top_radius, y + args.height)
            entities += [
                {"type": "line", "start": rim, "end": shoulder},
                {"type": "line", "start": shoulder, "end": axis_top},
            ]
        else:
            entities.append({"type": "line", "start": rim, "end": axis_top})
        entities.append({"type": "line", "start": axis_top, "end": axis_bottom})
        volume = (
            math.pi
            * args.height
            / 3
            * (args.radius**2 + args.radius * top_radius + top_radius**2)
        )
        return entities, "revolve", volume

    # torus
    return (
        [
            {
                "type": "centerline",
                "start": _point(x, y - args.radius),
                "end": _point(x, y + args.radius),
            },
            {
                "type": "circle",
                "center": _point(x + args.radius, y),
                "radius": _m(args.tube_radius),
            },
        ],
        "revolve",
        2 * math.pi**2 * args.radius * args.tube_radius**2,
    )


@op(
    name="sw_body_primitive",
    tier="core",
    domains=("feature", "body"),
    tags=("primitive", "box", "cylinder", "sphere", "cone", "torus", "wedge", "prism"),
    summary=(
        "Build a box, cylinder, sphere, cone, frustum, torus, wedge, or prism as an "
        "ordinary sketch and boss, and check the measured volume against the closed-form "
        "volume its dimensions imply."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("FEAT-014",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def body_primitive(ctx: OpContext, args: PrimitiveArgs) -> PrimitiveResult:
    from swmcp.handlers.feature import feature_extrude_boss, feature_revolve
    from swmcp.handlers.sketch import sketch_add_geometry, sketch_exit, sketch_start
    from swmcp.schemas.feature import ExtrudeArgs, RevolveArgs
    from swmcp.schemas.sketch import (
        SketchAddGeometryArgs,
        SketchExitArgs,
        SketchStartArgs,
    )

    doc = ctx.require_doc()
    before = model_snapshot(doc)
    entities, method, expected_m3 = _primitive_profile(args)

    started = sketch_start(ctx, SketchStartArgs(on={"standard_plane": args.plane}))
    added = sketch_add_geometry(ctx, SketchAddGeometryArgs(entities=entities))
    if added.failed:
        raise SwMcpError(
            make_error(
                "PRIMITIVE_PROFILE_FAILED",
                "solidworks",
                f"The {args.kind} profile could not be drawn.",
                context={"failed": added.failed},
                remediation=["Check the dimensions; a zero or negative size cannot be sketched."],
            )
        )
    # Exit with a rebuild, exactly as an ordinary sketch-then-boss sequence does.
    # Skipping it looked like a cheap saving and is not: the profile is not solved
    # yet, and the boss that follows fails with nothing but 'the profile may be
    # open, self-intersecting, or already consumed'.
    sketch_exit(ctx, SketchExitArgs(rebuild=True))

    if method == "extrude":
        # ``args.height`` is already metres, and ExtrudeArgs.depth is a Length whose
        # bare-number form means millimetres — the same trap the profile coordinates
        # fall into, and just as invisible: the solid comes out valid but a thousand
        # times too short.
        built = feature_extrude_boss(
            ctx,
            ExtrudeArgs(depth=_m(args.height), name=args.name, sketch_name=started.sketch_name),
        )
        feature_name = built.feature_name
    else:
        built = feature_revolve(
            ctx, RevolveArgs(angle=360.0, name=args.name, sketch_name=started.sketch_name)
        )
        feature_name = built.feature_name

    after = model_snapshot(doc)
    measured_mm3 = after["volume_mm3"]
    expected_mm3 = volume_to_display(expected_m3, "mm") or 0.0
    added_mm3 = (measured_mm3 or 0.0) - (before["volume_mm3"] or 0.0)
    ratio = abs(added_mm3 - expected_mm3) / expected_mm3 if expected_mm3 else None

    return PrimitiveResult(
        kind=args.kind,
        feature_name=feature_name,
        sketch_name=started.sketch_name,
        method=method,
        body_count_before=before["body_count"],
        body_count_after=after["body_count"],
        volume_mm3_after=measured_mm3,
        expected_volume_mm3=expected_mm3,
        volume_error_ratio=ratio,
        dimensions={
            field: from_meters(getattr(args, field), "mm")
            for field in ("width", "depth", "height", "radius", "top_radius", "tube_radius")
            if getattr(args, field) is not None
        }
        | ({"sides": args.sides} if args.sides else {}),
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=[
                Check(
                    name="body_created",
                    passed=after["body_count"] > before["body_count"]
                    or (after["volume_mm3"] or 0) > (before["volume_mm3"] or 0),
                    detail=f"bodies {before['body_count']} -> {after['body_count']}",
                ),
                Check(
                    name="volume_matches_the_formula",
                    passed=ratio is not None and ratio < 0.01,
                    detail=(
                        f"added {added_mm3:.3f} mm³, formula says {expected_mm3:.3f} mm³"
                        + (f" ({ratio:.2%} apart)" if ratio is not None else "")
                    ),
                ),
            ],
        ),
    )
