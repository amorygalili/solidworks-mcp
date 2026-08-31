"""Bill of materials export (IO-007).

Every value in this CSV is computed by walking the component tree. None of it is read
from a SOLIDWORKS BOM table, and the two can legitimately disagree — which is why the
requirement asks for a warning that survives into the result rather than a footnote in
the docs. The tool is a *precursor* to a bill of materials until somebody has checked it
against a native one.

The traceability matrix is the other half of that. A BOM line says "3 of PN-WIDGET"; the
matrix says which three instances, where each sits in the tree, and — for every property
column — whether the value came from the configuration-specific property set or the
file-level one. That last part is not decoration: the two sets are genuinely different
places, both are routinely populated, and they disagree.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from swmcp.envelope import SideEffectResult
from swmcp.safety.overwrite import OverwritePolicy
from swmcp.schemas.common import BaseArgs, StrictModel

#: The roll-up shapes this release computes. ``swBomType_e`` also has ``Flattened``,
#: which is deliberately not offered: it means indented-with-quantities-rolled-up, and
#: the exact rule SOLIDWORKS applies to it is not something this tool can verify without
#: a native BOM to compare against. Claiming a mode whose semantics are a guess is the
#: failure this whole requirement is written against.
BomShape = Literal["parts_only", "top_level_only", "indented"]

#: Cap on property columns. Discovery takes the union of names across every component,
#: and one assembly of purchased parts can carry a hundred; past this the CSV stops
#: being something a person opens and the caller should name the columns they want.
MAX_PROPERTY_COLUMNS = 40

#: Fixed leading columns of the BOM CSV, before the discovered property columns.
BOM_COLUMNS: tuple[str, ...] = (
    "item_number",
    "part_number",
    "part_number_source",
    "configuration",
    "quantity",
    "document_type",
    "file_name",
    "path",
)

#: Fixed columns of the traceability matrix, before the per-property source columns.
MATRIX_COLUMNS: tuple[str, ...] = (
    "item_number",
    "part_number",
    "instance_name",
    "parent_instance",
    "depth",
    "document_type",
    "configuration",
    "path",
    "suppression",
    "excluded_from_bom",
    "virtual",
    "reference_ok",
    "in_bom",
    "excluded_reason",
)

#: Suffix on a matrix column naming where a property value was read from.
SOURCE_SUFFIX = "__source"


class BomExportArgs(BaseArgs):
    """IO-007."""

    output_path: str = Field(
        min_length=1,
        description="CSV destination for the bill of materials. Must be under an allowed root.",
    )
    matrix_path: str | None = Field(
        default=None,
        description=(
            "CSV destination for the traceability matrix, one row per component "
            "instance. Defaults to the BOM path with '_traceability' before the "
            "extension. Pass matrix=false to skip it."
        ),
    )
    matrix: bool = Field(
        default=True,
        description=(
            "Write the traceability matrix. Turning it off leaves the quantities in the "
            "BOM unattributable, so it is on by default."
        ),
    )
    shape: BomShape = Field(
        default="parts_only",
        description=(
            "'parts_only' rolls every part in the tree up by part number, "
            "'top_level_only' lists only the assembly's direct children, 'indented' "
            "keeps the levels and numbers them 1, 1.1, 1.2, 2."
        ),
    )
    properties: list[str] | None = Field(
        default=None,
        max_length=MAX_PROPERTY_COLUMNS,
        description=(
            "Property columns, in this order. Omit to discover them: the union of every "
            "property name found on any component, sorted. A named property that no "
            "component has still gets a column, so a template stays stable across runs."
        ),
    )
    configuration: str | None = Field(
        default=None,
        description=(
            "Activate this configuration of the assembly first, and restore the previous "
            "one afterwards. Quantities depend on it, because a configuration can "
            "suppress components."
        ),
    )
    include_suppressed: bool = Field(
        default=False,
        description=(
            "Count suppressed components in the quantities. SOLIDWORKS' own BOM does "
            "not, so the default matches it; either way every instance appears in the "
            "matrix with its state, so nothing disappears without a record."
        ),
    )
    include_excluded: bool = Field(
        default=False,
        description=(
            "Count components flagged 'Exclude from bill of materials'. Off by default "
            "for the same reason, and they are likewise still listed in the matrix."
        ),
    )
    max_depth: int = Field(
        default=16, ge=1, le=64, description="How far down the component tree to walk."
    )
    overwrite: OverwritePolicy = Field(
        default="version",
        description=(
            "'version' writes name_vNNN when the target exists (default), 'forbid' "
            "refuses and proposes a free name, 'allow' replaces the file."
        ),
    )

    @model_validator(mode="after")
    def _columns_are_distinct(self) -> BomExportArgs:
        if self.properties is not None:
            if any(not name.strip() for name in self.properties):
                raise ValueError("a property column name is blank")
            folded = {name.casefold() for name in self.properties}
            if len(folded) != len(self.properties):
                raise ValueError(
                    "the same property is named twice, which would write two columns "
                    "with one heading"
                )
            clash = folded & {column.casefold() for column in BOM_COLUMNS}
            if clash:
                raise ValueError(
                    f"{sorted(clash)} collides with a fixed BOM column; rename the "
                    "property column or drop it"
                )
        if self.matrix_path is not None and not self.matrix:
            raise ValueError(
                "matrix_path was given with matrix=false; drop one of them rather than "
                "naming a file that will not be written"
            )
        return self


class BomLine(StrictModel):
    """One rolled-up line of the bill of materials."""

    item_number: str
    part_number: str
    part_number_source: str = Field(
        description="Which SOLIDWORKS rule produced the part number, decoded from "
        "swBOMPartNumberSource_e rather than assumed."
    )
    configuration: str
    quantity: int
    document_type: str
    file_name: str
    path: str
    properties: dict[str, str] = Field(default_factory=dict)


class BomExportResult(SideEffectResult):
    """IO-007.

    ``precursor`` is hard-wired true and says so in ``warnings`` as well. This is
    computed from the component tree, and a native SOLIDWORKS BOM applies rules this
    tool does not implement.
    """

    saved_path: str
    matrix_path: str | None = None
    overwrite_action: str
    shape: str
    line_count: int
    instance_count: int
    counted_instances: int = Field(
        description="Instances that contributed to a quantity, after exclusions."
    )
    excluded_instances: int = Field(
        description="Instances left out of the quantities. Each is still in the matrix."
    )
    property_columns: list[str] = Field(default_factory=list)
    lines: list[BomLine] = Field(default_factory=list)
    configuration: str | None = None
    property_sources: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "How many values came from each place: 'configuration', 'file', 'absent'. "
            "A column that is entirely 'file' on a configured assembly is worth a look."
        ),
    )
    precursor: bool = Field(
        default=True,
        description=(
            "Always true. This is computed from the component tree, not read from a "
            "SOLIDWORKS BOM table, and is not a checked bill of materials until "
            "somebody has compared it with a native one."
        ),
    )
