"""Argument and result models for the system domain."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from swmcp.envelope import ReadResult, SideEffectResult
from swmcp.schemas.common import BaseArgs, StrictModel


class ConnectArgs(StrictModel):
    start_if_missing: bool = Field(
        default=False,
        description=(
            "Launch SOLIDWORKS if no instance is running. Off by default because "
            "starting it is slow and visible on the user's desktop."
        ),
    )
    visible: bool = Field(
        default=True, description="Show the SOLIDWORKS window when launching it."
    )


class ConnectResult(SideEffectResult):
    attached: bool
    launched: bool = Field(description="Whether this call started the SOLIDWORKS process.")
    prog_id: str | None = None
    revision: str | None = None
    year: int | None = None
    active_document: dict[str, Any] | None = None


class SystemInfoArgs(StrictModel):
    pass


class SystemInfoResult(ReadResult):
    info: dict[str, Any] = Field(
        description="Version, ProgID, install, constants table, and active document."
    )


class HealthArgs(StrictModel):
    probe: bool = Field(
        default=False,
        description=(
            "Also make a live COM call to confirm SOLIDWORKS answers. Off by default so "
            "the snapshot still returns while the worker is wedged."
        ),
    )


class HealthResult(ReadResult):
    healthy: bool
    worker: dict[str, Any]
    probe: dict[str, Any] | None = None
    issues: list[str] = Field(default_factory=list)


class CapabilitiesArgs(StrictModel):
    pass


class CapabilitiesResult(ReadResult):
    capabilities: dict[str, Any]
    evidence: dict[str, Any] = Field(
        description="What was actually checked, so a claim can be traced to a probe."
    )


class ResolveNamesArgs(BaseArgs):
    pass


class ResolveNamesResult(ReadResult):
    language: Any | None = None
    standard_planes: list[dict[str, Any]] = Field(default_factory=list)
    units: dict[str, Any] = Field(default_factory=dict)
    note: str = (
        "Standard planes are addressed by tree position and the locale-invariant "
        "GetTypeName2 token, never by display name."
    )
