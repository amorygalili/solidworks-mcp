"""Neutral-format export (IO-002, IO-003).

Export is how a model reaches anything that is not SOLIDWORKS, so the result has to
answer more than "a file appeared". Every export reports the format it actually wrote,
verified against the file's own signature, plus the settings it used — a STEP written
as AP203 when AP242 was wanted is a silent problem downstream.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import SideEffectResult
from swmcp.safety.overwrite import OverwritePolicy
from swmcp.schemas.common import BaseArgs

#: Formats this release writes. Anything else is a schema rejection rather than a
#: SaveAs that fails, or worse, silently writes something unexpected.
ExportFormat = Literal[
    "step",
    "iges",
    "stl",
    "3mf",
    "obj",
    "ply",
    "parasolid_text",
    "parasolid_binary",
    "sat",
    "vrml",
    "pdf",
    "dxf",
    "dwg",
]

#: Extension to format. SOLIDWORKS dispatches ``SaveAs`` on the extension, so this is
#: both the accepted-extension list and the mapping the schema validates against.
BY_EXTENSION: dict[str, str] = {
    ".step": "step",
    ".stp": "step",
    ".iges": "iges",
    ".igs": "iges",
    ".stl": "stl",
    ".3mf": "3mf",
    ".obj": "obj",
    ".ply": "ply",
    ".x_t": "parasolid_text",
    ".x_b": "parasolid_binary",
    ".sat": "sat",
    ".wrl": "vrml",
    ".pdf": "pdf",
    ".dxf": "dxf",
    ".dwg": "dwg",
}


def format_for_extension(path: str) -> str | None:
    """The export format implied by a path's extension, or ``None`` if unknown."""
    return BY_EXTENSION.get(Path(path).suffix.lower())


StlQuality = Literal["coarse", "fine"]
LengthUnit = Literal["mm", "cm", "m", "in", "ft"]


class ExportArgs(BaseArgs):
    output_path: str = Field(
        description=(
            "Destination under an allowed output root. The extension selects the "
            "format unless 'format' says otherwise."
        )
    )
    format: ExportFormat | None = Field(
        default=None,
        description="Override the format implied by the extension. Must agree with it.",
    )
    overwrite: OverwritePolicy = Field(
        default="version",
        description=(
            "'version' writes name_vNNN when the target exists (default), 'forbid' "
            "refuses and proposes a free name, 'allow' replaces the file."
        ),
    )
    configuration: str | None = Field(
        default=None, description="Export this configuration rather than the active one."
    )

    stl_quality: StlQuality = Field(
        default="fine", description="Mesh tessellation quality for STL, 3MF, OBJ, and PLY."
    )
    stl_binary: bool = Field(default=True, description="Write STL as binary rather than ASCII.")
    mesh_unit: LengthUnit = Field(
        default="mm",
        description="Unit written into mesh formats, which carry no unit of their own.",
    )
    step_protocol: Literal["ap203", "ap214", "ap242"] = Field(
        default="ap214", description="STEP application protocol."
    )

    @model_validator(mode="after")
    def _format_agrees_with_extension(self) -> ExportArgs:
        implied = format_for_extension(self.output_path)
        if self.format and implied and self.format != implied:
            suffix = Path(self.output_path).suffix
            raise ValueError(
                f"format={self.format!r} disagrees with the {suffix!r} extension; "
                "give a matching extension or drop the format argument"
            )
        return self


class ExportResult(SideEffectResult):
    saved_path: str
    format: str
    overwrite_action: Literal["create", "overwrite", "versioned"]
    size_bytes: int
    signature_verified: bool = Field(
        description=(
            "Whether the written file's own header matched the format claimed. False "
            "means the format has no signature this server can check, not that the "
            "file is wrong — the reason is in signature_detail."
        )
    )
    signature_detail: str
    settings: dict[str, Any] = Field(
        default_factory=dict, description="The export settings actually applied."
    )
    save_error: dict[str, Any] = Field(default_factory=dict)
    save_warning: dict[str, Any] = Field(default_factory=dict)
