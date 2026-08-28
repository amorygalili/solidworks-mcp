"""The atomic mutate-and-validate workflow (REV-006).

Everything the safety layer already provides — a checkpoint, read-back verification, an
audit entry — protects one operation at a time. A sequence of operations can still end
half-finished, with each individual step reporting success. This is the piece that makes
a sequence all-or-nothing.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import MutationResult
from swmcp.schemas.common import BaseArgs, ConfirmField, StrictModel


class Step(StrictModel):
    """One operation in the sequence, named exactly as it would be called directly."""

    tool: str = Field(min_length=1, description="Operation name, e.g. 'sw_feature_fillet'.")
    args: dict[str, Any] = Field(
        default_factory=dict, description="That operation's own arguments."
    )
    label: str | None = Field(
        default=None, description="A name for this step in the report. Defaults to the tool name."
    )


class Invariants(StrictModel):
    """What must be true when the sequence finishes.

    An empty set of invariants is allowed and means "run these steps atomically"; the
    per-step verification still applies, and a step that fails still triggers rollback.
    """

    body_count: int | None = Field(
        default=None, ge=0, description="Exact number of solid bodies required at the end."
    )
    face_count: int | None = Field(default=None, ge=0, description="Exact face count required.")
    min_volume_mm3: float | None = Field(default=None, ge=0)
    max_volume_mm3: float | None = Field(default=None, ge=0)
    volume_change: Literal["increase", "decrease", "unchanged"] | None = Field(
        default=None, description="How the volume must have moved across the whole sequence."
    )
    require_features: list[str] = Field(
        default_factory=list, max_length=100, description="Features that must exist afterwards."
    )
    forbid_features: list[str] = Field(
        default_factory=list, max_length=100, description="Features that must not exist afterwards."
    )
    no_features_in_error: bool = Field(
        default=True, description="Every feature must rebuild without an error code."
    )
    no_rebuild_errors: bool = Field(
        default=True, description="The final rebuild must report no failure."
    )

    @model_validator(mode="after")
    def _volume_bounds_make_sense(self) -> Invariants:
        if (
            self.min_volume_mm3 is not None
            and self.max_volume_mm3 is not None
            and self.min_volume_mm3 > self.max_volume_mm3
        ):
            raise ValueError("min_volume_mm3 is greater than max_volume_mm3")
        return self


class SafeExecuteArgs(BaseArgs):
    steps: list[Step] = Field(min_length=1, max_length=50)
    invariants: Invariants = Field(default_factory=Invariants)
    rollback_on_failure: bool = Field(
        default=True,
        description=(
            "Restore the checkpoint if any step fails or any invariant does not hold. "
            "Turning this off keeps a partial result, which is occasionally what you "
            "want when debugging a sequence."
        ),
    )
    stop_on_error: bool = Field(
        default=True, description="Stop at the first failing step rather than trying the rest."
    )
    rebuild: bool = Field(default=True, description="Force a rebuild before checking invariants.")
    confirm: ConfirmField


class SafeExecuteResult(MutationResult):
    completed: int
    step_results: list[dict[str, Any]] = Field(default_factory=list)
    invariants_checked: list[dict[str, Any]] = Field(default_factory=list)
    invariants_held: bool
    rolled_back: bool
    rollback: dict[str, Any] | None = Field(
        default=None, description="Evidence for the restore, when one happened."
    )
    rebuild_errors: list[str] = Field(default_factory=list)
