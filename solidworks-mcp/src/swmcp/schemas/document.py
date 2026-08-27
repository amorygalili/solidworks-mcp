"""Argument and result models for the document domain."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from swmcp.envelope import MutationResult, ReadResult, SideEffectResult
from swmcp.safety.overwrite import OverwritePolicy
from swmcp.schemas.common import BaseArgs, ConfirmField, StrictModel

DocKind = Literal["part", "assembly", "drawing"]


class DocNewArgs(StrictModel):
    doc_type: DocKind = Field(description="Which kind of document to create.")
    template_path: str | None = Field(
        default=None,
        description=(
            "Explicit template file. When omitted the SOLIDWORKS default template for "
            "this document type is used, and the resolved path is reported back."
        ),
    )
    activate: bool = Field(default=True, description="Make the new document active.")


class DocNewResult(SideEffectResult):
    document: dict[str, Any]
    template_used: str
    template_source: Literal["explicit", "default_preference"]


class DocOpenArgs(StrictModel):
    path: str = Field(min_length=1, description="Full path of the document to open.")
    open_read_only: bool = Field(
        default=False, description="Open without taking a write lock on the file."
    )
    silent: bool = Field(default=True, description="Suppress SOLIDWORKS dialogs during load.")
    configuration: str = Field(default="", description="Configuration to activate on open.")


class DocOpenResult(SideEffectResult):
    document: dict[str, Any] | None = None
    load_errors: dict[str, Any] = Field(default_factory=dict)
    load_warnings: dict[str, Any] = Field(default_factory=dict)


class DocListArgs(StrictModel):
    pass


class DocListResult(ReadResult):
    active: dict[str, Any] | None = None
    documents: list[dict[str, Any]] = Field(default_factory=list)


class DocActivateArgs(BaseArgs):
    pass


class DocActivateResult(SideEffectResult):
    document: dict[str, Any]
    previously_active: str | None = None


class DocSaveArgs(BaseArgs):
    output_path: str | None = Field(
        default=None,
        description=(
            "Save-as destination. Must be under an allowed output root. Omit to save the "
            "document in place, which requires it to have been saved before."
        ),
    )
    overwrite: OverwritePolicy = Field(
        default="version",
        description=(
            "'version' writes name_vNNN when the target exists (default), 'forbid' "
            "refuses and proposes a free name, 'allow' replaces the file."
        ),
    )
    save_as_copy: bool = Field(
        default=False,
        description="Write a copy without repointing the open document at the new file.",
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Required only when overwrite='allow'. The default 'version' policy cannot "
            "replace an existing file, so it needs no confirmation."
        ),
    )


class DocSaveResult(SideEffectResult):
    document: dict[str, Any]
    saved_path: str
    action: str = Field(description="create, overwrite, or versioned.")
    save_errors: dict[str, Any] = Field(default_factory=dict)
    save_warnings: dict[str, Any] = Field(default_factory=dict)


class DocCloseArgs(BaseArgs):
    save_first: Literal["require", "discard", "error_if_dirty"] = Field(
        description=(
            "What to do about unsaved changes. There is no default: closing a dirty "
            "document silently would discard work. 'require' saves first, 'discard' "
            "throws the changes away, 'error_if_dirty' refuses."
        )
    )
    confirm: ConfirmField


class DocCloseResult(MutationResult):
    closed_title: str
    closed_path: str | None = None
    saved_before_close: bool = False


class DocRebuildArgs(BaseArgs):
    force: bool = Field(
        default=False, description="Rebuild every feature, not only what is out of date."
    )
    top_level_only: bool = Field(
        default=False, description="For assemblies, skip rebuilding components."
    )


class DocRebuildResult(MutationResult):
    document: dict[str, Any]
    succeeded: bool
    feature_errors: list[dict[str, Any]] = Field(default_factory=list)
    feature_warnings: list[dict[str, Any]] = Field(default_factory=list)


class DocUndoArgs(BaseArgs):
    steps: int = Field(default=1, ge=1, le=50)
    confirm: ConfirmField


class DocUndoResult(MutationResult):
    document: dict[str, Any]
    steps_requested: int
    note: str = (
        "Native undo is not a substitute for a checkpoint: SOLIDWORKS does not report "
        "reliably how many steps were actually undone."
    )
