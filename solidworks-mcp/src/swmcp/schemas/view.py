"""Viewport orientation and image capture (VIEW-003, VIEW-004).

A picture is the one piece of evidence a JSON result cannot carry. Everything else this
server reports — volumes, face counts, dimension values — is a number an agent has to
trust; a rendered image is something a person can check at a glance.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from swmcp.envelope import SideEffectResult
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
            "format: .png or .bmp."
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
    width: int = Field(default=1280, ge=64, le=8192, description="Image width in pixels.")
    height: int = Field(default=960, ge=64, le=8192, description="Image height in pixels.")
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
