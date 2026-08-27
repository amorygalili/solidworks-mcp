"""The MCP server: tools registered from the catalog, gated by tier.

The low-level ``Server`` is used rather than ``MCPServer``/FastMCP because the catalog
owns the schemas. FastMCP infers a schema from the Python signature, which would nest
a pydantic argument model under an ``args`` key and put a second source of truth in the
loop; here the model's own JSON schema is published verbatim.

``sw_search_tools`` is always registered regardless of tier, and searches the **whole**
catalog — including operations the active tier did not register — reporting which tier
would be needed. A search that can only find what you already have cannot tell you what
you are missing.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server

from swmcp.catalog.projection import project
from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.catalog.spec import OpSpec, tier_allowed
from swmcp.config import SwmcpConfig, get_config
from swmcp.dispatch import Dispatcher

SEARCH_TOOL = "sw_search_tools"

SERVER_INSTRUCTIONS = """\
Local SOLIDWORKS automation over Windows COM.

All calls are serialized onto one STA thread, so they run strictly one at a time.
Model-changing operations are checkpointed automatically and destructive ones require
confirm=true. Results carry read-back verification: treat an operation as done only
when its verification block says so.

Lengths accept a bare number (millimetres), a string such as "50mm" or "2in", or
{"value": 2, "unit": "inch"}. Angles default to degrees.

Use sw_search_tools to find operations, including any the active tier has not exposed.
"""


def active_ops(config: SwmcpConfig | None = None) -> dict[str, OpSpec]:
    """Operations exposed at the configured tier."""
    config = config or get_config()
    load_all_ops()
    return {name: spec for name, spec in OPS.items() if tier_allowed(spec.tier, config.tool_tier)}


def tool_descriptor(spec: OpSpec) -> types.Tool:
    projection = project(spec.safety)
    return types.Tool(
        name=spec.name,
        title=spec.name.replace("_", " "),
        description=spec.summary,
        input_schema=spec.args_model.model_json_schema(),
        annotations=types.ToolAnnotations(
            read_only_hint=projection.read_only,
            destructive_hint=projection.destructive,
            idempotent_hint=spec.idempotent,
            open_world_hint=False,
        ),
    )


def search_descriptor() -> types.Tool:
    return types.Tool(
        name=SEARCH_TOOL,
        title="search tools",
        description=(
            "Search every SOLIDWORKS operation this server knows by name, summary, tag, "
            "domain, or requirement id — including ones the active tier has not "
            "registered, reporting the tier each would need."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free text matched against name, summary, tags, domains, ids.",
                    "default": "",
                },
                "domain": {"type": "string", "description": "Restrict results to one domain."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "additionalProperties": False,
        },
        annotations=types.ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
        ),
    )


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


def list_tool_descriptors(config: SwmcpConfig | None = None) -> list[types.Tool]:
    config = config or get_config()
    ordered = sorted(active_ops(config).values(), key=lambda s: s.name)
    tools = [tool_descriptor(spec) for spec in ordered]
    tools.append(search_descriptor())
    return tools


def _as_text(payload: dict[str, Any]) -> types.CallToolResult:
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            )
        ],
        is_error=not payload.get("ok", True),
    )


def build_server(config: SwmcpConfig | None = None) -> tuple[Server, Dispatcher]:
    config = config or get_config()
    dispatcher = Dispatcher(config)

    async def on_list_tools(_ctx: Any, _params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=list_tool_descriptors(config))

    async def on_call_tool(_ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        arguments = params.arguments or {}
        if params.name == SEARCH_TOOL:
            try:
                payload = {"ok": True, "result": search_tools(config=config, **arguments)}
            except TypeError as exc:
                payload = {
                    "ok": False,
                    "error": {"code": "INVALID_ARGUMENTS", "message": str(exc)},
                }
            return _as_text(payload)
        return _as_text(dispatcher.call(params.name, arguments))

    server: Server = Server(
        "solidworks-mcp",
        version="0.1.0",
        instructions=SERVER_INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )
    return server, dispatcher
