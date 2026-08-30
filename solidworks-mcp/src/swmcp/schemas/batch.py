"""Batch export (IO-004).

A batch is not a loop over ``sw_export``. A loop reports whichever call failed last and
loses the rest; a batch has to say what it was asked for, what it wrote, what it did not
write and why, and leave a record on disk that outlives the response.

So the shape here is a *plan* — every requested output enumerated before anything runs —
and every planned output appears in the result exactly once, whether it was written,
failed, or was never attempted. A batch that stops halfway is still a complete account
of itself.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import SideEffectResult
from swmcp.safety.overwrite import OverwritePolicy
from swmcp.schemas.common import StrictModel
from swmcp.schemas.exchange import ExportFormat, LengthUnit, StlQuality

#: Cap on the number of files one call may write. A batch is the operation most likely
#: to exhaust the SOLIDWORKS session — it opens documents, activates configurations, and
#: tessellates — and an unbounded one would simply be a way of wedging the application
#: with a single request. Past this, split the work and the manifests are still readable
#: side by side.
MAX_PLANNED_OUTPUTS = 200

#: Characters Windows refuses in a filename, plus the separators. Configuration names
#: routinely contain them: "1/2 scale" and "Rev: B" are ordinary and both illegal.
ILLEGAL_NAME_CHARACTERS = '<>:"/\\|?*'


def _no_duplicates(values: list[str] | None, what: str) -> list[str] | None:
    if values is None:
        return None
    seen = {value.casefold() for value in values}
    if len(seen) != len(values):
        raise ValueError(
            f"{what} contains the same entry twice, which would write one file over "
            "another within a single batch"
        )
    return values


class BatchExportItem(StrictModel):
    """One document, and every file to be written from it.

    Formats multiply with configurations: three formats and two configurations is six
    files, named so that a person can tell them apart without opening them.
    """

    source_path: str | None = Field(
        default=None,
        description=(
            "A SOLIDWORKS file to export. Opened if it is not already open, and closed "
            "again afterwards unless it was open before the batch started."
        ),
    )
    title: str | None = Field(
        default=None,
        description="Window title of a document already open. Refused if it is ambiguous.",
    )
    formats: list[ExportFormat] = Field(
        min_length=1,
        max_length=13,
        description=(
            "Formats to write from this document. Neutral and mesh formats need a part "
            "or an assembly; PDF, DXF, and DWG need a drawing."
        ),
    )
    configurations: list[str] | None = Field(
        default=None,
        max_length=32,
        description=(
            "Export each of these configurations rather than the active one. Parts and "
            "assemblies only; a drawing has no configurations of its own."
        ),
    )
    sheets: list[str] | None = Field(
        default=None,
        max_length=64,
        description=(
            "Drawing sheets to export. Honoured for PDF only, exactly as in "
            "sw_drawing_export; for DXF and DWG the choice is reported as not applied "
            "rather than silently dropped."
        ),
    )
    name: str | None = Field(
        default=None,
        max_length=120,
        description=(
            "Base filename for this item's outputs. Defaults to the document's own "
            "stem. The configuration, when there is one, is appended to it."
        ),
    )

    @model_validator(mode="after")
    def _addressed_exactly_once(self) -> BatchExportItem:
        if self.source_path and self.title:
            raise ValueError(
                "an item names both source_path and title; give one, or neither to use "
                "the active document"
            )
        _no_duplicates(self.formats, "formats")
        _no_duplicates(self.configurations, "configurations")
        _no_duplicates(self.sheets, "sheets")
        if self.name is not None:
            if not self.name.strip():
                raise ValueError("name is blank; omit it to use the document's own stem")
            if any(character in self.name for character in ILLEGAL_NAME_CHARACTERS):
                raise ValueError(
                    f"name may not contain any of {ILLEGAL_NAME_CHARACTERS!r}; it is a "
                    "filename, not a path, and the batch chooses the directory"
                )
            if ".." in self.name:
                raise ValueError("name may not contain '..'")
        return self

    def planned_output_count(self) -> int:
        """How many files this item asks for."""
        return max(1, len(self.configurations or [])) * len(self.formats)


class BatchExportArgs(StrictModel):
    """IO-004.

    There is deliberately no ``document`` field. Every item addresses its own document,
    because a batch whose subject is "whatever happens to be active" is a batch that
    cannot be repeated.
    """

    items: list[BatchExportItem] = Field(
        min_length=1,
        max_length=64,
        description="The documents to export, in the order they will be processed.",
    )
    output_dir: str = Field(
        min_length=1,
        description=(
            "Directory for every written file and, by default, the manifest. Must "
            "resolve under an allowed output root."
        ),
    )
    manifest_path: str | None = Field(
        default=None,
        description=(
            "Where to write the JSON manifest. Defaults to batch_manifest.json in "
            "output_dir. The manifest obeys the same overwrite policy as the exports, "
            "so a re-run does not erase the record of the previous one."
        ),
    )
    overwrite: OverwritePolicy = Field(
        default="version",
        description=(
            "Applied to every written file and to the manifest. 'version' writes "
            "name_vNNN when the target exists (default), 'forbid' refuses and proposes "
            "a free name, 'allow' replaces the file."
        ),
    )
    continue_on_error: bool = Field(
        default=True,
        description=(
            "Keep going when one output fails. False stops at the first failure, and "
            "the outputs not attempted are reported as skipped rather than omitted."
        ),
    )
    close_opened: bool = Field(
        default=True,
        description=(
            "Close documents this call opened. Documents that were already open are "
            "never closed. A document the batch opens is opened read-only, which is "
            "what makes closing it safe; one SOLIDWORKS declines to close is reported "
            "rather than left unmentioned."
        ),
    )
    stop_when_strained: bool = Field(
        default=True,
        description=(
            "Stop between items once SOLIDWORKS has reached the measured point where "
            "calls hang rather than fail. This is the wall, not the 'worth watching' "
            "reading sw_health reports — a slower-than-fresh session keeps working. The "
            "remaining outputs are reported as skipped, and the manifest still names "
            "everything already written."
        ),
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
    def _plan_is_bounded(self) -> BatchExportArgs:
        planned = sum(item.planned_output_count() for item in self.items)
        if planned > MAX_PLANNED_OUTPUTS:
            raise ValueError(
                f"this batch asks for {planned} files, and the limit is "
                f"{MAX_PLANNED_OUTPUTS}; split it, because one request large enough to "
                "exhaust the SOLIDWORKS session takes the whole session with it"
            )
        return self


#: What happened to one planned output. ``skipped`` is not a synonym for ``failed``: it
#: means the file was never attempted, so nothing is known about whether it would work.
BatchStatus = Literal["written", "failed", "skipped"]


class BatchExportEntry(StrictModel):
    """One planned output. Every entry appears whatever became of it."""

    index: int = Field(description="Position in the plan, counting from zero.")
    item_index: int = Field(description="Which item of the request this came from.")
    source: str = Field(
        description="How the document was addressed: a path, a title, or 'active document'."
    )
    document_type: str | None = Field(
        default=None,
        description="'part', 'assembly', or 'drawing'. None when the document never resolved.",
    )
    format: str
    configuration: str | None = None
    sheets: list[str] = Field(default_factory=list)
    status: BatchStatus
    requested_path: str | None = Field(
        default=None,
        description="The path asked for. None when the document never resolved to a name.",
    )
    saved_path: str | None = Field(
        default=None, description="Where the file actually went. Differs when it was versioned."
    )
    overwrite_action: str | None = None
    size_bytes: int | None = None
    sha256: str | None = Field(
        default=None,
        description="SHA-256 of the written file. None for a file over 64 MB, or unwritten.",
    )
    signature_verified: bool | None = Field(
        default=None,
        description="Whether the bytes matched the format's own signature, not merely that "
        "SaveAs returned.",
    )
    signature_detail: str | None = None
    duration_s: float = 0.0
    error: dict[str, Any] | None = Field(
        default=None, description="The full error envelope for a failed output."
    )
    warnings: list[str] = Field(default_factory=list)


class BatchExportResult(SideEffectResult):
    """IO-004.

    ``artifacts`` holds the manifest alone, deliberately. The manifest is the artifact
    index: it names every file with its size, timestamp, and hash, so repeating two
    hundred evidence records inline would say nothing the manifest does not, at two
    hundred times the size.
    """

    manifest_path: str
    manifest_sha256: str
    output_dir: str
    totals: dict[str, int] = Field(
        description="planned, written, failed, and skipped. They always sum to planned."
    )
    entries: list[BatchExportEntry]
    documents_opened: list[str] = Field(default_factory=list)
    documents_closed: list[str] = Field(default_factory=list)
    documents_left_open: list[str] = Field(
        default_factory=list,
        description="Documents this call opened but did not close, each with the reason.",
    )
    stopped_early: bool = False
    stop_reason: str | None = None
