"""Drawings (DRW-001, DRW-002, DRW-003)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import MutationResult, ReadResult, SideEffectResult
from swmcp.schemas.common import BaseArgs
from swmcp.units import Length

#: Sheet sizes, named rather than numbered. ``custom`` is the only one that reads width
#: and height — and it is the trap this whole domain turned on: ``NewDocument`` ignores
#: those two arguments for every other size, so requesting ``custom`` without giving
#: them builds a sheet of zero area, and SOLIDWORKS then spins forever trying to scale a
#: view onto it. The schema therefore refuses ``custom`` unless both are supplied.
PaperSize = Literal[
    "a",
    "a_vertical",
    "b",
    "c",
    "d",
    "e",
    "a4",
    "a4_vertical",
    "a3",
    "a2",
    "a1",
    "a0",
    "custom",
]

#: The standard model views SOLIDWORKS names with a leading asterisk. The asterisk is
#: part of the name and is added when the call is made, not carried in the schema.
ViewOrientation = Literal[
    "front",
    "back",
    "left",
    "right",
    "top",
    "bottom",
    "isometric",
    "trimetric",
    "dimetric",
    "current",
]

ProjectionStandard = Literal["first_angle", "third_angle"]


class DrawingNewArgs(BaseArgs):
    """DRW-001."""

    model_path: str | None = Field(
        default=None,
        description=(
            "Part or assembly the drawing is for. Omit to use the active document. The "
            "model is only recorded here; views are added with sw_drawing_view_add."
        ),
    )
    template_path: str | None = Field(
        default=None,
        description="Explicit drawing template. Omitted means the SOLIDWORKS default.",
    )
    paper_size: PaperSize = Field(default="a", description="Sheet size.")
    width: Length | None = Field(
        default=None, description="Sheet width. Required for paper_size='custom'."
    )
    height: Length | None = Field(
        default=None, description="Sheet height. Required for paper_size='custom'."
    )
    scale: list[float] | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Sheet scale as [numerator, denominator], e.g. [1, 2] for 1:2.",
    )
    projection: ProjectionStandard = Field(
        default="third_angle", description="Projection standard for projected views."
    )
    sheet_name: str | None = Field(default=None, description="Rename the first sheet.")

    @model_validator(mode="after")
    def _custom_needs_dimensions(self) -> DrawingNewArgs:
        """A custom sheet with no size is the zero-by-zero sheet that spins SOLIDWORKS."""
        if self.paper_size == "custom" and (self.width is None or self.height is None):
            raise ValueError(
                "paper_size='custom' needs both width and height; a sheet of zero area "
                "makes SOLIDWORKS loop forever when a view is placed on it"
            )
        if self.paper_size != "custom" and (self.width is not None or self.height is not None):
            raise ValueError(
                f"width and height are only read for paper_size='custom', not "
                f"{self.paper_size!r}; SOLIDWORKS would ignore them"
            )
        for value, label in ((self.width, "width"), (self.height, "height")):
            if value is not None and value <= 0:
                raise ValueError(f"{label} must be greater than zero")
        if self.scale is not None and (self.scale[0] <= 0 or self.scale[1] <= 0):
            raise ValueError("both parts of scale must be greater than zero")
        return self


class DrawingNewResult(SideEffectResult):
    document: dict[str, Any]
    sheet_name: str
    paper_size: str
    width_mm: float
    height_mm: float
    scale: list[float]
    projection: str
    template_used: str
    template_source: Literal["explicit", "default_preference"]
    sheet_format: str | None = Field(
        default=None, description="The sheet format in use, or null when there is none."
    )


class DrawingViewAddArgs(BaseArgs):
    """DRW-002."""

    view_type: Literal["model", "standard_3"] = Field(
        default="model",
        description=(
            "'model' places one named view of the model; 'standard_3' places front, top "
            "and side together using the sheet's projection standard."
        ),
    )
    model_path: str | None = Field(
        default=None,
        description=(
            "Part or assembly to draw. Omit to reuse the model an existing view on this "
            "sheet already references."
        ),
    )
    orientation: ViewOrientation = Field(
        default="front", description="Which model view to place. Ignored for 'standard_3'."
    )
    at: list[Length] | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description=(
            "Where to put the view's centre, [x, y] from the sheet's lower-left corner. "
            "Omitted centres it on the sheet."
        ),
    )
    name: str | None = Field(default=None, description="Rename the created view.")

    @model_validator(mode="after")
    def _standard_3_places_itself(self) -> DrawingViewAddArgs:
        if self.view_type == "standard_3" and self.at is not None:
            raise ValueError(
                "'standard_3' arranges its own three views; 'at' applies to a single view"
            )
        if self.view_type == "standard_3" and self.name is not None:
            raise ValueError("'standard_3' creates three views, so a single name cannot apply")
        return self


class DrawingViewAddResult(MutationResult):
    view_type: str
    views_created: list[dict[str, Any]] = Field(default_factory=list)
    views_before: int
    views_after: int
    model_path: str


class DrawingListArgs(BaseArgs):
    """DRW-003."""

    sheet: str | None = Field(
        default=None, description="Only report this sheet. Omitted reports every sheet."
    )


class DrawingListResult(ReadResult):
    sheet_count: int
    active_sheet: str | None = None
    sheets: list[dict[str, Any]] = Field(default_factory=list)
    view_count: int = 0


# --- DRW-004 to DRW-009 -----------------------------------------------------------

#: What ``InsertModelAnnotations3`` may bring across, as names rather than a bitmask.
AnnotationKind = Literal[
    "dimensions",
    "notes",
    "datums",
    "geometric_tolerances",
    "cosmetic_threads",
    "surface_finishes",
    "welds",
    "axes",
    "planes",
    "points",
]

BomKind = Literal["parts_only", "top_level_only", "indented", "flattened"]

CenterMarkStyle = Literal["single", "linear_group", "circular_group"]


class DrawingSheetAddArgs(BaseArgs):
    """DRW-007."""

    name: str = Field(min_length=1, description="Name for the new sheet.")
    paper_size: PaperSize = Field(default="a", description="Sheet size.")
    width: Length | None = Field(default=None, description="Required for paper_size='custom'.")
    height: Length | None = Field(default=None, description="Required for paper_size='custom'.")
    scale: list[float] | None = Field(
        default=None, min_length=2, max_length=2, description="[numerator, denominator]."
    )
    projection: ProjectionStandard = Field(default="third_angle")
    activate: bool = Field(default=True, description="Make the new sheet current.")

    @model_validator(mode="after")
    def _custom_needs_dimensions(self) -> DrawingSheetAddArgs:
        """NewSheet3 carries the same zero-area trap as NewDocument."""
        if self.paper_size == "custom" and (self.width is None or self.height is None):
            raise ValueError(
                "paper_size='custom' needs both width and height; a sheet of zero area "
                "makes SOLIDWORKS loop forever when a view is placed on it"
            )
        if self.paper_size != "custom" and (self.width is not None or self.height is not None):
            raise ValueError("width and height are only read for paper_size='custom'")
        return self


class DrawingSheetAddResult(MutationResult):
    sheet_name: str
    paper_size: str
    width_mm: float
    height_mm: float
    scale: list[float]
    active_sheet: str | None = None
    sheets_before: int
    sheets_after: int
    sheet_names: list[str] = Field(default_factory=list)


class DrawingAnnotateModelArgs(BaseArgs):
    """DRW-004."""

    kinds: list[AnnotationKind] = Field(
        default_factory=lambda: ["dimensions"],
        min_length=1,
        max_length=10,
        description="Which model items to import.",
    )
    all_views: bool = Field(
        default=True, description="Import into every view, not just the selected one."
    )
    eliminate_duplicates: bool = Field(default=True, description="Drop duplicate dimensions.")
    hidden_feature_dimensions: bool = Field(
        default=False, description="Include dimensions from hidden features."
    )
    use_sketch_placement: bool = Field(
        default=False, description="Place dimensions where the sketch had them."
    )


class DrawingAnnotateModelResult(MutationResult):
    imported: int
    annotations: list[dict[str, Any]] = Field(default_factory=list)
    annotations_before: int
    annotations_after: int
    kinds: list[str] = Field(default_factory=list)


class DrawingNoteAddArgs(BaseArgs):
    """DRW-005, for the note and centre-mark half."""

    text: str | None = Field(
        default=None,
        min_length=1,
        max_length=4000,
        description="Note text. Required for annotation='note'.",
    )
    annotation: Literal["note", "center_mark"] = Field(default="note")
    at: list[Length] | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Where to place the note, [x, y] on the sheet.",
    )
    center_mark_style: CenterMarkStyle = Field(default="single")
    propagate: bool = Field(
        default=False, description="Centre marks: propagate to similar circles."
    )

    @model_validator(mode="after")
    def _note_needs_text(self) -> DrawingNoteAddArgs:
        if self.annotation == "note" and not self.text:
            raise ValueError("a note needs text")
        if self.annotation == "center_mark" and self.text:
            raise ValueError("a centre mark carries no text")
        return self


class DrawingNoteAddResult(MutationResult):
    annotation: str
    text: str | None = None
    name: str
    position_mm: list[float] = Field(default_factory=list)
    annotations_before: int
    annotations_after: int


class DrawingTableAddArgs(BaseArgs):
    """DRW-006, for the BOM half."""

    bom_type: BomKind = Field(default="parts_only", description="Which BOM to build.")
    configuration: str | None = Field(
        default=None, description="Configuration the quantities come from."
    )
    at: list[Length] | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Table anchor position, [x, y] on the sheet.",
    )
    template_path: str | None = Field(default=None, description="Explicit table template.")


class DrawingTableAddResult(MutationResult):
    table_type: str
    row_count: int
    column_count: int
    column_titles: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    tables_before: int
    tables_after: int


class DrawingReviewArgs(BaseArgs):
    """DRW-008. The policy is the caller's; the measurements are this tool's."""

    require_views: int = Field(
        default=1, ge=0, le=50, description="Fewest views each sheet should carry."
    )
    require_dimensions: int = Field(
        default=0, ge=0, le=500, description="Fewest dimensions the drawing should carry."
    )
    require_sheet_format: bool = Field(
        default=False, description="Treat a sheet with no format as a finding."
    )


class DrawingReviewResult(ReadResult):
    passed: bool
    findings: list[dict[str, Any]] = Field(default_factory=list)
    sheet_count: int
    view_count: int
    annotation_count: int
    dimension_count: int
    note_count: int
    table_count: int
    dangling_count: int
    visual_review_required: bool = Field(
        default=True,
        description=(
            "Always true. This counts and positions annotations; it does not and cannot "
            "judge whether the drawing reads correctly to an engineer."
        ),
    )
