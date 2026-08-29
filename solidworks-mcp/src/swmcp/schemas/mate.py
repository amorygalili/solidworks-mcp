"""Assembly mates (MATE-001, MATE-002, MATE-003, MATE-004)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import MutationResult, ReadResult
from swmcp.refs.model import EntityRef
from swmcp.schemas.common import BaseArgs
from swmcp.units import Angle, Length

#: The mate types ``AddMate5`` builds from exactly two selected entities. The rest of
#: ``swMateType_e`` — width, symmetric, gear, cam, slot, path, screw, and the others —
#: need three or more selections or extra arguments, and are declared unimplemented
#: rather than accepted and then failed at runtime.
MateType = Literal[
    "coincident",
    "concentric",
    "perpendicular",
    "parallel",
    "tangent",
    "distance",
    "angle",
    "lock",
]

MateAlignment = Literal["aligned", "anti_aligned", "closest"]


class MateAddArgs(BaseArgs):
    mate_type: MateType = Field(description="Which mate to create between the two references.")
    refs: list[EntityRef] = Field(
        min_length=2,
        max_length=2,
        description=(
            "Exactly two entities to mate: faces, edges, vertices, planes, axes, or "
            "component origins, addressed the same way as everywhere else."
        ),
    )
    alignment: MateAlignment = Field(
        default="closest", description="Which way the two references face each other."
    )
    flip: bool = Field(default=False, description="Flip the mate's dimension direction.")
    distance: Length | None = Field(
        default=None, description="Separation for a distance mate. Required for 'distance'."
    )
    angle: Angle | None = Field(
        default=None, description="Angle for an angle mate. Required for 'angle'."
    )
    distance_min: Length | None = Field(
        default=None, description="Lower limit for a limit-distance mate."
    )
    distance_max: Length | None = Field(
        default=None, description="Upper limit for a limit-distance mate."
    )
    angle_min: Angle | None = Field(default=None, description="Lower limit for a limit-angle mate.")
    angle_max: Angle | None = Field(default=None, description="Upper limit for a limit-angle mate.")
    lock_rotation: bool = Field(
        default=False, description="Lock rotation on a concentric mate."
    )
    for_positioning_only: bool = Field(
        default=False,
        description="Move the component into place without leaving a mate behind.",
    )
    name: str | None = Field(default=None, description="Rename the mate after creating it.")

    @model_validator(mode="after")
    def _value_matches_the_mate(self) -> MateAddArgs:
        """A distance mate with no distance silently becomes a coincident one at zero."""
        if self.mate_type == "distance" and self.distance is None:
            raise ValueError("a 'distance' mate needs a distance")
        if self.mate_type == "angle" and self.angle is None:
            raise ValueError("an 'angle' mate needs an angle")
        for low, high, label in (
            (self.distance_min, self.distance_max, "distance"),
            (self.angle_min, self.angle_max, "angle"),
        ):
            if (low is None) != (high is None):
                raise ValueError(f"a limit {label} mate needs both {label}_min and {label}_max")
            if low is not None and high is not None and low > high:
                raise ValueError(f"{label}_min must not exceed {label}_max")
        return self


class MateAddResult(MutationResult):
    mate_name: str
    mate_type: str
    alignment: str
    flipped: bool
    entity_count: int
    components: list[str] = Field(default_factory=list)
    mates_before: int
    mates_after: int


class MateListArgs(BaseArgs):
    pass


class MateListResult(ReadResult):
    mate_count: int
    mates: list[dict[str, Any]] = Field(default_factory=list)
    suppressed_count: int = 0
