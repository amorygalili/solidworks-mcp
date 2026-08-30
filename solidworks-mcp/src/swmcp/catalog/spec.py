"""The operation spec: what the catalog knows about every tool.

Safety is a *discriminated union*, never a bag of booleans. The union makes illegal
states unrepresentable — a ``non_model_side_effect`` cannot exist without a written
rationale saying what leaves the process, and a ``model_mutation`` always
auto-checkpoints. The booleans other layers want (``read_only``, ``confirm_required``,
``auto_checkpoint``) are derived in exactly one place: :mod:`swmcp.catalog.projection`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Tier = Literal["core", "extended", "advanced", "debug"]
TIER_ORDER: tuple[Tier, ...] = ("core", "extended", "advanced", "debug")

Domain = Literal[
    "system",
    "safety",
    "discovery",
    "document",
    "selection",
    "reference",
    "sketch",
    "constraint",
    "datum",
    "feature",
    "body",
    "measure",
    "assembly",
    "drawing",
]

DocPrecondition = Literal["none", "any", "part", "assembly", "drawing", "part_or_assembly"]


class ReadSafety(BaseModel):
    """Reads nothing but model state. No checkpoint, no confirmation, no audit entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["read"] = "read"


class ModelMutation(BaseModel):
    """Changes the model. Always auto-checkpointed; confirmation required when destructive."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["model_mutation"] = "model_mutation"
    destructive: bool


class NonModelSideEffect(BaseModel):
    """Effect outside the model — a file written, the UI changed, a process launched.

    ``rationale`` is mandatory and non-empty. If an operation cannot explain in writing
    what escapes the process, it has not been thought through well enough to ship.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["non_model_side_effect"] = "non_model_side_effect"
    destructive: bool
    rationale: str

    @field_validator("rationale")
    @classmethod
    def _rationale_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "non_model_side_effect requires a rationale explaining what leaves the "
                "process (file written, UI changed, application launched)."
            )
        return value


SafetyUnion = ReadSafety | ModelMutation | NonModelSideEffect
Safety = Annotated[SafetyUnion, Field(discriminator="kind")]


@dataclass(frozen=True, slots=True)
class OpSpec:
    """Everything the server, the docs, and the tests need to know about one operation."""

    name: str
    tier: Tier
    domains: tuple[Domain, ...]
    tags: tuple[str, ...]
    summary: str
    safety: SafetyUnion
    satisfies: tuple[str, ...]
    partially_satisfies: tuple[str, ...]
    precondition: DocPrecondition
    idempotent: bool
    args_model: type[BaseModel]
    result_model: type[BaseModel]
    handler: Callable[..., Any]
    handler_ref: str
    timeout_s: float
    #: Whether the dispatcher must attach to SOLIDWORKS before the handler runs.
    #:
    #: False for the operations that have to work when SOLIDWORKS is *not* running:
    #: the one that starts it, and the diagnostics whose whole purpose is to explain a
    #: machine where it is missing or wedged. ``precondition`` cannot express this — it
    #: says whether a *document* is needed, and ``sw_doc_new`` needs no document but
    #: very much needs a session.
    needs_session: bool = True
    #: Take a new snapshot even if a recent one exists. The debounce window
    #: exists to stop a burst of edits writing a file each time, but an
    #: operation that promises to undo *itself* cannot be rolled back to a
    #: snapshot taken before some earlier edit.
    fresh_checkpoint: bool = False


def tier_allowed(tier: Tier, max_tier: Tier | Literal["all"]) -> bool:
    """True when ``tier`` is at or below ``max_tier`` in :data:`TIER_ORDER`."""
    if max_tier == "all":
        return True
    return TIER_ORDER.index(tier) <= TIER_ORDER.index(max_tier)
