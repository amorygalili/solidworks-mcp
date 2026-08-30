"""Batch export with a manifest (IO-004).

This handler writes no files itself. Every output goes through ``sw_export`` or
``sw_drawing_export`` — the same preference handling, the same overwrite policy, the
same signature verification — because a batch that grew its own copy of ``SaveAs``
would be a second exporter to keep honest, and the second one always rots first.

What is genuinely new here is the *accounting*. A loop reports whichever call failed
last; a batch has to report what it was asked for, what it wrote, what it did not write
and why, and what it never attempted. Those are three different outcomes and the result
keeps them apart: ``failed`` means it was tried, ``skipped`` means nothing is known.

The record is written to disk as well as returned, because a batch that runs for twenty
minutes and then exceeds a response limit has still done twenty minutes of work.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import NonModelSideEffect
from swmcp.com.install import process_resources
from swmcp.com.marshal import try_com_member
from swmcp.context import OpContext
from swmcp.envelope import file_evidence
from swmcp.errors import ErrorEnvelope, SwMcpError, make_error, validation_error
from swmcp.handlers.document import open_document_on_disk
from swmcp.handlers.drawing import drawing_export
from swmcp.handlers.exchange import export
from swmcp.safety.overwrite import resolve_output_path
from swmcp.safety.paths import assert_output_path, prepare_document_path
from swmcp.schemas.batch import (
    BatchExportArgs,
    BatchExportEntry,
    BatchExportItem,
    BatchExportResult,
    BatchStatus,
)
from swmcp.schemas.drawing import DrawingExportArgs
from swmcp.schemas.exchange import (
    DRAWING_EXPORT_FORMATS,
    EXTENSION_FOR_FORMAT,
    ExportArgs,
)

#: The manifest's own shape, versioned. A consumer reading these files across releases
#: needs to know when the shape changed, and a filename never tells it.
MANIFEST_SCHEMA = "swmcp.batch_export/1"

DEFAULT_MANIFEST_NAME = "batch_manifest.json"

#: Extensions SOLIDWORKS gives its own documents, stripped from a window title when the
#: title is all there is to name an output after.
_NATIVE_SUFFIXES = frozenset({".sldprt", ".sldasm", ".slddrw"})

#: Characters Windows refuses in a filename. Configuration names routinely contain them.
_ILLEGAL_IN_FILENAME = '<>:"/\\|?*'


# --- the plan -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Unit:
    """One planned output: a document, a configuration, and a format."""

    index: int
    item_index: int
    configuration: str | None
    format: str


def _plan(items: list[BatchExportItem]) -> list[_Unit]:
    """Enumerate every requested output before anything runs.

    Doing this first is what lets a batch that stops halfway still account for the
    outputs it never reached, rather than simply ending.
    """
    units: list[_Unit] = []
    for item_index, item in enumerate(items):
        configurations: list[str | None] = list(item.configurations or []) or [None]
        for configuration in configurations:
            for fmt in item.formats:
                units.append(
                    _Unit(
                        index=len(units),
                        item_index=item_index,
                        configuration=configuration,
                        format=fmt,
                    )
                )
    return units


# --- naming -------------------------------------------------------------------


def _source_label(item: BatchExportItem) -> str:
    return item.source_path or item.title or "active document"


def _document_stem(info: Any) -> str:
    """What to name this document's outputs.

    A saved document is named after its file. One that has never been saved has only a
    window title, which SOLIDWORKS spells with the native extension attached — using it
    verbatim would produce ``Part1.SLDPRT.step``.
    """
    if info.path:
        return Path(info.path).stem
    title = str(info.title or "export")
    return Path(title).stem if Path(title).suffix.lower() in _NATIVE_SUFFIXES else title


def _sanitize(text: str) -> str:
    """Make a configuration name usable as part of a filename.

    ``1/2 scale`` and ``Rev: B`` are ordinary configuration names and both are illegal
    on Windows. Replacing rather than refusing is right here: the caller asked for a
    configuration, not for a filename, and the manifest records which configuration each
    file actually came from.
    """
    cleaned = "".join(
        "_" if character in _ILLEGAL_IN_FILENAME or ord(character) < 32 else character
        for character in text
    )
    return cleaned.strip(" .") or "configuration"


def _output_path(directory: Path, stem: str, configuration: str | None, fmt: str) -> Path:
    suffix = f"__{_sanitize(configuration)}" if configuration else ""
    return directory / f"{stem}{suffix}{EXTENSION_FOR_FORMAT[fmt]}"


def _name_on_disk(requested: Path) -> Path:
    """The name the file actually has, which is not always the name that was asked for.

    SOLIDWORKS writes an STL as ``.STL`` whatever case the path was given in. Windows
    resolves both spellings, so nothing fails locally and ``sw_export`` reasonably
    reports back the path its caller asked for — but a manifest is a portable claim,
    read on machines and filesystems that are not this one, and a manifest naming a file
    that is not there is worse than no manifest. So the batch records what is on disk.
    """
    try:
        siblings = list(requested.parent.iterdir())
    except OSError:  # pragma: no cover - the file was just written into this directory
        return requested
    names = {sibling.name for sibling in siblings}
    if requested.name in names:
        return requested
    folded = requested.name.casefold()
    return next((s for s in siblings if s.name.casefold() == folded), requested)


# --- outcomes -----------------------------------------------------------------


def _error_dict(exc: Exception) -> dict[str, Any]:
    """One entry's failure, as an envelope rather than a string.

    A batch is exactly where "it didn't work" is useless: the caller needs to know which
    of thirty outputs failed and whether the cause was the same each time.
    """
    if isinstance(exc, SwMcpError):
        return exc.envelope.model_dump(exclude_none=True)
    return ErrorEnvelope(
        code="UNEXPECTED_EXPORT_FAILURE",
        category="com",
        message=f"{type(exc).__name__}: {exc}",
        remediation=[
            "Open the document by hand and try the same export from the SOLIDWORKS UI "
            "to see what it reports.",
        ],
    ).model_dump(exclude_none=True)


def strain_stop_reason(resources: dict[str, Any] | None) -> str | None:
    """Why the batch should stop between items, or ``None`` to keep going.

    This keys off ``critical``, not ``strained``. They are different claims and using
    the wrong one is a real bug: ``strained`` is the advisory "worth watching" reading
    that ``sw_health`` reports, and a session past it is slower but entirely usable —
    keying a stop to it made every batch on a well-used machine give up after one item.
    ``critical`` is the measured wall, past which calls do not fail but *hang*, and a
    hung batch loses the manifest for everything already written.

    A pure function of what :func:`process_resources` reports, so it is testable without
    a SOLIDWORKS session.
    """
    if not resources or not resources.get("critical"):
        return None
    return (
        f"SOLIDWORKS has reached {resources.get('private_mb')} MB of private bytes, "
        f"past the point where calls stop returning rather than failing, so the "
        f"remaining outputs were not attempted. Restart SOLIDWORKS and re-run; the "
        f"manifest lists what was already written."
    )


def _entry(
    unit: _Unit,
    source: str,
    status: BatchStatus,
    *,
    document_type: str | None = None,
    sheets: list[str] | None = None,
    error: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> BatchExportEntry:
    return BatchExportEntry(
        index=unit.index,
        item_index=unit.item_index,
        source=source,
        document_type=document_type,
        format=unit.format,
        configuration=unit.configuration,
        sheets=list(sheets or []),
        status=status,
        error=error,
        warnings=list(warnings or []),
    )


# --- running one item ---------------------------------------------------------


@dataclass(slots=True)
class _Job:
    """What does not change between items."""

    ctx: OpContext
    args: BatchExportArgs
    directory: Path


@dataclass(slots=True)
class _Target:
    """One item's resolved document."""

    item: BatchExportItem
    doc: Any
    doc_type: str
    stem: str
    source: str


