"""SAFE-006: an append-only record of every write the server performs.

Best-effort by design: an audit failure must never break the MCP stdio channel or
abort a mutation that already happened. A dropped line is recorded as a warning on the
next successful read rather than raised.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swmcp.config import SwmcpConfig, get_config

_LOCK = threading.Lock()
_DEFAULT_DIR = ".mcp-audit"
_DEFAULT_NAME = "audit.jsonl"
# Arguments whose values are large or uninteresting in an audit trail.
_ELIDE_KEYS = {"entities", "candidates", "persistent", "tool_args"}
_MAX_VALUE_CHARS = 2000


def audit_path(config: SwmcpConfig | None = None) -> Path:
    config = config or get_config()
    if config.audit_path is not None:
        return config.audit_path
    return Path.cwd() / _DEFAULT_DIR / _DEFAULT_NAME


def _normalize_scalar(args: Any) -> Any:
    if isinstance(args, str) and len(args) > _MAX_VALUE_CHARS:
        return args[:_MAX_VALUE_CHARS] + "<truncated>"
    if isinstance(args, (str, int, float, bool)) or args is None:
        return args
    return repr(args)[:_MAX_VALUE_CHARS]


def normalize_args(args: Any, *, _depth: int = 0) -> Any:
    """Reduce arguments to something worth keeping: bounded, JSON-safe, no blobs."""
    if _depth > 4:
        return "<nested>"
    if isinstance(args, dict):
        return {
            key: (
                f"<elided {type(value).__name__}>"
                if key in _ELIDE_KEYS
                else normalize_args(value, _depth=_depth + 1)
            )
            for key, value in args.items()
        }
    if isinstance(args, (list, tuple)):
        head = [normalize_args(v, _depth=_depth + 1) for v in list(args)[:20]]
        overflow = len(args) - 20
        return [*head, f"<+{overflow} more>"] if overflow > 0 else head
    return _normalize_scalar(args)


def append_audit(
    *,
    tool: str,
    ok: bool,
    destructive: bool = False,
    args: Any = None,
    document: str | None = None,
    checkpoint_path: str | None = None,
    checkpoint_method: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    duration_ms: float | None = None,
    config: SwmcpConfig | None = None,
) -> bool:
    """Append one audit line. Returns whether the write succeeded."""
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "tool": tool,
        "ok": ok,
        "destructive": destructive,
        "document": document,
        "args": normalize_args(args),
        "checkpoint_path": checkpoint_path,
        "checkpoint_method": checkpoint_method,
        "error_code": error_code,
        "error_message": error_message,
        "duration_ms": duration_ms,
        "pid": os.getpid(),
    }
    try:
        line = json.dumps(entry, ensure_ascii=False, default=repr)
    except (TypeError, ValueError):
        return False

    target = audit_path(config)
    try:
        with _LOCK:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return True
    except OSError:
        # Auditing is evidence, not a gate. Losing a line must not lose the operation.
        return False


def read_recent(limit: int = 20, config: SwmcpConfig | None = None) -> list[dict[str, Any]]:
    """Most recent entries first."""
    target = audit_path(config)
    if not target.is_file():
        return []
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in reversed([line for line in lines if line.strip()]):
        if len(entries) >= limit:
            break
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"raw": line, "parse_error": True})
    return entries
