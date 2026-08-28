"""Derive every published artifact from the catalog, and detect drift.

``build_artifacts`` is deterministic — the catalog and this package's own source in,
canonical bytes out — so the drift check is just a comparison. It runs inside
``pytest`` rather than only in a separate script, because a check you have to remember
to run is a check that rots.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from swmcp.catalog.projection import project
from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.catalog.requirements import load_requirements
from swmcp.catalog.scope import DECLARED_PARTIAL, IN_SCOPE_REQUIREMENTS, PLATFORM_REQUIREMENTS
from swmcp.catalog.spec import OpSpec
from swmcp.com.apiver import build_usage

GENERATED = Path(__file__).resolve().parent.parent / "generated"


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _tool_entry(spec: OpSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "tier": spec.tier,
        "domains": list(spec.domains),
        "tags": list(spec.tags),
        "summary": spec.summary,
        "precondition": spec.precondition,
        "idempotent": spec.idempotent,
        "timeout_s": spec.timeout_s,
        "fresh_checkpoint": spec.fresh_checkpoint,
        "handler_ref": spec.handler_ref,
        "safety": spec.safety.model_dump(),
        "projection": project(spec.safety).model_dump(),
        "satisfies": list(spec.satisfies),
        "partially_satisfies": list(spec.partially_satisfies),
        "input_schema": spec.args_model.model_json_schema(),
        "result_schema": spec.result_model.model_json_schema(),
    }


def build_coverage() -> dict[str, Any]:
    """Requirement coverage, reported honestly rather than optimistically."""
    load_all_ops()
    requirements = load_requirements()
    full: dict[str, list[str]] = {}
    partial: dict[str, list[str]] = {}
    for spec in OPS.values():
        for rid in spec.satisfies:
            full.setdefault(rid, []).append(spec.name)
        for rid in spec.partially_satisfies:
            partial.setdefault(rid, []).append(spec.name)

    covered = set(full) | set(partial) | set(PLATFORM_REQUIREMENTS)
    uncovered = sorted(IN_SCOPE_REQUIREMENTS - covered)

    return {
        "totals": {
            "requirements_in_backlog": len(requirements),
            "in_scope": len(IN_SCOPE_REQUIREMENTS),
            "fully_covered_by_a_tool": len(set(full) & IN_SCOPE_REQUIREMENTS),
            "partially_covered": len(set(partial) & IN_SCOPE_REQUIREMENTS),
            "covered_by_platform": len(PLATFORM_REQUIREMENTS),
            "uncovered_in_scope": len(uncovered),
            "tools": len(OPS),
        },
        "fully_covered": {rid: sorted(names) for rid, names in sorted(full.items())},
        "partially_covered": {
            rid: {"tools": sorted(names), "limitation": DECLARED_PARTIAL.get(rid, "")}
            for rid, names in sorted(partial.items())
        },
        "covered_by_platform": dict(sorted(PLATFORM_REQUIREMENTS.items())),
        "uncovered_in_scope": uncovered,
        "note": (
            "A requirement listed under partially_covered is NOT done. The limitation "
            "field says what is missing."
        ),
    }


def _render_doc(spec: OpSpec) -> str:
    projection = project(spec.safety)
    lines = [
        f"# {spec.name}",
        "",
        spec.summary,
        "",
        "| | |",
        "|---|---|",
        f"| Tier | `{spec.tier}` |",
        f"| Domains | {', '.join(f'`{d}`' for d in spec.domains)} |",
        f"| Document precondition | `{spec.precondition}` |",
        f"| Safety | `{spec.safety.kind}` |",
        f"| Read-only | {projection.read_only} |",
        f"| Destructive | {projection.destructive} |",
        f"| Confirmation required | {projection.confirm_required} |",
        f"| Auto-checkpointed | {projection.auto_checkpoint} |",
        f"| Idempotent | {spec.idempotent} |",
        f"| Timeout | {spec.timeout_s:g}s |",
    ]
    if spec.fresh_checkpoint:
        lines.append(
            "| Checkpoint | Always fresh: the debounce is bypassed, because this "
            "operation restores its own snapshot. |"
        )
    if isinstance(spec.safety.model_dump().get("rationale"), str):
        lines.append(f"| Side-effect rationale | {spec.safety.model_dump()['rationale']} |")
    if spec.satisfies:
        lines.append(f"| Satisfies | {', '.join(f'`{r}`' for r in spec.satisfies)} |")
    if spec.partially_satisfies:
        lines.append(
            f"| Partially satisfies | {', '.join(f'`{r}`' for r in spec.partially_satisfies)} |"
        )

    lines += [
        "",
        "## Input schema",
        "",
        "```json",
        json.dumps(spec.args_model.model_json_schema(), indent=2, sort_keys=True),
        "```",
        "",
        "## Result schema",
        "",
        "```json",
        json.dumps(spec.result_model.model_json_schema(), indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def build_artifacts() -> dict[Path, str]:
    """Pure: the catalog in, the canonical file contents out."""
    load_all_ops()
    specs = sorted(OPS.values(), key=lambda s: s.name)

    artifacts: dict[Path, str] = {
        GENERATED
        / "tool_manifest.json": _json(
            {
                "version": 1,
                "generated_from": "swmcp.catalog.registry.OPS",
                "tool_count": len(specs),
                "tools": [_tool_entry(spec) for spec in specs],
            }
        ),
        GENERATED
        / "command_safety_policy.json": _json(
            {
                "note": (
                    "Derived from the safety union by swmcp.catalog.projection.project. "
                    "Do not edit; edit the safety declaration on the handler instead."
                ),
                "policies": {
                    spec.name: {
                        "safety": spec.safety.model_dump(),
                        **project(spec.safety).model_dump(),
                    }
                    for spec in specs
                },
            }
        ),
        GENERATED / "requirements_coverage.json": _json(build_coverage()),
        GENERATED / "api_usage.json": _json(build_usage()),
        GENERATED
        / "requirements.json": _json(
            {
                "note": "Snapshot of the parsed backlog so an installed package is self-contained.",
                "requirements": {
                    rid: {"priority": r.priority, "text": r.text}
                    for rid, r in sorted(load_requirements().items())
                },
            }
        ),
    }

    for spec in specs:
        artifacts[GENERATED / "docs" / f"{spec.name}.md"] = _render_doc(spec)

    return artifacts


def stale_artifacts() -> list[str]:
    """Paths whose committed contents differ from what the catalog would produce."""
    stale = []
    for path, expected in build_artifacts().items():
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(str(path))
    return sorted(stale)


def write_artifacts() -> list[str]:
    written = []
    for path, contents in build_artifacts().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_text(encoding="utf-8") != contents:
            path.write_text(contents, encoding="utf-8")
            written.append(str(path))
    _prune_orphan_docs()
    return sorted(written)


def _prune_orphan_docs() -> None:
    """Remove docs for operations that no longer exist."""
    docs_dir = GENERATED / "docs"
    if not docs_dir.is_dir():
        return
    expected = {f"{name}.md" for name in OPS}
    for existing in docs_dir.glob("*.md"):
        if existing.name not in expected:
            existing.unlink()
