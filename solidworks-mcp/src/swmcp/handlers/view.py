"""Viewport orientation and image capture.

``sw_view_capture`` reads the written file's own header back for its pixel size rather
than echoing the request: SOLIDWORKS clamps a capture to what the viewport can produce,
and a result that repeated the requested size would be describing an image that does
not exist.
"""

from __future__ import annotations

import contextlib
import hashlib
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from swmcp.catalog.registry import op
from swmcp.catalog.spec import NonModelSideEffect, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import (
    array_of_doubles,
    normalize_sequence,
    null_dispatch,
    out_long,
    try_com_member,
)
from swmcp.com.preferences import Preferences
from swmcp.context import OpContext
from swmcp.envelope import ArtifactEvidence
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.modeling import bodies, find_feature
from swmcp.refs.resolve import resolve
from swmcp.safety.overwrite import resolve_output_path
from swmcp.safety.paths import assert_output_path
from swmcp.schemas.view import (
    APPEARANCE_FIELDS,
    AppearanceGetArgs,
    AppearanceGetResult,
    AppearanceResult,
    AppearanceSetArgs,
    ViewCaptureArgs,
    ViewCaptureResult,
    ViewSetArgs,
    ViewSetResult,
    VisibilitySetArgs,
    VisibilitySetResult,
)

_ORIENTATIONS = {
    "front": "swFrontView",
    "back": "swBackView",
    "left": "swLeftView",
    "right": "swRightView",
    "top": "swTopView",
    "bottom": "swBottomView",
    "isometric": "swIsometricView",
    "dimetric": "swDimetricView",
    "trimetric": "swTrimetricView",
}

#: ``IModelDoc2`` names each display mode as its own method rather than taking a mode.
_DISPLAY_METHODS = {
    "wireframe": "ViewDisplayWireframe",
    "hidden_lines_removed": "ViewDisplayHiddenremoved",
    "hidden_lines_grayed": "ViewDisplayHiddengreyed",
    "shaded": "ViewDisplayShaded",
    "shaded_with_edges": "ViewDisplayShaded",
}

_FORMATS = {".png": "png", ".bmp": "bmp"}

#: What "reference geometry" means for a capture: the construction scaffolding a model
#: is built on, which is not the model. Deliberately excludes swDisplaySketches - an
#: unconsumed sketch is content a caller may be capturing on purpose, whereas nobody
#: asks for a preview in order to look at the front plane. Every name here was resolved
#: against swUserPreferenceToggle_e on 2026 (34.3.0); swDisplayDimension, which reads
#: like it belongs, is not a member of that enum at all.
_REFERENCE_GEOMETRY_TOGGLES = (
    "swDisplayPlanes",
    "swDisplayAxes",
    "swDisplayTemporaryAxes",
    "swDisplayOrigins",
    "swDisplayCoordSystems",
    "swDisplayReferencePoints",
    "swDisplayCurves",
    "swDisplayDatums",
    "swDisplaySketchPlanes",
)


def _hide_reference_geometry(preferences: Preferences) -> None:
    """Turn the datum scaffolding off for the length of one capture.

    Takes an already-constructed :class:`Preferences` rather than building one, so the
    caller holds the undo record *before* the first toggle is written. Building it here
    and returning it would mean a failure partway through the list threw away the
    record of the toggles already changed, leaving the user's planes switched off with
    nothing left that knew how to put them back.

    The caller restores in a ``finally``. These are the user's own view settings, and a
    capture that left them altered would be a lasting change made on their behalf
    without asking - the same fault as leaving ``AddToDB`` set.
    """
    for name in _REFERENCE_GEOMETRY_TOGGLES:
        preferences.set_toggle(name, False, label=name, shown=False)


def _orient(doc: Any, orientation: str | None, display_mode: str | None, *, fit: bool) -> None:
    if orientation:
        view_id = swconst.value("swStandardViews_e", _ORIENTATIONS[orientation])
        # ShowNamedView2 takes both a name and an id; the id is what makes it
        # locale-independent, so the name is left empty deliberately.
        try_com_member(doc, "ShowNamedView2", "", view_id, default=None)
    if display_mode:
        try_com_member(doc, _DISPLAY_METHODS[display_mode], default=None)
    if fit:
        try_com_member(doc, "ViewZoomtofit2", default=None)
    try_com_member(doc, "GraphicsRedraw2", default=None)


