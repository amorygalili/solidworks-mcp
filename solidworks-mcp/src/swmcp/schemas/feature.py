"""Datum geometry, part features, bodies, and measurement."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import MutationResult, ReadResult
from swmcp.refs.model import EntityRef
from swmcp.schemas.common import BaseArgs, ConfirmField, StrictModel
from swmcp.units import Angle, Length

# --- datum --------------------------------------------------------------------


class DatumListArgs(BaseArgs):
    pass


class DatumListResult(ReadResult):
    planes: list[dict[str, Any]] = Field(default_factory=list)
    axes: list[dict[str, Any]] = Field(default_factory=list)
    points: list[dict[str, Any]] = Field(default_factory=list)
    coordinate_systems: list[dict[str, Any]] = Field(default_factory=list)
    origin: dict[str, Any] | None = None


class DatumPlaneCreateArgs(BaseArgs):
    method: Literal["offset", "angle", "mid", "three_point", "tangent"] = Field(
        description="How the plane is defined; each method needs a different reference count."
    )
    refs: list[EntityRef] = Field(
        default_factory=list,
        max_length=3,
        description="Reference entities, or use standard_plane for a standard plane.",
    )
    standard_plane: Literal["front", "top", "right"] | None = Field(
        default=None, description="Use a standard plane as the single reference."
    )
    distance: Length | None = Field(default=None, description="Offset distance for 'offset'.")
    angle: Angle | None = Field(default=None, description="Angle for 'angle'.")
    flip: bool = Field(default=False, description="Reverse the offset or angle direction.")
    name: str | None = Field(default=None, description="Rename the plane after creating it.")


class DatumPlaneCreateResult(MutationResult):
    plane_name: str
    method: str
    reference: dict[str, Any] | None = None


class DatumAxisCreateArgs(BaseArgs):
    method: Literal["one_line", "two_planes", "two_points", "cyl_face", "point_and_plane"] = (
        Field(
            description=(
                "How the axis is defined. SOLIDWORKS infers the axis type from the "
                "selection, so this drives the required reference count and is checked "
                "against what was actually created."
            )
        )
    )
    refs: list[EntityRef] = Field(
        default_factory=list,
        max_length=2,
        description="Reference entities. Combine with standard_planes to reach the count.",
    )
    standard_planes: list[Literal["front", "top", "right"]] = Field(
        default_factory=list,
        max_length=2,
        description="Standard planes used as references, e.g. two of them for 'two_planes'.",
    )
    auto_size: bool = Field(
        default=True, description="Let SOLIDWORKS size the axis to the surrounding geometry."
    )
    name: str | None = Field(default=None, description="Rename the axis after creating it.")


class DatumAxisCreateResult(MutationResult):
    axis_name: str
    method: str
    reference: dict[str, Any] | None = None


class DatumPointCreateArgs(BaseArgs):
    method: Literal[
        "along_curve",
        "arc_center",
        "face_center",
        "face_vertex_projection",
        "intersection",
        "sketch_point",
    ] = Field(
        description=(
            "What geometry the point is derived from. 'arc_center' needs a circular "
            "edge and lands on its centre; a straight edge is rejected by SOLIDWORKS, "
            "so use 'along_curve' with percentage 50 for an edge midpoint."
        )
    )
    refs: list[EntityRef] = Field(
        default_factory=list,
        min_length=1,
        max_length=8,
        description="The edges, faces, vertices, or sketch points the point is built on.",
    )
    along_curve: Literal["distance", "percentage", "evenly"] = Field(
        default="evenly",
        description="For 'along_curve': place by distance, by percentage, or evenly spaced.",
    )
    distance: Length | None = Field(
        default=None, description="Distance along the curve when along_curve is 'distance'."
    )
    percent: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Percentage along the curve when along_curve is 'percentage'.",
    )
    count: int = Field(
        default=1,
        ge=1,
        le=50,
        description="How many points to distribute when along_curve is 'evenly'.",
    )
    name: str | None = Field(default=None, description="Rename the point feature afterwards.")

    @model_validator(mode="after")
    def _placement_is_complete(self) -> DatumPointCreateArgs:
        """A placement mode without its value would silently become a point at zero."""
        if self.method != "along_curve":
            return self
        if self.along_curve == "distance" and self.distance is None:
            raise ValueError("along_curve='distance' needs a distance")
        if self.along_curve == "percentage" and self.percent is None:
            raise ValueError("along_curve='percentage' needs a percent")
        return self


class DatumPointCreateResult(MutationResult):
    point_names: list[str] = Field(default_factory=list)
    count: int
    method: str
    references: list[dict[str, Any]] = Field(default_factory=list)


class DatumCsysCreateArgs(BaseArgs):
    origin: EntityRef | None = Field(
        default=None,
        description="Vertex, sketch point, or reference point placed at the system's origin.",
    )
    x_axis: EntityRef | None = Field(default=None, description="Edge, axis, or line for +X.")
    y_axis: EntityRef | None = Field(default=None, description="Edge, axis, or line for +Y.")
    z_axis: EntityRef | None = Field(default=None, description="Edge, axis, or line for +Z.")
    flip_x: bool = Field(default=False, description="Reverse the resolved X direction.")
    flip_y: bool = Field(default=False, description="Reverse the resolved Y direction.")
    flip_z: bool = Field(default=False, description="Reverse the resolved Z direction.")
    name: str | None = Field(default=None, description="Rename the coordinate system afterwards.")

    @model_validator(mode="after")
    def _has_at_least_one_reference(self) -> DatumCsysCreateArgs:
        """With nothing selected SOLIDWORKS builds a system at the model origin.

        That is a legal feature but almost never what the caller meant, and it would
        come back verified — an identity transform is still a transform. Requiring one
        reference makes the empty call a validation error instead of a silent no-op.
        """
        if not any((self.origin, self.x_axis, self.y_axis, self.z_axis)):
            raise ValueError(
                "a coordinate system needs at least one of origin, x_axis, y_axis, or z_axis"
            )
        return self


class DatumCsysTransform(StrictModel):
    """The created system's placement, read back out of SOLIDWORKS."""

    rotation: list[list[float]] = Field(
        description="3x3 rotation matrix, row-major, mapping system axes into model space."
    )
    translation_mm: list[float] = Field(description="Origin position in millimetres.")
    scale: float = Field(description="Uniform scale factor; 1.0 for an ordinary system.")


