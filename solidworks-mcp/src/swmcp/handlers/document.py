"""Document domain: create, open, list, activate, save, close, rebuild, undo."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, NonModelSideEffect, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import (
    call_with_outparams,
    get_com_member,
    null_dispatch,
    out_long,
    try_com_member,
)
from swmcp.context import OpContext
from swmcp.decode.status import decode_open, decode_save
from swmcp.envelope import ArtifactEvidence, Check, Verification
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.safety.overwrite import resolve_output_path
from swmcp.safety.paths import assert_output_path, normalize_cad_path
from swmcp.schemas.document import (
    DocActivateArgs,
    DocActivateResult,
    DocCloseArgs,
    DocCloseResult,
    DocListArgs,
    DocListResult,
    DocNewArgs,
    DocNewResult,
    DocOpenArgs,
    DocOpenResult,
    DocRebuildArgs,
    DocRebuildResult,
    DocSaveArgs,
    DocSaveResult,
    DocUndoArgs,
    DocUndoResult,
)

#: swUserPreferenceStringValue_e members for the default template of each type.
_TEMPLATE_PREFERENCE = {
    "part": "swDefaultTemplatePart",
    "assembly": "swDefaultTemplateAssembly",
    "drawing": "swDefaultTemplateDrawing",
}

_DOC_TYPE_CONST = {
    "part": "swDocPART",
    "assembly": "swDocASSEMBLY",
    "drawing": "swDocDRAWING",
}

_EXTENSION_TO_TYPE = {
    ".sldprt": "part",
    ".prtdot": "part",
    ".sldasm": "assembly",
    ".asmdot": "assembly",
    ".slddrw": "drawing",
    ".drwdot": "drawing",
}


def _doc_type_code(kind: str) -> int:
    return swconst.value("swDocumentTypes_e", _DOC_TYPE_CONST[kind])


def _type_from_extension(path: str) -> int:
    kind = _EXTENSION_TO_TYPE.get(Path(path).suffix.lower())
    if kind is None:
        raise SwMcpError(
            validation_error(
                "UNSUPPORTED_DOCUMENT_TYPE",
                f"{Path(path).suffix!r} is not a SOLIDWORKS document extension.",
                context={"supported": sorted(_EXTENSION_TO_TYPE)},
            )
        )
    return _doc_type_code(kind)


def _evidence(path: str | Path, *, digest: bool = True) -> ArtifactEvidence:
    target = Path(path)
    if not target.is_file():
        return ArtifactEvidence(path=str(target), exists=False, size_bytes=0)
    stat = target.stat()
    sha = None
    if digest and stat.st_size <= 64 * 1024 * 1024:
        sha = hashlib.sha256(target.read_bytes()).hexdigest()
    return ArtifactEvidence(
        path=str(target),
        exists=True,
        size_bytes=stat.st_size,
        modified_utc=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        sha256=sha,
    )


def open_document_on_disk(
    ctx: OpContext,
    path: str,
    *,
    open_read_only: bool = False,
    silent: bool = True,
    configuration: str = "",
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Open a document, decoding the load errors and warnings SOLIDWORKS reports."""
    normalized = normalize_cad_path(path)
    if not Path(normalized).is_file():
        raise SwMcpError(
            make_error(
                "FILE_NOT_FOUND",
                "validation",
                f"There is no file at {normalized!r}.",
                context={"path": normalized},
                remediation=[
                    "Check the path, or list open documents to address one already loaded.",
                ],
            )
        )

    options = 0
    if silent:
        options |= swconst.value("swOpenDocOptions_e", "swOpenDocOptions_Silent")
    if open_read_only:
        options |= swconst.value("swOpenDocOptions_e", "swOpenDocOptions_ReadOnly")

    errors, warnings = out_long(0), out_long(0)
    doc, outs = call_with_outparams(
        ctx.session.app.OpenDoc6,
        normalized,
        _type_from_extension(normalized),
        options,
        configuration,
        errors,
        warnings,
        outparams=(errors, warnings),
    )
    error_decode, warning_decode = decode_open(outs[0], outs[1])

    if doc is None:
        raise SwMcpError(
            make_error(
                "DOCUMENT_OPEN_FAILED",
                "solidworks",
                f"SOLIDWORKS could not open {normalized!r}: {error_decode.summary}.",
                sw_error_code=error_decode.value,
                sw_error_name=", ".join(error_decode.names) or None,
                context={"path": normalized, "warnings": warning_decode.names},
                remediation=error_decode.remediation
                or ["Open the file manually in SOLIDWORKS to see the underlying problem."],
            )
        )

    return (
        doc,
        {
            "value": error_decode.value,
            "names": error_decode.names,
            "summary": error_decode.summary,
        },
        {
            "value": warning_decode.value,
            "names": warning_decode.names,
            "summary": warning_decode.summary,
        },
    )


