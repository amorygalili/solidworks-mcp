"""Surface bodies (FEAT-018)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import MutationResult
from swmcp.refs.model import EntityRef
from swmcp.schemas.common import BaseArgs
from swmcp.units import Length

SurfaceMethod = Literal["planar", "offset", "extend", "knit"]


class SurfaceCreateArgs(BaseArgs):
    method: SurfaceMethod = Field(
        description=(
            "'planar' fills a closed sketch, 'offset' copies faces at a distance "
            "(0 copies them in place), 'extend' stretches surface edges, and 'knit' "
            "sews touching surfaces into one."
        )
    )
    sketch_name: str | None = Field(
        default=None, description="Closed profile for 'planar'. Defaults to the newest unused."
    )
    face_refs: list[EntityRef] = Field(
        default_factory=list,
        max_length=64,
        description="Faces to offset, or the surfaces to knit.",
    )
    edge_refs: list[EntityRef] = Field(
        default_factory=list, max_length=64, description="Surface edges to extend."
    )
    distance: Length | None = Field(
        default=None,
        description="Offset or extend distance. An offset of 0 copies the faces in place.",
    )
    reverse: bool = Field(default=False, description="Offset the other way.")
    extend_linear: bool = Field(
        default=True,
        description="Extend along the surface's tangent rather than following its curvature.",
    )
    name: str | None = None

    @model_validator(mode="after")
    def _method_has_what_it_needs(self) -> SurfaceCreateArgs:
        """Each method reads a different selection; the wrong one builds nothing."""
        if self.method == "offset":
            if not self.face_refs:
                raise ValueError("'offset' needs face_refs")
            if self.distance is None:
                raise ValueError("'offset' needs a distance (0 copies the faces in place)")
        if self.method == "extend":
            if not self.edge_refs:
                raise ValueError("'extend' needs edge_refs")
            if self.distance is None:
                raise ValueError("'extend' needs a distance")
        if self.method == "knit" and len(self.face_refs) < 2:
            raise ValueError("'knit' needs at least two surfaces to sew together")
        return self


class SurfaceCreateResult(MutationResult):
    feature_name: str
    method: str
    sheet_bodies_before: int
    sheet_bodies_after: int
    solid_bodies_after: int
    reference: dict[str, Any] | None = None