class DatumCsysCreateResult(MutationResult):
    csys_name: str
    transform: DatumCsysTransform | None = None
    reference: dict[str, Any] | None = None


# --- features -----------------------------------------------------------------

EndCondition = Literal[
    "blind",
    "through_all",
    "through_all_both",
    "up_to_next",
    "up_to_vertex",
    "up_to_surface",
    "offset_from_surface",
    "mid_plane",
    "up_to_body",
]


class ExtrudeArgs(BaseArgs):
    sketch_name: str | None = Field(
        default=None, description="Profile sketch. Defaults to the most recent unused sketch."
    )
    end_condition: EndCondition = Field(
        default="blind",
        description=(
            "'through_all' reaches one way from the sketch plane, 'through_all_both' "
            "reaches both and needs no second direction - prefer it to a blind depth "
            "picked larger than the part, which silently cuts short if the guess is too "
            "small."
        ),
    )
    depth: Length = Field(default=10.0, description="Depth for blind and mid-plane conditions.")
    reverse: bool = Field(default=False, description="Extrude in the opposite direction.")
    draft: Angle = Field(default=0.0, description="Draft angle.")
    draft_outward: bool = False
    merge_result: bool = Field(
        default=True, description="Merge with existing bodies rather than creating a new one."
    )
    thin_thickness: Length | None = Field(
        default=None, description="Wall thickness for a thin feature. Omit for a solid extrude."
    )
    second_direction: bool = Field(
        default=False,
        description=(
            "Also extrude the other way, to second_depth. Implied by "
            "'through_all_both', which sets both directions itself."
        ),
    )
    second_depth: Length = Field(default=10.0, description="Depth of the second direction.")
    name: str | None = None


class ExtrudeResult(MutationResult):
    feature_name: str
    feature_type: str
    body_count_before: int
    body_count_after: int
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None
    reference: dict[str, Any] | None = None


class RevolveArgs(BaseArgs):
    mode: Literal["boss", "cut"] = Field(
        default="boss",
        description="Add material or remove it. The option set is identical either way.",
    )
    sketch_name: str | None = None
    axis_ref: EntityRef | None = Field(
        default=None, description="Axis of revolution. Defaults to a centerline in the sketch."
    )
    angle: Angle = Field(default=360.0)
    reverse: bool = False
    merge_result: bool = True
    thin_thickness: Length | None = None
    name: str | None = None


