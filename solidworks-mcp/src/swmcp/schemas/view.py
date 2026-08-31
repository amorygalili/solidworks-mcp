"""Viewport orientation and image capture (VIEW-003, VIEW-004).

A picture is the one piece of evidence a JSON result cannot carry. Everything else this
server reports — volumes, face counts, dimension values — is a number an agent has to
trust; a rendered image is something a person can check at a glance.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from swmcp.envelope import ReadResult, SideEffectResult
from swmcp.safety.overwrite import OverwritePolicy
from swmcp.schemas.common import BaseArgs

StandardView = Literal[
    "front",
    "back",
    "left",
    "right",
    "top",
    "bottom",
    "isometric",
    "dimetric",
    "trimetric",
]

DisplayMode = Literal[
    "wireframe",
    "hidden_lines_removed",
    "hidden_lines_grayed",
    "shaded",
    "shaded_with_edges",
]


class ViewSetArgs(BaseArgs):
    orientation: StandardView | None = Field(
        default=None, description="Standard view to switch to."
    )
    display_mode: DisplayMode | None = Field(
        default=None, description="How the model is drawn in the viewport."
    )
    fit: bool = Field(default=True, description="Zoom to fit after orienting.")
    clear_selection: bool = Field(
        default=True,
        description="Deselect first, so highlighted geometry does not colour the view.",
    )


class ViewSetResult(SideEffectResult):
    orientation: str | None = None
    display_mode: str | None = None
    fitted: bool
    selection_cleared: bool


class ViewCaptureArgs(BaseArgs):
    output_path: str = Field(
        description=(
            "Image destination under an allowed output root. The extension picks the "
            "format, and the two do not behave alike: **.bmp honours width and height "
            "exactly**, because SaveBMP takes a pixel size, while .png comes out at "
            "whatever the SOLIDWORKS viewport happens to be and ignores both. Ask for "
            ".bmp when the size matters."
        )
    )
    overwrite: OverwritePolicy = Field(
        default="version",
        description=(
            "'version' writes name_vNNN when the target exists (default), 'forbid' "
            "refuses and proposes a free name, 'allow' replaces the file."
        ),
    )
    orientation: StandardView | None = Field(
        default=None, description="Orient the view before capturing. Omit to keep the current one."
    )
    display_mode: DisplayMode | None = None
    width: int = Field(
        default=1280,
        ge=64,
        le=8192,
        description="Image width in pixels. Honoured for .bmp; advisory for .png.",
    )
    height: int = Field(
        default=960,
        ge=64,
        le=8192,
        description="Image height in pixels. Honoured for .bmp; advisory for .png.",
    )
    fit: bool = Field(default=True, description="Zoom to fit before capturing.")
    clear_selection: bool = Field(
        default=True, description="Deselect first, so nothing is highlighted in the image."
    )


class ViewCaptureResult(SideEffectResult):
    saved_path: str
    format: Literal["png", "bmp"]
    requested_size: list[int]
    actual_size: list[int] | None = Field(
        default=None,
        description=(
            "Pixel size read back out of the written file. SOLIDWORKS may not honour "
            "the request exactly, and the difference should be visible rather than "
            "assumed away."
        ),
    )
    orientation: str | None = None
    display_mode: str | None = None
    overwrite_action: Literal["create", "overwrite", "versioned"]
    method: str = Field(description="Which SOLIDWORKS call produced the file.")
    details: dict[str, Any] = Field(default_factory=dict)


# --- appearance and visibility (VIEW-001, VIEW-002) ---------------------------

#: ``MaterialPropertyValues`` is nine doubles in a fixed order. Naming them here is the
#: difference between a caller setting transparency and a caller setting index 7.
APPEARANCE_FIELDS = (
    "red",
    "green",
    "blue",
    "ambient",
    "diffuse",
    "specular",
    "shininess",
    "transparency",
    "emission",
)

AppearanceTarget = Literal["document", "body", "feature", "face"]


class AppearanceSetArgs(BaseArgs):
    target: AppearanceTarget = Field(
        default="document", description="What the appearance is applied to."
    )
    body_name: str | None = Field(default=None, description="Required when target is 'body'.")
    feature_name: str | None = Field(
        default=None, description="Required when target is 'feature'."
    )
    face_ref: dict[str, Any] | None = Field(
        default=None, description="Entity reference to a face; required when target is 'face'."
    )
    color: list[float] | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="RGB, each 0.0-1.0. Omit to leave the colour alone.",
    )
    ambient: float | None = Field(default=None, ge=0.0, le=1.0)
    diffuse: float | None = Field(default=None, ge=0.0, le=1.0)
    specular: float | None = Field(default=None, ge=0.0, le=1.0)
    shininess: float | None = Field(default=None, ge=0.0, le=1.0)
    transparency: float | None = Field(
        default=None, ge=0.0, le=1.0, description="0 is opaque, 1 is fully transparent."
    )
    emission: float | None = Field(default=None, ge=0.0, le=1.0)


class AppearanceResult(SideEffectResult):
    target: str
    applied_to: str
    appearance: dict[str, float] = Field(default_factory=dict)
    changed: list[str] = Field(default_factory=list)


class AppearanceGetArgs(BaseArgs):
    target: AppearanceTarget = "document"
    body_name: str | None = None
    feature_name: str | None = None
    face_ref: dict[str, Any] | None = None


class AppearanceGetResult(ReadResult):
    target: str
    applied_to: str
    appearance: dict[str, float] = Field(default_factory=dict)
    inherited: bool = Field(
        default=False,
        description="True when the entity has no appearance of its own and shows the document's.",
    )


class VisibilitySetArgs(BaseArgs):
    target: Literal["body", "feature"] = Field(
        description="Bodies hide through IBody2; reference geometry and sketches blank."
    )
    name: str = Field(min_length=1, description="Body or feature name.")
    visible: bool = Field(description="True to show, false to hide.")


class VisibilitySetResult(SideEffectResult):
    target: str
    name: str
    visible: bool
    method: str = Field(description="Which SOLIDWORKS call was used, since they differ by type.")
