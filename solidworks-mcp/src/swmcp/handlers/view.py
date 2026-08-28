"""Viewport orientation and image capture.

``sw_view_capture`` reads the written file's own header back for its pixel size rather
than echoing the request: SOLIDWORKS clamps a capture to what the viewport can produce,
and a result that repeated the requested size would be describing an image that does
not exist.
"""

from __future__ import annotations

import hashlib
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import NonModelSideEffect
from swmcp.com import swconst
from swmcp.com.marshal import null_dispatch, out_long, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import ArtifactEvidence
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.safety.overwrite import resolve_output_path
from swmcp.safety.paths import assert_output_path
from swmcp.schemas.view import (
    ViewCaptureArgs,
    ViewCaptureResult,
    ViewSetArgs,
    ViewSetResult,
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
    _orient(doc, args.orientation, args.display_mode, fit=args.fit)

    details: dict[str, Any] = {}
    if _FORMATS[suffix] == "bmp":
        # SaveBMP is the only call that takes an explicit pixel size.
        method = "SaveBMP"
        details["returned"] = try_com_member(
            doc, "SaveBMP", str(target), args.width, args.height, default=None
        )
    else:
        method = "Extension.SaveAs"
        errors, warnings = out_long(0), out_long(0)
        details["returned"] = doc.Extension.SaveAs(
            str(target),
            swconst.value("swSaveAsVersion_e", "swSaveAsCurrentVersion"),
            swconst.value("swSaveAsOptions_e", "swSaveAsOptions_Silent"),
            null_dispatch(),
            errors,
            warnings,
        )
        details["error_code"] = getattr(errors, "value", errors)
        details["warning_code"] = getattr(warnings, "value", warnings)

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
        result_warnings.append(
            f"SOLIDWORKS produced {actual[0]}x{actual[1]} rather than the requested "
            f"{args.width}x{args.height}; a capture is limited by the viewport."
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