class RevolveResult(MutationResult):
    feature_name: str
    mode: str
    body_count_before: int
    body_count_after: int
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None


# --- draft --------------------------------------------------------------------

DraftPropagation = Literal["none", "tangent", "all_loops", "inner_loops", "outer_loops"]


class DraftArgs(BaseArgs):
    method: Literal["neutral_plane", "parting_line", "step"] = Field(
        default="neutral_plane",
        description=(
            "Neutral plane tapers faces away from a reference; parting line drafts from "
            "selected edges; step draft adds a step at the parting line."
        ),
    )
    angle: Angle = Field(description="Draft angle. Positive tapers away from the neutral plane.")
    neutral_ref: EntityRef | None = Field(
        default=None,
        description="Planar face or plane the draft is measured from, or the pull direction.",
    )
    neutral_standard_plane: Literal["front", "top", "right"] | None = Field(
        default=None, description="Use a standard plane as the neutral reference instead."
    )
    face_refs: list[EntityRef] = Field(
        default_factory=list,
        max_length=64,
        description="Faces to draft. Required for neutral_plane and step.",
    )
    edge_refs: list[EntityRef] = Field(
        default_factory=list,
        max_length=64,
        description="Edges defining the parting line. Required for parting_line.",
    )
    flip: bool = Field(
        default=False,
        description=(
            "Reverse the taper. Unflipped, SOLIDWORKS drafts outward and the part gains "
            "material; measured, not assumed."
        ),
    )
    propagation: DraftPropagation = Field(
        default="none", description="How far the draft spreads from the selected faces."
    )
    body_draft: bool = Field(default=False, description="Draft the whole body.")
    name: str | None = None

    @model_validator(mode="after")
    def _selection_matches_the_method(self) -> DraftArgs:
        """Each method reads a different selection, and the wrong one builds nothing."""
        if self.neutral_ref is None and self.neutral_standard_plane is None:
            raise ValueError("a draft needs neutral_ref or neutral_standard_plane")
        if self.neutral_ref is not None and self.neutral_standard_plane is not None:
            raise ValueError("give either neutral_ref or neutral_standard_plane, not both")
        if self.method == "parting_line" and not self.edge_refs:
            raise ValueError("parting_line drafting needs edge_refs")
        if self.method != "parting_line" and not self.face_refs and not self.body_draft:
            raise ValueError(f"{self.method!r} drafting needs face_refs, or body_draft=true")
        return self


class DraftResult(MutationResult):
    feature_name: str
    method: str
    faces_drafted: int = 0
    edges_used: int = 0
    body_count_before: int
    body_count_after: int
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None
    reference: dict[str, Any] | None = None


# --- sweep and loft -----------------------------------------------------------

#: Profile orientation along the path. These are the SOLIDWORKS "Profile Twist"
#: options; the API splits them across TwistControlType and PathAlignmentType, which
#: is why the caller picks one word and the handler sets both.
SweepOrientation = Literal[
    "follow_path",
    "keep_normal_constant",
    "follow_path_and_first_guide",
    "follow_first_and_second_guide",
    "constant_twist_along_path",
]

TangencyType = Literal["none", "normal_to_profile", "direction_vector", "all_faces"]


