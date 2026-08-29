"""Document review: inspection, validation, hole audit, and reports.

REV-001, REV-002, REV-004, REV-005, REV-007.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from swmcp.envelope import ReadResult, SideEffectResult
from swmcp.safety.overwrite import OverwritePolicy
from swmcp.schemas.common import BaseArgs, StrictModel

Outcome = Literal["pass", "warn", "block"]

#: What a review can look at. Each maps to machinery that already exists, so a caller
#: asking for everything gets one payload instead of eight round trips.
InspectSection = Literal[
    "document",
    "features",
    "sketches",
    "bodies",
    "configurations",
    "equations",
    "dimensions",
    "properties",
    "components",
    "mass",
]


class ReviewInspectArgs(BaseArgs):
    sections: list[InspectSection] = Field(
        default_factory=list,
        description="Sections to include. Empty means every section that applies.",
    )
    max_items: int = Field(
        default=200,
        ge=1,
        le=5000,
        description="Cap per section, so one huge model cannot produce an unusable payload.",
    )


class ReviewInspectResult(ReadResult):
    document: dict[str, Any] = Field(default_factory=dict)
    sections: dict[str, Any] = Field(default_factory=dict)
    truncated: list[str] = Field(
        default_factory=list, description="Sections cut short by max_items."
    )


class ReviewPolicy(StrictModel):
    """The rules a review applies. REV-007: the caller owns these, not the server.

    Every field is a rule the caller can turn on, off, or tune. A default set is
    supplied so a bare call still means something, but nothing here is a rule this
    server insists on — a check that cannot be disabled is a policy pretending to be a
    fact.
    """

    require_no_feature_errors: bool = Field(
        default=True, description="Any feature reporting an error code fails the review."
    )
    require_bodies_min: int | None = Field(
        default=1, description="Fewest solid bodies the model must have. None to skip."
    )
    forbid_zero_volume: bool = Field(
        default=True, description="A model with no volume is almost always a failed build."
    )
    min_volume_mm3: float | None = Field(default=None, description="Lower bound on total volume.")
    max_volume_mm3: float | None = Field(default=None, description="Upper bound on total volume.")
    require_fully_defined_sketches: bool = Field(
        default=False, description="Every sketch must be fully defined."
    )
    forbid_dangling_relations: bool = Field(
        default=True, description="Sketch relations pointing at deleted geometry fail."
    )
    forbid_suppressed_features: bool = Field(
        default=False, description="Suppressed features fail the review."
    )
    require_material: bool = Field(
        default=False, description="The part must have a material assigned."
    )
    severity: dict[str, Outcome] = Field(
        default_factory=dict,
        description=(
            "Override the outcome of a named check, e.g. {'sketches_fully_defined': "
            "'warn'}. Names are the check names in the result."
        ),
    )


class ReviewValidateArgs(BaseArgs):
    policy: ReviewPolicy = Field(
        default_factory=ReviewPolicy, description="Rules to apply. Defaults are conservative."
    )


class ReviewFinding(StrictModel):
    name: str
    outcome: Outcome
    detail: str
    source: str = Field(description="What was read to reach this, so a reader can re-check it.")


class ReviewValidateResult(ReadResult):
    outcome: Outcome = Field(description="The worst outcome among the findings.")
    findings: list[ReviewFinding] = Field(default_factory=list)
    blocked: int = 0
    warned: int = 0
    passed: int = 0


class HoleExpectation(StrictModel):
    """One expected hole group, for comparing a model against an intent."""

    diameter_mm: float = Field(gt=0)
    count: int = Field(ge=1)
    tolerance_mm: float = Field(
        default=0.01, ge=0.0, description="How far a measured diameter may differ and still match."
    )


class ReviewHolesArgs(BaseArgs):
    expect: list[HoleExpectation] = Field(
        default_factory=list,
        max_length=64,
        description="Optional expected hole groups. Without these the tool only reports.",
    )
    min_diameter_mm: float | None = Field(
        default=None, gt=0, description="Ignore cylindrical faces smaller than this."
    )
    max_diameter_mm: float | None = Field(
        default=None, gt=0, description="Ignore cylindrical faces larger than this."
    )

    @model_validator(mode="after")
    def _range_is_sane(self) -> ReviewHolesArgs:
        low, high = self.min_diameter_mm, self.max_diameter_mm
        if low is not None and high is not None and low > high:
            raise ValueError("min_diameter_mm must not exceed max_diameter_mm")
        return self


class ReviewHolesResult(ReadResult):
    hole_count: int
    groups: list[dict[str, Any]] = Field(
        default_factory=list, description="Cylindrical faces grouped by diameter."
    )
    matched: list[dict[str, Any]] = Field(default_factory=list)
    unmatched: list[dict[str, Any]] = Field(
        default_factory=list, description="Expectations no measured group satisfied."
    )
    outcome: Outcome = "pass"


class ReviewReportArgs(BaseArgs):
    output_path: str = Field(
        description=(
            "Where to write the report. The extension picks the format: .md for "
            "Markdown, .json for JSON. Both are written either way, side by side."
        )
    )
    policy: ReviewPolicy = Field(default_factory=ReviewPolicy)
    overwrite: OverwritePolicy = Field(default="version")
    title: str | None = Field(default=None, description="Heading for the Markdown report.")


class ReviewReportResult(SideEffectResult):
    markdown_path: str
    json_path: str
    outcome: Outcome
    finding_count: int
    blocked: int = 0
    warned: int = 0
