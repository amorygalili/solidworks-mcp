"""Assembly components (ASM-001, ASM-002, ASM-003)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from swmcp.envelope import MutationResult, ReadResult
from swmcp.schemas.common import BaseArgs
from swmcp.units import Length

#: ``swComponentSuppressionState_e``. The names callers use are the SOLIDWORKS words
#: for the same states, so a caller never passes a bare integer.
SuppressionState = Literal["suppressed", "lightweight", "resolved", "fully_resolved"]


class AsmInsertArgs(BaseArgs):
    component_path: str = Field(
        min_length=1,
        description="Full path to the .SLDPRT or .SLDASM to insert. Must be under an allowed root.",
    )
    at: list[Length] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description="Where to place the component's origin.",
    )
    configuration: str | None = Field(
        default=None,
        description="Configuration of the inserted component. Defaults to its active one.",
    )
    fixed: bool = Field(
        default=False,
        description=(
            "Fix the component in place. SOLIDWORKS fixes the *first* component of an "
            "assembly on its own regardless; this controls the rest."
        ),
    )


class AsmInsertResult(MutationResult):
    component_name: str
    component_path: str
    configuration: str
    fixed: bool
    position_mm: list[float] = Field(default_factory=list)
    components_before: int
    components_after: int


class AsmTreeArgs(BaseArgs):
    top_level_only: bool = Field(
        default=False, description="List only the top level rather than walking subassemblies."
    )
    max_depth: int = Field(
        default=16, ge=1, le=64, description="Guard against a pathological nesting depth."
    )


class AsmTreeResult(ReadResult):
    component_count: int
    components: list[dict[str, Any]] = Field(default_factory=list)
    quantities: dict[str, int] = Field(
        default_factory=dict, description="Instance count per referenced file path."
    )
    broken_references: list[str] = Field(
        default_factory=list,
        description="Referenced files that are not on disk where the assembly expects them.",
    )


class AsmComponentSetArgs(BaseArgs):
    component_name: str = Field(
        min_length=1,
        description="Component instance name, e.g. 'bracket-1', as sw_asm_tree reports it.",
    )
    suppression: SuppressionState | None = Field(
        default=None, description="Suppress, make lightweight, or resolve the component."
    )
    fixed: bool | None = Field(default=None, description="Fix in place, or float it.")
    visible: bool | None = Field(default=None, description="Show or hide it.")
    configuration: str | None = Field(
        default=None, description="Switch which configuration this instance references."
    )


class AsmComponentSetResult(MutationResult):
    component_name: str
    suppression: str
    fixed: bool
    visible: bool
    configuration: str
    changed: list[str] = Field(default_factory=list)