@dataclass(slots=True)
class _ItemOutcome:
    """Everything one item contributed to the run."""

    entries: list[BatchExportEntry] = field(default_factory=list)
    opened: str | None = None
    closed: str | None = None
    left_open: str | None = None
    stop_reason: str | None = None


def _resolve_item_document(ctx: OpContext, item: BatchExportItem) -> tuple[Any, bool]:
    """The document for one item, and whether this call opened it.

    A file named by path is opened *read-only* when it is not already loaded. That is
    what makes closing it afterwards safe: an export changes nothing, but activating a
    configuration marks a document dirty, and closing a dirty document the caller could
    have saved would be discarding work. Read-only removes the question.
    """
    if item.source_path:
        normalized = prepare_document_path(item.source_path)
        already_open = try_com_member(
            ctx.session.app, "GetOpenDocumentByName", normalized, default=None
        )
        if already_open is not None:
            return already_open, False
        doc, _errors, _warnings = open_document_on_disk(
            ctx, normalized, open_read_only=True, silent=True
        )
        return doc, True

    if item.title:
        return ctx.session.resolve_doc(title=item.title), False

    doc = ctx.session.active_doc()
    if doc is None:
        raise SwMcpError(
            make_error(
                "NO_ACTIVE_DOCUMENT",
                "validation",
                "This item names neither source_path nor title, and no document is active.",
                remediation=[
                    "Give the item a source_path, or activate the document to export.",
                ],
            )
        )
    return doc, False