class SweepArgs(BaseArgs):
    mode: Literal["boss", "cut"] = Field(
        default="boss",
        description="Add material or remove it. The option set is identical either way.",
    )
    profile_sketch: str = Field(
        min_length=1,
        description=(
            "Closed sketch swept along the path. Named explicitly rather than guessed: "
            "a sweep always has at least two sketches in play, so 'the most recent one' "
            "would be a coin flip."
        ),
    )
    path_sketch: str | None = Field(
        default=None, description="Sketch whose curves form the sweep path."
    )
    path_ref: EntityRef | None = Field(
        default=None, description="Model edge used as the path instead of a sketch."
    )
    guide_sketches: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Guide curve sketches. Each must touch the profile or a point on it.",
    )
    guide_refs: list[EntityRef] = Field(
        default_factory=list, max_length=8, description="Guide curves given as entity references."
    )
    orientation: SweepOrientation = Field(
        default="follow_path", description="How the profile is oriented as it travels the path."
    )
    twist_angle: Angle | None = Field(
        default=None,
        description="End twist angle; only used when orientation is constant_twist_along_path.",
    )
    direction: Literal["forward", "reverse", "bidirectional"] = Field(
        default="forward",
        description=(
            "Only meaningful when the path extends through both sides of the profile; "
            "SOLIDWORKS ignores it otherwise."
        ),
    )
    merge_result: bool = Field(default=True, description="Merge into existing bodies.")
    merge_smooth_faces: bool = True
    align_with_end_faces: bool = Field(
        default=False, description="Run the sweep through end faces rather than stopping square."
    )
    tangent_propagation: bool = Field(
        default=False, description="Propagate the sweep to the next tangent edge."
    )
    thin_thickness: Length | None = Field(
        default=None, description="Wall thickness for a thin sweep. Omit for a solid one."
    )
    thin_direction: Literal["outward", "inward", "mid_plane", "both"] = Field(
        default="outward",
        description=(
            "Which side of the profile the wall is added to. Measured, not assumed: "
            "'outward' grows the wall away from the profile, so a thin sweep of a "
            "circle r=5 with a 1 mm wall is the annulus between r=5 and r=6, not "
            "between r=4 and r=5. Use 'inward' to keep the profile as the outer wall."
        ),
    )
    name: str | None = None

    @model_validator(mode="after")
    def _has_exactly_one_path(self) -> SweepArgs:
        """No path means SOLIDWORKS sweeps nothing; two means the caller is guessing."""
        if (self.path_sketch is None) == (self.path_ref is None):
            raise ValueError("a sweep needs exactly one of path_sketch or path_ref")
        if self.orientation == "constant_twist_along_path" and self.twist_angle is None:
            raise ValueError("orientation='constant_twist_along_path' needs a twist_angle")
        return self


class SweepResult(MutationResult):
    feature_name: str
    mode: str
    profile_sketch: str
    path: str
    guide_curve_count: int = 0
    body_count_before: int
    body_count_after: int
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None
    reference: dict[str, Any] | None = None


class LoftArgs(BaseArgs):
    mode: Literal["boss", "cut"] = Field(
        default="boss", description="Add material or remove it."
    )
    profile_sketches: list[str] = Field(
        min_length=2,
        max_length=32,
        description=(
            "Closed profiles, in the order the loft should run through them. Order is "
            "the shape: SOLIDWORKS lofts in selection order, not tree order."
        ),
    )
    guide_sketches: list[str] = Field(
        default_factory=list, max_length=8, description="Guide curve sketches."
    )
    centerline_sketch: str | None = Field(
        default=None, description="Centerline the loft follows between profiles."
    )
    closed: bool = Field(
        default=False, description="Close the loft back to the first profile."
    )
    keep_tangency: bool = Field(
        default=True, description="Keep tangency where the section curves are tangent."
    )
    start_tangency: TangencyType = "none"
    end_tangency: TangencyType = "none"
    merge_result: bool = True
    thin_thickness: Length | None = Field(
        default=None, description="Wall thickness for a thin loft. Omit for a solid one."
    )
    name: str | None = None

    @model_validator(mode="after")
    def _profiles_are_distinct(self) -> LoftArgs:
        """The same sketch twice cannot define a section, and SOLIDWORKS will not say so."""
        if len(set(self.profile_sketches)) != len(self.profile_sketches):
            raise ValueError("profile_sketches must not repeat a sketch")
        return self


class LoftResult(MutationResult):
    feature_name: str
    mode: str
    profile_sketches: list[str] = Field(default_factory=list)
    guide_curve_count: int = 0
    centerline: str | None = None
    body_count_before: int
    body_count_after: int
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None
    reference: dict[str, Any] | None = None


class EdgeQuery(StrictModel):
    """Choose edges by what they are, instead of capturing every one of them first.

    Rounding the edges of a shape means naming them, and naming them one at a time is
    the slow, brittle half of the job: a knight's head has dozens, each needing a probe
    and a captured reference, and any of them can go stale. The predicate says the thing
    the caller actually means - "every edge on this body longer than 2mm" - and is
    resolved through the same probe that backs sw_probe_faces, so it matches whatever
    that already reports.
    """

    body_name: str | None = Field(
        default=None, description="Restrict to one body. Omit to search them all."
    )
    feature_name: str | None = Field(
        default=None,
        description="Restrict to the edges a named feature created. Takes precedence "
        "over body_name, matching sw_probe_faces.",
    )
    geometry_type: str | None = Field(
        default=None, description="Edge geometry, e.g. 'line' or 'circle'."
    )
    min_length: Length | None = Field(
        default=None,
        description="Skip edges shorter than this. The usual guard: a fillet larger "
        "than the edge it is applied to is how the feature fails.",
    )
    max_length: Length | None = Field(default=None, description="Skip edges longer than this.")
    limit: int = Field(
        default=200,
        ge=1,
        le=200,
        description="Most edges to take, longest first. Capped at what the feature "
        "itself accepts, so a selection can never be silently truncated later.",
    )


