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