@op(
    name="sw_doc_new",
    tier="core",
    domains=("document",),
    tags=("new", "create", "template"),
    summary=(
        "Create a part, assembly, or drawing from an explicit template or the "
        "SOLIDWORKS default for that type. Reports which template was actually used."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Creates a document in the SOLIDWORKS session and changes what is on screen. "
            "Nothing reaches disk until it is saved."
        ),
    ),
    satisfies=("DOC-001",),
    precondition="none",
    idempotent=False,
    timeout_s=180.0,
)
def doc_new(ctx: OpContext, args: DocNewArgs) -> DocNewResult:
    if args.template_path:
        template = normalize_cad_path(args.template_path)
        source = "explicit"
        if not Path(template).is_file():
            raise SwMcpError(
                validation_error(
                    "TEMPLATE_NOT_FOUND",
                    f"No template at {template!r}.",
                    remediation=["Omit template_path to use the SOLIDWORKS default."],
                )
            )
    else:
        preference = swconst.value(
            "swUserPreferenceStringValue_e", _TEMPLATE_PREFERENCE[args.doc_type]
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
                    f"SOLIDWORKS reports no usable default {args.doc_type} template "
                    f"(got {template!r}).",
                    context={"template_dirs": list(ctx.session.install().template_dirs)},
                    remediation=[
                        "Pass template_path explicitly.",
                        # Not File Locations, which is the directory list: populating
                        # that does not set this preference. The page that does names
                        # three specific files, which is why this can be empty on an
                        # install whose template directory is perfectly well configured.
                        "Or set it in Tools > Options > System Options > "
                        "Default Templates.",
                    ],
                )
            )

    doc = ctx.session.app.NewDocument(template, 0, 0.0, 0.0)
    if doc is None:
        raise SwMcpError(
            make_error(
                "DOCUMENT_CREATE_FAILED",
                "solidworks",
                f"SOLIDWORKS refused to create a document from {template!r}.",
                remediation=["Confirm the template matches the requested document type."],
            )
        )

    if args.activate:
        title = str(try_com_member(doc, "GetTitle", default="") or "")
        if title:
            errors = out_long(0)
            call_with_outparams(
                ctx.session.app.ActivateDoc3, title, False, 0, errors, outparams=(errors,)
            )

    return DocNewResult(
        document=ctx.session.describe(doc).as_dict(),
        template_used=template,
        template_source=source,
    )


@op(
    name="sw_doc_open",
    tier="core",
    domains=("document",),
    tags=("open", "load"),
    summary=(
        "Open a SOLIDWORKS document from disk, decoding the load errors and warnings "
        "into names and remediation rather than returning raw status integers."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Loads a document into the session, which can build an import feature tree "
            "and take a write lock on the file. The source file is not modified."
        ),
    ),
    satisfies=("DOC-002",),
    precondition="none",
    idempotent=True,
    timeout_s=300.0,
)
def doc_open(ctx: OpContext, args: DocOpenArgs) -> DocOpenResult:
    doc, errors, warnings = open_document_on_disk(
        ctx,
        args.path,
        open_read_only=args.open_read_only,
        silent=args.silent,
        configuration=args.configuration,
    )
    info = ctx.session.describe(doc)
    return DocOpenResult(
        document=info.as_dict(),
        load_errors=errors,
        load_warnings=warnings,
        artifacts=[_evidence(info.path, digest=False)] if info.path else [],
        warnings=(
            [f"SOLIDWORKS reported: {warnings['summary']}"] if warnings["names"] else []
        ),
    )


