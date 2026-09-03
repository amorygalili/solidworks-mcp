"""Sketch geometry, relations, and dimensions.

``SketchEntity`` is a discriminated union rather than one tool per shape. SK-003
enumerates thirteen primitives as a single requirement; thirteen tools would be a
fifth of the whole surface, and batching a profile into one call turns thirteen COM
round trips on the STA thread into one.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

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


#: ``swSketchSlotLengthType_e``. This selects how SOLIDWORKS *dimensions* the slot, not
#: how it is shaped: measured either way, the same points and width produce identical
#: geometry, and the setting only becomes visible once ``add_dimension`` is true.
SlotLength = Literal["center_to_center", "overall"]


class SlotStraightEntity(_Segment):
    """A straight slot between two centre points."""

    type: Literal["slot_straight"] = "slot_straight"
    start: Point2D
    end: Point2D
    width: Length = Field(gt=0)
    length_type: SlotLength = "center_to_center"
    add_dimension: bool = Field(
        default=False,
        description=(
            "Add SOLIDWORKS' automatic slot dimension, expressed the way length_type "
            "says. Without this the slot is under-defined and length_type does nothing."
        ),
    )


class SlotCenterpointEntity(_Segment):
    """A straight slot given its middle and one end, rather than both ends."""

    type: Literal["slot_centerpoint"] = "slot_centerpoint"
    center: Point2D
    end: Point2D
    width: Length = Field(gt=0)
    length_type: SlotLength = "center_to_center"
    add_dimension: bool = Field(
        default=False,
        description=(
            "Add SOLIDWORKS' automatic slot dimension, expressed the way length_type "
            "says. Without this the slot is under-defined and length_type does nothing."
        ),
    )


class SlotArcEntity(_Segment):
    """An arc slot swept about a centre point.

    A semicircular slot is this with ``start`` and ``end`` diametrically opposite the
    centre; SOLIDWORKS has no separate semicircular slot type.
    """

    type: Literal["slot_arc"] = "slot_arc"
    center: Point2D
    start: Point2D
    end: Point2D
    width: Length = Field(gt=0)
    direction: Literal["clockwise", "counterclockwise"] = "counterclockwise"
    length_type: SlotLength = "center_to_center"
    add_dimension: bool = Field(
        default=False,
        description=(
            "Add SOLIDWORKS' automatic slot dimension, expressed the way length_type "
            "says. Without this the slot is under-defined and length_type does nothing."
        ),
    )


class SlotArc3PointEntity(_Segment):
    """An arc slot through three points on its centreline."""

    type: Literal["slot_3point_arc"] = "slot_3point_arc"
    start: Point2D
    end: Point2D
    through: Point2D = Field(description="A point the slot centreline passes through.")
    width: Length = Field(gt=0)
    length_type: SlotLength = "center_to_center"
    add_dimension: bool = Field(
        default=False,
        description=(
            "Add SOLIDWORKS' automatic slot dimension, expressed the way length_type "
            "says. Without this the slot is under-defined and length_type does nothing."
        ),
    )


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
    | SlotCenterpointEntity
    | SlotArcEntity
    | SlotArc3PointEntity
    | SplineEntity,
    Field(discriminator="type"),
]


class SketchTextArgs(BaseArgs):
    """SK-008. Font is deliberately absent — see the handler for why."""

    text: str = Field(min_length=1, max_length=1000, description="The characters to draw.")
    at: Point2D = Field(
        default_factory=lambda: [0.0, 0.0],
        description="Start of the text block. Ignored when the text follows a path.",
    )
    path_segment_id: str | None = Field(
        default=None,
        description=(
            "Sketch segment in this sketch for the text to run along. Alignment and "
            "flip only mean anything with a path; without one the text sits horizontally."
        ),
    )
    alignment: Literal["left", "center", "right", "justified"] = "left"
    flip_vertical: bool = False
    mirror_horizontal: bool = False
    width_factor: int = Field(
        default=100, ge=6, le=1667, description="Percentage width of each character."
    )
    char_spacing: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Percentage spacing between characters. SOLIDWORKS ignores it when "
        "alignment is 'justified'.",
    )
    sketch_name: str | None = Field(
        default=None, description="Sketch to draw into. Defaults to the open one."
    )

    @model_validator(mode="after")
    def _alignment_needs_a_path(self) -> SketchTextArgs:
        """Without a path SOLIDWORKS ignores alignment, so asking for it is a mistake."""
        if self.path_segment_id is None and self.alignment != "left":
            raise ValueError(
                "alignment only applies to text on a path; give path_segment_id or "
                "leave alignment as 'left'"
            )
        if self.path_segment_id is None and self.flip_vertical:
            raise ValueError("flip_vertical only applies to text on a path")
        return self


class SketchTextResult(MutationResult):
    sketch_name: str
    text: str
    on_path: bool
    text_segment_count: int
    alignment: str
    sketch_state: SketchState


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


#: Shared wording: the same field appears on every result that names a sketch.
FRAME_DESCRIPTION = (
    "Where this sketch's own axes point in model space: the origin, the model "
    "direction of sketch +X and +Y, the plane normal, and a 'maps' sentence stating "
    "it in words. Without this, which way a sketch coordinate runs in the model has "
    "to be guessed and then confirmed from a finished body's bounding box."
)


class SketchStartResult(MutationResult):
    sketch_name: str
    plane: str
    frame: dict[str, Any] | None = Field(default=None, description=FRAME_DESCRIPTION)


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


#: Above this many created segments, ``detail="auto"`` stops restating every field of
#: every entity. A 240-segment profile returned 64 KB describing geometry the caller had
#: just supplied, which is the bulk of what one of these calls costs to read.
CREATED_DETAIL_LIMIT = 60

#: What a ``created`` entry keeps when the batch is compacted. The handle is the load
#: bearing part - relations, dimensions and deletes all address segments by it - so
#: compacting must never drop it.
_COMPACT_KEYS = ("index", "requested_type", "sketch_local_id", "type")

DetailLevel = Literal["auto", "full", "compact"]


def compact_created(
    created: list[dict[str, Any]], detail: DetailLevel
) -> tuple[list[dict[str, Any]], bool]:
    """Trim ``created`` entries to their handles, and say whether that happened.

    Anything that landed away from the coordinates it was given keeps its full entry
    whatever the mode: those are the entries a caller actually has to look at.
    """
    if detail == "full" or (detail == "auto" and len(created) <= CREATED_DETAIL_LIMIT):
        return created, False
    trimmed = [
        entry
        if entry.get("deviation_mm")
        else {key: entry[key] for key in _COMPACT_KEYS if key in entry}
        for entry in created
    ]
    return trimmed, True


class DetailMixin(StrictModel):
    detail: DetailLevel = Field(
        default="auto",
        description=(
            "How much to say about each created segment. 'full' describes every one; "
            "'compact' returns only the handle, type and index; 'auto' (the default) "
            f"is full up to {CREATED_DETAIL_LIMIT} segments and compact beyond that. "
            "Handles are always returned, so relations, dimensions and deletes can "
            "still address the geometry. Entities that landed off their requested "
            "coordinates keep full detail in every mode."
        ),
    )


class SketchAddGeometryArgs(BaseArgs, PreflightMixin, DetailMixin):
    entities: list[SketchEntity] = Field(
        default_factory=list,
        max_length=500,
        description=(
            "Sketch primitives to create, in order. Give this or entities_file, not "
            "both."
        ),
    )
    entities_file: str | None = Field(
        default=None,
        description=(
            "Path to a UTF-8 JSON file holding the same list, so a generated profile "
            "does not have to travel through the request. Either a bare array of "
            "entities or an object with an 'entities' key. A few hundred splined "
            "segments is tens of kilobytes of argument otherwise, and anything that "
            "computes a profile has already written it to a file."
        ),
    )
    sketch_name: str | None = Field(
        default=None,
        description="Sketch to edit. Defaults to the sketch currently open for editing.",
    )
    auto_relations: bool = Field(
        default=True,
        description=(
            "Let SOLIDWORKS infer relations as each primitive is drawn. Inference snaps "
            "new geometry onto whatever is already nearby, which silently moves "
            "endpoints off the coordinates you gave - convenient when sketching by "
            "hand, wrong when the coordinates are the specification. Pass false to "
            "place geometry exactly as written; the trade is that no coincident "
            "relations are added, so segments meet by position rather than by "
            "constraint. Either way the result reports how far each point actually "
            "landed from the one asked for."
        ),
    )

    @model_validator(mode="after")
    def _one_source_of_entities(self):
        """Exactly one of the two, and never zero.

        ``entities`` lost its ``min_length=1`` when the file route arrived, so an empty
        request would otherwise validate and open an empty sketch.
        """
        if bool(self.entities) == bool(self.entities_file):
            raise ValueError(
                "Give either entities or entities_file, not both and not neither."
            )
        return self


class SketchAddGeometryResult(MutationResult):
    sketch_name: str
    created: list[dict[str, Any]] = Field(default_factory=list)
    failed: list[dict[str, Any]] = Field(default_factory=list)
    sketch_state: SketchState
    max_deviation_mm: float | None = Field(
        default=None,
        description=(
            "Worst gap between a requested coordinate and where the geometry actually "
            "landed. None when no entity in the batch had checkable anchor points."
        ),
    )
    created_total: int = Field(
        default=0, description="How many segments were created, however much detail is shown."
    )
    created_compacted: bool = Field(
        default=False,
        description=(
            "True when 'created' entries were trimmed to their handles. Nothing is "
            "omitted from the list; each entry says less."
        ),
    )


class SketchCreateArgs(BaseArgs, DetailMixin):
    """Open a sketch, draw a profile, and close it - the whole cadence in one call.

    Starting a sketch, adding geometry and exiting are three separate operations
    because they are three separate things, but almost nobody wants them apart: every
    profile in a part is that exact sequence, and on a serialized COM thread the two
    extra round trips buy nothing. Building six chess pieces took about sixty calls,
    most of them this pattern.
    """

    on: SketchPlaneTarget
    entities: list[SketchEntity] = Field(
        default_factory=list,
        max_length=500,
        description=(
            "Sketch primitives to create, in order. Give this or entities_file, not "
            "both."
        ),
    )
    entities_file: str | None = Field(
        default=None,
        description=(
            "Path to a UTF-8 JSON file holding the same list, so a generated profile "
            "does not have to travel through the request. Either a bare array of "
            "entities or an object with an 'entities' key. A few hundred splined "
            "segments is tens of kilobytes of argument otherwise, and anything that "
            "computes a profile has already written it to a file."
        ),
    )
    auto_relations: bool = Field(
        default=True,
        description=(
            "As on sw_sketch_add_geometry: false places geometry at exactly the "
            "coordinates given, instead of letting SOLIDWORKS snap it onto neighbours."
        ),
    )
    exit_sketch: bool = Field(
        default=True,
        description=(
            "Close the sketch when the geometry is in. Leave it open only to keep "
            "adding relations or dimensions before a feature consumes it."
        ),
    )
    rebuild: bool = Field(default=True, description="Rebuild the model on exiting.")

    @model_validator(mode="after")
    def _one_source_of_entities(self):
        """Exactly one of the two, and never zero.

        ``entities`` lost its ``min_length=1`` when the file route arrived, so an empty
        request would otherwise validate and open an empty sketch.
        """
        if bool(self.entities) == bool(self.entities_file):
            raise ValueError(
                "Give either entities or entities_file, not both and not neither."
            )
        return self


class SketchCreateResult(MutationResult):
    sketch_name: str
    plane: str | None = None
    created: list[dict[str, Any]] = Field(default_factory=list)
    failed: list[dict[str, Any]] = Field(default_factory=list)
    sketch_state: SketchState
    max_deviation_mm: float | None = None
    created_total: int = 0
    created_compacted: bool = False
    exited: bool = False
    frame: dict[str, Any] | None = Field(default=None, description=FRAME_DESCRIPTION)
    contours: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "The profile topology of what was just drawn, so whether it closes is known "
            "before a revolve or extrude is attempted rather than after one is refused."
        ),
    )


class SketchDeriveArgs(BaseArgs, DetailMixin):
    source_sketch: str = Field(
        description="The sketch to copy geometry from. It is read, never modified."
    )
    on: SketchPlaneTarget = Field(description="Where the derived sketch goes.")
    scale: float = Field(
        default=1.0,
        gt=0,
        description=(
            "Uniform scale about 'about'. Only uniform: a non-uniform scale turns a "
            "circle into an ellipse and an arc into a curve with no arc_center spec, "
            "so the derived sketch could not be expressed at all."
        ),
    )
    rotate: Angle = Field(default=0, description="Rotation about 'about'.")
    translate: list[Length] = Field(
        default_factory=lambda: [0.0, 0.0],
        min_length=2,
        max_length=2,
        description="Applied last, after mirror, scale and rotation.",
    )
    mirror: Literal["x", "y"] | None = Field(
        default=None,
        description=(
            "Mirror across the named sketch axis through 'about'. This reverses every "
            "arc's direction, which is done for you: leaving it alone would rebuild "
            "each arc as its own complement, with identical endpoints and no complaint."
        ),
    )
    about: list[Length] = Field(
        default_factory=lambda: [0.0, 0.0],
        min_length=2,
        max_length=2,
        description="The fixed point for scale, rotation and mirror. Sketch origin by default.",
    )
    include_construction: bool = Field(
        default=True, description="Carry construction geometry across as construction."
    )
    exit_sketch: bool = Field(default=True, description="Close the sketch when the geometry is in.")
    rebuild: bool = Field(default=True, description="Rebuild the model on exiting.")


class SketchDeriveResult(MutationResult):
    sketch_name: str
    source_sketch: str
    plane: str | None = None
    created: list[dict[str, Any]] = Field(default_factory=list)
    created_total: int = 0
    created_compacted: bool = False
    failed: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Source segments that have no lossless primitive spec - an ellipse, a "
            "parabola, sketch text. Named rather than dropped, because a derived "
            "sketch quietly missing a segment is a profile that will not close."
        ),
    )
    sketch_state: SketchState
    max_deviation_mm: float | None = None
    exited: bool = False
    frame: dict[str, Any] | None = Field(default=None, description=FRAME_DESCRIPTION)
    contours: dict[str, Any] = Field(default_factory=dict)


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
    sketch_name: str | None = Field(
        default=None,
        description=(
            "Sketch to edit, as on sw_sketch_add_geometry. Defaults to the sketch "
            "currently open for editing. Naming a closed sketch opens it, deletes, and "
            "closes it again; another sketch already open is refused rather than shut "
            "on your behalf."
        ),
    )
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
    frame: dict[str, Any] | None = Field(default=None, description=FRAME_DESCRIPTION)
    contours: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Profile topology: how many closed contours the sketch holds, and where "
            "the ones that do not close come apart. Revolve and extrude need a closed "
            "contour, which the solver status does not report - a fully defined sketch "
            "can still have a gap, and an under-defined one can close perfectly."
        ),
    )


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