def _image_size(path: Path) -> list[int] | None:
    """Pixel dimensions read out of the file's own header."""
    try:
        header = path.read_bytes()[:32]
    except OSError:  # pragma: no cover - the file was just written
        return None

    if header[:8] == b"\x89PNG\r\n\x1a\n" and len(header) >= 24:
        width, height = struct.unpack(">II", header[16:24])
        return [int(width), int(height)]
    if header[:2] == b"BM" and len(header) >= 26:
        width, height = struct.unpack("<ii", header[18:26])
        return [int(width), abs(int(height))]
    return None


@op(
    name="sw_view_set",
    tier="extended",
    domains=("view",),
    tags=("view", "orientation", "zoom", "display"),
    summary=(
        "Orient the viewport to a standard view, set the display mode, and zoom to fit, "
        "so a later capture shows the model rather than whatever was last on screen."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Changes what the SOLIDWORKS window displays and the view orientation stored "
            "with the document. No geometry, feature, or parameter is altered, but the "
            "application's visible state is, which a user watching the screen will see."
        ),
    ),
    satisfies=("VIEW-003",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=120.0,
)
def view_set(ctx: OpContext, args: ViewSetArgs) -> ViewSetResult:
    doc = ctx.require_doc()
    if args.clear_selection:
        try_com_member(doc, "ClearSelection2", True, default=None)
    _orient(doc, args.orientation, args.display_mode, fit=args.fit)

    return ViewSetResult(
        orientation=args.orientation,
        display_mode=args.display_mode,
        fitted=args.fit,
        selection_cleared=args.clear_selection,
    )


def _save_as_png(doc: Any, target: Path) -> dict[str, Any]:
    """SOLIDWORKS' own PNG writer: whatever size the viewport happens to be."""
    errors, warnings = out_long(0), out_long(0)
    details: dict[str, Any] = {
        "returned": doc.Extension.SaveAs(
            str(target),
            swconst.value("swSaveAsVersion_e", "swSaveAsCurrentVersion"),
            swconst.value("swSaveAsOptions_e", "swSaveAsOptions_Silent"),
            null_dispatch(),
            errors,
            warnings,
        )
    }
    details["error_code"] = getattr(errors, "value", errors)
    details["warning_code"] = getattr(warnings, "value", warnings)
    return details


