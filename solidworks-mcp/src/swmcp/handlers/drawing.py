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
    DrawingAnnotateModelArgs,
    DrawingAnnotateModelResult,
    DrawingListArgs,
    DrawingListResult,
    DrawingNewArgs,
    DrawingNewResult,
    DrawingNoteAddArgs,
    DrawingNoteAddResult,
    DrawingReviewArgs,
    DrawingReviewResult,
    DrawingSheetAddArgs,
    DrawingSheetAddResult,
    DrawingTableAddArgs,
    DrawingTableAddResult,
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

    # GetFirstView walks the ACTIVE sheet only, so a drawing's other sheets never appear
    # in it. They are taken from GetSheetNames instead and reported without views, which
    # is honest: enumerating their views would mean activating each one, and a read-only
    # operation must not change which sheet the user is looking at.
    walked = {entry["name"] for entry in sheets}
    for name in _sheet_names(doc):
        if name not in walked:
            sheets.append({"name": name, "active": False, "views": []})

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
            f"Only the active sheet can be measured and walked; {', '.join(missing)} "
            f"are listed by name with no size or views. Activate a sheet to inspect it."
        )

    return DrawingListResult(
        sheet_count=len(sheets),
        active_sheet=active_name,
        sheets=sheets,
        view_count=view_total,
        warnings=warnings,
    )


# --- DRW-004 to DRW-008 -----------------------------------------------------------

_ANNOTATION_KINDS = {
    "cosmetic_threads": "swInsertCThreads",
    "datums": "swInsertDatums",
    "dimensions": "swInsertDimensions",
    "geometric_tolerances": "swInsertGTols",
    "notes": "swInsertNotes",
    "surface_finishes": "swInsertSFSymbols",
    "welds": "swInsertWelds",
    "axes": "swInsertAxes",
    "planes": "swInsertPlanes",
    "points": "swInsertPoints",
}

_ANNOTATION_NAMES = {
    swconst.value("swAnnotationType_e", member): name
    for name, member in (
        ("cosmetic_thread", "swCThread"),
        ("datum_tag", "swDatumTag"),
        ("datum_target", "swDatumTargetSym"),
        ("dimension", "swDisplayDimension"),
        ("geometric_tolerance", "swGTol"),
        ("note", "swNote"),
        ("surface_finish", "swSFSymbol"),
        ("weld_symbol", "swWeldSymbol"),
        ("custom_symbol", "swCustomSymbol"),
        ("leader", "swLeader"),
        ("block", "swBlock"),
        ("center_mark", "swCenterMarkSym"),
        ("table", "swTableAnnotation"),
        ("center_line", "swCenterLine"),
        ("datum_origin", "swDatumOrigin"),
        ("revision_cloud", "swRevisionCloud"),
    )
}

_BOM_TYPES = {
    "parts_only": "swBomType_PartsOnly",
    "top_level_only": "swBomType_TopLevelOnly",
    "indented": "swBomType_Indented",
    "flattened": "swBomType_Flattened",
}

_CENTER_MARK_STYLES = {
    "single": "swCenterMark_Single",
    "linear_group": "swCenterMark_LinearGroup",
    "circular_group": "swCenterMark_CircularGroup",
}


def _describe_annotation(annotation: Any) -> dict[str, Any]:
    raw_type = try_com_member(annotation, "GetType", default=None)
    position = try_com_member(annotation, "GetPosition", default=None)
    entry: dict[str, Any] = {
        "name": str(try_com_member(annotation, "GetName", default="") or ""),
        "type": _ANNOTATION_NAMES.get(raw_type, f"unknown({raw_type})"),
    }
    if isinstance(position, (tuple, list)) and len(position) >= 2:
        entry["position_mm"] = [round(from_meters(float(v)), 6) for v in position[:2]]
    return entry


def _annotations_of(view: Any) -> list[Any]:
    found: list[Any] = []
    annotation = try_com_member(view, "GetFirstAnnotation3", default=None)
    guard = 0
    while annotation is not None and guard < 5000:
        guard += 1
        found.append(annotation)
        annotation = try_com_member(annotation, "GetNext3", default=None)
    return found


