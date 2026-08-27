"""The entity reference (REF-002/003/004/007).

Every capture emits **all** addressing modes at once, because each fails differently:

* a persistent reference is exact but opaque, document-scoped, and dies with the entity;
* a semantic reference survives a rebuild that changed identity but can be ambiguous;
* a select hint lets the entity be re-picked geometrically when both fail.

Serialization is the whole of REF-007: every leaf is JSON-native, so a workflow
checkpoints its references with ``model_dump(mode="json")`` and nothing else is needed.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

REF_VERSION = 1

EntityKind = Literal[
    "face",
    "edge",
    "vertex",
    "body",
    "feature",
    "sketch",
    "sketch_segment",
    "plane",
    "axis",
    "point",
    "coordinate_system",
    "component",
    "unknown",
]

GeometryType = str


class RefTolerance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linear_m: float = 1.0e-6
    angular_rad: float = 1.0e-6
    relative: float = 1.0e-4


class RefMeasurements(BaseModel):
    """Geometry sampled at capture time, in API units (metres)."""

    model_config = ConfigDict(extra="forbid")

    point_m: list[float] | None = Field(
        default=None, description="A point on the entity: face centre, edge midpoint, or vertex."
    )
    direction: list[float] | None = Field(
        default=None, description="Plane normal, cylinder axis, or edge tangent at the midpoint."
    )
    radius_m: float | None = None
    area_m2: float | None = None
    length_m: float | None = None
    bbox_m: list[float] | None = Field(
        default=None, description="[xmin, ymin, zmin, xmax, ymax, zmax]."
    )


class SemanticRef(BaseModel):
    """The fallback that survives when a persistent reference does not."""

    model_config = ConfigDict(extra="forbid")

    component_path: list[str] = Field(default_factory=list)
    feature_ancestry: list[str] = Field(
        default_factory=list, description="Display names, outermost last."
    )
    feature_type_names: list[str] = Field(
        default_factory=list,
        description="Locale-invariant GetTypeName2 tokens for the same ancestry.",
    )
    geometry_type: GeometryType = "unknown"
    body_name: str | None = None
    measurements: RefMeasurements = Field(default_factory=RefMeasurements)
    signature: str = Field(default="", description="Hash of the rounded geometry.")
    tolerance: RefTolerance = Field(default_factory=RefTolerance)


class PersistentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheme: str = "GetPersistReference3"
    data_b64: str
    captured_revision: str | None = None


class DocumentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    title: str | None = None
    configuration: str | None = None


class SelectHint(BaseModel):
    """Last-resort geometric re-pick information."""

    model_config = ConfigDict(extra="forbid")

    sw_select_type: str | None = None
    mark: int = 0
    ray_origin_m: list[float] | None = None
    ray_direction: list[float] | None = None


class EntityRef(BaseModel):
    """A reference to one SOLIDWORKS entity, in every addressing mode at once."""

    model_config = ConfigDict(extra="forbid")

    ref_version: int = REF_VERSION
    kind: EntityKind = "unknown"
    label: str = Field(default="", description="A human sentence describing the entity.")
    document: DocumentRef = Field(default_factory=DocumentRef)
    persistent: PersistentRef | None = None
    semantic: SemanticRef = Field(default_factory=SemanticRef)
    select_hint: SelectHint | None = None
    captured_at: str | None = None
    warnings: list[str] = Field(default_factory=list)

    def addressing(self) -> EntityRef:
        """The subset worth passing back in: identity, not presentation.

        ``label``, ``captured_at``, ``warnings``, and ``select_hint`` describe the
        capture rather than the entity, so they are dropped from the paste-ready form.
        """
        return EntityRef(
            ref_version=self.ref_version,
            kind=self.kind,
            document=self.document,
            persistent=self.persistent,
            semantic=self.semantic,
        )

    def tool_args(self, key: str = "ref") -> dict[str, Any]:
        """A dict that can be pasted straight into the next call's arguments."""
        return {key: self.addressing().model_dump(mode="json", exclude_none=True)}


class ReferenceDrift(BaseModel):
    """What changed between capture and resolution."""

    model_config = ConfigDict(extra="forbid")

    via: Literal["persistent", "semantic"]
    score: float | None = None
    persistent_status: str | None = None
    moved_mm: float | None = None
    radius_delta_mm: float | None = None
    area_ratio: float | None = None
    note: str | None = None
