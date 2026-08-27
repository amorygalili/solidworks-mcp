"""Argument and result models for the safety domain."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from swmcp.envelope import MutationResult, ReadResult, SideEffectResult
from swmcp.safety.overwrite import OverwritePolicy
from swmcp.schemas.common import BaseArgs, ConfirmField, StrictModel


class CheckpointCreateArgs(BaseArgs):
    force: bool = Field(
        default=True,
        description="Take a snapshot even if a recent one exists (bypasses the debounce).",
    )
    tag: str = Field(
        default="",
        max_length=40,
        pattern=r"^[A-Za-z0-9_-]*$",
        description="Optional label folded into the checkpoint filename.",
    )


class CheckpointCreateResult(SideEffectResult):
    checkpoint: dict[str, Any]
    document: dict[str, Any] | None = None


class CheckpointListArgs(BaseArgs):
    limit: int = Field(default=20, ge=1, le=200)


class CheckpointListResult(ReadResult):
    document: dict[str, Any] | None = None
    checkpoint_dir: str | None = None
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)


class CheckpointRestoreArgs(StrictModel):
    checkpoint_path: str = Field(min_length=1, description="Checkpoint file to restore from.")
    target_path: str | None = Field(
        default=None,
        description="Document to overwrite. Inferred from the checkpoint name when omitted.",
    )
    confirm: ConfirmField
    close_open_document: bool = Field(
        default=True,
        description="Close the document in SOLIDWORKS first. Restoring a file that is "
        "open would otherwise be undone the next time it is saved.",
    )
    reopen: bool = Field(default=True, description="Reopen the document after restoring.")


class CheckpointRestoreResult(MutationResult):
    restored_from: str
    restored_to: str
    pre_restore_checkpoint: str | None = None
    pre_restore_method: str | None = None
    reopened: bool = False


class AuditTailArgs(StrictModel):
    limit: int = Field(default=20, ge=1, le=200)
    tool: str | None = Field(default=None, description="Only entries for this operation.")
    failures_only: bool = Field(default=False)


class AuditTailResult(ReadResult):
    audit_path: str
    entries: list[dict[str, Any]] = Field(default_factory=list)


class ExplainErrorArgs(StrictModel):
    code: str | None = Field(default=None, description="An error code such as PATH_NOT_ALLOWED.")
    hresult: int | None = Field(default=None, description="A raw HRESULT, signed or unsigned.")
    sw_enum: str | None = Field(
        default=None, description="A SOLIDWORKS enum name, e.g. swFileLoadError_e."
    )
    sw_value: int | None = Field(default=None, description="A value within sw_enum.")


class ExplainErrorResult(ReadResult):
    explanations: list[dict[str, Any]] = Field(default_factory=list)


class PathPolicyArgs(StrictModel):
    path: str = Field(min_length=1, description="A candidate path to evaluate.")
    intent: str = Field(
        default="output",
        pattern="^(output|document_input)$",
        description="'output' applies the allowed-roots policy; 'document_input' only normalizes.",
    )
    overwrite: OverwritePolicy = Field(default="version")


class PathPolicyResult(ReadResult):
    normalized: str
    intent: str
    allowed: bool
    reason: str | None = None
    exists: bool = False
    resolved_write_path: str | None = None
    action: str | None = None
    allowed_roots: list[str] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)
