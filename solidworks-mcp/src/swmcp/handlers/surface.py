"""Surface bodies (FEAT-018).

Every call here is ``void`` or a bare ``bool``: ``InsertOffsetSurface``,
``InsertExtendSurface``, and ``InsertSewRefSurface`` report nothing at all, and
``InsertPlanarRefSurface`` returns a bool that is true even in cases where nothing
lands in the tree. So each operation is confirmed by counting sheet bodies and looking
for the feature the call was supposed to add — never by the return value.

The requirement asks for these "where the API supports a stable implementation", and
trimming is where that runs out: SOLIDWORKS exposes no ``InsertTrimSurface``, and the
nearest call, ``InsertCutSurface``, cuts a solid *with* a surface rather than trimming
one surface against another. It is declared rather than approximated.
"""

from __future__ import annotations

from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation
from swmcp.com.marshal import normalize_sequence, null_dispatch, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error
from swmcp.modeling import find_feature, latest_unused_sketch
from swmcp.refs.capture import capture
from swmcp.refs.resolve import resolve
from swmcp.schemas.surface import SurfaceCreateArgs, SurfaceCreateResult

#: ``swBodyType_e``: 0 solid, 1 sheet (a surface), 2 wire.
_SHEET_BODY = 1
_SOLID_BODY = 0


def _body_count(doc: Any, kind: int) -> int:
    return len(normalize_sequence(try_com_member(doc, "GetBodies2", kind, False, default=None)))


def _feature_names(doc: Any) -> set[str]:
    names: set[str] = set()
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        names.add(str(try_com_member(feature, "Name", default="") or ""))
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return names


def _select_all(ctx: OpContext, doc: Any, refs: list[Any]) -> int:
    selected = 0
    for ref in refs:
        resolution = resolve(ctx.session, doc, ref, max_candidates=ctx.config.max_candidates)
        if try_com_member(resolution.entity, "Select4", True, null_dispatch(), default=False):
            selected += 1
    return selected


@op(
    name="sw_surface_create",
    tier="core",
    domains=("feature",),
    tags=("surface", "planar", "offset", "extend", "knit"),
    summary=(
        "Create a surface body by filling a closed sketch, offsetting faces, extending "
        "surface edges, or knitting touching surfaces, verified by counting sheet bodies."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("FEAT-018",),
    precondition="part",
    idempotent=False,
    timeout_s=300.0,
)
def surface_create(ctx: OpContext, args: SurfaceCreateArgs) -> SurfaceCreateResult:
    doc = ctx.require_doc()
    sheets_before = _body_count(doc, _SHEET_BODY)
    names_before = _feature_names(doc)

    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = 0

    if args.method == "planar":
        chosen = args.sketch_name or latest_unused_sketch(doc)
        if not chosen:
            raise SwMcpError(
                make_error(
                    "NO_PROFILE_SKETCH",
                    "validation",
                    "No sketch is available to fill.",
                    remediation=["Create a closed sketch first, or name one explicitly."],
                )
            )
        if not doc.Extension.SelectByID2(
            chosen, "SKETCH", 0, 0, 0, False, 0, null_dispatch(), 0
        ):
            raise SwMcpError(
                make_error(
                    "SKETCH_NOT_SELECTABLE",
                    "reference",
                    f"Could not select the sketch {chosen!r}.",
                    remediation=["List the document's sketches to check the name."],
                )
            )
        selected = 1
        try_com_member(doc, "InsertPlanarRefSurface", default=None)
    elif args.method == "offset":
        selected = _select_all(ctx, doc, args.face_refs)
        try_com_member(doc, "InsertOffsetSurface", float(args.distance), args.reverse, default=None)
    elif args.method == "extend":
        selected = _select_all(ctx, doc, args.edge_refs)
        # EndCondition 0 is "extend by a distance"; the other conditions need a target
        # face or point, which this tool does not take.
        try_com_member(
            doc, "InsertExtendSurface", args.extend_linear, 0, float(args.distance), default=None
        )
    else:  # knit
        selected = _select_all(ctx, doc, args.face_refs)
        try_com_member(doc, "InsertSewRefSurface", default=None)

    expected = (
        1
        if args.method == "planar"
        else len(args.edge_refs)
        if args.method == "extend"
        else len(args.face_refs)
    )
    if selected != expected:
        try_com_member(doc, "ClearSelection2", True, default=None)
        raise SwMcpError(
            make_error(
                "REFERENCE_NOT_SELECTABLE",
                "reference",
                f"Selected {selected} of {expected} references for a {args.method} surface.",
                remediation=["Re-capture the references; the model may have changed."],
            )
        )

    sheets_after = _body_count(doc, _SHEET_BODY)
    created = sorted(_feature_names(doc) - names_before)
    try_com_member(doc, "ClearSelection2", True, default=None)

    if not created:
        raise SwMcpError(
            make_error(
                "SURFACE_FAILED",
                "solidworks",
                f"SOLIDWORKS added no {args.method} surface feature.",
                context={
                    "method": args.method,
                    "sheet_bodies_before": sheets_before,
                    "sheet_bodies_after": sheets_after,
                },
                remediation=[
                    "'planar' needs a closed, non-self-intersecting profile.",
                    "'knit' only sews surfaces that actually touch along an edge; "
                    "parallel or separated sheets are left alone and nothing is built.",
                    "'extend' needs an edge of a surface body, not of a solid.",
                ],
            )
        )

    name = created[-1]
    feature = find_feature(doc, name)
    if args.name and feature is not None:
        feature.Name = args.name
        name = args.name
        feature = find_feature(doc, name)

    reference = capture(ctx.session, doc, feature) if feature is not None else None

    return SurfaceCreateResult(
        feature_name=name,
        method=args.method,
        sheet_bodies_before=sheets_before,
        sheet_bodies_after=sheets_after,
        solid_bodies_after=_body_count(doc, _SOLID_BODY),
        reference=(
            {
                **reference.model_dump(mode="json", exclude_none=True),
                "tool_args": reference.tool_args(),
            }
            if reference is not None
            else None
        ),
        verification=Verification(
            read_back=True,
            before={"sheet_bodies": sheets_before},
            after={"sheet_bodies": sheets_after, "feature": name},
            checks=[
                Check(
                    name="surface_feature_created",
                    passed=bool(created),
                    detail=f"added {', '.join(created)}",
                ),
                Check(
                    name="sheet_bodies_changed_as_expected",
                    # Knit merges sheets, so it should reduce the count; extend reshapes
                    # one in place and leaves it; the others add a body.
                    passed=(
                        sheets_after < sheets_before
                        if args.method == "knit"
                        else sheets_after >= sheets_before
                    ),
                    detail=f"{sheets_before} -> {sheets_after} sheet body(ies)",
                ),
            ],
        ),
    )
