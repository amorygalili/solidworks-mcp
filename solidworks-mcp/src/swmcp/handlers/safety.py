"""Safety domain: checkpoints, audit trail, error explanation, and path policy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, NonModelSideEffect, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import null_dispatch, out_long, try_com_member
from swmcp.context import OpContext
from swmcp.decode.hresult import HRESULT_TABLE, decode_hresult, format_hresult
from swmcp.decode.status import decode_status
from swmcp.envelope import ArtifactEvidence, Check, Verification
from swmcp.errors import SwMcpError, make_error
from swmcp.safety.audit import audit_path, read_recent
from swmcp.safety.overwrite import resolve_output_path
from swmcp.safety.paths import assert_output_path, normalize_cad_path
from swmcp.schemas.safety import (
    AuditTailArgs,
    AuditTailResult,
    CheckpointCreateArgs,
    CheckpointCreateResult,
    CheckpointListArgs,
    CheckpointListResult,
    CheckpointRestoreArgs,
    CheckpointRestoreResult,
    ExplainErrorArgs,
    ExplainErrorResult,
    PathPolicyArgs,
    PathPolicyResult,
)


def _save_as_copy(ctx: OpContext, doc: Any):
    """A saver that captures unsaved session state, unlike a plain file copy."""

    def saver(destination: str) -> bool:
        options = swconst.value("swSaveAsOptions_e", "swSaveAsOptions_Silent") | swconst.value(
            "swSaveAsOptions_e", "swSaveAsOptions_Copy"
        )
        errors, warnings = out_long(0), out_long(0)
        return bool(
            doc.Extension.SaveAs(
                destination,
                swconst.value("swSaveAsVersion_e", "swSaveAsCurrentVersion"),
                options,
                null_dispatch(),
                errors,
                warnings,
            )
        )

    _ = ctx
    return saver


@op(
    name="sw_checkpoint_create",
    tier="core",
    domains=("safety",),
    tags=("checkpoint", "snapshot", "backup"),
    summary=(
        "Snapshot a document so a later change can be rolled back. Prefers a SaveAs-Copy "
        "so unsaved session state is captured, and reports which method was used."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Writes a snapshot file into the document's .checkpoints directory. "
            "The model itself is not modified."
        ),
    ),
    satisfies=("SAFE-005",),
    precondition="any",
    idempotent=False,
    timeout_s=180.0,
)
def checkpoint_create(ctx: OpContext, args: CheckpointCreateArgs) -> CheckpointCreateResult:
    doc = ctx.require_doc()
    info = ctx.session.describe(doc)
    record = ctx.checkpoints.create(
        info.path,
        saver=_save_as_copy(ctx, doc) if info.checkpointable else None,
        force=args.force,
        tag=args.tag,
    )

    artifacts = []
    if record.checkpoint_path:
        path = Path(record.checkpoint_path)
        artifacts.append(
            ArtifactEvidence(
                path=str(path),
                exists=path.is_file(),
                size_bytes=path.stat().st_size if path.is_file() else 0,
                modified_utc=record.created_utc,
            )
        )

    warnings = list(info.warnings)
    if record.method == "skipped":
        warnings.append(f"No checkpoint was taken: {record.reason}")
    elif record.method == "file_copy":
        warnings.append(
            "This snapshot is a file copy of the last saved state; edits made since the "
            "last save are NOT captured."
        )

    return CheckpointCreateResult(
        checkpoint=record.model_dump(),
        document=info.as_dict(),
        artifacts=artifacts,
        warnings=warnings,
    )


@op(
    name="sw_checkpoint_list",
    tier="core",
    domains=("safety",),
    tags=("checkpoint", "history"),
    summary="List the snapshots available for a document, newest first, with sizes and times.",
    safety=ReadSafety(),
    satisfies=("SAFE-005",),
    precondition="any",
    idempotent=True,
)
def checkpoint_list(ctx: OpContext, args: CheckpointListArgs) -> CheckpointListResult:
    doc = ctx.require_doc()
    info = ctx.session.describe(doc)
    if not info.path:
        return CheckpointListResult(
            document=info.as_dict(),
            checkpoints=[],
            warnings=["This document has never been saved, so it has no checkpoints."],
        )

    found = ctx.checkpoints.list(info.path)[: args.limit]
    return CheckpointListResult(
        document=info.as_dict(),
        checkpoint_dir=str(ctx.checkpoints.checkpoint_dir(info.path)),
        checkpoints=[
            {
                "checkpoint_path": entry.checkpoint_path,
                "size_bytes": entry.size_bytes,
                "modified_utc": entry.modified_utc,
            }
            for entry in found
        ],
    )


@op(
    name="sw_checkpoint_restore",
    tier="core",
    domains=("safety",),
    tags=("checkpoint", "rollback", "undo"),
    summary=(
        "Restore a document from a checkpoint, overwriting its current contents. A "
        "snapshot of the present state is staged first, so restoring by mistake is "
        "itself reversible."
    ),
    safety=ModelMutation(destructive=True),
    satisfies=("SAFE-005", "SAFE-003"),
    precondition="none",
    idempotent=False,
    timeout_s=300.0,
)
def checkpoint_restore(ctx: OpContext, args: CheckpointRestoreArgs) -> CheckpointRestoreResult:
    checkpoint = normalize_cad_path(args.checkpoint_path)
    target = ctx.checkpoints.infer_target(checkpoint) if not args.target_path else Path(
        normalize_cad_path(args.target_path)
    )
    if target is None:
        raise SwMcpError(
            make_error(
                "RESTORE_TARGET_UNKNOWN",
                "validation",
                f"Could not infer which document {checkpoint!r} belongs to.",
                remediation=["Pass target_path explicitly."],
            )
        )

    before_size = target.stat().st_size if target.is_file() else 0

    open_doc = try_com_member(ctx.session.app, "GetOpenDocumentByName", str(target), default=None)
    if open_doc is not None:
        if not args.close_open_document:
            raise SwMcpError(
                make_error(
                    "DOCUMENT_OPEN",
                    "validation",
                    f"{str(target)!r} is open in SOLIDWORKS; restoring under it would be "
                    "undone the next time it is saved.",
                    remediation=["Re-send with close_open_document=true, or close it yourself."],
                )
            )
        title = str(try_com_member(open_doc, "GetTitle", default="") or "")
        if title:
            ctx.session.app.CloseDoc(title)

    outcome = ctx.checkpoints.restore(checkpoint, confirm=True, target_path=target)

    after_size = target.stat().st_size if target.is_file() else 0
    reopened = False
    if args.reopen:
        from swmcp.handlers.document import open_document_on_disk

        try:
            open_document_on_disk(ctx, str(target))
            reopened = True
        except SwMcpError as exc:
            ctx.warn(f"Restored, but reopening failed: {exc.envelope.code}")

    return CheckpointRestoreResult(
        restored_from=outcome["restored_from"],
        restored_to=outcome["restored_to"],
        pre_restore_checkpoint=outcome["pre_restore_checkpoint"] or None,
        pre_restore_method=outcome["pre_restore_method"],
        reopened=reopened,
        verification=Verification(
            read_back=True,
            before={"size_bytes": before_size},
            after={"size_bytes": after_size},
            checks=[
                Check(
                    name="target_exists",
                    passed=target.is_file(),
                    detail=str(target),
                ),
                Check(
                    name="contents_replaced",
                    passed=after_size == Path(checkpoint).stat().st_size,
                    detail=f"{before_size} -> {after_size} bytes",
                ),
                Check(
                    name="restore_is_reversible",
                    passed=bool(outcome["pre_restore_checkpoint"]),
                    detail=outcome["pre_restore_checkpoint"] or "no pre-restore snapshot staged",
                ),
            ],
        ),
    )


@op(
    name="sw_audit_tail",
    tier="extended",
    domains=("safety",),
    tags=("audit", "history", "log"),
    summary=(
        "Read the most recent entries from the append-only write audit, including the "
        "checkpoint each mutation was covered by."
    ),
    safety=ReadSafety(),
    satisfies=("SAFE-006",),
    precondition="none",
    idempotent=True,
    needs_session=False,
)
def audit_tail(ctx: OpContext, args: AuditTailArgs) -> AuditTailResult:
    entries = read_recent(args.limit * 4, config=ctx.config)
    if args.tool:
        entries = [e for e in entries if e.get("tool") == args.tool]
    if args.failures_only:
        entries = [e for e in entries if e.get("ok") is False]
    return AuditTailResult(
        audit_path=str(audit_path(ctx.config)),
        entries=entries[: args.limit],
    )


@op(
    name="sw_explain_error",
    tier="extended",
    domains=("safety", "discovery"),
    tags=("error", "hresult", "diagnostics"),
    summary=(
        "Explain an error code, an HRESULT, or a SOLIDWORKS status value, returning what "
        "it means and the concrete steps that address it."
    ),
    safety=ReadSafety(),
    satisfies=("SAFE-009",),
    precondition="none",
    idempotent=True,
    needs_session=False,
)
def explain_error(ctx: OpContext, args: ExplainErrorArgs) -> ExplainErrorResult:
    _ = ctx
    explanations: list[dict[str, Any]] = []

    if args.hresult is not None:
        info = decode_hresult(args.hresult)
        explanations.append(
            {
                "kind": "hresult",
                "hresult": format_hresult(args.hresult),
                "code": info.code if info else "COM_ERROR",
                "symbol": info.symbol if info else None,
                "message": info.message if info else "This HRESULT is not in the known table.",
                "remediation": list(info.remediation) if info else [],
            }
        )

    if args.code:
        matches = [
            {
                "kind": "hresult",
                "hresult": format_hresult(raw),
                "code": info.code,
                "symbol": info.symbol,
                "message": info.message,
                "remediation": list(info.remediation),
            }
            for raw, info in HRESULT_TABLE.items()
            if info.code == args.code
        ]
        explanations.extend(matches)
        if not matches:
            explanations.append(
                {
                    "kind": "code",
                    "code": args.code,
                    "message": (
                        f"{args.code} is not an HRESULT-derived code. It is raised by the "
                        "server's own validation, policy, or reference layers; the error "
                        "envelope that produced it carries its remediation."
                    ),
                    "remediation": [],
                }
            )

    if args.sw_enum:
        decoded = decode_status(args.sw_enum, args.sw_value or 0)
        explanations.append(
            {
                "kind": "solidworks_status",
                "enum": decoded.enum,
                "value": decoded.value,
                "names": decoded.names,
                "unmatched_bits": decoded.unmatched_bits,
                "message": decoded.summary,
                "remediation": decoded.remediation,
            }
        )

    if not explanations:
        explanations.append(
            {
                "kind": "usage",
                "message": "Provide at least one of: code, hresult, or sw_enum with sw_value.",
                "known_codes": sorted({info.code for info in HRESULT_TABLE.values()}),
            }
        )

    return ExplainErrorResult(explanations=explanations)


@op(
    name="sw_path_policy",
    tier="extended",
    domains=("safety",),
    tags=("path", "policy", "overwrite"),
    summary=(
        "Check a path against the output-root policy and the overwrite rules before "
        "using it, returning the normalized path and the non-clobbering name that "
        "would actually be written."
    ),
    safety=ReadSafety(),
    satisfies=("SAFE-004", "SAFE-008"),
    precondition="none",
    idempotent=True,
    needs_session=False,
)
def path_policy(ctx: OpContext, args: PathPolicyArgs) -> PathPolicyResult:
    roots = [str(root) for root in ctx.config.allowed_roots]
    normalized = normalize_cad_path(args.path)
    exists = Path(normalized).exists()

    if args.intent == "document_input":
        return PathPolicyResult(
            normalized=normalized,
            intent=args.intent,
            allowed=True,
            exists=exists,
            allowed_roots=roots,
            remediation=[],
        )

    try:
        assert_output_path(args.path, ctx.config.allowed_roots)
    except SwMcpError as exc:
        return PathPolicyResult(
            normalized=normalized,
            intent=args.intent,
            allowed=False,
            reason=exc.envelope.message,
            exists=exists,
            allowed_roots=roots,
            remediation=list(exc.envelope.remediation),
        )

    try:
        resolved, action = resolve_output_path(normalized, args.overwrite)
        reason = None
        remediation: list[str] = []
    except SwMcpError as exc:
        resolved = exc.envelope.context.get("proposed_path")
        action = "refused"
        reason = exc.envelope.message
        remediation = list(exc.envelope.remediation)

    return PathPolicyResult(
        normalized=normalized,
        intent=args.intent,
        allowed=True,
        reason=reason,
        exists=exists,
        resolved_write_path=resolved,
        action=action,
        allowed_roots=roots,
        remediation=remediation,
    )
