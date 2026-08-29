"""Neutral-format exchange: export and import.

Two things make this more than a wrapper around ``SaveAs``.

The first is that the export settings are user preferences, not call arguments: writing
a fine binary STL in millimetres means changing three application-wide preferences,
which belong to the person using SOLIDWORKS. So they are saved, applied, and put back
afterwards, and the values actually used are reported.

The second is verification. ``SaveAs`` reports success through out-parameters that
frequently say nothing useful, so the written file is opened and checked against the
format's own signature — a binary STL's triangle count is even checked against its file
size, which catches a truncated write that every other check would pass.
"""

from __future__ import annotations

import contextlib
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
from swmcp.decode.status import decode_save
from swmcp.envelope import ArtifactEvidence
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.modeling import configuration_names, model_snapshot
from swmcp.safety.overwrite import resolve_output_path
from swmcp.safety.paths import assert_output_path, normalize_cad_path
from swmcp.schemas.exchange import (
    BY_EXTENSION,
    IMPORT_BY_EXTENSION,
    MESH_IMPORT_FORMATS,
    ExportArgs,
    ExportResult,
    ImportArgs,
    ImportResult,
    format_for_extension,
    import_format_for_extension,
)

#: Formats whose settings come from the mesh preferences rather than the solid ones.
_MESH_FORMATS = frozenset({"stl", "3mf", "obj", "ply", "vrml"})

_STEP_PROTOCOL = {"ap203": 203, "ap214": 214, "ap242": 242}

#: ``swExportStlUnits`` and friends use ``swLengthUnit_e``.
_MESH_UNITS = {
    "mm": "swMM",
    "cm": "swCM",
    "m": "swMETER",
    "in": "swINCHES",
    "ft": "swFEET",
}

#: Images have their own operation, which controls size and orientation.
_IMAGE_EXTENSIONS = frozenset({".png", ".bmp", ".jpg", ".jpeg", ".tif", ".tiff"})


def _status_dict(status: Any) -> dict[str, Any]:
    return {
        "value": status.value,
        "names": list(status.names),
        "summary": status.summary,
        "remediation": list(status.remediation),
    }


# --- signature verification ---------------------------------------------------


def _verify_stl(data: bytes, size: int) -> tuple[bool, str]:
    if data[:5].lower() == b"solid" and b"facet" in data[:2048].lower():
        return True, "ASCII STL: starts with 'solid' and contains a facet"
    if size >= 84:
        (triangles,) = struct.unpack("<I", data[80:84])
        expected = 84 + 50 * triangles
        if expected == size:
            return True, f"binary STL: {triangles} triangles, and 84 + 50*n == {size} bytes"
        return False, (
            f"binary STL header claims {triangles} triangles, which needs {expected} "
            f"bytes, but the file is {size}"
        )
    return False, "file is too short to be an STL"


def _verify(fmt: str, path: Path) -> tuple[bool, str]:
    """Check the written file against the format's own signature."""
    size = path.stat().st_size
    if size == 0:
        return False, "the file is empty"
    data = path.read_bytes()[:4096]

    if fmt == "step":
        ok = data.lstrip().startswith(b"ISO-10303-21")
        return ok, "STEP part 21 header found" if ok else "no ISO-10303-21 header"
    if fmt == "iges":
        lines = data.split(b"\n")
        ok = bool(lines) and len(lines[0]) >= 73 and lines[0][72:73] == b"S"
        return ok, "IGES section letter S in column 73" if ok else "no IGES S record"
    if fmt == "stl":
        return _verify_stl(data, size)
    if fmt == "3mf":
        ok = data[:2] == b"PK"
        return ok, "3MF container is a zip archive" if ok else "not a zip container"
    if fmt == "pdf":
        ok = data[:4] == b"%PDF"
        return ok, "PDF header found" if ok else "no %PDF header"
    if fmt == "obj":
        text = data[:512].lstrip()
        ok = text.startswith((b"#", b"v ", b"g ", b"o ", b"mtllib"))
        return ok, "OBJ text header found" if ok else "no recognisable OBJ header"
    if fmt in {"parasolid_text", "parasolid_binary"}:
        # Both flavours open with the same printable sentinel and a **PARASOLID marker;
        # only the geometry after the header differs. The binary form went unchecked
        # until a live test exported one and looked at the bytes.
        ok = b"**ABCDEFGHIJKLMNOPQRSTUVWXYZ" in data[:256] and b"**PARASOLID" in data[:512]
        kind = "text" if fmt == "parasolid_text" else "binary"
        return ok, (
            f"Parasolid {kind} header and **PARASOLID marker found"
            if ok
            else "no Parasolid header"
        )
    if fmt == "dwg":
        ok = data[:2] == b"AC"
        return ok, "DWG version header found" if ok else "no AC1xxx header"
    if fmt == "dxf":
        ok = b"SECTION" in data[:1024] or data[:2] == b"AC"
        return ok, "DXF SECTION marker found" if ok else "no DXF SECTION marker"

    return False, f"no signature check is implemented for {fmt}; only size was verified"


