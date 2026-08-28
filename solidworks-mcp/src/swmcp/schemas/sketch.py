"""Sketch geometry, relations, and dimensions.

``SketchEntity`` is a discriminated union rather than one tool per shape. SK-003
enumerates thirteen primitives as a single requirement; thirteen tools would be a
fifth of the whole surface, and batching a profile into one call turns thirteen COM
round trips on the STA thread into one.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from swmcp.envelope import MutationResult, ReadResult
from swmcp.refs.model import EntityRef
from swmcp.schemas.common import BaseArgs, ConfirmField, PreflightMixin, StrictModel
from swmcp.units import Angle, Length

Point2D = Annotated[list[Length], Field(min_length=2, max_length=2)]
Point3D = Annotated[list[Length], Field(min_length=3, max_length=3)]


class _Segment(StrictModel):
    construction: bool = Field(
        default=False, description="Create as construction geometry rather than profile geometry."
    )


class LineEntity(_Segment):
    type: Literal["line"] = "line"
    start: Point2D
    end: Point2D


class CenterlineEntity(_Segment):
    type: Literal["centerline"] = "centerline"
    start: Point2D
    end: Point2D


class PointEntity(_Segment):
    type: Literal["point"] = "point"
    at: Point2D


class RectCornerEntity(_Segment):
    type: Literal["rect_corner"] = "rect_corner"
    corner: Point2D
    opposite: Point2D


class RectCenterEntity(_Segment):
    type: Literal["rect_center"] = "rect_center"
    center: Point2D
    corner: Point2D


class CircleEntity(_Segment):
    type: Literal["circle"] = "circle"
    center: Point2D
    radius: Length = Field(gt=0)


class ArcCenterEntity(_Segment):
    type: Literal["arc_center"] = "arc_center"
    center: Point2D
    start: Point2D
    end: Point2D
    direction: Literal["clockwise", "counterclockwise"] = "counterclockwise"


class Arc3PointEntity(_Segment):
    type: Literal["arc_3pt"] = "arc_3pt"
    start: Point2D
    end: Point2D
    through: Point2D


class EllipseEntity(_Segment):
    type: Literal["ellipse"] = "ellipse"
    center: Point2D
    major_axis_point: Point2D
    minor_axis_point: Point2D


class PolygonEntity(_Segment):
    type: Literal["polygon"] = "polygon"
    center: Point2D
    circumradius: Length = Field(gt=0)
    sides: int = Field(ge=3, le=64)
    inscribed: bool = True


class SlotStraightEntity(_Segment):
    type: Literal["slot_straight"] = "slot_straight"
    start: Point2D
    end: Point2D
    width: Length = Field(gt=0)


class SplineEntity(_Segment):
    type: Literal["spline"] = "spline"
    points: list[Point2D] = Field(min_length=2, max_length=200)


SketchEntity = Annotated[
    LineEntity
    | CenterlineEntity
    | PointEntity
    | RectCornerEntity
    | RectCenterEntity
    | CircleEntity
    | ArcCenterEntity
    | Arc3PointEntity
    | EllipseEntity
    | PolygonEntity
    | SlotStraightEntity
    | SplineEntity,
    Field(discriminator="type"),
]


class SketchPlaneTarget(StrictModel):
    """Where a sketch goes. Exactly one of these should be given."""

    standard_plane: Literal["front", "top", "right"] | None = Field(
        default=None,
        description=(
            "Resolved by position in the feature tree and the locale-invariant RefPlane "
            "token, so a non-English SOLIDWORKS works without an alias table."
        ),
    )
    plane_name: str | None = Field(default=None, description="A named reference plane.")
    ref: EntityRef | None = Field(default=None, description="A planar face or datum plane.")


class SketchStartArgs(BaseArgs):
    on: SketchPlaneTarget


class SketchState(StrictModel):
    """CON-005, carried on every relation and dimension result so it cannot be skipped."""

    status: str = Field(description="fully_defined, under_defined, over_defined, or no_solution.")
    status_code: int
    fully_defined: bool
    over_defined: bool
    relation_count: int
    dangling_relations: list[dict[str, Any]] = Field(default_factory=list)
    over_defining_relations: list[dict[str, Any]] = Field(default_factory=list)


class SketchStartResult(MutationResult):
    sketch_name: str
    plane: str


class SketchExitArgs(BaseArgs):
    rebuild: bool = Field(default=True, description="Rebuild the model on exiting the sketch.")


class SketchExitResult(MutationResult):
    exited: bool
    sketch_name: str | None = None


class SketchListArgs(BaseArgs):
    include_geometry: bool = Field(default=False, description="Include per-segment detail.")


class SketchListResult(ReadResult):
    active_sketch: str | None = None
    sketches: list[dict[str, Any]] = Field(default_factory=list)


class SketchAddGeometryArgs(BaseArgs, PreflightMixin):
    entities: list[SketchEntity] = Field(
        min_length=1,
        max_length=500,
        description="Sketch primitives to create, in order.",
    )
    sketch_name: str | None = Field(
        default=None,
        description="Sketch to edit. Defaults to the sketch currently open for editing.",
    )


class SketchAddGeometryResult(MutationResult):
    sketch_name: str
    created: list[dict[str, Any]] = Field(default_factory=list)
    failed: list[dict[str, Any]] = Field(default_factory=list)
    sketch_state: SketchState


class SketchSetConstructionArgs(BaseArgs):
    segment_ids: list[str] = Field(
        min_length=1, max_length=500, description="sketch_local_id values from a create call."
    )
    construction: bool = True


class SketchSetConstructionResult(MutationResult):
    changed: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class SketchDeleteArgs(BaseArgs):
    segment_ids: list[str] = Field(min_length=1, max_length=500)
    confirm: ConfirmField


class SketchDeleteResult(MutationResult):
    deleted: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    sketch_state: SketchState | None = None


RelationType = Literal[
    "horizontal",
    "vertical",
    "coincident",
    "collinear",
    "parallel",
    "perpendicular",
    "tangent",
    "equal",
    "concentric",
    "midpoint",
    "symmetric",
    "fix",
    "merge",
]


class RelationSpec(StrictModel):
    type: RelationType
    segment_ids: list[str] = Field(
        min_length=1, max_length=3, description="Segments the relation applies to."
    )


class SketchAddRelationsArgs(BaseArgs, PreflightMixin):
    relations: list[RelationSpec] = Field(min_length=1, max_length=200)
    sketch_name: str | None = None


class SketchAddRelationsResult(MutationResult):
    applied: int
    failed: list[dict[str, Any]] = Field(default_factory=list)
    sketch_state: SketchState


DimensionType = Literal[
    "distance",
    "horizontal_distance",
    "vertical_distance",
    "radius",
    "diameter",
    "angle",
    "arc_length",
]


class DimensionSpec(StrictModel):
    type: DimensionType
    segment_ids: list[str] = Field(min_length=1, max_length=3)
    value: Length | None = Field(
        default=None, description="Target value. Omit to dimension without driving a change."
    )
    angle_value: Angle | None = Field(
        default=None, description="Target angle for angle dimensions."
    )
    place_at: Point3D | None = Field(
        default=None, description="Where to put the dimension annotation."
    )
    name: str | None = Field(default=None, description="Rename the dimension after creating it.")


class SketchAddDimensionsArgs(BaseArgs, PreflightMixin):
    dimensions: list[DimensionSpec] = Field(min_length=1, max_length=200)
    sketch_name: str | None = None


class SketchAddDimensionsResult(MutationResult):
    created: list[dict[str, Any]] = Field(default_factory=list)
    failed: list[dict[str, Any]] = Field(default_factory=list)
    sketch_state: SketchState


class SketchDiagnoseArgs(BaseArgs):
    sketch_name: str | None = None


class SketchDiagnoseResult(ReadResult):
    sketch_name: str
    sketch_state: SketchState
    segment_count: int


class DimensionListArgs(BaseArgs):
    sketch_name: str | None = Field(
        default=None, description="Restrict to one sketch. Omit for every driving dimension."
    )
    unit: str = Field(default="mm", description="Unit to report lengths in.")
    configuration: str | None = Field(
        default=None,
        description=(
            "Read each dimension's value in this configuration rather than the active "
            "one. A dimension can hold a different value per configuration."
        ),
    )


class DimensionListResult(ReadResult):
    unit: str
    configuration: str | None = None
    dimensions: list[dict[str, Any]] = Field(default_factory=list)


class DimensionSetArgs(BaseArgs):
    name: str = Field(min_length=1, description="Dimension name, e.g. 'D1@Sketch1'.")
    value: Length = Field(description="New value.")
    rebuild: bool = Field(default=True, description="Rebuild after changing the value.")
    configuration_scope: Literal["this", "all", "specify"] = Field(
        default="all",
        description=(
            "Which configurations take the new value. 'all' is the default because a "
            "single-configuration part has only one, and a silent per-configuration "
            "write is a common way to change less than you meant to."
        ),
    )
    configurations: list[str] = Field(
        default_factory=list,
        max_length=200,
        description="Required when configuration_scope is 'specify'.",
    )


class DimensionSetResult(MutationResult):
    name: str
    before_mm: float
    after_mm: float
    requested_mm: float
    configuration_scope: str = "all"
    configurations: list[str] = Field(default_factory=list)


class SketchAutoDimensionArgs(BaseArgs):
    policy: Literal["baseline", "chain", "ordinate"] = Field(
        description=(
            "Required, with no default: CON-004 allows auto-dimensioning only under an "
            "explicit policy, because it creates dimensions the caller did not choose."
        )
    )
    sketch_name: str | None = None
    confirm: ConfirmField


class SketchAutoDimensionResult(MutationResult):
    sketch_name: str
    dimensions_before: int
    dimensions_after: int
    created: list[dict[str, Any]] = Field(default_factory=list)
    sketch_state: SketchState


class SketchConvertEntitiesArgs(BaseArgs):
    refs: list[EntityRef] = Field(
        min_length=1, max_length=100, description="Edges or faces to project into the sketch."
    )
    inner_loops: bool = Field(default=False, description="Also convert inner loops of a face.")


class SketchConvertEntitiesResult(MutationResult):
    sketch_name: str
    created: list[dict[str, Any]] = Field(default_factory=list)


class SketchModifyArgs(BaseArgs):
    operation: Literal["move", "rotate", "scale", "mirror", "trim", "offset"] = Field(
        description="Which modification to apply to the named segments."
    )
    segment_ids: list[str] = Field(default_factory=list, max_length=500)
    delta: Point2D | None = Field(default=None, description="Translation for 'move'.")
    angle: Angle | None = Field(default=None, description="Rotation angle.")
    about: Point2D | None = Field(
        default=None,
        description="Centre of rotation, or the fixed point a scale works from.",
    )
    factor: float | None = Field(default=None, gt=0, description="Scale factor.")
    distance: Length | None = Field(default=None, description="Offset distance.")
    mirror_axis_id: str | None = Field(default=None, description="Centerline to mirror about.")
    keep_original: bool = Field(
        default=False,
        description=(
            "Leave the original geometry in place and act on a copy. Supported by move, "
            "scale, mirror, and offset. Rotate transforms in place and refuses this "
            "rather than ignoring it."
        ),
    )
    confirm: ConfirmField


class SketchModifyResult(MutationResult):
    operation: str
    affected: int
    sketch_state: SketchState | None = None
