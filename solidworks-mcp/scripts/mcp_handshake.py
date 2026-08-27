"""Spawn the server over stdio and check what a real MCP client would see.

Needs no SOLIDWORKS: it exercises the protocol handshake and the published schemas,
which are built from the catalog and never touch COM.

    uv run python scripts/mcp_handshake.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


async def handshake(tier: str) -> list:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    environment = {**os.environ, "SWMCP_TOOL_TIER": tier}
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "swmcp"],
        env=environment,
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return (await session.list_tools()).tools


def check_schema(tool) -> list[str]:
    problems = []
    schema = tool.inputSchema if hasattr(tool, "inputSchema") else tool.input_schema
    if schema.get("type") != "object":
        problems.append(f"{tool.name}: input schema is not an object")
    if schema.get("additionalProperties") is not False:
        problems.append(f"{tool.name}: schema allows unknown properties")
    if not tool.description:
        problems.append(f"{tool.name}: no description")
    return problems


def main() -> int:
    core = asyncio.run(handshake("core"))
    every = asyncio.run(handshake("all"))

    print(f"core tier:  {len(core)} tools")
    print(f"all tier:   {len(every)} tools")

    problems: list[str] = []
    if len(core) >= len(every):
        problems.append("the core tier should register fewer tools than 'all'")
    if not any(tool.name == "sw_search_tools" for tool in core):
        problems.append("sw_search_tools must be registered at every tier")

    for tool in every:
        problems.extend(check_schema(tool))

    if problems:
        print("\nproblems:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print("every published schema is a strict object with a description")
    return 0


if __name__ == "__main__":
    sys.exit(main())