# --- preferences --------------------------------------------------------------


class _Preferences:
    """Apply export preferences, then put the user's own settings back.

    These are application-wide settings that belong to whoever is using SOLIDWORKS.
    Changing them permanently as a side effect of one export would be rude, and would
    also make the next export's behaviour depend on the previous one.
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        self.integers: dict[int, int] = {}
        self.toggles: dict[int, bool] = {}
        self.applied: dict[str, Any] = {}

    def set_integer(self, name: str, value: int, *, label: str, shown: Any) -> None:
        code = swconst.value("swUserPreferenceIntegerValue_e", name)
        previous = try_com_member(self.app, "GetUserPreferenceIntegerValue", code, default=None)
        if isinstance(previous, int):
            self.integers.setdefault(code, previous)
        try_com_member(self.app, "SetUserPreferenceIntegerValue", code, value, default=None)
        self.applied[label] = shown

    def set_toggle(self, name: str, value: bool, *, label: str, shown: Any) -> None:
        code = swconst.value("swUserPreferenceToggle_e", name)
        previous = try_com_member(self.app, "GetUserPreferenceToggle", code, default=None)
        if previous is not None:
            self.toggles.setdefault(code, bool(previous))
        try_com_member(self.app, "SetUserPreferenceToggle", code, value, default=None)
        self.applied[label] = shown

    def restore(self) -> None:
        for code, previous in self.integers.items():
            with contextlib.suppress(Exception):
                self.app.SetUserPreferenceIntegerValue(code, previous)
        for code, previous in self.toggles.items():
            with contextlib.suppress(Exception):
                self.app.SetUserPreferenceToggle(code, previous)


def _apply_settings(app: Any, args: ExportArgs, fmt: str) -> _Preferences:
    preferences = _Preferences(app)
    if fmt in _MESH_FORMATS:
        preferences.set_integer(
            "swSTLQuality",
            swconst.value(
                "swSTLQuality_e",
                "swSTLQuality_Fine" if args.stl_quality == "fine" else "swSTLQuality_Coarse",
            ),
            label="stl_quality",
            shown=args.stl_quality,
        )
        preferences.set_integer(
            "swExportStlUnits",
            swconst.value("swLengthUnit_e", _MESH_UNITS[args.mesh_unit]),
            label="mesh_unit",
            shown=args.mesh_unit,
        )
        if fmt == "stl":
            preferences.set_toggle(
                "swSTLBinaryFormat", args.stl_binary, label="stl_binary", shown=args.stl_binary
            )
        # A "show info on save" dialog would wedge every subsequent COM call.
        preferences.set_toggle(
            "swSTLShowInfoOnSave", False, label="stl_info_dialog", shown=False
        )
    elif fmt == "step":
        preferences.set_integer(
            "swStepAP",
            _STEP_PROTOCOL[args.step_protocol],
            label="step_protocol",
            shown=args.step_protocol,
        )
    return preferences


# --- the operation ------------------------------------------------------------


@op(
    name="sw_export",
    tier="core",
    domains=("exchange",),
    tags=("export", "step", "stl", "iges", "3mf", "obj", "parasolid", "pdf", "dxf"),
    summary=(
        "Export the model to a neutral format with explicit tessellation, unit, and "
        "protocol settings, then verify the written file against that format's own "
        "signature rather than trusting that SaveAs returned."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Writes a file under an allowed output root, and temporarily changes the "
            "SOLIDWORKS export preferences it needs, restoring them afterwards. The "
            "file is reported with its size, timestamp, and SHA-256."
        ),
    ),
    satisfies=("IO-002",),
    partially_satisfies=("IO-003",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=600.0,
)
def export(ctx: OpContext, args: ExportArgs) -> ExportResult:
    doc = ctx.require_doc()

    checked = assert_output_path(args.output_path, ctx.config.allowed_roots)
    suffix = Path(checked).suffix.lower()

    if suffix in _IMAGE_EXTENSIONS:
        raise SwMcpError(
            validation_error(
                "USE_VIEW_CAPTURE",
                f"{suffix!r} is an image format; sw_view_capture writes those and also "
                "controls the size and orientation.",
                context={"output_path": checked},
                remediation=["Call sw_view_capture for a PNG or BMP preview."],
            )
        )

    fmt = args.format or format_for_extension(checked)
    if fmt is None:
        raise SwMcpError(
            validation_error(
                "UNSUPPORTED_EXPORT_FORMAT",
                f"{suffix!r} is not an export format this release writes.",
                context={"supported_extensions": sorted(BY_EXTENSION)},
                remediation=[
                    "Use one of the supported extensions, or say which format you meant.",
                ],
            )
        )

    previous_configuration = None
    if args.configuration:
        previous_configuration = _activate_configuration(doc, args.configuration)

    resolved, action = resolve_output_path(checked, args.overwrite)
    target = Path(resolved)
    target.parent.mkdir(parents=True, exist_ok=True)

    preferences = _apply_settings(ctx.session.app, args, fmt)
    try:
        errors, warnings = out_long(0), out_long(0)
        doc.Extension.SaveAs(
            str(target),
            swconst.value("swSaveAsVersion_e", "swSaveAsCurrentVersion"),
            swconst.value("swSaveAsOptions_e", "swSaveAsOptions_Silent"),
            null_dispatch(),
            errors,
            warnings,
        )
        error_code = getattr(errors, "value", errors)
        warning_code = getattr(warnings, "value", warnings)
    finally:
        preferences.restore()
        if previous_configuration and previous_configuration != args.configuration:
            try_com_member(doc, "ShowConfiguration2", previous_configuration, default=None)

    error_status, warning_status = decode_save(error_code, warning_code)

    if not target.is_file():
        raise SwMcpError(
            make_error(
                "EXPORT_NOT_WRITTEN",
                "solidworks",
                f"SOLIDWORKS did not write {target.name}.",
                context={"format": fmt, "error": _status_dict(error_status)},
                remediation=[
                    *error_status.remediation,
                    "Check that the format is available for this document type.",
                ],
            )
        )

    verified, detail = _verify(fmt, target)
    stat = target.stat()

    result_warnings: list[str] = []
    if action == "versioned":
        result_warnings.append(
            f"Wrote {target.name} rather than the requested name, to avoid replacing an "
            "existing file."
        )
    if not verified:
        result_warnings.append(f"The written file did not verify as {fmt}: {detail}")
    if warning_status.value:
        result_warnings.append(
            f"SOLIDWORKS reported a save warning: {warning_status.summary}"
        )

    return ExportResult(
        saved_path=str(target),
        format=fmt,
        overwrite_action=action,
        size_bytes=stat.st_size,
        signature_verified=verified,
        signature_detail=detail,
        settings=preferences.applied
        | ({"configuration": args.configuration} if args.configuration else {}),
        save_error=_status_dict(error_status),
        save_warning=_status_dict(warning_status),
        warnings=result_warnings,
        artifacts=[
            ArtifactEvidence(
                path=str(target),
                exists=True,
                size_bytes=stat.st_size,
                modified_utc=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                sha256=hashlib.sha256(target.read_bytes()).hexdigest()
                if stat.st_size <= 64 * 1024 * 1024
                else None,
            )
        ],
    )


def _activate_configuration(doc: Any, name: str) -> str | None:
    """Switch to ``name``, returning the configuration that was active before.

    Exporting one configuration is not a request to leave the model showing it, so the
    caller's own configuration is restored once the file is written.
    """
    known = configuration_names(doc)
    if name not in known:
        raise SwMcpError(
            validation_error(
                "CONFIGURATION_NOT_FOUND",
                f"No configuration named {name!r}.",
                context={"existing": known},
            )
        )

    active = try_com_member(doc, "GetActiveConfiguration", default=None)
    previous = (
        str(try_com_member(active, "Name", default="") or "") or None if active else None
    )
    try_com_member(doc, "ShowConfiguration2", name, default=None)
    return previous


# --- import (IO-001) ----------------------------------------------------------

#: ``swImportStlVrmlModelType_e``. SOLIDWORKS' own default is Graphics, which produces a
#: picture rather than a body: zero bodies, no volume, nothing addressable.
_MESH_BODY_TYPES = {
    "graphics": "swImportStlVrmlModelType_Graphics",
    "surface": "swImportStlVrmlModelType_Surface",
    "solid": "swImportStlVrmlModelType_Solid",
}

_NEUTRAL_UNITS = {
    "file": "swImportNeutralUnits_ImportFileUnits",
    "template": "swImportNeutralUnits_TemplateUnits",
}

_KNIT_OPTIONS = {
    "form_solids": "swImportNeutralKnitOption_FormSolids",
    "do_not_knit": "swImportNeutralKnitOption_DoNotKnit",
}


def _apply_import_settings(app: Any, args: ImportArgs, fmt: str) -> _Preferences:
    """Import options are user preferences, exactly as the export ones are.

    ``ISldWorks::GetImportFileData`` looks like the argument-shaped alternative, but on
    this build it returns ``None`` for Parasolid, ACIS, and STL, and for STEP returns an
    object whose only reachable property is ``MapConfigurationData`` — passing it back
    into ``LoadFile4`` changed nothing that could be measured. So the preference route is
    the one that works, and the caller's own settings are put back afterwards.
    """
    preferences = _Preferences(app)
    if fmt in MESH_IMPORT_FORMATS:
        preferences.set_integer(
            "swImportStlVrmlModelType",
            swconst.value("swImportStlVrmlModelType_e", _MESH_BODY_TYPES[args.mesh_body_type]),
            label="mesh_body_type",
            shown=args.mesh_body_type,
        )
        if args.mesh_unit is not None:
            preferences.set_integer(
                "swImportStlVrmlUnits",
                swconst.value("swLengthUnit_e", _MESH_UNITS[args.mesh_unit]),
                label="mesh_unit",
                shown=args.mesh_unit,
            )
    else:
        preferences.set_integer(
            "swImportNeutral_KnitOption",
            swconst.value("swImportNeutralKnitOption_e", _KNIT_OPTIONS[args.knit]),
            label="knit",
            shown=args.knit,
        )
        preferences.set_integer(
            "swImportNeutralUnits",
            swconst.value("swImportNeutralUnits_e", _NEUTRAL_UNITS[args.neutral_units]),
            label="neutral_units",
            shown=args.neutral_units,
        )
    return preferences


def _geometry_summary(doc: Any) -> dict[str, Any]:
    """What actually arrived, measured rather than assumed."""
    snapshot = model_snapshot(doc)
    solids = snapshot.get("solid_body_count", 0)
    return {
        "body_count": snapshot.get("body_count", 0),
        "solid_body_count": solids,
        "sheet_body_count": snapshot.get("sheet_body_count", 0),
        "volume_mm3": snapshot.get("volume_mm3") if solids else None,
        "surface_area_mm2": snapshot.get("surface_area_mm2"),
        "face_count": snapshot.get("face_count", 0),
        "edge_count": snapshot.get("edge_count", 0),
    }


def _run_import_diagnostics(doc: Any, args: ImportArgs) -> dict[str, Any]:
    """``IPartDoc::ImportDiagnosis``, reported by what it changed.

    The call returns 1 on a body that needed nothing doing, so its return value alone
    would let a tool claim it repaired geometry that was never broken. The face count and
    volume on either side are what make the claim checkable.
    """
    before = _geometry_summary(doc)
    returned = try_com_member(
        doc,
        "ImportDiagnosis",
        args.close_gaps,
        args.remove_bad_faces,
        args.fix_faces,
        0,
        default=None,
    )
    after = _geometry_summary(doc)
    changed = (
        before["face_count"] != after["face_count"]
        or before["body_count"] != after["body_count"]
        or before["volume_mm3"] != after["volume_mm3"]
    )
    return {
        "ran": True,
        "returned": returned,
        "changed_the_model": changed,
        "faces_before": before["face_count"],
        "faces_after": after["face_count"],
        "volume_mm3_before": before["volume_mm3"],
        "volume_mm3_after": after["volume_mm3"],
        "options": {
            "close_gaps": args.close_gaps,
            "fix_faces": args.fix_faces,
            "remove_bad_faces": args.remove_bad_faces,
        },
    }


@op(
    name="sw_import",
    tier="core",
    domains=("exchange",),
    tags=("import", "step", "iges", "parasolid", "acis", "stl", "translate"),
    summary=(
        "Import a STEP, IGES, Parasolid, ACIS, or STL file into a new document, then "
        "report the geometry that actually arrived — body counts, volume, and topology "
        "— rather than trusting that LoadFile4 returned."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Reads a file and opens a new document in the session. The source file is "
            "not modified, and the import preferences it changes are restored "
            "afterwards."
        ),
    ),
    partially_satisfies=("IO-001",),
    precondition="none",
    idempotent=False,
    timeout_s=900.0,
)
def import_geometry(ctx: OpContext, args: ImportArgs) -> ImportResult:
    source = normalize_cad_path(args.input_path)
    if not Path(source).is_file():
        raise SwMcpError(
            make_error(
                "FILE_NOT_FOUND",
                "validation",
                f"There is no file at {source!r}.",
                context={"input_path": source},
                remediation=["Check the path, or export the file first."],
            )
        )

    fmt = args.format or import_format_for_extension(source)
    if fmt is None:
        raise SwMcpError(
            validation_error(
                "UNSUPPORTED_IMPORT_FORMAT",
                f"{Path(source).suffix!r} is not a format this release imports.",
                context={"supported_extensions": sorted(IMPORT_BY_EXTENSION)},
                remediation=[
                    "Use a supported extension, or open a native document with sw_doc_open.",
                ],
            )
        )

    app = ctx.session.app
    # LoadFile4 leaves the previously active document active when it fails, so the new
    # document has to be identified by difference. Reading ActiveDoc afterwards would
    # happily report the caller's own model as the import result.
    before_titles = {
        str(try_com_member(doc, "GetTitle", default="") or "")
        for doc in ctx.session.open_documents()
    }

    preferences = _apply_import_settings(app, args, fmt)
    try:
        errors = out_long(0)
        app.LoadFile4(source, "r", null_dispatch(), errors)
        error_code = int(getattr(errors, "value", errors) or 0)
    finally:
        preferences.restore()

    imported = None
    for doc in ctx.session.open_documents():
        title = str(try_com_member(doc, "GetTitle", default="") or "")
        if title not in before_titles:
            imported = doc
            break

    if imported is None:
        raise SwMcpError(
            make_error(
                "IMPORT_PRODUCED_NO_DOCUMENT",
                "solidworks",
                f"SOLIDWORKS did not open a document for {Path(source).name}.",
                context={"format": fmt, "load_error_code": error_code},
                remediation=[
                    "Check that the file is readable and not truncated.",
                    "Open it by hand in SOLIDWORKS to see the translator's own message.",
                ],
            )
        )

    diagnostics = _run_import_diagnostics(imported, args) if args.run_diagnostics else None
    geometry = _geometry_summary(imported)

    result_warnings: list[str] = []
    if error_code:
        result_warnings.append(
            f"SOLIDWORKS reported load error code {error_code}, but a document was "
            "opened; check the geometry counts below."
        )
    if geometry["body_count"] == 0:
        mesh_graphics = args.mesh_body_type == "graphics" and fmt in MESH_IMPORT_FORMATS
        result_warnings.append(
            "The import produced no body this server can measure. "
            + (
                "mesh_body_type='graphics' brings a mesh in as a picture; ask for "
                "'solid' or 'surface' to get geometry."
                if mesh_graphics
                else "The file may contain no solid or surface geometry."
            )
        )
    if geometry["solid_body_count"] == 0 and geometry["sheet_body_count"]:
        result_warnings.append(
            f"{geometry['sheet_body_count']} surface bodies arrived and no solid. "
            "A sheet body encloses no volume, so none is reported."
        )

    stat = Path(source).stat()
    return ImportResult(
        document=ctx.session.describe(imported).as_dict(),
        format=fmt,
        source_path=source,
        geometry_found=geometry["body_count"] > 0,
        settings=preferences.applied,
        diagnostics=diagnostics,
        warnings=result_warnings,
        artifacts=[
            ArtifactEvidence(
                path=source,
                exists=True,
                size_bytes=stat.st_size,
                modified_utc=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest()
                if stat.st_size <= 64 * 1024 * 1024
                else None,
            )
        ],
        **geometry,
    )
