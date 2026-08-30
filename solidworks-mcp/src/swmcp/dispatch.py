"""The request pipeline: validate → guard → checkpoint → run → verify → audit.

The order matters. Validation, path policy, and the confirmation gate all run **before
the COM boundary**, so a refused request never reaches SOLIDWORKS and every one of
those rules is testable on a machine with no CAD installed.

Document resolution, checkpointing, and the handler itself run together inside one job
on the STA thread, because all three touch COM proxies with thread affinity.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ValidationError

from swmcp.catalog.projection import project
from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.catalog.spec import OpSpec
from swmcp.com.session import SwSession
from swmcp.com.worker import StaWorker
from swmcp.config import SwmcpConfig, get_config
from swmcp.context import OpContext
from swmcp.envelope import MutationResult
from swmcp.errors import (
    ErrorEnvelope,
    SwMcpError,
    make_error,
    policy_error,
    validation_error,
    wire_safe_validation_errors,
)
from swmcp.safety.audit import append_audit
from swmcp.safety.checkpoint import CheckpointStore
from swmcp.safety.paths import assert_output_path, prepare_document_path
from swmcp.schemas.common import DOCUMENT_PATH_FIELDS, OUTPUT_PATH_FIELDS
from swmcp.timing import elapsed_ms


class Dispatcher:
    """Holds the worker, the checkpoint store, and the catalog for one process."""

    def __init__(
        self,
        config: SwmcpConfig | None = None,
        *,
        worker: StaWorker | None = None,
        checkpoints: CheckpointStore | None = None,
    ):
        self.config = config or get_config()
        self.checkpoints = checkpoints or CheckpointStore(self.config)
        self.worker = worker or StaWorker(
            self.config, session_factory=lambda: SwSession(self.config)
        )
        load_all_ops()

    # -- gates that run before COM ----------------------------------------

    @staticmethod
    def _validate(spec: OpSpec, raw: dict[str, Any]) -> BaseModel:
        try:
            return spec.args_model.model_validate(raw or {})
        except ValidationError as exc:
            errors = wire_safe_validation_errors(exc)
            # A destructive op types confirm as Literal[True], so omitting it surfaces
            # here as a schema error. Report it as the policy problem it actually is,
            # with the remediation, rather than as an anonymous validation failure.
            if all(error.get("loc") == ["confirm"] for error in errors):
                raise SwMcpError(
                    policy_error(
                        "CONFIRM_REQUIRED",
                        f"{spec.name} is destructive and needs explicit confirmation.",
                        context={"tool": spec.name, "safety": spec.safety.model_dump()},
                        remediation=[
                            "Re-send the request with confirm=true once you are sure.",
                        ],
                    )
                ) from exc
            raise SwMcpError(
                validation_error(
                    "INVALID_ARGUMENTS",
                    f"{spec.name} rejected its arguments.",
                    context={"errors": errors},
                    remediation=[
                        "Check the tool's input schema; unknown fields are refused "
                        "rather than ignored, so a typo shows up here.",
                    ],
                )
            ) from exc

    def _guard_paths(self, spec: OpSpec, args: BaseModel) -> None:
        """SAFE-004. Output paths are refused outside the roots; inputs are normalized.

        The walk descends into nested models and lists of them. It did not, until an
        operation took a *list of items* each naming its own document and output — at
        which point every path in the request was invisible to this gate, because the
        only string field at the top level was a directory. A guard that inspects one
        level of a tree is not a guard.
        """
        self._guard_model(args)
        _ = spec  # kept for symmetry with the other gates

    def _guard_model(self, model: BaseModel, depth: int = 0) -> None:
        if depth > 8:  # pragma: no cover - no args model nests anywhere near this deep
            return
        for name in type(model).model_fields:
            value = getattr(model, name, None)
            if isinstance(value, str) and value:
                if name in OUTPUT_PATH_FIELDS:
                    assert_output_path(value, self.config.allowed_roots, field=name)
                elif name in DOCUMENT_PATH_FIELDS:
                    prepare_document_path(value)
            elif isinstance(value, BaseModel):
                self._guard_model(value, depth + 1)
            elif isinstance(value, (list, tuple)):
                for element in value:
                    if isinstance(element, BaseModel):
                        self._guard_model(element, depth + 1)

    @staticmethod
    def _guard_confirmation(spec: OpSpec, args: BaseModel) -> None:
        """SAFE-003. Re-checked here even though the schema types it as ``Literal[True]``."""
        if not project(spec.safety).confirm_required:
            return
        if getattr(args, "confirm", False) is not True:
            raise SwMcpError(
                policy_error(
                    "CONFIRM_REQUIRED",
                    f"{spec.name} is destructive and needs explicit confirmation.",
                    context={"tool": spec.name, "safety": spec.safety.model_dump()},
                    remediation=["Re-send the request with confirm=true once you are sure."],
                )
            )

    # -- the COM-side job --------------------------------------------------

    def _resolve_document(self, ctx: OpContext, session: SwSession, args: BaseModel) -> None:
        if ctx.spec.precondition == "none":
            return
        target = getattr(args, "document", None)
        try:
            ctx.doc = session.resolve_doc(
                path=getattr(target, "path", None) if target else None,
                title=getattr(target, "title", None) if target else None,
                require_type=ctx.spec.precondition,
            )
        except SwMcpError:
            if ctx.spec.precondition == "any" and target is not None and not target.is_explicit():
                # Some "any" operations legitimately run with nothing open.
                ctx.doc = None
                return
            raise

    def _checkpoint(self, ctx: OpContext, session: SwSession) -> None:
        """SAFE-005. Runs for every model mutation, and never blocks it."""
        if not project(ctx.spec.safety).auto_checkpoint:
            return

        info = session.describe(ctx.doc) if ctx.doc is not None else None
        source = info.path if info else None

        # SaveAs-Copy captures unsaved state, but it also ends whatever edit is in
        # progress: taking one while a sketch is open closes the sketch, and the very
        # next operation finds nothing to draw into. While an edit is open, fall back to
        # copying the file on disk — a weaker snapshot, but one that leaves the session
        # alone. The checkpoint record reports which was used, so nothing is over-claimed.
        editing = ctx.doc is not None and _sketch_is_open(ctx.doc)
        saver = None
        if ctx.doc is not None and info is not None and info.checkpointable and not editing:
            def saver(destination: str) -> bool:
                from swmcp.com.marshal import null_dispatch, out_long
                from swmcp.com.swconst import value as sw_value

                silent = sw_value("swSaveAsOptions_e", "swSaveAsOptions_Silent")
                copy = sw_value("swSaveAsOptions_e", "swSaveAsOptions_Copy")
                errors, warnings = out_long(0), out_long(0)
                return bool(
                    ctx.doc.Extension.SaveAs(
                        destination,
                        sw_value("swSaveAsVersion_e", "swSaveAsCurrentVersion"),
                        silent | copy,
                        # An optional IDispatch argument needs a typed null VARIANT.
                        null_dispatch(),
                        errors,
                        warnings,
                    )
                )

        ctx.checkpoint = self.checkpoints.create(
            source, saver=saver, force=ctx.spec.fresh_checkpoint
        )
        if editing and ctx.checkpoint.method == "file_copy":
            ctx.warn(
                "A sketch is open for editing, so the checkpoint is a copy of the last "
                "saved file; edits made since that save are not captured."
            )

        if ctx.checkpoint.method != "skipped":
            return

        reason = ctx.checkpoint.reason or "unknown"
        destructive = project(ctx.spec.safety).destructive

        # A checkpoint protects state that is already on disk. A document that has never
        # been saved has none, so refusing to edit it would be pointless friction — the
        # very first sketch on a new part would be impossible. A document that *does*
        # live somewhere unreachable (platform-managed, a URI rather than a file) is a
        # different matter: there is real saved state that a destructive edit would put
        # beyond recovery.
        unreachable = reason == "not_a_local_file"
        if destructive and unreachable and not self.config.allow_uncheckpointed:
            raise SwMcpError(
                policy_error(
                    "NOT_CHECKPOINTABLE",
                    f"{ctx.spec.name} is destructive, but this document cannot be "
                    f"snapshotted first ({reason}), so the change would not be reversible.",
                    context={"reason": reason, "document": info.as_dict() if info else None},
                    remediation=[
                        "Save the document to a local path first, then retry.",
                        "Or set SWMCP_ALLOW_UNCHECKPOINTED=1 to proceed without a safety "
                        "net, accepting that rollback will be unavailable.",
                    ],
                )
            )

        ctx.warn(
            f"No checkpoint was taken ({reason}), so this change cannot be rolled back "
            f"by {'restoring a snapshot' if not destructive else 'any means'}."
        )

    def _run_on_worker(self, spec: OpSpec, args: BaseModel, request_id: str) -> BaseModel:
        def job(session: SwSession) -> BaseModel:
            # sw_connect launches SOLIDWORKS, and the diagnostics exist to describe a
            # machine where it is not running. Attaching here first made both
            # impossible: every one of them failed with SOLIDWORKS_NOT_RUNNING before
            # its handler was ever reached.
            if spec.needs_session:
                session.ensure()
            ctx = OpContext(
                session=session,
                config=self.config,
                checkpoints=self.checkpoints,
                spec=spec,
                request_id=request_id,
                worker=self.worker,
            )
            self._resolve_document(ctx, session, args)
            self._checkpoint(ctx, session)

            result = spec.handler(ctx, args)

            for warning in ctx.warnings:
                if warning not in result.warnings:
                    result.warnings.append(warning)
            if isinstance(result, MutationResult):
                if result.checkpoint is None:
                    result.checkpoint = ctx.checkpoint
                _warn_about_failed_checks(result)
            return result

        kind = "read" if project(spec.safety).read_only else "mutation"
        return self.worker.call(job, label=spec.name, kind=kind, timeout_s=spec.timeout_s)

    # -- entry point -------------------------------------------------------

    def call(self, name: str, raw_args: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run one operation and return its wire payload."""
        started = time.monotonic()
        request_id = uuid.uuid4().hex[:12]
        spec = OPS.get(name)
        if spec is None:
            return _error_payload(
                make_error(
                    "UNKNOWN_TOOL",
                    "validation",
                    f"There is no operation named {name!r}.",
                    remediation=["Use the tool search operation to find the right name."],
                ),
                request_id,
            )

        projection = project(spec.safety)
        args: BaseModel | None = None
        try:
            args = self._validate(spec, raw_args or {})
            self._guard_paths(spec, args)
            self._guard_confirmation(spec, args)
            result = self._run_on_worker(spec, args, request_id)
        except SwMcpError as exc:
            self._audit(spec, projection, args, ok=False, error=exc.envelope, started=started)
            return _error_payload(exc.envelope, request_id)
        except Exception as exc:
            from swmcp.com.classify import to_envelope

            envelope = to_envelope(exc, context={"tool": spec.name})
            self._audit(spec, projection, args, ok=False, error=envelope, started=started)
            return _error_payload(envelope, request_id)

        self._audit(spec, projection, args, ok=True, result=result, started=started)
        return {
            "ok": True,
            "tool": spec.name,
            "request_id": request_id,
            "units": {"length": "mm", "angle": "deg", "mass": "kg"},
            "duration_ms": elapsed_ms(started),
            "result": result.model_dump(mode="json"),
        }

    def _audit(
        self,
        spec: OpSpec,
        projection: Any,
        args: BaseModel | None,
        *,
        ok: bool,
        result: BaseModel | None = None,
        error: ErrorEnvelope | None = None,
        started: float,
    ) -> None:
        if not projection.audited:
            return
        checkpoint = getattr(result, "checkpoint", None)
        append_audit(
            tool=spec.name,
            ok=ok,
            destructive=projection.destructive,
            args=args.model_dump(mode="json") if args is not None else None,
            checkpoint_path=getattr(checkpoint, "checkpoint_path", None),
            checkpoint_method=getattr(checkpoint, "method", None),
            error_code=error.code if error else None,
            error_message=error.message if error else None,
            duration_ms=elapsed_ms(started),
            config=self.config,
        )

    def close(self) -> None:
        self.worker.stop()


def _warn_about_failed_checks(result: MutationResult) -> None:
    """Raise a failed read-back check to the top of the response.

    A COM call can succeed and still change nothing — a chamfer given a type its API
    does not accept adds a feature that removes no material. The evidence is already in
    ``verification.checks``, but a caller reading only ``ok`` would miss it, so the
    failure is repeated as a warning where it cannot be overlooked.
    """
    failed = [check for check in result.verification.checks if not check.passed]
    if not failed:
        return
    detail = "; ".join(f"{check.name} ({check.detail})" if check.detail else check.name
                       for check in failed)
    warning = f"Read-back verification did not hold: {detail}"
    if warning not in result.warnings:
        result.warnings.append(warning)


def _error_payload(envelope: ErrorEnvelope, request_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "request_id": request_id,
        "error": envelope.model_dump(mode="json", exclude_none=True),
    }


def _sketch_is_open(doc: Any) -> bool:
    """Whether a sketch is currently open for editing in the given document."""
    from swmcp.sketching import active_sketch

    return active_sketch(doc) is not None
