"""Part material assignment and read-back (FEAT-020)."""

from __future__ import annotations

from pydantic import Field

from swmcp.envelope import MutationResult, ReadResult
from swmcp.schemas.common import BaseArgs

#: The library every stock SOLIDWORKS install ships with. Named as a default rather
#: than hardcoded, because a site with its own library needs to say so.
DEFAULT_DATABASE = "SOLIDWORKS Materials"


class MaterialSetArgs(BaseArgs):
    name: str = Field(
        description=(
            "Material name exactly as the library spells it, e.g. '6061 Alloy' or "
            "'Plain Carbon Steel'. An empty string removes the material, which returns "
            "the part to SOLIDWORKS' density of 1.0."
        )
    )
    database: str = Field(
        default=DEFAULT_DATABASE,
        description="Material library holding the name. Defaults to the stock library.",
    )
    configuration: str | None = Field(
        default=None,
        description="Configuration to apply it to. Defaults to the active one.",
    )


class MaterialSetResult(MutationResult):
    material: str
    database: str
    configuration: str
    density_kg_m3: float | None = None
    mass_kg: float | None = None
    volume_m3: float | None = None


class MaterialGetArgs(BaseArgs):
    configuration: str | None = Field(
        default=None, description="Configuration to read. Defaults to the active one."
    )


class MaterialGetResult(ReadResult):
    material: str | None = Field(
        default=None, description="None when the part has no material assigned."
    )
    database: str | None = None
    configuration: str
    density_kg_m3: float | None = None
    mass_kg: float | None = None
    volume_m3: float | None = None
    bodies: list[dict] = Field(
        default_factory=list,
        description="Per-body material names, which are empty unless set on the body itself.",
    )