@op(
    name="sw_doc_list",
    tier="core",
    domains=("document",),
    tags=("list", "inspect", "session"),
    summary=(
        "List every open document with its type, path, saved and dirty state, active "
        "configuration, and whether it can be checkpointed."
    ),
    safety=ReadSafety(),
    satisfies=("DOC-003",),
    precondition="none",
    idempotent=True,
)
def doc_list(ctx: OpContext, args: DocListArgs) -> DocListResult:
    _ = args
    documents = [ctx.session.describe(doc).as_dict() for doc in ctx.session.open_documents()]
    active = ctx.session.active_doc()
    return DocListResult(
        active=ctx.session.describe(active).as_dict() if active is not None else None,
        documents=documents,
    )


@op(
    name="sw_doc_activate",
    tier="core",
    domains=("document",),
    tags=("activate", "focus"),
    summary=(
        "Make an open document the active one, addressed by path or title. An ambiguous "
        "title is refused rather than resolved arbitrarily."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale="Changes which document is active in the SOLIDWORKS user interface.",
    ),
    satisfies=("DOC-004",),
    precondition="any",
    idempotent=True,
    timeout_s=120.0,
)
def doc_activate(ctx: OpContext, args: DocActivateArgs) -> DocActivateResult:
    _ = args
    doc = ctx.require_doc()
    previous = ctx.session.active_doc()
    previous_title = (
        str(try_com_member(previous, "GetTitle", default="") or "")
        if previous is not None
        else None
    )

    title = str(try_com_member(doc, "GetTitle", default="") or "")
    errors = out_long(0)
    call_with_outparams(ctx.session.app.ActivateDoc3, title, False, 0, errors, outparams=(errors,))

    active = ctx.session.active_doc()
    info = ctx.session.describe(active) if active is not None else ctx.session.describe(doc)
    return DocActivateResult(document=info.as_dict(), previously_active=previous_title)


@op(
    name="sw_doc_save",
    tier="core",
    domains=("document",),
    tags=("save", "saveas", "export"),
    summary=(
        "Save a document in place or to a new path, applying the overwrite policy so an "
        "existing deliverable is never replaced silently, and verifying the file on disk."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Writes a CAD file to disk. The default 'version' overwrite policy never "
            "replaces an existing file, so the write is additive; replacing one requires "
            "overwrite='allow' plus confirm=true, gated inside the handler."
        ),
    ),
    satisfies=("DOC-005", "SAFE-008"),
    precondition="any",
    idempotent=False,
    timeout_s=300.0,
)
def doc_save(ctx: OpContext, args: DocSaveArgs) -> DocSaveResult:
    doc = ctx.require_doc()
    info = ctx.session.describe(doc)

    if args.overwrite == "allow" and not args.confirm:
        raise SwMcpError(
            make_error(
                "CONFIRM_REQUIRED",
                "policy",
                "overwrite='allow' replaces an existing file, which needs confirmation.",
                context={"tool": "sw_doc_save", "overwrite": args.overwrite},
                remediation=[
                    "Re-send with confirm=true to replace the file deliberately.",
                    "Or use the default overwrite='version', which writes a new name instead.",
                ],
            )
        )

    if args.output_path:
        checked = assert_output_path(args.output_path, ctx.config.allowed_roots)
        target, action = resolve_output_path(checked, args.overwrite)
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    elif info.path:
        target, action = info.path, "overwrite"
    else:
        raise SwMcpError(
            validation_error(
                "OUTPUT_PATH_REQUIRED",
                "This document has never been saved, so an output path is required.",
                remediation=["Pass output_path pointing inside an allowed output root."],
            )
        )

    options = swconst.value("swSaveAsOptions_e", "swSaveAsOptions_Silent")
    if args.save_as_copy:
        options |= swconst.value("swSaveAsOptions_e", "swSaveAsOptions_Copy")

    errors, warnings = out_long(0), out_long(0)
    call_with_outparams(
        doc.Extension.SaveAs,
        target,
        swconst.value("swSaveAsVersion_e", "swSaveAsCurrentVersion"),
        options,
        # Python None is rejected by the marshaller for an optional IDispatch argument.
        null_dispatch(),
        errors,
        warnings,
        outparams=(errors, warnings),
    )
    error_decode, warning_decode = decode_save(errors.value, warnings.value)

    evidence = _evidence(target)
    if not evidence.exists:
        raise SwMcpError(
            make_error(
                "SAVE_FAILED",
                "solidworks",
                f"SOLIDWORKS reported {error_decode.summary} and no file exists at {target!r}.",
                sw_error_code=error_decode.value,
                sw_error_name=", ".join(error_decode.names) or None,
                remediation=error_decode.remediation
                or ["Check disk space, permissions, and whether the file is open elsewhere."],
            )
        )

    return DocSaveResult(
        document=ctx.session.describe(doc).as_dict(),
        saved_path=target,
        action=action,
        save_errors={
            "value": error_decode.value,
            "names": error_decode.names,
            "summary": error_decode.summary,
        },
        save_warnings={
            "value": warning_decode.value,
            "names": warning_decode.names,
            "summary": warning_decode.summary,
        },
        artifacts=[evidence],
        warnings=(
            [
                f"Saved to {target} rather than the requested path, "
                "to avoid overwriting an existing file."
            ]
            if action == "versioned"
            else []
        ),
    )


