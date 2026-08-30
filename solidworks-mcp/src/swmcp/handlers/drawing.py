"""Drawings (DRW-001 to DRW-003).

Two things here are not guessable from the type library, and both cost real time.

``ISldWorks::NewDocument`` reads its width and height arguments **only** when the paper
size is ``swDwgPapersUserDefined``. Passing that size with zeros builds a sheet of zero
area; SOLIDWORKS then pegs one core forever the moment a view is placed on it, trying to
auto-scale geometry to fit nothing. It never errors and never returns. The schema
refuses that combination, and :func:`_sheet_geometry` reads the size back so a
degenerate sheet is caught at creation rather than at the next call.

``IDrawingDoc::GetFirstView`` returns the **sheet**, not a view — it reports
``swDrawingSheet`` and a null referenced document, and the real views follow it through
``GetNextView``. ``GetViews`` groups by sheet but handed back views whose ``GetName2``
was ``None`` on this build, so the ``GetFirstView`` walk is the traversal used here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, NonModelSideEffect, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import call_with_outparams, out_long, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.safety.paths import normalize_cad_path
from swmcp.schemas.drawing import (
    DrawingListArgs,
    DrawingListResult,
    DrawingNewArgs,
    DrawingNewResult,
    DrawingViewAddArgs,
    DrawingViewAddResult,
)
from swmcp.units import from_meters

_PAPER_SIZES = {
    "a": "swDwgPaperAsize",
    "a_vertical": "swDwgPaperAsizeVertical",
    "b": "swDwgPaperBsize",
    "c": "swDwgPaperCsize",
    "d": "swDwgPaperDsize",
    "e": "swDwgPaperEsize",
    "a4": "swDwgPaperA4size",
    "a4_vertical": "swDwgPaperA4sizeVertical",
    "a3": "swDwgPaperA3size",
    "a2": "swDwgPaperA2size",
    "a1": "swDwgPaperA1size",
    "a0": "swDwgPaperA0size",
    "custom": "swDwgPapersUserDefined",
}

_PAPER_NAMES = {
    swconst.value("swDwgPaperSizes_e", member): name for name, member in _PAPER_SIZES.items()
}

_VIEW_TYPES = {
    swconst.value("swDrawingViewTypes_e", member): name
    for name, member in (
        ("sheet", "swDrawingSheet"),
        ("section", "swDrawingSectionView"),
        ("detail", "swDrawingDetailView"),
        ("projected", "swDrawingProjectedView"),
        ("auxiliary", "swDrawingAuxiliaryView"),
        ("standard", "swDrawingStandardView"),
        ("named", "swDrawingNamedView"),
        ("relative", "swDrawingRelativeView"),
        ("detached", "swDrawingDetachedView"),
        ("alternate_position", "swDrawingAlternatePositionView"),
    )
}

#: The leading asterisk is part of the name SOLIDWORKS knows these by, and omitting it
#: makes the view call fail rather than fall back to something sensible.
_ORIENTATIONS = {
    "front": "*Front",
    "back": "*Back",
    "left": "*Left",
    "right": "*Right",
    "top": "*Top",
    "bottom": "*Bottom",
    "isometric": "*Isometric",
    "trimetric": "*Trimetric",
    "dimetric": "*Dimetric",
    "current": "*Current",
}

_SHEET_TYPE = swconst.value("swDrawingViewTypes_e", "swDrawingSheet")


def _require_drawing(ctx: OpContext) -> Any:
    doc = ctx.require_doc()
    ctx.session.require_type(doc, "drawing")
    return doc


def _sheet_geometry(sheet: Any) -> dict[str, Any]:
    """``GetProperties2`` as named values.

    The array is ``[paperSize, templateIn, scale1, scale2, firstAngle, width, height,
    sameCustomProp]``. Slots 5 and 6 are the ones worth looking at: a zero there is the
    sheet that makes every later view call spin.
    """
    raw = try_com_member(sheet, "GetProperties2", default=None)
    values = list(raw) if isinstance(raw, (tuple, list)) else []
    if len(values) < 7:
        return {}
    paper = int(values[0])
    # Kept in API units as well as display ones: the SOLIDWORKS calls below want
    # metres, and converting back from the millimetre figures would put a second unit
    # boundary in this module. from_meters in units.py is the only one there is.
    return {
        "paper_size": _PAPER_NAMES.get(paper, f"unknown({paper})"),
        "template_index": int(values[1]),
        "scale": [float(values[2]), float(values[3])],
        "first_angle": bool(values[4]),
        "width_m": float(values[5]),
        "height_m": float(values[6]),
        "width_mm": round(from_meters(float(values[5])), 6),
        "height_mm": round(from_meters(float(values[6])), 6),
    }


def _describe_view(view: Any) -> dict[str, Any]:
    raw_type = try_com_member(view, "Type", default=None)
    position = try_com_member(view, "Position", default=None)
    outline = try_com_member(view, "GetOutline", default=None)
    ratio = try_com_member(view, "ScaleRatio", default=None)
    referenced = try_com_member(view, "ReferencedDocument", default=None)

    entry: dict[str, Any] = {
        "name": str(try_com_member(view, "GetName2", default="") or ""),
        "type": _VIEW_TYPES.get(raw_type, f"unknown({raw_type})"),
        "scale_decimal": float(try_com_member(view, "ScaleDecimal", default=0.0) or 0.0),
        "angle_rad": float(try_com_member(view, "Angle", default=0.0) or 0.0),
        "referenced_configuration": str(
            try_com_member(view, "ReferencedConfiguration", default="") or ""
        ),
        # Null for the sheet, which is how a sheet is told from a view when the type
        # code is not enough.
        "referenced_document": str(try_com_member(referenced, "GetPathName", default="") or "")
        or None,
    }
    if isinstance(ratio, (tuple, list)) and len(ratio) == 2:
        entry["scale"] = [float(ratio[0]), float(ratio[1])]
    if isinstance(position, (tuple, list)) and len(position) == 2:
        entry["position_mm"] = [round(from_meters(float(v)), 6) for v in position]
    if isinstance(outline, (tuple, list)) and len(outline) == 4:
        entry["outline_mm"] = [round(from_meters(float(v)), 6) for v in outline]
    return entry


def _walk_views(doc: Any) -> list[Any]:
    """Every view on every sheet, the sheet entries included.

    ``GetFirstView`` is documented as returning the sheet rather than a view, and it
    does; callers that want only real views filter on the type.
    """
    found: list[Any] = []
    view = try_com_member(doc, "GetFirstView", default=None)
    guard = 0
    while view is not None and guard < 2000:
        guard += 1
        found.append(view)
        view = try_com_member(view, "GetNextView", default=None)
    return found


def _real_views(doc: Any) -> list[Any]:
    return [
        view
        for view in _walk_views(doc)
        if try_com_member(view, "Type", default=None) != _SHEET_TYPE
    ]


@op(
    name="sw_drawing_new",
    tier="core",
    domains=("drawing", "document"),
    tags=("drawing", "sheet", "create", "template"),
    summary=(
        "Create a drawing with an explicit template, sheet size, scale, and projection "
        "standard, reading the sheet back so a degenerate one is caught at creation."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Creates a drawing document in the SOLIDWORKS session and changes what is on "
            "screen. Nothing reaches disk until it is saved."
        ),
    ),
    partially_satisfies=("DRW-001",),
    precondition="none",
    idempotent=False,
    timeout_s=300.0,
    needs_session=True,
)
def drawing_new(ctx: OpContext, args: DrawingNewArgs) -> DrawingNewResult:
    """DRW-001.

    The sheet is measured after creation rather than assumed. A sheet of zero area is
    accepted silently by ``NewDocument`` and only bites at the next call, where it
    presents as SOLIDWORKS hanging rather than as an error — so it is refused here,
    while there is still something useful to say about it.
    """
    if args.template_path:
        template = normalize_cad_path(args.template_path)
        source = "explicit"
        if not Path(template).is_file():
            raise SwMcpError(
                validation_error(
                    "TEMPLATE_NOT_FOUND",
                    f"No drawing template at {template!r}.",
                    remediation=["Omit template_path to use the SOLIDWORKS default."],
                )
            )
    else:
        preference = swconst.value(
            "swUserPreferenceStringValue_e", "swDefaultTemplateDrawing"
        )
        found = try_com_member(
            ctx.session.app, "GetUserPreferenceStringValue", preference, default=None
        )
        template = str(found) if found else ""
        source = "default_preference"
        if not template or not Path(template).is_file():
            raise SwMcpError(
                make_error(
                    "TEMPLATE_NOT_FOUND",
                    "validation",
                    f"SOLIDWORKS reports no usable default drawing template (got "
                    f"{template!r}).",
                    remediation=[
                        "Pass template_path explicitly.",
                        "Or set it in Tools > Options > Default Templates.",
                    ],
                )
            )

    model_path = None
    if args.model_path:
        model_path = normalize_cad_path(args.model_path)
        if not Path(model_path).is_file():
            raise SwMcpError(
                validation_error(
                    "MODEL_NOT_FOUND",
                    f"There is no model at {model_path!r}.",
                    remediation=["Save the part or assembly before drawing it."],
                )
            )

    size = swconst.value("swDwgPaperSizes_e", _PAPER_SIZES[args.paper_size])
    doc = ctx.session.app.NewDocument(
        template, size, float(args.width or 0.0), float(args.height or 0.0)
    )
    if doc is None:
        raise SwMcpError(
            make_error(
                "DRAWING_CREATE_FAILED",
                "solidworks",
                f"SOLIDWORKS refused to create a drawing from {template!r}.",
                remediation=["Confirm the template is a drawing template (.drwdot)."],
            )
        )

    title = str(try_com_member(doc, "GetTitle", default="") or "")
    if title:
        errors = out_long(0)
        call_with_outparams(
            ctx.session.app.ActivateDoc3, title, False, 0, errors, outparams=(errors,)
        )

    sheet = try_com_member(doc, "GetCurrentSheet", default=None)
    if args.sheet_name and sheet is not None:
        try_com_member(sheet, "SetName", args.sheet_name, default=None)
        sheet = try_com_member(doc, "GetCurrentSheet", default=None)

    if args.scale is not None and sheet is not None:
        geometry = _sheet_geometry(sheet)
        try_com_member(
            doc,
            "SetupSheet5",
            str(try_com_member(sheet, "GetName", default="") or ""),
            size,
            swconst.value("swDwgTemplates_e", "swDwgTemplateNone"),
            float(args.scale[0]),
            float(args.scale[1]),
            args.projection == "first_angle",
            str(try_com_member(sheet, "GetTemplateName", default="") or ""),
            geometry.get("width_m", 0.0),
            geometry.get("height_m", 0.0),
            "Default",
            True,
            default=None,
        )
        sheet = try_com_member(doc, "GetCurrentSheet", default=None)

    geometry = _sheet_geometry(sheet) if sheet is not None else {}
    if not geometry or geometry["width_mm"] <= 0 or geometry["height_mm"] <= 0:
        raise SwMcpError(
            make_error(
                "DRAWING_SHEET_DEGENERATE",
                "solidworks",
                f"The new sheet measures {geometry.get('width_mm')} x "
                f"{geometry.get('height_mm')} mm, which is unusable.",
                context={"sheet": geometry, "paper_size": args.paper_size},
                remediation=[
                    "A sheet with no area makes SOLIDWORKS loop forever when a view is "
                    "placed on it, so the drawing is reported as failed now rather than "
                    "hanging on the next call.",
                    "Pass a standard paper_size, or give both width and height with "
                    "paper_size='custom'.",
                ],
            )
        )

    template_name = str(try_com_member(sheet, "GetTemplateName", default="") or "")
    return DrawingNewResult(
        document=ctx.session.describe(doc).as_dict(),
        sheet_name=str(try_com_member(sheet, "GetName", default="") or ""),
        paper_size=geometry["paper_size"],
        width_mm=geometry["width_mm"],
        height_mm=geometry["height_mm"],
        scale=geometry["scale"],
        projection="first_angle" if geometry["first_angle"] else "third_angle",
        template_used=template,
        template_source=source,
        sheet_format=template_name or None,
        warnings=(
            [
                f"The sheet has no sheet format, so there is no border or title block "
                f"(template index {geometry['template_index']})."
            ]
            if geometry["template_index"]
            == swconst.value("swDwgTemplates_e", "swDwgTemplateNone")
            else []
        ),
    )


@op(
    name="sw_drawing_view_add",
    tier="core",
    domains=("drawing",),
    tags=("drawing", "view", "projected", "model"),
    summary=(
        "Place a model view or a standard three-view arrangement on the active sheet, "
        "verified by reading each created view's position, scale, and referenced model."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("DRW-002",),
    precondition="drawing",
    idempotent=False,
    timeout_s=300.0,
)
def drawing_view_add(ctx: OpContext, args: DrawingViewAddArgs) -> DrawingViewAddResult:
    """DRW-002 for model and standard-three views."""
    doc = _require_drawing(ctx)
    before = _real_views(doc)
    before_names = {str(try_com_member(v, "GetName2", default="") or "") for v in before}

    model_path = None
    if args.model_path:
        model_path = normalize_cad_path(args.model_path)
        if not Path(model_path).is_file():
            raise SwMcpError(
                validation_error(
                    "MODEL_NOT_FOUND",
                    f"There is no model at {model_path!r}.",
                    remediation=["Save the part or assembly before drawing it."],
                )
            )
    else:
        for view in before:
            referenced = try_com_member(view, "ReferencedDocument", default=None)
            path = str(try_com_member(referenced, "GetPathName", default="") or "")
            if path:
                model_path = path
                break
        if model_path is None:
            raise SwMcpError(
                validation_error(
                    "MODEL_NOT_GIVEN",
                    "This sheet has no view to take the model from, so model_path is "
                    "required.",
                    remediation=["Pass model_path with the part or assembly to draw."],
                )
            )

    sheet = try_com_member(doc, "GetCurrentSheet", default=None)
    geometry = _sheet_geometry(sheet) if sheet is not None else {}

    if args.view_type == "standard_3":
        method = (
            "Create1stAngleViews2"
            if geometry.get("first_angle")
            else "Create3rdAngleViews2"
        )
        made = try_com_member(doc, method, model_path, default=None)
        placed_ok = bool(made)
    else:
        if args.at is not None:
            x, y = float(args.at[0]), float(args.at[1])
        else:
            # Centre it. The sheet is measured rather than assumed, because a view
            # placed off the sheet is not an error SOLIDWORKS reports.
            x = geometry.get("width_m", 0.0) / 2.0
            y = geometry.get("height_m", 0.0) / 2.0
        view = try_com_member(
            doc,
            "CreateDrawViewFromModelView3",
            model_path,
            _ORIENTATIONS[args.orientation],
            x,
            y,
            0.0,
            default=None,
        )
        placed_ok = view is not None
        if placed_ok and args.name:
            try_com_member(view, "SetName2", args.name, default=None)

    after = _real_views(doc)
    fresh = [
        view
        for view in after
        if str(try_com_member(view, "GetName2", default="") or "") not in before_names
    ]
    created = [_describe_view(view) for view in fresh]

    if not created:
        raise SwMcpError(
            make_error(
                "DRAWING_VIEW_FAILED",
                "solidworks",
                f"SOLIDWORKS placed no view for {args.view_type!r}.",
                context={
                    "model_path": model_path,
                    "orientation": args.orientation,
                    "returned": placed_ok,
                    "sheet": geometry,
                },
                remediation=[
                    "The model must be a part or assembly SOLIDWORKS can open.",
                    "A named view must exist in the model; 'current' uses whatever "
                    "orientation the model was last left in.",
                ],
            )
        )

    expected = 3 if args.view_type == "standard_3" else 1
    on_sheet = [
        view
        for view in created
        if view.get("position_mm")
        and 0.0 <= view["position_mm"][0] <= geometry.get("width_mm", 0.0)
        and 0.0 <= view["position_mm"][1] <= geometry.get("height_mm", 0.0)
    ]

    return DrawingViewAddResult(
        view_type=args.view_type,
        views_created=created,
        views_before=len(before),
        views_after=len(after),
        model_path=model_path,
        verification=Verification(
            read_back=True,
            before={"view_count": len(before)},
            after={"view_count": len(after), "views": created},
            checks=[
                Check(
                    name="views_appeared",
                    passed=len(after) > len(before),
                    detail=f"{len(before)} -> {len(after)} view(s)",
                ),
                Check(
                    name="expected_count_created",
                    passed=len(created) == expected,
                    detail=f"created {len(created)}, expected {expected}",
                ),
                Check(
                    name="views_reference_the_model",
                    passed=all(
                        (view.get("referenced_document") or "").lower()
                        == model_path.lower()
                        for view in created
                    ),
                    detail=f"all referencing {Path(model_path).name}",
                ),
                Check(
                    name="views_land_on_the_sheet",
                    passed=len(on_sheet) == len(created),
                    detail=(
                        f"{len(on_sheet)} of {len(created)} inside "
                        f"{geometry.get('width_mm')} x {geometry.get('height_mm')} mm"
                    ),
                ),
            ],
        ),
    )


@op(
    name="sw_drawing_list",
    tier="core",
    domains=("drawing",),
    tags=("drawing", "sheet", "view", "inspect"),
    summary=(
        "List a drawing's sheets and views with size, scale, projection, and each "
        "view's type, position, outline, referenced model, and configuration."
    ),
    safety=ReadSafety(),
    satisfies=("DRW-003",),
    precondition="drawing",
    idempotent=True,
    timeout_s=180.0,
)
def drawing_list(ctx: OpContext, args: DrawingListArgs) -> DrawingListResult:
    """DRW-003.

    Views are grouped under the sheet whose name each one follows in the ``GetFirstView``
    walk: the walk emits a sheet entry and then that sheet's views, which is the only
    ordering SOLIDWORKS offers here — ``GetViews`` returned views whose names were
    ``None`` on this build.
    """
    doc = _require_drawing(ctx)
    active = try_com_member(doc, "GetCurrentSheet", default=None)
    active_name = str(try_com_member(active, "GetName", default="") or "") or None

    sheets: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    view_total = 0

    for view in _walk_views(doc):
        described = _describe_view(view)
        if try_com_member(view, "Type", default=None) == _SHEET_TYPE:
            current = {
                "name": described["name"],
                "active": described["name"] == active_name,
                "views": [],
            }
            sheets.append(current)
            continue
        if current is None:
            # A view before any sheet entry should not happen; recording it under a
            # named placeholder is better than dropping it silently.
            current = {"name": "(unknown sheet)", "active": False, "views": []}
            sheets.append(current)
        current["views"].append(described)
        view_total += 1

    # The sheet geometry comes from ISheet, which the walk does not hand back.
    for entry in sheets:
        if entry["name"] == active_name and active is not None:
            measured = _sheet_geometry(active)
            entry.update(
                {k: v for k, v in measured.items() if not k.endswith("_m")}
            )

    if args.sheet is not None:
        sheets = [entry for entry in sheets if entry["name"] == args.sheet]
        view_total = sum(len(entry["views"]) for entry in sheets)

    warnings: list[str] = []
    missing = [entry["name"] for entry in sheets if "width_mm" not in entry]
    if missing:
        warnings.append(
            f"Size and scale were only read for the active sheet; {', '.join(missing)} "
            f"report their views only. Activate a sheet to measure it."
        )

    return DrawingListResult(
        sheet_count=len(sheets),
        active_sheet=active_name,
        sheets=sheets,
        view_count=view_total,
        warnings=warnings,
    )