def _routing_error(target: _Target, unit: _Unit) -> ErrorEnvelope | None:
    """Why this format cannot come from this document, or ``None`` if it can.

    Checked before the export rather than reported from inside it, so a batch that mixes
    parts and drawings names the mismatch instead of failing somewhere in ``SaveAs``.
    """
    wants_drawing = unit.format in DRAWING_EXPORT_FORMATS
    if target.doc_type == "drawing" and not wants_drawing:
        return validation_error(
            "WRONG_FORMAT_FOR_DOCUMENT",
            f"{unit.format!r} needs a part or an assembly, and this is a drawing.",
            context={"drawing_formats": sorted(DRAWING_EXPORT_FORMATS)},
            remediation=["Ask a drawing for PDF, DXF, or DWG."],
        )
    if target.doc_type != "drawing" and wants_drawing:
        # SOLIDWORKS can save a part straight to PDF, but per-sheet selection and the
        # drawing review counts cannot exist without a drawing, so a batch routes these
        # formats by document type rather than guessing which was meant.
        return validation_error(
            "WRONG_FORMAT_FOR_DOCUMENT",
            f"{unit.format!r} is exported from a drawing, and this is a "
            f"{target.doc_type}.",
            context={"drawing_formats": sorted(DRAWING_EXPORT_FORMATS)},
            remediation=[
                "Make a drawing of this model and add it to the batch, or ask for a "
                "neutral format such as step.",
            ],
        )
    if target.doc_type == "drawing" and unit.configuration is not None:
        return validation_error(
            "CONFIGURATIONS_NEED_A_MODEL",
            "A drawing has no configurations of its own; its views reference the "
            "model's.",
            remediation=["Drop configurations from this item, or list the model instead."],
        )
    return None


def _run_unit(job: _Job, target: _Target, unit: _Unit) -> BatchExportEntry:
    """Write one file, and describe what happened either way."""
    started = time.perf_counter()
    sheets = list(target.item.sheets or [])

    def finish(entry: BatchExportEntry, **update: Any) -> BatchExportEntry:
        return entry.model_copy(
            update={"duration_s": round(time.perf_counter() - started, 3), **update}
        )

    refusal = _routing_error(target, unit)
    if refusal is not None:
        return finish(
            _entry(
                unit,
                target.source,
                "failed",
                document_type=target.doc_type,
                sheets=sheets,
                error=refusal.model_dump(exclude_none=True),
            )
        )

    output = _output_path(job.directory, target.stem, unit.configuration, unit.format)
    warnings: list[str] = []
    if sheets and target.doc_type != "drawing":
        warnings.append(
            f"sheets was given for a {target.doc_type}, which has none, so it was ignored."
        )

    sub_ctx = replace(job.ctx, doc=target.doc, warnings=[])
    try:
        if target.doc_type == "drawing":
            result: Any = drawing_export(
                sub_ctx,
                DrawingExportArgs(
                    output_path=str(output),
                    sheets=sheets or None,
                    overwrite=job.args.overwrite,
                ),
            )
        else:
            result = export(
                sub_ctx,
                ExportArgs(
                    output_path=str(output),
                    overwrite=job.args.overwrite,
                    configuration=unit.configuration,
                    stl_quality=job.args.stl_quality,
                    stl_binary=job.args.stl_binary,
                    mesh_unit=job.args.mesh_unit,
                    step_protocol=job.args.step_protocol,
                ),
            )
    except Exception as exc:  # one bad output must not cost the manifest for the rest
        return finish(
            _entry(
                unit,
                target.source,
                "failed",
                document_type=target.doc_type,
                sheets=sheets,
                error=_error_dict(exc),
                warnings=warnings,
            ),
            requested_path=str(output),
        )

    on_disk = _name_on_disk(Path(result.saved_path))
    if on_disk.name != Path(result.saved_path).name:
        warnings.append(
            f"SOLIDWORKS wrote {on_disk.name} rather than {Path(result.saved_path).name}; "
            "the manifest records the name on disk."
        )
    evidence = file_evidence(on_disk)
    return finish(
        _entry(
            unit,
            target.source,
            "written",
            document_type=target.doc_type,
            sheets=sheets,
            warnings=warnings + list(result.warnings),
        ),
        requested_path=str(output),
        saved_path=str(on_disk),
        overwrite_action=result.overwrite_action,
        size_bytes=evidence.size_bytes,
        sha256=evidence.sha256,
        signature_verified=result.signature_verified,
        signature_detail=result.signature_detail,
    )