def _one_way_of_naming_edges(model: Any, kind: str) -> None:
    """Refuse both or neither, rather than quietly preferring one."""
    if bool(model.refs) == (model.edges is not None):
        raise ValueError(
            f"A {kind} needs exactly one of refs or edges: refs names the entities "
            "explicitly, edges describes them and lets the server find them."
        )


class FilletArgs(BaseArgs):
    refs: list[EntityRef] = Field(
        default_factory=list, max_length=200, description="Edges or faces to round."
    )
    edges: EdgeQuery | None = Field(
        default=None,
        description="Select the edges by predicate instead of naming them. Give this "
        "or refs, not both.",
    )
    radius: Length = Field(gt=0)
    kind: Literal["constant", "variable_ends"] = "constant"
    propagate: bool = Field(default=True, description="Continue across tangent edges.")
    name: str | None = None

    @model_validator(mode="after")
    def _edges_named_once(self) -> FilletArgs:
        _one_way_of_naming_edges(self, "fillet")
        return self


class ChamferArgs(BaseArgs):
    refs: list[EntityRef] = Field(default_factory=list, max_length=200)
    edges: EdgeQuery | None = Field(
        default=None,
        description="Select the edges by predicate instead of naming them. Give this "
        "or refs, not both.",
    )
    distance: Length = Field(gt=0)
    angle: Angle = Field(default=45.0, description="Used by the angle-distance chamfer.")
    kind: Literal["angle_distance", "equal_distance"] = "equal_distance"
    propagate: bool = True
    name: str | None = None

    @model_validator(mode="after")
    def _edges_named_once(self) -> ChamferArgs:
        _one_way_of_naming_edges(self, "chamfer")
        return self


class EdgeFeatureResult(MutationResult):
    feature_name: str
    feature_type: str
    edges_selected: int
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None
    edges_examined: int | None = Field(
        default=None,
        description=(
            "How many edges the predicate looked at, when one was used. The ratio of "
            "matched to examined is what says whether the predicate meant what you "
            "thought - 4 of 400 is a typo, not a selection."
        ),
    )
    edges_matched: int | None = Field(
        default=None,
        description="How many the predicate chose, before the feature was attempted.",
    )


class PatternArgs(BaseArgs):
    type: Literal["linear", "circular"] = Field(
        description=(
            "Only linear and circular are supported. Curve-driven, sketch-driven, "
            "table-driven, fill, and variable patterns are rejected here rather than "
            "failing at runtime."
        )
    )
    feature_names: list[str] = Field(
        min_length=1, max_length=50, description="Features to repeat."
    )
    direction_ref: EntityRef | None = Field(
        default=None, description="Edge, axis, or planar face giving the first direction."
    )
    standard_axis: Literal["x", "y", "z"] | None = Field(
        default=None,
        description=(
            "Shorthand for the model's own X, Y or Z axis, so patterning about the "
            "part's centreline does not need an EntityRef captured from geometry that "
            "may not exist yet. Resolved as the intersection of two standard planes; "
            "SOLIDWORKS can only pattern about a real axis, so a reference axis named "
            "'swmcp_axis_<x|y|z>' is added to the tree the first time and reused after "
            "that. Give this or direction_ref, not both."
        ),
    )
    count: int = Field(ge=2, le=1000, description="Total instances including the original.")
    spacing: Length = Field(default=10.0, description="Spacing for a linear pattern.")
    angle: Angle = Field(default=90.0, description="Total or per-instance angle for circular.")
    equal_spacing: bool = Field(default=True, description="Circular: spread instances evenly.")
    second_direction_ref: EntityRef | None = None
    second_count: int = Field(default=1, ge=1, le=1000)
    second_spacing: Length = Field(default=10.0)
    reverse: bool = False
    name: str | None = None

    @model_validator(mode="after")
    def _one_direction_only(self) -> PatternArgs:
        if self.direction_ref is not None and self.standard_axis is not None:
            raise ValueError(
                "Give direction_ref or standard_axis, not both: naming two directions "
                "would leave the handler quietly preferring one of them."
            )
        return self