@op(
    name="sw_doc_close",
    tier="core",
    domains=("document",),
    tags=("close", "unload"),
    summary=(
        "Close an open document. The handling of unsaved changes must be stated "
        "explicitly, because closing a dirty document silently would discard work."
    ),
    safety=ModelMutation(destructive=True),
    satisfies=("DOC-005",),
    precondition="any",
    idempotent=False,
    timeout_s=180.0,
)
def doc_close(ctx: OpContext, args: DocCloseArgs) -> DocCloseResult:
    doc = ctx.require_doc()
    info = ctx.session.describe(doc)
    saved_before = False

    if info.is_dirty:
        if args.save_first == "error_if_dirty":
            raise SwMcpError(
                make_error(
                    "DOCUMENT_DIRTY",
                    "policy",
                    f"{info.title!r} has unsaved changes and save_first is 'error_if_dirty'.",
                    context={"document": info.as_dict()},
                    remediation=[
                        "Re-send with save_first='require' to save, "
                        "or save_first='discard' to throw the changes away.",
                    ],
                )
            )
        if args.save_first == "require":
            if not info.path:
                raise SwMcpError(
                    validation_error(
                        "OUTPUT_PATH_REQUIRED",
                        f"{info.title!r} has never been saved, so save_first='require' "
                        "cannot save it.",
                        remediation=[
                        "Save it with an output path first, or use save_first='discard'.",
                    ],
                    )
                )
            errors, warnings = out_long(0), out_long(0)
            call_with_outparams(doc.Save3, 1, errors, warnings, outparams=(errors, warnings))
            saved_before = True

    open_before = len(ctx.session.open_documents())
    ctx.session.app.CloseDoc(info.title)
    open_after = len(ctx.session.open_documents())
    still_open = try_com_member(
        ctx.session.app, "GetOpenDocumentByName", info.path or info.title, default=None
    )

    return DocCloseResult(
        closed_title=info.title,
        closed_path=info.path,
        saved_before_close=saved_before,
        verification=Verification(
            read_back=True,
            before={"open_documents": open_before, "was_dirty": info.is_dirty},
            after={"open_documents": open_after},
            checks=[
                Check(
                    name="document_closed",
                    passed=still_open is None,
                    detail=f"{info.title} is no longer addressable"
                    if still_open is None
                    else "the document is still open",
                ),
                Check(
                    name="open_count_decreased",
                    passed=open_after < open_before,
                    detail=f"{open_before} -> {open_after}",
                ),
            ],
        ),
    )


