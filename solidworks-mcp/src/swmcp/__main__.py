"""CLI entry point: the MCP server, plus the commands the skill drives.

With no command it serves MCP over stdio, as it always has. ``stdout`` is then the MCP
transport, so every diagnostic goes to ``stderr``; a stray ``print`` in a handler would
otherwise corrupt the protocol stream.

The other commands run one thing and exit::

    solidworks-mcp call <operation> [JSON | @file.json | -]
    solidworks-mcp tools [query ...] [--domain D]
    solidworks-mcp describe <operation>
    solidworks-mcp install-skill [--dest DIR]

``call`` prints the same JSON payload an MCP client would receive and exits 0 when the
operation succeeded and verified, 1 when it failed, and 2 when it ran but its read-back
verification did not hold — so a shell caller cannot mistake the last for success.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

#: Exit status for an operation that ran but whose read-back checks did not hold.
EXIT_UNVERIFIED = 2


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="solidworks-mcp",
        description="SOLIDWORKS automation: an MCP server, and the commands a skill drives.",
    )
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

    commands = parser.add_subparsers(dest="command", metavar="command")
    commands.add_parser("serve", help="serve MCP over stdio (the default with no command)")

    call = commands.add_parser("call", help="run one operation and print its JSON payload")
    call.add_argument("operation", help="e.g. sw_doc_new, or doc_new")
    call.add_argument(
        "arguments",
        nargs="?",
        default=None,
        help="a JSON object, @path to read one from a file, or - to read stdin",
    )
    call.add_argument(
        "--allowed-root",
        action="append",
        default=None,
        metavar="DIR",
        help="a directory this call may write into (repeatable); replaces SWMCP_ALLOWED_ROOTS",
    )

    tools = commands.add_parser("tools", help="search the operation catalog")
    tools.add_argument("query", nargs="*", help="words matched against names, summaries, tags")
    tools.add_argument("--domain", default=None, help="restrict results to one domain")
    tools.add_argument("--limit", type=int, default=20)

    describe = commands.add_parser("describe", help="print one operation's schema and safety")
    describe.add_argument("operation")

    install = commands.add_parser(
        "install-skill", help="copy the agent skill into a skills directory"
    )
    install.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="the skill directory to create (default: ~/.claude/skills/solidworks)",
    )
    install.add_argument(
        "--force", action="store_true", help="replace an earlier install of this skill"
    )
    return parser


def _emit(payload: Any) -> None:
    """Print JSON as UTF-8 whatever the console's code page.

    Warnings and remediation text carry em dashes and degree signs, and a Windows
    console defaulting to cp1252 would raise on the first one — after the operation had
    already run, which is the worst moment to lose its result.
    """
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    sys.stdout.flush()


def _read_arguments(source: str | None) -> dict[str, Any]:
    if source is None or not source.strip():
        return {}
    if source == "-":
        text = sys.stdin.read()
    elif source.startswith("@"):
        text = Path(source[1:]).read_text(encoding="utf-8")
    else:
        text = source
    value = json.loads(text) if text.strip() else {}
    if not isinstance(value, dict):
        raise ValueError("arguments must be a JSON object")
    return value


def _call(arguments: argparse.Namespace) -> int:
    from swmcp.library import SolidWorks

    try:
        raw = _read_arguments(arguments.arguments)
    except (OSError, ValueError) as exc:
        _emit({"ok": False, "error": {"code": "INVALID_ARGUMENTS", "message": str(exc)}})
        return 1

    sw = SolidWorks(allowed_roots=arguments.allowed_root, strict=False)
    drain = 5.0
    try:
        outcome = sw.execute(arguments.operation, raw)
        _emit(outcome.payload())
        if outcome.error is not None:
            if outcome.error.code == "WORKER_OUTCOME_UNKNOWN":
                # The call is still running inside SOLIDWORKS. The worker is a daemon
                # thread, so exiting now would abandon it mid-flight; wait it out.
                drain = sw.config.call_timeout_s
                print(
                    f"waiting up to {drain:.0f}s for the call to finish inside SOLIDWORKS "
                    "before exiting",
                    file=sys.stderr,
                )
            return 1
        verification = getattr(outcome.result, "verification", None)
        if verification is not None and not verification.all_passed:
            return EXIT_UNVERIFIED
        return 0
    finally:
        sw.close(drain)


def _tools(arguments: argparse.Namespace) -> int:
    from dataclasses import replace

    from swmcp.catalog.search import search_tools
    from swmcp.config import get_config

    # Every tier: the CLI can call anything, so its search must not hide anything.
    config = replace(get_config(), tool_tier="all")
    _emit(search_tools(" ".join(arguments.query), arguments.domain, arguments.limit, config))
    return 0


def _describe(arguments: argparse.Namespace) -> int:
    from swmcp.library import SolidWorks

    try:
        _emit(SolidWorks.describe(arguments.operation))
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    return 0


def _install_skill(arguments: argparse.Namespace) -> int:
    from swmcp.skill_install import SkillInstallError, install_skill

    try:
        installed = install_skill(arguments.dest, force=arguments.force)
    except SkillInstallError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"installed the solidworks skill at {installed.resolve()}", file=sys.stderr)
    return 0


_COMMANDS = {
    "call": _call,
    "tools": _tools,
    "describe": _describe,
    "install-skill": _install_skill,
}


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)

    _configure_logging(arguments.verbose)

    handler = _COMMANDS.get(arguments.command)
    if handler is not None:
        return handler(arguments)

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
