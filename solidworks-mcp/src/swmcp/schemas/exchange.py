"""Neutral-format exchange: export (IO-002, IO-003) and import (IO-001).

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
from swmcp.schemas.common import BaseArgs, StrictModel

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


# --- import (IO-001) ------------------------------------------------------------

#: Formats this release reads back in. Each was measured round-tripping a 40 x 30 x 20 mm
#: block; anything not on the list is a schema rejection rather than a LoadFile4 that
#: quietly produces an empty document.
ImportFormat = Literal["step", "iges", "parasolid", "acis", "stl"]

IMPORT_BY_EXTENSION: dict[str, str] = {
    ".step": "step",
    ".stp": "step",
    ".iges": "iges",
    ".igs": "iges",
    ".x_t": "parasolid",
    ".x_b": "parasolid",
    ".sat": "acis",
    ".stl": "stl",
}

#: STEP, IGES, and the other neutral solid formats share one set of preferences; STL and
#: VRML have their own. Which set applies is decided by the format, not the caller.
MESH_IMPORT_FORMATS = frozenset({"stl"})


def import_format_for_extension(path: str) -> str | None:
    """The import format implied by a path's extension, or ``None`` if unknown."""
    return IMPORT_BY_EXTENSION.get(Path(path).suffix.lower())


#: What SOLIDWORKS builds from a mesh file. ``graphics`` is its own default and produces
#: no body at all — nothing to measure, select, or model against.
MeshBodyType = Literal["graphics", "surface", "solid"]


class ImportArgs(StrictModel):
    input_path: str = Field(
        min_length=1,
        description=(
            "File to import. The extension selects the format unless 'format' says "
            "otherwise. The file is read, never written."
        ),
    )
    format: ImportFormat | None = Field(
        default=None,
        description="Override the format implied by the extension. Must agree with it.",
    )
    mesh_body_type: MeshBodyType = Field(
        default="solid",
        description=(
            "For STL: what to build from the mesh. SOLIDWORKS defaults to 'graphics', "
            "which produces zero bodies and nothing measurable, so this defaults to "
            "'solid' instead. A large mesh converts slowly, and 'graphics' remains the "
            "cheap choice when the file is only there to be looked at."
        ),
    )
    mesh_unit: LengthUnit | None = Field(
        default=None,
        description="Unit to read an STL in. Mesh formats carry no unit of their own.",
    )
    neutral_units: Literal["file", "template"] = Field(
        default="file",
        description=(
            "For STEP and IGES: take the units from the file, or from the part template."
        ),
    )
    knit: Literal["form_solids", "do_not_knit"] = Field(
        default="form_solids",
        description=(
            "For STEP and IGES: sew the imported faces into solids, or leave them as "
            "separate surfaces. Not knitting a closed block yields one sheet body per "
            "face and no volume."
        ),
    )
    run_diagnostics: bool = Field(
        default=False,
        description=(
            "Run import diagnostics on the result, which tries to close gaps and repair "
            "faces. Reported by what it changed, not by what it returned."
        ),
    )
    close_gaps: bool = Field(default=True, description="Diagnostics: close gaps between faces.")
    fix_faces: bool = Field(default=True, description="Diagnostics: repair faulty faces.")
    remove_bad_faces: bool = Field(
        default=False,
        description="Diagnostics: delete faces that cannot be repaired, leaving holes.",
    )

    @model_validator(mode="after")
    def _format_agrees_with_extension(self) -> ImportArgs:
        implied = import_format_for_extension(self.input_path)
        if self.format and implied and self.format != implied:
            suffix = Path(self.input_path).suffix
            raise ValueError(
                f"format={self.format!r} disagrees with the {suffix!r} extension; "
                "give a matching extension or drop the format argument"
            )
        return self


class ImportResult(SideEffectResult):
    document: dict[str, Any] = Field(description="The new document the import created.")
    format: str
    source_path: str
    geometry_found: bool = Field(
        description=(
            "Whether the import produced any body this server can measure. False for a "
            "mesh brought in as graphics, which is a picture rather than geometry."
        )
    )
    body_count: int
    solid_body_count: int
    sheet_body_count: int
    volume_mm3: float | None = Field(
        default=None, description="Total volume of the solid bodies. None when there are none."
    )
    surface_area_mm2: float | None = None
    face_count: int = 0
    edge_count: int = 0
    settings: dict[str, Any] = Field(
        default_factory=dict, description="The import preferences actually applied."
    )
    diagnostics: dict[str, Any] | None = Field(
        default=None,
        description=(
            "What import diagnostics changed, if it was run: face counts before and "
            "after, not merely the value the call returned."
        ),
    )
