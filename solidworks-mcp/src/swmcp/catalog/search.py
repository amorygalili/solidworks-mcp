"""Catalog search and tier filtering, shared by every front end.

Lives in the catalog rather than in the MCP server because the library and the CLI
search the same catalog the same way, and neither should need the ``mcp`` package to
do it.
"""

from __future__ import annotations

import keyword
from typing import Any

from swmcp.catalog.projection import project
from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.catalog.spec import OpSpec, tier_allowed
from swmcp.config import SwmcpConfig, get_config

#: Every operation name carries this prefix on the wire. Python callers drop it.
OP_PREFIX = "sw_"


def method_name(op_name: str) -> str:
    """The library method for an operation: ``sw_doc_new`` becomes ``doc_new``.

    A name that would be a Python keyword takes a trailing underscore, the PEP 8
    convention — ``sw_import`` is ``import_``, because ``sw.import(...)`` cannot parse.
    """
    bare = op_name.removeprefix(OP_PREFIX)
    return f"{bare}_" if keyword.iskeyword(bare) else bare


def resolve_op_name(name: str) -> str:
    """Accept a wire name, a bare name, or a method name, and return the wire name.

    An unrecognised name is returned unchanged, so the dispatcher can refuse it with
    ``UNKNOWN_TOOL`` like any other unknown name rather than this guessing at it.
    """
    load_all_ops()
    if name in OPS:
        return name
    for candidate in (OP_PREFIX + name, OP_PREFIX + name.removesuffix("_")):
        if candidate in OPS:
            return candidate
    return name


def describe_tool(spec: OpSpec) -> dict[str, Any]:
    """Everything published about one operation, in one shape.

    The tool manifest, the CLI's ``describe``, and the library's ``describe`` all
    print this, so the three cannot disagree about what an operation is.
    """
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


def active_ops(config: SwmcpConfig | None = None) -> dict[str, OpSpec]:
    """Operations exposed at the configured tier."""
    config = config or get_config()
    load_all_ops()
    return {name: spec for name, spec in OPS.items() if tier_allowed(spec.tier, config.tool_tier)}


def search_tools(
    query: str = "",
    domain: str | None = None,
    limit: int = 20,
    config: SwmcpConfig | None = None,
) -> dict[str, Any]:
    """DISC-001. Searches the full catalog, not just the registered subset."""
    config = config or get_config()
    load_all_ops()
    terms = [t for t in query.lower().split() if t]
    available = set(active_ops(config))

    scored: list[tuple[int, OpSpec]] = []
    for spec in OPS.values():
        if domain and domain not in spec.domains:
            continue
        haystack = " ".join(
            [
                spec.name,
                spec.summary,
                *spec.tags,
                *spec.domains,
                *spec.satisfies,
                *spec.partially_satisfies,
            ]
        ).lower()
        if not terms:
            scored.append((0, spec))
            continue
        score = sum(
            3 if term in spec.name.lower() else (1 if term in haystack else 0) for term in terms
        )
        if score:
            scored.append((-score, spec))

    scored.sort(key=lambda item: (item[0], item[1].name))
    hits = []
    for _score, spec in scored[:limit]:
        projection = project(spec.safety)
        hits.append(
            {
                "name": spec.name,
                "tier": spec.tier,
                "available": spec.name in available,
                "tier_needed": None if spec.name in available else spec.tier,
                "domains": list(spec.domains),
                "summary": spec.summary,
                "read_only": projection.read_only,
                "destructive": projection.destructive,
                "satisfies": list(spec.satisfies),
            }
        )

    return {
        "query": query,
        "domain": domain,
        "active_tier": config.tool_tier,
        "matched": len(scored),
        "returned": len(hits),
        "tools": hits,
        "hint": (
            "Set SWMCP_TOOL_TIER=all to register every operation."
            if any(not hit["available"] for hit in hits)
            else None
        ),
    }