def _close_if_opened(ctx: OpContext, doc: Any) -> tuple[str | None, str | None]:
    """Close a document this call opened. Returns ``(closed, left_open_with_reason)``."""
    info = ctx.session.describe(doc)
    label = info.path or info.title
    ctx.session.app.CloseDoc(info.title)
    still_open = try_com_member(
        ctx.session.app, "GetOpenDocumentByName", info.path or info.title, default=None
    )
    if still_open is None:
        return label, None
    return None, f"{label} (SOLIDWORKS did not close it; it may have dependants open)"


def _process_item(job: _Job, item: BatchExportItem, units: list[_Unit]) -> _ItemOutcome:
    """Resolve one document, write everything asked of it, and let it go again."""
    outcome = _ItemOutcome()
    source = _source_label(item)

    try:
        doc, opened_here = _resolve_item_document(job.ctx, item)
    except Exception as exc:
        error = _error_dict(exc)
        outcome.entries = [_entry(unit, source, "failed", error=error) for unit in units]
        if not job.args.continue_on_error:
            outcome.stop_reason = f"{source} could not be opened and continue_on_error is false."
        return outcome

    info = job.ctx.session.describe(doc)
    target = _Target(
        item=item,
        doc=doc,
        doc_type=info.doc_type,
        stem=item.name or _document_stem(info),
        source=source,
    )
    if opened_here:
        outcome.opened = info.path or info.title

    for unit in units:
        if outcome.stop_reason is not None:
            outcome.entries.append(
                _entry(unit, source, "skipped", document_type=target.doc_type)
            )
            continue
        entry = _run_unit(job, target, unit)
        outcome.entries.append(entry)
        if entry.status == "failed" and not job.args.continue_on_error:
            named = Path(entry.requested_path).name if entry.requested_path else source
            outcome.stop_reason = f"{named} failed and continue_on_error is false."

    if opened_here and job.args.close_opened:
        outcome.closed, outcome.left_open = _close_if_opened(job.ctx, doc)
    elif opened_here:
        outcome.left_open = f"{info.path or info.title} (close_opened is false)"

    if outcome.stop_reason is None and job.args.stop_when_strained:
        outcome.stop_reason = strain_stop_reason(process_resources())
    return outcome


# --- the manifest -------------------------------------------------------------


def _write_manifest(path: Path, policy: str, payload: dict[str, Any]) -> tuple[Path, str]:
    resolved, action = resolve_output_path(path, policy)  # type: ignore[arg-type]
    target = Path(resolved)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target, action