class PatternResult(MutationResult):
    feature_name: str
    pattern_type: str
    instances_requested: int
    body_count_before: int
    body_count_after: int
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None
    axis_name: str | None = Field(
        default=None,
        description=(
            "The reference axis the pattern turned about, when standard_axis resolved "
            "one. Named so a later call reuses it instead of adding another."
        ),
    )
    axis_was_created: bool = Field(
        default=False,
        description=(
            "True when this call added that axis to the feature tree. A shorthand that "
            "changes the tree should say so rather than let the caller find it later."
        ),
    )


HoleKind = Literal["simple", "counterbore", "countersink", "tapped"]


class HoleArgs(BaseArgs):
    strategy: Literal["auto", "hole_wizard", "simple_hole", "cut_extrude"] = Field(
        default="auto",
        description=(
            "'auto' probes for Hole Wizard support and falls back, always reporting "
            "which strategy was actually used. A tapped hole is never silently "
            "downgraded to a plain cut."
        ),
    )
    kind: HoleKind = "simple"
    face_ref: EntityRef = Field(description="Face to place the hole on.")
    at: list[Length] = Field(
        min_length=3, max_length=3, description="Hole centre in model coordinates [x, y, z]."
    )
    diameter: Length = Field(gt=0)
    depth: Length | None = Field(default=None, description="Omit for a through hole.")
    through_all: bool = False
    counterbore_diameter: Length | None = None
    counterbore_depth: Length | None = None
    countersink_angle: Angle = Field(default=90.0)
    name: str | None = None

    @model_validator(mode="after")
    def _check_kind_inputs(self) -> HoleArgs:
        if self.kind == "counterbore" and (
            self.counterbore_diameter is None or self.counterbore_depth is None
        ):
            raise ValueError(
                "a counterbore needs counterbore_diameter and counterbore_depth"
            )
        if not self.through_all and self.depth is None:
            raise ValueError("give a depth, or set through_all=true")
        return self


class HoleResult(MutationResult):
    feature_name: str
    strategy_used: str
    kind: str
    holes_found: int = Field(description="Cylindrical faces matching the requested diameter.")
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None


class FeatureListArgs(BaseArgs):
    include_suppressed: bool = True
    types: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Filter by GetTypeName2 token, e.g. ['Extrusion', 'Fillet'].",
    )


class FeatureListResult(ReadResult):
    count: int
    features: list[dict[str, Any]] = Field(default_factory=list)


class FeatureEditArgs(BaseArgs):
    feature_name: str = Field(min_length=1)
    rename_to: str | None = None
    suppress: bool | None = Field(
        default=None, description="True suppresses the feature, False unsuppresses it."
    )


class FeatureEditResult(MutationResult):
    feature_name: str
    renamed_to: str | None = None
    suppressed: bool | None = None


class FeatureDeleteArgs(BaseArgs):
    feature_name: str = Field(min_length=1)
    delete_children: bool = Field(
        default=False, description="Also delete features that depend on this one."
    )
    confirm: ConfirmField


class FeatureDeleteResult(MutationResult):
    feature_name: str
    deleted: bool
    features_before: int
    features_after: int
    also_removed: list[str] = Field(
        default_factory=list,
        description=(
            "Other features that went with it - absorbed sketches, dependent features. "
            "A delete that quietly takes more than it was asked for should say what."
        ),
    )


class BodyListArgs(BaseArgs):
    include_surfaces: bool = True


class BodyListResult(ReadResult):
    count: int
    bodies: list[dict[str, Any]] = Field(default_factory=list)


class MeasureScope(StrictModel):
    document: bool = Field(default=True, description="Measure every solid body.")
    body_name: str | None = None
    feature_name: str | None = None
    ref: EntityRef | None = Field(default=None, description="Measure a single face or edge.")


class MeasureArgs(BaseArgs):
    scope: MeasureScope = Field(default_factory=MeasureScope)
    unit: str = Field(default="mm", description="Unit for reported lengths.")


class MeasureResult(ReadResult):
    unit: str
    scope: str
    mass_properties: dict[str, Any] = Field(default_factory=dict)
    bounding_box: dict[str, Any] = Field(default_factory=dict)
    topology: dict[str, Any] = Field(default_factory=dict)
    entity: dict[str, Any] | None = None
    validity: dict[str, Any] = Field(default_factory=dict)