def _write_png(doc: Any, target: Path, width: int, height: int) -> tuple[str, dict[str, Any]]:
    """Write a PNG at the size that was actually asked for.

    ``Extension.SaveAs`` ignores width and height entirely - every request came back at
    the viewport's own size - so a PNG route through it can only ever report the
    mismatch, never fix it. ``SaveBMP`` does take pixel dimensions, so the image is
    rendered there at full size and re-encoded to PNG.

    Re-encoding rather than resampling is the point: the bitmap is a true render at the
    requested resolution, not an upscale of a smaller one, and BMP to PNG is lossless in
    both directions. A caller asking for 4000px gets 4000px of actual geometry.

    The fallback matters as much as the path. If SaveBMP or the encode fails for any
    reason, SOLIDWORKS' own writer still produces a usable image at viewport size, and
    the existing size warning tells the caller what they got. A capture that is the
    wrong size beats no capture at all.
    """
    scratch = target.with_name(f"{target.stem}__swmcp_capture.bmp")
    details: dict[str, Any] = {}
    try:
        # Called directly rather than through try_com_member: that helper degrades a COM
        # failure to a default, which would leave the fallback reporting "wrote no
        # bitmap" for something that actually raised. The reason is the useful part, and
        # the except below is already the safety net.
        details["bmp_returned"] = doc.SaveBMP(str(scratch), width, height)
        if scratch.is_file():
            with Image.open(scratch) as bitmap:
                bitmap.save(target, format="PNG")
            if target.is_file():
                details["rendered_via"] = "SaveBMP + PNG re-encode"
                return "SaveBMP+PIL", details
        details["fallback_reason"] = "SaveBMP wrote no bitmap"
    except Exception as exc:  # a wrong-size capture beats no capture
        details["fallback_reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        with contextlib.suppress(OSError):
            scratch.unlink(missing_ok=True)

    details.update(_save_as_png(doc, target))
    return "Extension.SaveAs", details


@op(
    name="sw_view_capture",
    tier="core",
    domains=("view",),
    tags=("preview", "screenshot", "png", "bmp", "evidence"),
    summary=(
        "Save a PNG or BMP of the model at a requested size, after clearing the "
        "selection and fitting the view, and report the pixel size read back out of "
        "the written file."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Writes an image file under an allowed output root, and changes the "
            "SOLIDWORKS viewport to take it. The file is reported with its size, "
            "timestamp, and SHA-256; the default overwrite policy never replaces one."
        ),
    ),
    satisfies=("VIEW-004",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def view_capture(ctx: OpContext, args: ViewCaptureArgs) -> ViewCaptureResult:
    doc = ctx.require_doc()

    checked = assert_output_path(args.output_path, ctx.config.allowed_roots)
    suffix = Path(checked).suffix.lower()
    if suffix not in _FORMATS:
        raise SwMcpError(
            validation_error(
                "UNSUPPORTED_IMAGE_FORMAT",
                f"{suffix!r} is not a supported preview format.",
                context={"supported": sorted(_FORMATS)},
                remediation=["Use a .png or .bmp output_path."],
            )
        )

    resolved, action = resolve_output_path(checked, args.overwrite)
    target = Path(resolved)
    target.parent.mkdir(parents=True, exist_ok=True)

    if args.clear_selection:
        try_com_member(doc, "ClearSelection2", True, default=None)

    hidden = None if args.show_reference_geometry else Preferences(ctx.session.app)

    details: dict[str, Any] = {}
    try:
        # Hidden before the orient, so the zoom-to-fit frames the model rather than
        # whatever the datum planes happen to extend to.
        if hidden is not None:
            _hide_reference_geometry(hidden)
        _orient(doc, args.orientation, args.display_mode, fit=args.fit)
        if _FORMATS[suffix] == "bmp":
            # SaveBMP is the only SOLIDWORKS call that takes an explicit pixel size.
            method = "SaveBMP"
            details["returned"] = try_com_member(
                doc, "SaveBMP", str(target), args.width, args.height, default=None
            )
        else:
            method, png_details = _write_png(doc, target, args.width, args.height)
            details.update(png_details)
    finally:
        # Unconditional: these are the user's own view settings, and a failed capture
        # must not leave their planes switched off.
        if hidden is not None:
            hidden.restore()
            try_com_member(doc, "GraphicsRedraw2", default=None)
    details["reference_geometry_hidden"] = (
        sorted(hidden.applied) if hidden is not None else []
    )

    if not target.is_file():
        raise SwMcpError(
            make_error(
                "PREVIEW_NOT_WRITTEN",
                "solidworks",
                f"SOLIDWORKS did not write {target.name}.",
                context={"method": method, **details},
                remediation=[
                    "The document must have an open, visible window for a capture.",
                    "Check that the output directory is writable.",
                ],
            )
        )

    actual = _image_size(target)
    stat = target.stat()
    result_warnings: list[str] = []
    if action == "versioned":
        result_warnings.append(
            f"Wrote {target.name} rather than the requested name, to avoid replacing an "
            "existing file."
        )
    if actual is not None and actual != [args.width, args.height]:
        # Reaching here now means the sized path failed and the fallback ran, so the
        # warning should say that rather than present the viewport size as the rule.
        result_warnings.append(
            f"SOLIDWORKS produced {actual[0]}x{actual[1]} rather than the requested "
            f"{args.width}x{args.height}. The sized capture did not run, so this is the "
            f"viewport's own size: {details.get('fallback_reason', 'reason unknown')}."
        )
    if actual is None:
        result_warnings.append(
            "The image size could not be read back from the file header, so only the "
            "requested size is reported."
        )

    return ViewCaptureResult(
        saved_path=str(target),
        format=_FORMATS[suffix],
        requested_size=[args.width, args.height],
        actual_size=actual,
        orientation=args.orientation,
        display_mode=args.display_mode,
        overwrite_action=action,
        method=method,
        details=details,
        warnings=result_warnings,
        artifacts=[
            ArtifactEvidence(
                path=str(target),
                exists=True,
                size_bytes=stat.st_size,
                modified_utc=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            )
        ],
    )


# --- appearance and visibility ------------------------------------------------


def _appearance_owner(ctx: OpContext, doc: Any, args: Any) -> tuple[Any, str, str]:
    """The COM object carrying the appearance, plus a label for the result."""
    target = args.target
    if target == "document":
        return doc, "document", "the document"
    if target == "body":
        if not args.body_name:
            raise SwMcpError(
                validation_error("MISSING_ARGUMENT", "target='body' needs body_name.")
            )
        for body in bodies(doc):
            if str(try_com_member(body, "Name", default="")) == args.body_name:
                return body, "body", args.body_name
        raise SwMcpError(
            make_error(
                "BODY_NOT_FOUND",
                "validation",
                f"There is no body named {args.body_name!r}.",
                remediation=["List the document's bodies to see the exact names."],
            )
        )
    if target == "feature":
        if not args.feature_name:
            raise SwMcpError(
                validation_error("MISSING_ARGUMENT", "target='feature' needs feature_name.")
            )
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
        return feature, "feature", args.feature_name
    if not args.face_ref:
        raise SwMcpError(validation_error("MISSING_ARGUMENT", "target='face' needs face_ref."))
    resolution = resolve(ctx.session, doc, args.face_ref, max_candidates=ctx.config.max_candidates)
    return resolution.entity, "face", resolution.refreshed.label


def _read_appearance(owner: Any) -> list[float]:
    """The nine doubles, from whichever spelling this object uses.

    IPartDoc and IModelDoc2 expose ``MaterialPropertyValues``; IBody2 and IFace2 use
    ``MaterialPropertyValues2``. Reading the wrong one returns nothing rather than
    raising, so both are tried before concluding there is no appearance here.
    """
    for member in ("MaterialPropertyValues2", "MaterialPropertyValues"):
        values = normalize_sequence(try_com_member(owner, member, default=None))
        if len(values) >= 9:
            return [float(v) for v in values[:9]]
    return []


def _write_appearance(owner: Any, values: list[float]) -> bool:
    """Assign the array, trying both spellings. A plain list will not marshal.

    Assigning a Python tuple appears to work and then reads back as uninitialised
    memory, so the value has to go across as a real VT_R8 SAFEARRAY.
    """
    packed = array_of_doubles(values)
    for member in ("MaterialPropertyValues2", "MaterialPropertyValues"):
        try:
            setattr(owner, member, packed)
        except Exception:
            continue
        if _read_appearance(owner)[:9] == values:
            return True
    return False


@op(
    name="sw_appearance_set",
    tier="core",
    domains=("view",),
    tags=("appearance", "colour", "transparency", "display"),
    summary=(
        "Set the colour, transparency, and shading of the document, a body, a feature, "
        "or a face, changing only the values given and reading the result back."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Changes how the model is displayed and is stored in the document. No "
            "geometry, feature, or dimension is created, changed, or removed."
        ),
    ),
    satisfies=("VIEW-001",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def appearance_set(ctx: OpContext, args: AppearanceSetArgs) -> AppearanceResult:
    doc = ctx.require_doc()
    owner, target, label = _appearance_owner(ctx, doc, args)

    current = _read_appearance(owner) or _read_appearance(doc) or [0.8] * 9
    wanted = list(current)
    changed: list[str] = []

    if args.color is not None:
        for index, value in enumerate(args.color):
            if wanted[index] != value:
                changed.append(APPEARANCE_FIELDS[index])
            wanted[index] = float(value)
    for index, field in enumerate(APPEARANCE_FIELDS):
        if index < 3:
            continue
        supplied = getattr(args, field, None)
        if supplied is not None:
            if wanted[index] != supplied:
                changed.append(field)
            wanted[index] = float(supplied)

    if not _write_appearance(owner, wanted):
        raise SwMcpError(
            make_error(
                "APPEARANCE_NOT_APPLIED",
                "solidworks",
                f"SOLIDWORKS did not apply the appearance to {label}.",
                context={"target": target},
                remediation=[
                    "A face or body appearance needs the entity to still exist; "
                    "re-capture the reference if the model has been rebuilt.",
                ],
            )
        )

    try_com_member(doc, "GraphicsRedraw2", default=None)
    final = _read_appearance(owner)
    return AppearanceResult(
        target=target,
        applied_to=label,
        appearance=dict(zip(APPEARANCE_FIELDS, final, strict=False)),
        changed=sorted(set(changed)),
    )


@op(
    name="sw_appearance_get",
    tier="core",
    domains=("view",),
    tags=("appearance", "colour", "transparency", "inspect"),
    summary=(
        "Read the colour, transparency, and shading of the document, a body, a feature, "
        "or a face, reporting whether the value is its own or inherited."
    ),
    safety=ReadSafety(),
    satisfies=("VIEW-001",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=120.0,
)
def appearance_get(ctx: OpContext, args: AppearanceGetArgs) -> AppearanceGetResult:
    doc = ctx.require_doc()
    owner, target, label = _appearance_owner(ctx, doc, args)

    own = _read_appearance(owner)
    inherited = not own and target != "document"
    values = own or _read_appearance(doc)

    return AppearanceGetResult(
        target=target,
        applied_to=label,
        appearance=dict(zip(APPEARANCE_FIELDS, values, strict=False)),
        inherited=inherited,
        warnings=(
            [f"{label} has no appearance of its own; these are the document's values."]
            if inherited
            else []
        ),
    )


@op(
    name="sw_visibility_set",
    tier="core",
    domains=("view",),
    tags=("visibility", "hide", "show", "body", "feature"),
    summary=(
        "Hide or show a solid body, or blank a reference plane, axis, point, or sketch, "
        "verified by reading the visibility back rather than trusting the call."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Changes what is drawn and is stored in the document. Hidden geometry is "
            "still present and still measured; nothing is created or removed."
        ),
    ),
    satisfies=("VIEW-002",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def visibility_set(ctx: OpContext, args: VisibilitySetArgs) -> VisibilitySetResult:
    """Bodies and features hide through completely different calls.

    ``IBody2::HideBody`` is void, and reference geometry does not use it at all - it
    blanks through ``IModelDoc2::BlankRefGeom``, with sketches on a third pair of calls
    again. All three are void, so each is confirmed by reading the state back.
    """
    doc = ctx.require_doc()

    if args.target == "body":
        body = next(
            (b for b in bodies(doc) if str(try_com_member(b, "Name", default="")) == args.name),
            None,
        )
        if body is None:
            raise SwMcpError(
                make_error(
                    "BODY_NOT_FOUND",
                    "validation",
                    f"There is no body named {args.name!r}.",
                    remediation=["List the document's bodies to see the exact names."],
                )
            )
        try_com_member(body, "HideBody", not args.visible, default=None)
        refreshed = next(
            (b for b in bodies(doc) if str(try_com_member(b, "Name", default="")) == args.name),
            None,
        )
        actual = bool(try_com_member(refreshed, "Visible", default=not args.visible))
        method = "IBody2::HideBody"
    else:
        feature = find_feature(doc, args.name)
        if feature is None:
            raise SwMcpError(
                make_error(
                    "FEATURE_NOT_FOUND",
                    "validation",
                    f"There is no feature named {args.name!r}.",
                    remediation=["List the document's features to see the exact names."],
                )
            )
        type_name = str(try_com_member(feature, "GetTypeName2", default="") or "")
        sketch = type_name in {"ProfileFeature", "3DProfileFeature"}
        member = (
            ("UnblankSketch" if args.visible else "BlankSketch")
            if sketch
            else ("UnBlankRefGeom" if args.visible else "BlankRefGeom")
        )
        try_com_member(doc, "ClearSelection2", True, default=None)
        if not try_com_member(feature, "Select2", False, 0, default=False):
            raise SwMcpError(
                make_error(
                    "FEATURE_NOT_SELECTABLE",
                    "reference",
                    f"Could not select {args.name!r} to change its visibility.",
                )
            )
        try_com_member(doc, member, default=None)
        try_com_member(doc, "ClearSelection2", True, default=None)
        refreshed = find_feature(doc, args.name)
        # IFeature::Visible is swVisibilityState_e (1 hidden, 2 shown), not a boolean -
        # unlike IBody2::Visible on the line above, which really is one. bool() on the
        # enum is True for both states, so a hidden feature read back as visible and the
        # operation reported failure for work it had done correctly.
        state = try_com_member(refreshed, "Visible", default=None)
        shown = swconst.value("swVisibilityState_e", "swVisibilityStateShown")
        actual = (int(state) == shown) if isinstance(state, int) else args.visible
        method = f"IModelDoc2::{member}"

    if actual != args.visible:
        raise SwMcpError(
            make_error(
                "VISIBILITY_NOT_APPLIED",
                "solidworks",
                f"{args.name!r} still reads as {'visible' if actual else 'hidden'}.",
                context={"target": args.target, "method": method, "requested": args.visible},
                remediation=[
                    "A body inside a hidden parent, or a feature consumed by another, "
                    "may not be independently hideable.",
                ],
            )
        )

    return VisibilitySetResult(
        target=args.target,
        name=args.name,
        visible=actual,
        method=method,
    )