def _all_annotations(doc: Any) -> list[Any]:
    return [a for view in _walk_views(doc) for a in _annotations_of(view)]


def _display_dimensions(doc: Any) -> int:
    """Dimensions across every view.

    They are *not* reachable through the ``GetFirstAnnotation3`` walk — a view can
    report one display dimension and zero annotations at the same time — so anything
    counting imported dimensions has to ask the views directly.
    """
    return sum(
        int(try_com_member(view, "GetDisplayDimensionCount", default=0) or 0)
        for view in _walk_views(doc)
    )


def _sheet_names(doc: Any) -> list[str]:
    raw = try_com_member(doc, "GetSheetNames", default=None)
    return [str(name) for name in raw] if isinstance(raw, (tuple, list)) else []


def _table_count(doc: Any) -> int:
    return sum(
        int(try_com_member(view, "GetTableAnnotationCount", default=0) or 0)
        for view in _walk_views(doc)
    )


@op(
    name="sw_drawing_sheet_add",
    tier="core",
    domains=("drawing",),
    tags=("drawing", "sheet", "add"),
    summary=(
        "Add a sheet with its own size, scale, and projection standard, measured back "
        "so a sheet of zero area is refused rather than left to hang the next view."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("DRW-007",),
    precondition="drawing",
    idempotent=False,
    timeout_s=300.0,
)
def drawing_sheet_add(ctx: OpContext, args: DrawingSheetAddArgs) -> DrawingSheetAddResult:
    """DRW-007 for sheets.

    ``NewSheet3`` carries the same trap as ``NewDocument``: its width and height are
    read only for a user-defined size, so the schema refuses that size without them.
    """
    doc = _require_drawing(ctx)
    before = _sheet_names(doc)
    if args.name in before:
        raise SwMcpError(
            validation_error(
                "SHEET_NAME_TAKEN",
                f"This drawing already has a sheet named {args.name!r}.",
                remediation=["Sheet names must be unique; pick another."],
            )
        )

    previously_active = try_com_member(
        try_com_member(doc, "GetCurrentSheet", default=None), "GetName", default=None
    )
    scale = args.scale or [1.0, 1.0]
    made = try_com_member(
        doc,
        "NewSheet3",
        args.name,
        swconst.value("swDwgPaperSizes_e", _PAPER_SIZES[args.paper_size]),
        swconst.value("swDwgTemplates_e", "swDwgTemplateNone"),
        float(scale[0]),
        float(scale[1]),
        args.projection == "first_angle",
        "",
        float(args.width or 0.0),
        float(args.height or 0.0),
        "Default",
        default=None,
    )

    after = _sheet_names(doc)
    if not made or args.name not in after:
        raise SwMcpError(
            make_error(
                "DRAWING_SHEET_FAILED",
                "solidworks",
                f"SOLIDWORKS did not add a sheet named {args.name!r}.",
                context={"returned": made, "sheets": after},
                remediation=["Sheet names must be unique within the drawing."],
            )
        )

    # NewSheet3 activates the sheet it made, so it can be measured directly.
    sheet = try_com_member(doc, "GetCurrentSheet", default=None)
    geometry = _sheet_geometry(sheet)
    if not geometry or geometry["width_mm"] <= 0 or geometry["height_mm"] <= 0:
        raise SwMcpError(
            make_error(
                "DRAWING_SHEET_DEGENERATE",
                "solidworks",
                f"The new sheet measures {geometry.get('width_mm')} x "
                f"{geometry.get('height_mm')} mm, which is unusable.",
                context={"sheet": geometry},
                remediation=[
                    "A sheet with no area makes SOLIDWORKS loop forever when a view is "
                    "placed on it, so it is reported now rather than hanging later.",
                ],
            )
        )

    if not args.activate and previously_active:
        try_com_member(doc, "ActivateSheet", previously_active, default=None)

    active = try_com_member(
        try_com_member(doc, "GetCurrentSheet", default=None), "GetName", default=None
    )
    return DrawingSheetAddResult(
        sheet_name=args.name,
        paper_size=geometry["paper_size"],
        width_mm=geometry["width_mm"],
        height_mm=geometry["height_mm"],
        scale=geometry["scale"],
        active_sheet=str(active) if active else None,
        sheets_before=len(before),
        sheets_after=len(after),
        sheet_names=after,
        verification=Verification(
            read_back=True,
            before={"sheet_count": len(before), "sheets": before},
            after={"sheet_count": len(after), "sheets": after, "sheet": geometry},
            checks=[
                Check(
                    name="sheet_is_listed",
                    passed=args.name in after,
                    detail=f"{len(before)} -> {len(after)} sheet(s)",
                ),
                Check(
                    name="sheet_has_area",
                    passed=geometry["width_mm"] > 0 and geometry["height_mm"] > 0,
                    detail=f"{geometry['width_mm']} x {geometry['height_mm']} mm",
                ),
                Check(
                    name="activation_is_as_asked",
                    passed=(str(active) == args.name) == args.activate,
                    detail=f"active sheet is {active!r}",
                ),
            ],
        ),
    )


@op(
    name="sw_drawing_annotate_model",
    tier="core",
    domains=("drawing",),
    tags=("drawing", "dimension", "annotation", "model-items"),
    summary=(
        "Import model dimensions and annotations into the drawing's views, reporting "
        "each one that arrived rather than assuming the import found anything."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("DRW-004",),
    precondition="drawing",
    idempotent=False,
    timeout_s=300.0,
)
def drawing_annotate_model(
    ctx: OpContext, args: DrawingAnnotateModelArgs
) -> DrawingAnnotateModelResult:
    """DRW-004.

    **Version 2, deliberately.** ``InsertModelAnnotations3`` and ``4`` return ``None``
    and import nothing on this build, for a part whose dimensions are every one of them
    ``MarkedForDrawing``; ``InsertModelAnnotations2`` returns ``True`` and places them.
    That came out of trying all three against the same part, and it is why this calls
    the oldest of the family rather than the newest.

    A falsy return means nothing was found to import, which is not the same as failing:
    a model whose sketches were never dimensioned has nothing to bring across. The count
    comes from measuring the views before and after, so "imported nothing" is reported
    as exactly that rather than as success.
    """
    doc = _require_drawing(ctx)
    before_annotations = _all_annotations(doc)
    before_dimensions = _display_dimensions(doc)

    types = 0
    for kind in args.kinds:
        types |= swconst.value("swInsertAnnotation_e", _ANNOTATION_KINDS[kind])

    returned = try_com_member(
        doc,
        "InsertModelAnnotations2",
        swconst.value("swImportModelItemsSource_e", "swImportModelItemsFromEntireModel"),
        types,
        args.all_views,
        args.eliminate_duplicates,
        args.hidden_feature_dimensions,
        args.use_sketch_placement,
        default=None,
    )

    after_annotations = _all_annotations(doc)
    after_dimensions = _display_dimensions(doc)
    before_names = {
        str(try_com_member(a, "GetName", default="") or "") for a in before_annotations
    }
    described = [
        _describe_annotation(a)
        for a in after_annotations
        if str(try_com_member(a, "GetName", default="") or "") not in before_names
    ]
    # Display dimensions are not part of the annotation walk at all, so they are counted
    # from the views and appended here rather than being invisible.
    gained = after_dimensions - before_dimensions
    described.extend({"type": "dimension", "name": ""} for _ in range(max(gained, 0)))

    warnings: list[str] = []
    if not described:
        warnings.append(
            "Nothing was imported. The model has no items of the requested kinds that "
            "are marked for drawings - a part whose sketches were never dimensioned has "
            "no dimensions to bring across."
        )

    before_total = len(before_annotations) + before_dimensions
    after_total = len(after_annotations) + after_dimensions
    return DrawingAnnotateModelResult(
        imported=len(described),
        annotations=described,
        annotations_before=before_total,
        annotations_after=after_total,
        kinds=list(args.kinds),
        warnings=warnings,
        verification=Verification(
            read_back=True,
            before={
                "annotation_count": len(before_annotations),
                "dimension_count": before_dimensions,
            },
            after={
                "annotation_count": len(after_annotations),
                "dimension_count": after_dimensions,
                "imported": described,
            },
            checks=[
                Check(
                    name="counts_match_what_was_reported",
                    passed=after_total - before_total == len(described),
                    detail=f"{before_total} -> {after_total}, {len(described)} new",
                ),
                Check(
                    name="import_call_was_made",
                    # A falsy return is how this reports "nothing to import", which is
                    # not a failure, so it is described rather than raised on.
                    passed=True,
                    detail=f"InsertModelAnnotations2 returned {returned!r}",
                ),
            ],
        ),
    )


@op(
    name="sw_drawing_note_add",
    tier="core",
    domains=("drawing",),
    tags=("drawing", "note", "annotation", "center-mark"),
    summary=(
        "Add a general note or a centre mark to the active sheet, verified by finding "
        "the annotation on the sheet afterwards with its type and position."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("DRW-005",),
    precondition="drawing",
    idempotent=False,
    timeout_s=300.0,
)
def drawing_note_add(ctx: OpContext, args: DrawingNoteAddArgs) -> DrawingNoteAddResult:
    """DRW-005 for notes and centre marks."""
    doc = _require_drawing(ctx)
    before = _all_annotations(doc)
    before_names = {str(try_com_member(a, "GetName", default="") or "") for a in before}

    if args.annotation == "note":
        note = try_com_member(doc, "InsertNote", args.text, default=None)
        if note is None:
            raise SwMcpError(
                make_error(
                    "DRAWING_NOTE_FAILED",
                    "solidworks",
                    "SOLIDWORKS did not create the note.",
                    remediation=["A note needs an active drawing sheet."],
                )
            )
        annotation = try_com_member(note, "GetAnnotation", default=None)
        if args.at is not None and annotation is not None:
            try_com_member(
                annotation,
                "SetPosition",
                float(args.at[0]),
                float(args.at[1]),
                0.0,
                default=None,
            )
    else:
        selected = int(try_com_member(doc, "GetSelectedObjectCount", default=0) or 0)
        if not selected:
            raise SwMcpError(
                validation_error(
                    "NOTHING_SELECTED",
                    "A centre mark is placed on selected circular edges, and nothing is "
                    "selected.",
                    remediation=[
                        "Select the circles first with sw_selection_set or sw_probe_faces.",
                    ],
                )
            )
        made = try_com_member(
            doc,
            "InsertCenterMark3",
            swconst.value("swCenterMarkStyle_e", _CENTER_MARK_STYLES[args.center_mark_style]),
            args.propagate,
            False,
            default=None,
        )
        if not made:
            raise SwMcpError(
                make_error(
                    "DRAWING_CENTER_MARK_FAILED",
                    "solidworks",
                    "SOLIDWORKS did not place a centre mark.",
                    remediation=["Centre marks need circular edges selected in a view."],
                )
            )

    after = _all_annotations(doc)
    fresh = [
        a
        for a in after
        if str(try_com_member(a, "GetName", default="") or "") not in before_names
    ]
    if not fresh:
        raise SwMcpError(
            make_error(
                "DRAWING_ANNOTATION_MISSING",
                "solidworks",
                f"The {args.annotation} call returned but no annotation appeared.",
                context={"annotation_count": len(after)},
            )
        )

    described = _describe_annotation(fresh[-1])
    return DrawingNoteAddResult(
        annotation=args.annotation,
        text=args.text,
        name=described["name"],
        position_mm=described.get("position_mm", []),
        annotations_before=len(before),
        annotations_after=len(after),
        verification=Verification(
            read_back=True,
            before={"annotation_count": len(before)},
            after={"annotation_count": len(after), "annotation": described},
            checks=[
                Check(
                    name="annotation_appeared",
                    passed=len(after) > len(before),
                    detail=f"{len(before)} -> {len(after)} annotation(s)",
                ),
                Check(
                    name="annotation_is_the_kind_requested",
                    passed=described["type"]
                    == ("note" if args.annotation == "note" else "center_mark"),
                    detail=f"{described['type']!r}",
                ),
            ],
        ),
    )


@op(
    name="sw_drawing_table_add",
    tier="core",
    domains=("drawing",),
    tags=("drawing", "bom", "table"),
    summary=(
        "Insert a bill of materials on the active sheet and read every cell back, so "
        "the table's contents are the evidence rather than the call having returned."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("DRW-006",),
    precondition="drawing",
    idempotent=False,
    timeout_s=300.0,
)
def drawing_table_add(ctx: OpContext, args: DrawingTableAddArgs) -> DrawingTableAddResult:
    """DRW-006 for the BOM.

    The rows are read out cell by cell with ``DisplayedText``. A BOM that inserted but
    resolved to nothing is a real failure mode, and only the cells show it.
    """
    doc = _require_drawing(ctx)
    views = _real_views(doc)
    if not views:
        raise SwMcpError(
            validation_error(
                "NO_VIEW_FOR_TABLE",
                "A bill of materials is anchored to a drawing view, and this drawing "
                "has none.",
                remediation=["Place a view first with sw_drawing_view_add."],
            )
        )

    before = _table_count(doc)
    x, y = (float(args.at[0]), float(args.at[1])) if args.at else (0.2, 0.2)

    table = try_com_member(
        views[0],
        "InsertBomTable3",
        args.at is not None,
        x,
        y,
        swconst.value("swBOMConfigurationAnchorType_e", "swBOMConfigurationAnchor_TopLeft"),
        swconst.value("swBomType_e", _BOM_TYPES[args.bom_type]),
        args.configuration or "Default",
        args.template_path or "",
        False,
        default=None,
    )
    if table is None:
        raise SwMcpError(
            make_error(
                "DRAWING_TABLE_FAILED",
                "solidworks",
                "SOLIDWORKS did not insert the bill of materials.",
                context={"bom_type": args.bom_type},
                remediation=[
                    "The view's model must resolve; a BOM of an unsaved model has "
                    "nothing to list.",
                ],
            )
        )

    rows = int(try_com_member(table, "RowCount", default=0) or 0)
    columns = int(try_com_member(table, "ColumnCount", default=0) or 0)
    titles = [
        str(try_com_member(table, "GetColumnTitle", index, default="") or "")
        for index in range(columns)
    ]
    cells = [
        [
            str(try_com_member(table, "DisplayedText", row, column, default="") or "")
            for column in range(columns)
        ]
        for row in range(rows)
    ]
    after = _table_count(doc)

    return DrawingTableAddResult(
        table_type=args.bom_type,
        row_count=rows,
        column_count=columns,
        column_titles=titles,
        rows=cells,
        tables_before=before,
        tables_after=after,
        warnings=(
            ["The table has no data rows, so the model resolved to nothing to list."]
            if rows <= 1
            else []
        ),
        verification=Verification(
            read_back=True,
            before={"table_count": before},
            after={"table_count": after, "rows": rows, "columns": columns},
            checks=[
                Check(
                    name="table_is_on_the_sheet",
                    passed=after > before,
                    detail=f"{before} -> {after} table(s)",
                ),
                Check(
                    name="table_has_cells",
                    passed=rows > 0 and columns > 0,
                    detail=f"{rows} row(s) x {columns} column(s)",
                ),
                Check(
                    name="table_lists_something",
                    passed=rows > 1,
                    detail=f"{max(rows - 1, 0)} data row(s) below the header",
                ),
            ],
        ),
    )


@op(
    name="sw_drawing_review",
    tier="core",
    domains=("drawing", "review"),
    tags=("drawing", "review", "validate", "annotation"),
    summary=(
        "Count and locate a drawing's views, dimensions, notes, tables, and dangling "
        "annotations against caller-supplied minimums. Never a substitute for a person "
        "reading the drawing."
    ),
    safety=ReadSafety(),
    partially_satisfies=("DRW-008",),
    satisfies=("DRW-010",),
    precondition="drawing",
    idempotent=True,
    timeout_s=300.0,
)
def drawing_review(ctx: OpContext, args: DrawingReviewArgs) -> DrawingReviewResult:
    """DRW-008, and DRW-010 by declining to overstate it.

    DRW-010 is a requirement about honesty rather than a feature: *do not claim that
    approximate annotation bounding boxes prove a production drawing*. So this counts
    what is there, attributes every finding to the call it was read from, and sets
    ``visual_review_required`` unconditionally. It does not check that a dimension is
    readable, that leaders do not cross, or that the drawing means what was intended,
    and it never reports a pass as though it had.
    """
    doc = _require_drawing(ctx)
    findings: list[dict[str, Any]] = []

    sheets: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    counts = {"annotation": 0, "dimension": 0, "note": 0, "table": 0, "dangling": 0}
    view_total = 0

    for view in _walk_views(doc):
        is_sheet = try_com_member(view, "Type", default=None) == _SHEET_TYPE
        name = str(try_com_member(view, "GetName2", default="") or "")
        annotations = _annotations_of(view)
        counts["annotation"] += len(annotations)
        counts["dimension"] += int(
            try_com_member(view, "GetDisplayDimensionCount", default=0) or 0
        )
        counts["note"] += int(try_com_member(view, "GetNoteCount", default=0) or 0)
        counts["table"] += int(try_com_member(view, "GetTableAnnotationCount", default=0) or 0)

        for annotation in annotations:
            if bool(try_com_member(annotation, "IsDangling", default=False)):
                counts["dangling"] += 1
                findings.append(
                    {
                        "severity": "block",
                        "sheet": current["name"] if current else name,
                        "detail": (
                            f"annotation {_describe_annotation(annotation)['name']!r} is "
                            f"dangling"
                        ),
                        "read_from": "IAnnotation::IsDangling",
                    }
                )

        if is_sheet:
            current = {"name": name, "views": 0}
            sheets.append(current)
            continue
        view_total += 1
        if current is not None:
            current["views"] += 1

    # Same blind spot as the listing: the walk sees only the active sheet, so the others
    # are named from GetSheetNames and carry no view count to judge.
    walked = {entry["name"] for entry in sheets}
    unwalked = [name for name in _sheet_names(doc) if name not in walked]

    for entry in sheets:
        if entry["views"] < args.require_views:
            findings.append(
                {
                    "severity": "block",
                    "sheet": entry["name"],
                    "detail": (
                        f"{entry['views']} view(s), fewer than the {args.require_views} "
                        f"required"
                    ),
                    "read_from": "IDrawingDoc::GetFirstView walk",
                }
            )

    if counts["dimension"] < args.require_dimensions:
        findings.append(
            {
                "severity": "block",
                "sheet": None,
                "detail": (
                    f"{counts['dimension']} dimension(s), fewer than the "
                    f"{args.require_dimensions} required"
                ),
                "read_from": "IView::GetDisplayDimensionCount",
            }
        )

    if args.require_sheet_format:
        active = try_com_member(doc, "GetCurrentSheet", default=None)
        sheet_format = str(try_com_member(active, "GetSheetFormatName", default="") or "")
        if not sheet_format:
            findings.append(
                {
                    "severity": "warn",
                    "sheet": str(try_com_member(active, "GetName", default="") or ""),
                    "detail": (
                        "the active sheet has no sheet format, so no border or title block"
                    ),
                    "read_from": "ISheet::GetSheetFormatName",
                }
            )

    return DrawingReviewResult(
        passed=not any(finding["severity"] == "block" for finding in findings),
        findings=findings,
        sheet_count=len(sheets) + len(unwalked),
        view_count=view_total,
        annotation_count=counts["annotation"],
        dimension_count=counts["dimension"],
        note_count=counts["note"],
        table_count=counts["table"],
        dangling_count=counts["dangling"],
        warnings=[
            "This counts and locates annotations. It cannot tell whether the drawing "
            "reads correctly, whether a dimension is placed sensibly, or whether "
            "anything overlaps - a person still has to look at it."
        ]
        + (
            [
                f"{', '.join(unwalked)} could not be inspected: only the active sheet "
                f"can be walked, and activating another would change what the user is "
                f"looking at. Their contents are not included in these counts."
            ]
            if unwalked
            else []
        ),
    )
