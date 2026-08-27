"""CLI entry point.

``stdout`` is the MCP transport, so every diagnostic goes to ``stderr``. A stray
``print`` in a handler would otherwise corrupt the protocol stream.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def _serve() -> None:
    from mcp.server.stdio import stdio_server

    from swmcp.server import build_server

    server, dispatcher = build_server()
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        dispatcher.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solidworks-mcp", description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="debug logging on stderr")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--print-manifest", action="store_true", help="dump the tool manifest")
    group.add_argument("--print-coverage", action="store_true", help="dump requirement coverage")
    group.add_argument(
        "--check-artifacts", action="store_true", help="exit 1 if generated files are stale"
    )
    group.add_argument(
        "--write-artifacts", action="store_true", help="regenerate the generated files"
    )
    group.add_argument("--doctor", action="store_true", help="report install and session health")
    arguments = parser.parse_args(argv)

    _configure_logging(arguments.verbose)

    if arguments.print_manifest:
        from swmcp.catalog.artifacts import GENERATED, build_artifacts

        print(build_artifacts()[GENERATED / "tool_manifest.json"], end="")
        return 0

    if arguments.print_coverage:
        from swmcp.catalog.artifacts import build_coverage

        print(json.dumps(build_coverage(), indent=2))
        return 0

    if arguments.check_artifacts:
        from swmcp.catalog.artifacts import stale_artifacts

        stale = stale_artifacts()
        if stale:
            print("stale generated files:", file=sys.stderr)
            for path in stale:
                print(f"  {path}", file=sys.stderr)
            print("run: uv run solidworks-mcp --write-artifacts", file=sys.stderr)
            return 1
        print("generated files are current", file=sys.stderr)
        return 0

    if arguments.write_artifacts:
        from swmcp.catalog.artifacts import write_artifacts

        written = write_artifacts()
        print(f"updated {len(written)} file(s)", file=sys.stderr)
        for path in written:
            print(f"  {path}", file=sys.stderr)
        return 0

    if arguments.doctor:
        from swmcp.dispatch import Dispatcher

        dispatcher = Dispatcher()
        try:
            print(json.dumps(dispatcher.call("sw_health", {"probe": True}), indent=2, default=str))
        finally:
            dispatcher.close()
        return 0

    asyncio.run(_serve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
