"""System domain: connect, version/install reporting, health, capabilities, naming."""

from __future__ import annotations

import time
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, NonModelSideEffect, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import try_com_member
from swmcp.context import OpContext
from swmcp.schemas.system import (
    CapabilitiesArgs,
    CapabilitiesResult,
    ConnectArgs,
    ConnectResult,
    HealthArgs,
    HealthResult,
    ResolveNamesArgs,
    ResolveNamesResult,
    SystemInfoArgs,
    SystemInfoResult,
)
from swmcp.timing import elapsed_ms

_ = ModelMutation  # re-exported for symmetry with other handler modules


@op(
    name="sw_connect",
    tier="core",
    domains=("system",),
    tags=("connect", "attach", "session"),
    summary=(
        "Attach to a running SOLIDWORKS instance, optionally launching one. Reports the "
        "version, the ProgID that worked, and the active document."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "With start_if_missing=true this launches SLDWORKS.exe, a visible desktop "
            "process. Attaching alone changes nothing."
        ),
    ),
    satisfies=("SYS-001",),
    precondition="none",
    idempotent=True,
    timeout_s=240.0,
)
def connect(ctx: OpContext, args: ConnectArgs) -> ConnectResult:
    was_running = ctx.session.attached
    ctx.session.ensure(start_if_missing=args.start_if_missing, visible=args.visible)
    info = ctx.session.system_info()
    return ConnectResult(
        attached=True,
        launched=bool(info.get("launched_by_this_server")) and not was_running,
        prog_id=info.get("attached_prog_id"),
        revision=info.get("revision"),
        year=info.get("year"),
        active_document=info.get("active_document"),
    )


@op(
    name="sw_system_info",
    tier="core",
    domains=("system",),
    tags=("version", "install", "diagnostics"),
    summary=(
        "Report the SOLIDWORKS version and service pack, COM registration, install "
        "location, session identity, active document, and constant-table provenance."
    ),
    safety=ReadSafety(),
    satisfies=("SYS-002",),
    precondition="none",
    idempotent=True,
)
def system_info(ctx: OpContext, args: SystemInfoArgs) -> SystemInfoResult:
    _ = args
    return SystemInfoResult(info=ctx.session.system_info())


@op(
    name="sw_health",
    tier="core",
    domains=("system", "safety"),
    tags=("health", "diagnostics", "worker"),
    summary=(
        "Report worker, session, and dependency health without needing an active "
        "document. The snapshot answers immediately even while a COM call is stuck, so "
        "a wedged worker can still be diagnosed."
    ),
    safety=ReadSafety(),
    satisfies=("SYS-005",),
    precondition="none",
    idempotent=True,
    timeout_s=30.0,
)
def health(ctx: OpContext, args: HealthArgs) -> HealthResult:
    snapshot = ctx.worker.health_snapshot() if ctx.worker is not None else {}
    issues: list[str] = []

    install = ctx.session.install()
    if not install.found:
        issues.append("SOLIDWORKS is not registered on this machine.")
    issues.extend(install.notes)

    probe: dict[str, Any] | None = None
    if args.probe:
        started = time.monotonic()
        revision = try_com_member(ctx.session.app, "RevisionNumber", default=None)
        probe = {
            "revision": str(revision) if revision else None,
            "latency_ms": elapsed_ms(started),
            "answered": revision is not None,
        }
        if not probe["answered"]:
            issues.append("SOLIDWORKS did not answer a live version probe.")

    inflight = snapshot.get("inflight")
    if inflight and inflight.get("elapsed_s", 0) > 120:
        issues.append(
            f"{inflight['label']} has been running for {inflight['elapsed_s']:.0f}s. "
            "Check SOLIDWORKS for a modal dialog."
        )

    return HealthResult(
        healthy=not issues,
        worker=snapshot,
        probe=probe,
        issues=issues,
    )


@op(
    name="sw_capabilities",
    tier="extended",
    domains=("system", "discovery"),
    tags=("capability", "probe", "license", "addin"),
    summary=(
        "Probe what this installation can actually do — edition, add-ins, type "
        "libraries, and template availability — so a caller can branch on evidence "
        "rather than assuming a feature exists."
    ),
    safety=ReadSafety(),
    satisfies=("DISC-005",),
    precondition="none",
    idempotent=True,
    timeout_s=60.0,
)
def capabilities(ctx: OpContext, args: CapabilitiesArgs) -> CapabilitiesResult:
    _ = args
    app = ctx.session.app
    install = ctx.session.install()

    templates = {}
    for kind, preference in (("part", 8), ("assembly", 9), ("drawing", 10)):
        value = try_com_member(app, "GetUserPreferenceStringValue", preference, default=None)
        templates[kind] = str(value) if value else None

    from pathlib import Path

    return CapabilitiesResult(
        capabilities={
            "attach": ctx.session.attached,
            "default_templates": templates,
            "templates_present": {
                kind: bool(path and Path(path).is_file()) for kind, path in templates.items()
            },
            "constant_table": swconst.table_info(),
            "revision": ctx.session.system_info().get("revision"),
        },
        evidence={
            "install_root": install.install_root,
            "registered_prog_ids": list(install.registered_progids),
            "template_dirs": list(install.template_dirs),
            "probe_method": (
                "Templates come from GetUserPreferenceStringValue and are then checked "
                "on disk; the registry supplies the install location."
            ),
        },
    )


@op(
    name="sw_resolve_names",
    tier="extended",
    domains=("system", "reference"),
    tags=("localization", "planes", "units"),
    summary=(
        "Resolve standard plane names and document units for the target document, "
        "reporting both the display name and the locale-invariant type token so "
        "callers never string-match an English feature tree."
    ),
    safety=ReadSafety(),
    satisfies=("SYS-007",),
    precondition="any",
    idempotent=True,
)
def resolve_names(ctx: OpContext, args: ResolveNamesArgs) -> ResolveNamesResult:
    _ = args
    doc = ctx.require_doc()
    return ResolveNamesResult(
        language=try_com_member(ctx.session.app, "GetCurrentLanguage", default=None),
        standard_planes=ctx.session.standard_planes(doc),
        units=ctx.session.units(doc),
    )
