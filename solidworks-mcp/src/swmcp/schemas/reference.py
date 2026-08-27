"""Argument and result models for selection and entity references."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from swmcp.envelope import ReadResult, SideEffectResult
from swmcp.refs.model import EntityRef
from swmcp.schemas.common import BaseArgs, StrictModel
from swmcp.units import Length


class SelectionGetArgs(BaseArgs):
    capture_references: bool = Field(
        default=True,
        description="Capture a full entity reference for each selection, ready to reuse.",
    )


class SelectionGetResult(ReadResult):
    count: int
    selections: list[dict[str, Any]] = Field(default_factory=list)
    hint: str = (
        "Each selection carries tool_args that can be pasted into the next call's "
        "arguments verbatim."
    )


class SelectionSetArgs(BaseArgs):
    clear_first: bool = Field(default=True, description="Clear the existing selection first.")
    refs: list[EntityRef] = Field(
        default_factory=list,
        max_length=200,
        description="Entity references to select. An empty list with clear_first just clears.",
    )
    names: list[str] = Field(
        default_factory=list,
        max_length=200,
        description="Typed SelectByID2 names, e.g. 'Front Plane'.",
    )
    name_type: str = Field(default="PLANE", description="Selection type for the names list.")
    mark: int = Field(default=0, ge=-1, le=1024, description="Selection mark to apply.")


class SelectionSetResult(SideEffectResult):
    selected: int
    failed: list[dict[str, Any]] = Field(default_factory=list)
    selection: list[dict[str, Any]] = Field(default_factory=list)


class RefCaptureArgs(BaseArgs):
    from_selection: bool = Field(
        default=True, description="Capture references for the current UI selection."
    )
    selection_index: int | None = Field(
        default=None, ge=1, description="Capture only this 1-based selection."
    )


class RefCaptureResult(ReadResult):
    references: list[dict[str, Any]] = Field(default_factory=list)


class RefResolveArgs(BaseArgs):
    ref: EntityRef = Field(description="A reference previously captured or probed.")
    select: bool = Field(
        default=False, description="Also select the resolved entity in SOLIDWORKS."
    )


class RefResolveResult(ReadResult):
    status: Literal["resolved"] = "resolved"
    via: Literal["persistent", "semantic"]
    score: int | None = None
    drift: dict[str, Any] | None = None
    refreshed: dict[str, Any] = Field(
        description="A freshly captured reference; store this to avoid re-searching."
    )
    tool_args: dict[str, Any] = Field(default_factory=dict)


class ProbeFacesArgs(BaseArgs):
    entity_class: Literal["face", "edge"] = "face"
    feature_name: str | None = Field(
        default=None, description="Restrict to the faces or edges of this feature."
    )
    body_name: str | None = Field(default=None, description="Restrict to this body.")
    geometry_type: str | None = Field(
        default=None,
        description=(
            "planar_face, cylindrical_face, conical_face, spherical_face, toroidal_face, "
            "bspline_face, line_edge, or circular_edge."
        ),
    )
    radius_min: Length | None = Field(default=None, description="Smallest acceptable radius.")
    radius_max: Length | None = Field(default=None, description="Largest acceptable radius.")
    area_min_mm2: float | None = Field(
        default=None, ge=0, description="Smallest acceptable face area, in square millimetres."
    )
    area_max_mm2: float | None = Field(
        default=None, ge=0, description="Largest acceptable face area, in square millimetres."
    )
    normal: list[float] | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Direction to match, e.g. [0,0,1] for upward-facing planes.",
    )
    normal_within_deg: float = Field(default=5.0, ge=0, le=180)
    contains_point: list[Length] | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Keep only entities whose bounding box contains this point.",
    )
    contains_tolerance: Length = Field(default=1.0, description="Slack for contains_point.")
    limit: int = Field(default=50, ge=1, le=500)


class ProbeFacesResult(ReadResult):
    examined: int
    matched: int
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    hint: str = (
        "Each candidate carries tool_args ready to paste. If more than one matches, "
        "add a filter rather than assuming the first is correct."
    )


class ProbeRayArgs(BaseArgs):
    origin: list[Length] = Field(
        min_length=3, max_length=3, description="Ray start point [x, y, z]."
    )
    direction: list[float] = Field(
        min_length=3, max_length=3, description="Ray direction [x, y, z]; need not be normalized."
    )
    radius: Length = Field(default=2.0, description="Hit radius around the ray.")


class ProbeRayResult(ReadResult):
    hit: bool
    reference: dict[str, Any] | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)


class StrictProbeBase(StrictModel):
    """Reserved for future probe variants that do not target a document."""