def _summarise(
    totals: dict[str, int], stop_reason: str | None, manifest: Path, action: str,
    left_open: list[str],
) -> list[str]:
    warnings: list[str] = []
    if totals["failed"]:
        warnings.append(
            f"{totals['failed']} of {totals['planned']} outputs failed. Each entry "
            "carries its own error; nothing was retried."
        )
    if totals["skipped"]:
        warnings.append(
            f"{totals['skipped']} outputs were never attempted, so nothing is known "
            "about whether they would have worked."
        )
    if stop_reason:
        warnings.append(stop_reason)
    if action == "versioned":
        warnings.append(
            f"The manifest was written as {manifest.name} rather than the requested "
            "name, to avoid replacing an earlier run's record."
        )
    warnings.extend(f"Left open: {reason}" for reason in left_open)
    return warnings


# --- the operation ------------------------------------------------------------


@op(
    name="sw_batch_export",
    tier="core",
    domains=("exchange", "document"),
    tags=("batch", "export", "manifest", "hash", "delivery"),
    summary=(
        "Export many documents, configurations, sheets, and formats in one call, "
        "writing a JSON manifest that names every file with its size, timestamp, and "
        "SHA-256, and reporting each requested output as written, failed, or skipped."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Writes each export and a JSON manifest under an allowed output root, and "
            "opens the documents it was given. A document opened by this call is opened "
            "read-only and closed again afterwards; one that was already open is never "
            "closed. No model is modified."
        ),
    ),
    partially_satisfies=("IO-004",),
    precondition="none",
    idempotent=False,
    timeout_s=3600.0,
)
def batch_export(ctx: OpContext, args: BatchExportArgs) -> BatchExportResult:
    """IO-004.

    Every output is written by ``sw_export`` or ``sw_drawing_export``, so the settings,
    the signature check, and the overwrite policy are the ones those tools already
    prove — including that a manifest never silently replaces the previous run's.
    """
    directory = Path(assert_output_path(args.output_dir, ctx.config.allowed_roots))
    directory.mkdir(parents=True, exist_ok=True)
    manifest_target = Path(
        assert_output_path(
            args.manifest_path or str(directory / DEFAULT_MANIFEST_NAME),
            ctx.config.allowed_roots,
            field="manifest_path",
        )
    )

    job = _Job(ctx=ctx, args=args, directory=directory)
    units = _plan(args.items)
    entries: list[BatchExportEntry] = []
    opened: list[str] = []
    closed: list[str] = []
    left_open: list[str] = []
    stop_reason: str | None = None

    for item_index, item in enumerate(args.items):
        item_units = [unit for unit in units if unit.item_index == item_index]
        if stop_reason is not None:
            source = _source_label(item)
            entries.extend(_entry(unit, source, "skipped") for unit in item_units)
            continue

        outcome = _process_item(job, item, item_units)
        entries.extend(outcome.entries)
        opened.extend(x for x in [outcome.opened] if x)
        closed.extend(x for x in [outcome.closed] if x)
        left_open.extend(x for x in [outcome.left_open] if x)
        stop_reason = outcome.stop_reason

    totals = {
        "planned": len(units),
        "written": sum(1 for entry in entries if entry.status == "written"),
        "failed": sum(1 for entry in entries if entry.status == "failed"),
        "skipped": sum(1 for entry in entries if entry.status == "skipped"),
    }

    manifest_written, manifest_action = _write_manifest(
        manifest_target,
        args.overwrite,
        {
            "schema": MANIFEST_SCHEMA,
            "generated_utc": datetime.now(UTC).isoformat(),
            "output_dir": str(directory),
            "overwrite_policy": args.overwrite,
            "totals": totals,
            "stopped_early": stop_reason is not None,
            "stop_reason": stop_reason,
            "documents_opened": opened,
            "documents_closed": closed,
            "documents_left_open": left_open,
            "entries": [entry.model_dump() for entry in entries],
        },
    )
    manifest_evidence = file_evidence(manifest_written)

    return BatchExportResult(
        manifest_path=str(manifest_written),
        manifest_sha256=manifest_evidence.sha256 or "",
        output_dir=str(directory),
        totals=totals,
        entries=entries,
        documents_opened=opened,
        documents_closed=closed,
        documents_left_open=left_open,
        stopped_early=stop_reason is not None,
        stop_reason=stop_reason,
        warnings=_summarise(
            totals, stop_reason, manifest_written, manifest_action, left_open
        ),
        artifacts=[manifest_evidence],
    )
