"""Equations, configurations, and custom properties (PAR-002, PAR-003, PAR-006).

These are what make a part *parametric* rather than merely modelled: an agent that can
read and drive named values can change a design without re-deriving its geometry.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import MutationResult, ReadResult, SideEffectResult
from swmcp.safety.overwrite import OverwritePolicy
from swmcp.schemas.common import BaseArgs, ConfirmField, StrictModel

# --- equations ----------------------------------------------------------------


class EquationListArgs(BaseArgs):
    include_dependencies: bool = Field(
        default=True,
        description=(
            "Also report which equations each one reads, and any circular chain. "
            "This is textual analysis of the equation strings, not a solver result."
        ),
    )


class EquationListResult(ReadResult):
    document_length_unit: str = Field(
        default="unknown",
        description="The unit SOLIDWORKS reads a number that carries no unit of "
        "its own in. Equations are text evaluated in document units, so this is "
        "what '120' means here.",
    )
    count: int
    equations: list[dict[str, Any]] = Field(default_factory=list)
    global_variables: list[dict[str, Any]] = Field(default_factory=list)
    status: dict[str, Any] = Field(
        default_factory=dict, description="Solver status as reported by SOLIDWORKS."
    )
    circular_references: list[list[str]] = Field(
        default_factory=list, description="Each cycle found, as the chain of names in it."
    )
    unresolved_references: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Names an equation reads that no equation or dimension defines.",
    )


class EquationSpec(StrictModel):
    """One edit to the equation list."""

    operation: Literal["add", "update", "delete"] = "add"
    name: str | None = Field(
        default=None,
        description=(
            "The left-hand side, without quotes: a dimension like 'D1@Sketch1' or a "
            "global variable like 'Width'. Required for update and delete."
        ),
    )
    expression: str | None = Field(
        default=None,
        description="The right-hand side, e.g. '\"Width\" * 2'. Required for add and update.",
    )
    global_variable: bool = Field(
        default=False, description="Add as a global variable rather than a dimension equation."
    )
    configuration_scope: Literal["all", "this", "specify"] = Field(
        default="all",
        description=(
            "Which configurations the equation applies to. Anything but 'all' needs a "
            "part with more than one configuration - the API that scopes an equation "
            "works only on multi-configuration parts - and cannot be used for a global "
            "variable, which SOLIDWORKS requires to apply to every configuration."
        ),
    )
    configurations: list[str] = Field(
        default_factory=list,
        description="Required when configuration_scope is 'specify'; name the current one too.",
    )

    @model_validator(mode="after")
    def _scope_is_achievable(self) -> EquationSpec:
        if self.configuration_scope != "all" and self.global_variable:
            raise ValueError(
                "a global variable applies to every configuration, so "
                "configuration_scope must be 'all'"
            )
        if self.configuration_scope == "specify" and not self.configurations:
            raise ValueError("configuration_scope='specify' needs at least one configuration")
        return self


class EquationSetArgs(BaseArgs):
    equations: list[EquationSpec] = Field(min_length=1, max_length=200)
    preflight: bool = Field(
        default=False,
        description="Validate and report what would change, without touching the model.",
    )
    rebuild: bool = Field(default=True, description="Rebuild after applying, to pick up errors.")


class EquationSetResult(MutationResult):
    document_length_unit: str = Field(
        default="unknown",
        description="The unit SOLIDWORKS reads a number that carries no unit of "
        "its own in. Equations are text evaluated in document units, so this is "
        "what '120' means here.",
    )
    applied: int
    failed: list[dict[str, Any]] = Field(default_factory=list)
    status: dict[str, Any] = Field(default_factory=dict)
    circular_references: list[list[str]] = Field(default_factory=list)
    rebuild_errors: list[str] = Field(default_factory=list)


# --- configurations -----------------------------------------------------------


class ConfigListArgs(BaseArgs):
    include_properties: bool = Field(
        default=False, description="Include each configuration's custom properties."
    )


class ConfigListResult(ReadResult):
    count: int
    active: str | None = None
    configurations: list[dict[str, Any]] = Field(default_factory=list)


class ConfigCreateArgs(BaseArgs):
    name: str = Field(min_length=1, description="Name for the new configuration.")
    parent: str | None = Field(
        default=None, description="Create as a derived configuration of this one."
    )
    comment: str = ""
    description: str = ""
    alternate_name: str = ""
    suppress_new_features: bool = Field(
        default=False, description="New features are suppressed in this configuration by default."
    )
    activate: bool = Field(default=True, description="Make it the active configuration.")


class ConfigCreateResult(MutationResult):
    name: str
    parent: str | None = None
    derived: bool = False
    active: str | None = None
    count_before: int
    count_after: int


class ConfigActivateArgs(BaseArgs):
    name: str = Field(min_length=1)
    rebuild: bool = True


class ConfigActivateResult(MutationResult):
    active: str | None = None
    previous: str | None = None
    rebuild_errors: list[str] = Field(default_factory=list)


class ConfigDeleteArgs(BaseArgs):
    name: str = Field(min_length=1)
    confirm: ConfirmField


class ConfigDeleteResult(MutationResult):
    deleted: bool
    name: str
    count_before: int
    count_after: int
    active: str | None = None


# --- custom properties --------------------------------------------------------


class PropertyListArgs(BaseArgs):
    configuration: str | None = Field(
        default=None,
        description=(
            "Read this configuration's properties. Omit for the file-level set; use "
            "'*' for the file-level set plus every configuration."
        ),
    )


class PropertyListResult(ReadResult):
    count: int
    file_properties: list[dict[str, Any]] = Field(default_factory=list)
    configuration_properties: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class PropertySpec(StrictModel):
    name: str = Field(min_length=1)
    value: str | None = Field(
        default=None,
        description=(
            "The raw value, which may be an expression such as "
            "'\"SW-Mass@@Default@part.SLDPRT\"'. Required unless deleting."
        ),
    )
    type: Literal["text", "date", "number", "double", "yes_no"] = "text"
    delete: bool = False


class PropertySetArgs(BaseArgs):
    properties: list[PropertySpec] = Field(min_length=1, max_length=200)
    configuration: str | None = Field(
        default=None, description="Write into this configuration rather than the file."
    )
    overwrite: bool = Field(
        default=True, description="Replace an existing property of the same name."
    )


class PropertySetResult(MutationResult):
    written: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)
    failed: list[dict[str, Any]] = Field(default_factory=list)
    configuration: str | None = None


# --- parameter table ----------------------------------------------------------


class ParameterTableExportArgs(BaseArgs):
    output_path: str = Field(
        description="CSV destination. Must be under an allowed output root."
    )
    overwrite: OverwritePolicy = Field(
        default="version",
        description=(
            "'version' writes name_vNNN when the target exists (default), 'forbid' "
            "refuses and proposes a free name, 'allow' replaces the file."
        ),
    )
    include: list[Literal["dimensions", "equations", "properties"]] = Field(
        default_factory=lambda: ["dimensions", "equations", "properties"],
        min_length=1,
    )
    configuration: str | None = Field(
        default=None, description="Read values from this configuration."
    )
    unit: Literal["mm", "cm", "m", "in", "ft"] = "mm"


class ParameterTableExportResult(SideEffectResult):
    row_count: int
    kinds: dict[str, int] = Field(default_factory=dict)
    saved_path: str
    overwrite_action: Literal["create", "overwrite", "versioned"]


class ParameterTableImportArgs(BaseArgs):
    input_path: str = Field(description="A CSV previously written by the export tool.")
    preflight: bool = Field(
        default=False,
        description="Report every change the file would make, without applying any of them.",
    )
    unit: Literal["mm", "cm", "m", "in", "ft"] = "mm"
    rebuild: bool = True


class ParameterTableImportResult(MutationResult):
    applied: int
    unchanged: int
    failed: list[dict[str, Any]] = Field(default_factory=list)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    rebuild_errors: list[str] = Field(default_factory=list)
