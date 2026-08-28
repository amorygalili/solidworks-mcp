"""The atomic mutate-and-validate workflow.

One checkpoint is taken for the whole sequence — by the ordinary dispatch pipeline,
because this operation is itself a model mutation — and the steps then run against the
same document without each taking its own. If any step fails, or any invariant does not
hold at the end, that one checkpoint is restored.

The steps run through the same gates a direct call would: each step's arguments are
validated against its own schema, its output paths are root-checked, and a destructive
step still needs its own ``confirm``. What a step does *not* get is a second checkpoint,
which is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from swmcp.catalog.projection import project
from swmcp.catalog.registry import OPS, load_all_ops, op
from swmcp.catalog.spec import ModelMutation
from swmcp.com.marshal import get_com_member, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, MutationResult, Verification
from swmcp.errors import (
    SwMcpError,
    policy_error,
    validation_error,
    wire_safe_validation_errors,
)
from swmcp.modeling import model_snapshot
from swmcp.schemas.review import Invariants, SafeExecuteArgs, SafeExecuteResult, Step

#: Operations that would make the rollback meaningless, because they change which
#: document the checkpoint belongs to or fight the restore directly.
_FORBIDDEN_STEPS = frozenset(
    {
        "sw_safe_execute",
        "sw_checkpoint_restore",
        "sw_doc_new",
        "sw_doc_open",
        "sw_doc_close",
        "sw_doc_activate",
        "sw_connect",
    }
)


def _prepare(step: Step, index: int) -> tuple[Any, Any]:
    """Resolve one step to ``(spec, validated args)``, or explain why it cannot run."""
    load_all_ops()
    spec = OPS.get(step.tool)
    if spec is None:
        raise SwMcpError(
            validation_error(
                "UNKNOWN_TOOL",
                f"steps[{index}] names {step.tool!r}, which is not an operation.",
                context={"tool": step.tool},
                remediation=["Use sw_search_tools to find the right name."],
            )
        )
    if step.tool in _FORBIDDEN_STEPS:
        raise SwMcpError(
            policy_error(
                "STEP_NOT_ALLOWED",
                f"{step.tool!r} cannot run inside sw_safe_execute: it would change or "
                "close the document the rollback depends on.",
                context={"tool": step.tool, "forbidden": sorted(_FORBIDDEN_STEPS)},
                remediation=[
                    "Open or create the document first, then run the sequence against it.",
                ],
            )
        )

    try:
        args = spec.args_model.model_validate(step.args)
    except ValidationError as exc:
        errors = wire_safe_validation_errors(exc)
        # A destructive step types confirm as Literal[True], so leaving it out arrives
        # here as a schema error. Report it as the policy problem it is, exactly as the
        # dispatcher does for a direct call.
        if all(error.get("loc") == ["confirm"] for error in errors):
            raise SwMcpError(_needs_confirmation(step, index)) from exc
        raise SwMcpError(
            validation_error(
                "INVALID_ARGUMENTS",
                f"steps[{index}] ({step.tool}) rejected its arguments.",
                context={"tool": step.tool, "errors": errors},
                remediation=["Check that step's own input schema."],
            )
        ) from exc

    if project(spec.safety).confirm_required and getattr(args, "confirm", False) is not True:
        raise SwMcpError(_needs_confirmation(step, index))
    return spec, args


def _needs_confirmation(step: Step, index: int) -> Any:
    return policy_error(
        "CONFIRM_REQUIRED",
        f"steps[{index}] ({step.tool}) is destructive and needs confirm=true of its "
        "own; confirming the sequence does not confirm each step.",
        context={"tool": step.tool},
        remediation=["Add confirm=true to that step's args."],
    )


def _guard_paths(ctx: OpContext, spec: Any, args: Any) -> None:
    from swmcp.safety.paths import assert_output_path, prepare_document_path
    from swmcp.schemas.common import DOCUMENT_PATH_FIELDS, OUTPUT_PATH_FIELDS

    for name in type(args).model_fields:
        value = getattr(args, name, None)
        if not isinstance(value, str) or not value:
            continue
        if name in OUTPUT_PATH_FIELDS:
            assert_output_path(value, ctx.config.allowed_roots, field=name)
        elif name in DOCUMENT_PATH_FIELDS:
            prepare_document_path(value)
    _ = spec


def _feature_report(doc: Any) -> tuple[set[str], list[str]]:
    """``(feature names, names of features in error)``."""
    names: set[str] = set()
    errored: list[str] = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        name = str(try_com_member(feature, "Name", default="") or "")
        if name:
            names.add(name)
            if try_com_member(feature, "GetErrorCode2", default=0):
                errored.append(name)
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return names, errored


@dataclass(frozen=True)
class _EndState:
    """What the model looked like once the sequence finished."""

    before: dict[str, Any]
    after: dict[str, Any]
    features: set[str]
    features_in_error: list[str]
    rebuild_errors: list[str]


def _check_invariants(invariants: Invariants, state: _EndState) -> list[dict[str, Any]]:
    """Evaluate each declared invariant, reporting what was wanted and what was found."""
    before, after = state.before, state.after
    features, errored = state.features, state.features_in_error
    rebuild_errors = state.rebuild_errors
    results: list[dict[str, Any]] = []

    def record(name: str, held: bool, wanted: Any, found: Any) -> None:
        results.append({"invariant": name, "held": held, "wanted": wanted, "found": found})

    if invariants.body_count is not None:
        record(
            "body_count", after["body_count"] == invariants.body_count,
            invariants.body_count, after["body_count"],
        )
    if invariants.face_count is not None:
        record(
            "face_count", after["face_count"] == invariants.face_count,
            invariants.face_count, after["face_count"],
        )

    volume = after.get("volume_mm3")
    if invariants.min_volume_mm3 is not None:
        record(
            "min_volume_mm3", volume is not None and volume >= invariants.min_volume_mm3,
            f">= {invariants.min_volume_mm3}", volume,
        )
    if invariants.max_volume_mm3 is not None:
        record(
            "max_volume_mm3", volume is not None and volume <= invariants.max_volume_mm3,
            f"<= {invariants.max_volume_mm3}", volume,
        )
    if invariants.volume_change is not None:
        started, ended = before.get("volume_m3") or 0.0, after.get("volume_m3") or 0.0
        held = {
            "increase": ended > started,
            "decrease": ended < started,
            "unchanged": ended == started,
        }[invariants.volume_change]
        record(
            "volume_change", held, invariants.volume_change,
            f"{before.get('volume_mm3')} -> {after.get('volume_mm3')} mm³",
        )

    for required in invariants.require_features:
        record("require_feature", required in features, required, required in features)
    for forbidden in invariants.forbid_features:
        record(
            "forbid_feature",
            forbidden not in features,
            f"no {forbidden}",
            forbidden in features,
        )

    if invariants.no_features_in_error:
        record("no_features_in_error", not errored, "no feature errors", errored)
    if invariants.no_rebuild_errors:
        record("no_rebuild_errors", not rebuild_errors, "a clean rebuild", rebuild_errors)

    return results


def _run_one(ctx: OpContext, step: Step, spec: Any, step_args: Any, index: int) -> dict[str, Any]:
    """Run one step, treating a failed read-back check as a failed step.

    A step whose own verification did not hold has not done what it was asked, and
    letting the sequence carry on past that would defeat the point of running it here.
    """
    entry: dict[str, Any] = {
        "index": index,
        "label": step.label or step.tool,
        "tool": step.tool,
        "ok": True,
    }
    try:
        result = spec.handler(ctx, step_args)
        entry["result"] = result.model_dump(mode="json", exclude_none=True)
        if isinstance(result, MutationResult):
            entry["verification_held"] = result.verification.all_passed
            if not result.verification.all_passed:
                entry["ok"] = False
                entry["error"] = {
                    "code": "VERIFICATION_FAILED",
                    "message": "the step ran but its own read-back check did not hold",
                    "checks": [
                        check.model_dump()
                        for check in result.verification.checks
                        if not check.passed
                    ],
                }
    except SwMcpError as error:
        entry["ok"] = False
        entry["error"] = error.envelope.model_dump(mode="json", exclude_none=True)
    return entry


def _run_steps(
    ctx: OpContext, prepared: list[tuple[Step, Any, Any]], *, stop_on_error: bool
) -> tuple[list[dict[str, Any]], bool]:
    results: list[dict[str, Any]] = []
    failed = False
    for index, (step, spec, step_args) in enumerate(prepared):
        entry = _run_one(ctx, step, spec, step_args, index)
        results.append(entry)
        if not entry["ok"]:
            failed = True
            if stop_on_error:
                break
    return results, failed


def _rollback(ctx: OpContext) -> dict[str, Any] | None:
    """Restore the checkpoint the dispatch pipeline took before this operation."""
    from swmcp.handlers.safety import checkpoint_restore
    from swmcp.schemas.safety import CheckpointRestoreArgs

    record = ctx.checkpoint
    if record is None or not record.checkpoint_path:
        ctx.warn(
            "Nothing was rolled back: no checkpoint exists for this document, so the "
            "partial result is still in the model."
        )
        return None

    outcome = checkpoint_restore(
        ctx,
        CheckpointRestoreArgs(
            checkpoint_path=record.checkpoint_path,
            confirm=True,
            close_open_document=True,
            reopen=True,
        ),
    )
    return {
        "restored_from": outcome.restored_from,
        "restored_to": outcome.restored_to,
        "pre_restore_checkpoint": outcome.pre_restore_checkpoint,
        "reopened": outcome.reopened,
        "checkpoint_method": record.method,
    }


@op(
    name="sw_safe_execute",
    tier="core",
    domains=("safety", "review"),
    tags=("atomic", "transaction", "rollback", "validate", "invariant"),
    summary=(
        "Run a sequence of operations under one checkpoint, check the declared "
        "invariants afterwards, and roll the whole thing back if any step fails or any "
        "invariant does not hold."
    ),
    safety=ModelMutation(destructive=True),
    satisfies=("REV-006",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=900.0,
    # A debounced checkpoint would predate this call, so rolling back to it
    # would undo work the caller never asked to lose.
    fresh_checkpoint=True,
)
def safe_execute(ctx: OpContext, args: SafeExecuteArgs) -> SafeExecuteResult:
    doc = ctx.require_doc()
    before = model_snapshot(doc)

    # Everything is validated before anything runs, so a typo in step five does not
    # leave steps one to four applied.
    prepared = []
    for index, step in enumerate(args.steps):
        spec, step_args = _prepare(step, index)
        _guard_paths(ctx, spec, step_args)
        prepared.append((step, spec, step_args))

    step_results, failed = _run_steps(ctx, prepared, stop_on_error=args.stop_on_error)
    completed = sum(1 for entry in step_results if entry["ok"])

    rebuild_errors: list[str] = []
    if args.rebuild:
        outcome = get_com_member(doc, "ForceRebuild3", False, default=None)
        if outcome is False:
            rebuild_errors.append("ForceRebuild3 reported a failure.")

    after = model_snapshot(doc)
    features, errored = _feature_report(doc)
    checked = _check_invariants(
        args.invariants,
        _EndState(
            before=before,
            after=after,
            features=features,
            features_in_error=errored,
            rebuild_errors=rebuild_errors,
        ),
    )
    invariants_held = all(entry["held"] for entry in checked)

    rolled_back = False
    rollback: dict[str, Any] | None = None
    if (failed or not invariants_held) and args.rollback_on_failure:
        rollback = _rollback(ctx)
        rolled_back = rollback is not None
        if rolled_back:
            doc = ctx.session.active_doc()
            after = model_snapshot(doc) if doc is not None else after

    warnings: list[str] = []
    if failed:
        warnings.append(f"{len(step_results) - completed} step(s) did not succeed.")
    if not invariants_held:
        broken = [entry["invariant"] for entry in checked if not entry["held"]]
        warnings.append(f"invariants that did not hold: {broken}")
    if rolled_back:
        warnings.append("The model was rolled back to the checkpoint taken before this call.")
    elif failed or not invariants_held:
        warnings.append(
            "The model was NOT rolled back, so the partial result is still in place."
        )

    return SafeExecuteResult(
        completed=completed,
        step_results=step_results,
        invariants_checked=checked,
        invariants_held=invariants_held,
        rolled_back=rolled_back,
        rollback=rollback,
        rebuild_errors=rebuild_errors,
        warnings=warnings,
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=[
                Check(
                    name="every_step_succeeded",
                    passed=not failed,
                    detail=f"{completed} of {len(args.steps)} step(s) succeeded",
                ),
                Check(
                    name="invariants_held",
                    passed=invariants_held,
                    detail="; ".join(
                        f"{entry['invariant']}: wanted {entry['wanted']}, found {entry['found']}"
                        for entry in checked
                        if not entry["held"]
                    )
                    or f"{len(checked)} invariant(s) held",
                ),
                Check(
                    name="model_state_is_defined",
                    passed=(not failed and invariants_held) or rolled_back
                    or not args.rollback_on_failure,
                    detail=(
                        "rolled back to the checkpoint"
                        if rolled_back
                        else "the sequence completed"
                        if not failed and invariants_held
                        else "a rollback was wanted but no checkpoint was available"
                    ),
                ),
            ],
        ),
    )
