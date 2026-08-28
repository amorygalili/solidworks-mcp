"""Body-level modelling: shell, rib, and primitives.

FEAT-014 asks for "direct/composed primitive workflows". Composed is what this is: a
primitive here is a sketch and a boss built by the same operations a caller could run
by hand, so the feature tree stays editable and the result is verified the same way.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import MutationResult
from swmcp.refs.model import EntityRef
from swmcp.schemas.common import BaseArgs
from swmcp.units import Angle, Length

StandardPlane = Literal["front", "top", "right"]
Point2D = list[Length]


class ShellArgs(BaseArgs):
    thickness: Length = Field(gt=0, description="Wall thickness.")
    face_refs: list[EntityRef] = Field(
        default_factory=list,
        max_length=50,
        description="Faces to remove, leaving the shell open there. Empty hollows the body.",
    )
    outward: bool = Field(
        default=False, description="Add the wall outside the original surface rather than inside."
    )
    name: str | None = None


class ShellResult(MutationResult):
    feature_name: str
    faces_removed: int
    thickness_mm: float
    outward: bool
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None
    face_count_before: int
    face_count_after: int


class RibArgs(BaseArgs):
    thickness: Length = Field(gt=0, description="Total rib thickness.")
    sketch_name: str | None = Field(
        default=None, description="Open profile to thicken. Defaults to the newest unused sketch."
    )
    both_sides: bool = Field(
        default=True, description="Grow the thickness either side of the sketch."
    )
    reverse_thickness: bool = False
    reverse_material: bool = Field(
        default=False,
        description="Flip which way the rib grows toward the body. If the rib misses the "
        "body entirely, this is the argument to change.",
    )
    normal_to_sketch: bool = Field(
        default=False,
        description=(
            "Extrude the rib normal to its sketch plane rather than parallel to it. The "
            "default is parallel, which is what the usual workflow wants: a profile "
            "drawn on a plane cutting through the solid, thickened either side of that "
            "plane. Normal-to-sketch is measurably a no-op for that arrangement."
        ),
    )
    draft_angle: Angle | None = Field(default=None, description="Draft the rib walls.")
    draft_outward: bool = False
    name: str | None = None


class RibResult(MutationResult):
    feature_name: str
    thickness_mm: float
    volume_mm3_before: float | None = None
    volume_mm3_after: float | None = None


# --- primitives ---------------------------------------------------------------

PrimitiveKind = Literal[
    "box",
    "cylinder",
    "sphere",
    "cone",
    "frustum",
    "torus",
    "wedge",
    "prism",
]


#: What each primitive needs. Missing dimensions are a schema rejection, so a caller
#: never gets a half-built solid because one field was forgotten.
PRIMITIVE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "box": ("width", "depth", "height"),
    "cylinder": ("radius", "height"),
    "sphere": ("radius",),
    "cone": ("radius", "height"),
    "frustum": ("radius", "top_radius", "height"),
    "torus": ("radius", "tube_radius"),
    "wedge": ("width", "depth", "height"),
    "prism": ("radius", "sides", "height"),
}


class PrimitiveArgs(BaseArgs):
    kind: PrimitiveKind = Field(description="Which primitive to build.")
    plane: StandardPlane = Field(
        default="front", description="Standard plane the defining sketch is drawn on."
    )
    at: Point2D = Field(
        default_factory=lambda: [0.0, 0.0],
        min_length=2,
        max_length=2,
        description="Where the primitive is centred in the sketch plane.",
    )

    width: Length | None = Field(default=None, gt=0, description="Box and wedge: X size.")
    depth: Length | None = Field(default=None, gt=0, description="Box and wedge: Y size.")
    height: Length | None = Field(
        default=None, gt=0, description="Extrusion or revolve height for every solid that has one."
    )
    radius: Length | None = Field(
        default=None, gt=0, description="Cylinder, sphere, cone base, torus tube centre, prism."
    )
    top_radius: Length | None = Field(
        default=None, ge=0, description="Frustum only: the radius at the top."
    )
    tube_radius: Length | None = Field(
        default=None, gt=0, description="Torus only: the radius of the tube itself."
    )
    sides: int | None = Field(default=None, ge=3, le=64, description="Prism only: how many sides.")
    name: str | None = None

    @model_validator(mode="after")
    def _has_the_dimensions_its_kind_needs(self) -> PrimitiveArgs:
        needed = PRIMITIVE_REQUIREMENTS[self.kind]
        missing = [field for field in needed if getattr(self, field) is None]
        if missing:
            raise ValueError(
                f"a {self.kind} needs {', '.join(needed)}; missing {', '.join(missing)}"
            )
        if self.kind == "torus" and self.tube_radius >= self.radius:
            raise ValueError(
                "a torus needs tube_radius smaller than radius, or the tube swallows its own hole"
            )
        if self.kind == "frustum" and self.top_radius >= self.radius:
            raise ValueError(
                "a frustum needs top_radius smaller than radius; use a cylinder if they are equal"
            )
        return self


class PrimitiveResult(MutationResult):
    kind: str
    feature_name: str
    sketch_name: str
    method: Literal["extrude", "revolve"]
    body_count_before: int
    body_count_after: int
    volume_mm3_after: float | None = None
    expected_volume_mm3: float | None = Field(
        default=None,
        description=(
            "Closed-form volume for this primitive's dimensions. Compared against the "
            "measured volume, which is what turns 'a feature was created' into "
            "'the right solid was created'."
        ),
    )
    volume_error_ratio: float | None = None
    dimensions: dict[str, Any] = Field(default_factory=dict)