@op(
    name="sw_doc_rebuild",
    tier="core",
    domains=("document",),
    tags=("rebuild", "regenerate", "errors"),
    summary=(
        "Rebuild the document and report which features ended up in error or warning, "
        "so a rebuild that 'succeeded' with a broken tree is not mistaken for success."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("DOC-006",),
    precondition="any",
    idempotent=True,
    timeout_s=600.0,
)
def doc_rebuild(ctx: OpContext, args: DocRebuildArgs) -> DocRebuildResult:
    doc = ctx.require_doc()
    before = _feature_health(doc)

    # Both are property-or-method members depending on binding; use the shim.
    if args.force:
        succeeded = bool(get_com_member(doc, "ForceRebuild3", args.top_level_only))
    else:
        succeeded = bool(get_com_member(doc, "EditRebuild3"))

    after = _feature_health(doc)
    return DocRebuildResult(
        document=ctx.session.describe(doc).as_dict(),
        succeeded=succeeded,
        feature_errors=after["errors"],
        feature_warnings=after["warnings"],
        rebuild_errors=[entry["name"] for entry in after["errors"]],
        verification=Verification(
            read_back=True,
            before={"error_count": len(before["errors"]), "warning_count": len(before["warnings"])},
            after={"error_count": len(after["errors"]), "warning_count": len(after["warnings"])},
            checks=[
                Check(
                    name="rebuild_reported_success",
                    passed=succeeded,
                    detail=(
                        "SOLIDWORKS returned success"
                        if succeeded
                        else "SOLIDWORKS returned failure"
                    ),
                ),
                Check(
                    name="no_feature_errors",
                    passed=not after["errors"],
                    detail=", ".join(e["name"] for e in after["errors"]) or "no features in error",
                ),
            ],
        ),
        warnings=(
            [f"{len(after['errors'])} feature(s) are in error after the rebuild."]
            if after["errors"]
            else []
        ),
    )


def _feature_health(doc: Any) -> dict[str, list[dict[str, Any]]]:
    """Walk the tree once, collecting features that are not healthy.

    ``IFeature.GetErrorCode2`` returns a ``swFeatureError_e`` value where zero means no
    error; there is no separate warning tier on this API, so suppressed features are
    reported separately rather than invented as warnings.
    """
    errors: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []

    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        code = try_com_member(feature, "GetErrorCode2", default=0)
        name = str(try_com_member(feature, "Name", default="") or "")
        entry = {
            "name": name,
            "type": str(try_com_member(feature, "GetTypeName2", default="") or ""),
            "error_code": code,
            "error_name": swconst.name_of("swFeatureError_e", code) if code else None,
        }
        if isinstance(code, int) and code != 0:
            errors.append(entry)
        if try_com_member(feature, "IsSuppressed", default=False):
            suppressed.append(entry)
        feature = try_com_member(feature, "GetNextFeature", default=None)

    return {"errors": errors, "warnings": suppressed}


@op(
    name="sw_doc_undo",
    tier="extended",
    domains=("document",),
    tags=("undo", "history"),
    summary=(
        "Undo the last operations in SOLIDWORKS. Native undo is opportunistic and does "
        "not report what it reverted, so checkpoints remain the reliable way back."
    ),
    safety=ModelMutation(destructive=True),
    satisfies=("DOC-007",),
    precondition="any",
    idempotent=False,
    timeout_s=180.0,
)
def doc_undo(ctx: OpContext, args: DocUndoArgs) -> DocUndoResult:
    doc = ctx.require_doc()
    before = _feature_count(doc)

    for _ in range(args.steps):
        try_com_member(doc, "EditUndo2", 1, default=None)

    after = _feature_count(doc)
    return DocUndoResult(
        document=ctx.session.describe(doc).as_dict(),
        steps_requested=args.steps,
        verification=Verification(
            read_back=True,
            before={"feature_count": before},
            after={"feature_count": after},
            checks=[
                Check(
                    name="model_state_read_back",
                    passed=True,
                    detail=f"feature count {before} -> {after}",
                ),
                Check(
                    name="undo_had_an_effect",
                    passed=after != before,
                    detail=(
                        "the feature count changed"
                        if after != before
                        else "the feature count is unchanged; the undo may have reverted "
                        "a non-structural edit, or there was nothing to undo"
                    ),
                ),
            ],
        ),
    )


def _feature_count(doc: Any) -> int:
    count = 0
    feature = try_com_member(doc, "FirstFeature", default=None)
    while feature is not None and count < 5000:
        count += 1
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return count
