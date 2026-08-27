"""The one and only place safety booleans are derived from the safety union.

Every other layer reads :class:`SafetyProjection` attributes. Nothing else in ``src/``
is allowed to define or assign ``read_only`` / ``confirm_required`` / ``auto_checkpoint``
— ``tests/test_no_second_source_of_truth.py`` enforces that by scanning the tree. This
is what keeps a destructive operation from ever drifting out of its confirmation gate.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from swmcp.catalog.spec import ModelMutation, NonModelSideEffect, ReadSafety, SafetyUnion


class SafetyProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    read_only: bool
    destructive: bool
    confirm_required: bool
    auto_checkpoint: bool
    audited: bool


def project(safety: SafetyUnion) -> SafetyProjection:
    """Derive the boolean policy flags for one operation."""
    match safety:
        case ReadSafety():
            return SafetyProjection(
                read_only=True,
                destructive=False,
                confirm_required=False,
                auto_checkpoint=False,
                audited=False,
            )
        case ModelMutation(destructive=is_destructive):
            return SafetyProjection(
                read_only=False,
                destructive=is_destructive,
                confirm_required=is_destructive,
                auto_checkpoint=True,
                audited=True,
            )
        case NonModelSideEffect(destructive=is_destructive):
            return SafetyProjection(
                read_only=False,
                destructive=is_destructive,
                confirm_required=is_destructive,
                auto_checkpoint=False,
                audited=True,
            )
        case _:  # pragma: no cover - guarded by the exhaustiveness test
            raise AssertionError(f"unhandled safety variant: {safety!r}")
