"""Typed, auditable SOLIDWORKS automation over COM: a library, an MCP server, a skill.

The library is the core. The MCP server (``solidworks-mcp``) and the skill's CLI
(``python -m swmcp call ...``) are front ends over the same dispatch pipeline::

    from swmcp import SolidWorks

    with SolidWorks() as sw:
        print(sw.health().model_dump())

The names below are imported on first use, so ``import swmcp`` stays cheap and the CLI
can start without loading the handler modules.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

__version__ = "0.1.0"

__all__ = [
    "OperationError",
    "SolidWorks",
    "SwMcpError",
    "SwmcpConfig",
    "VerificationFailed",
    "__version__",
]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from swmcp.config import SwmcpConfig
    from swmcp.errors import SwMcpError
    from swmcp.library import OperationError, SolidWorks, VerificationFailed

_LAZY = {
    "OperationError": "swmcp.library",
    "SolidWorks": "swmcp.library",
    "VerificationFailed": "swmcp.library",
    "SwMcpError": "swmcp.errors",
    "SwmcpConfig": "swmcp.config",
}


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module 'swmcp' has no attribute {name!r}")
    return getattr(importlib.import_module(module), name)
