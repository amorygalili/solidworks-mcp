"""What a handler receives.

Handlers are plain synchronous functions of ``(ctx, args)`` returning a pydantic
model. They never see the queue, the event loop, or the MCP protocol — which is what
makes them directly callable from tests against fake COM objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from swmcp.config import SwmcpConfig
from swmcp.envelope import CheckpointRecord, UnitEcho

if TYPE_CHECKING:  # pragma: no cover - typing only
    from swmcp.catalog.spec import OpSpec
    from swmcp.com.session import SwSession
    from swmcp.com.worker import StaWorker
    from swmcp.safety.checkpoint import CheckpointStore


@dataclass(slots=True)
class OpContext:
    """Everything a handler needs, resolved by the dispatch pipeline."""

    session: SwSession
    config: SwmcpConfig
    checkpoints: CheckpointStore
    spec: OpSpec
    request_id: str
    worker: StaWorker | None = None
    doc: Any | None = None
    checkpoint: CheckpointRecord | None = None
    units: UnitEcho = field(default_factory=UnitEcho)
    warnings: list[str] = field(default_factory=list)

    @property
    def app(self) -> Any:
        """The ``ISldWorks`` application object."""
        return self.session.app

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def require_doc(self) -> Any:
        """The resolved document, or a clear error naming what to do about it."""
        if self.doc is None:
            from swmcp.errors import SwMcpError, make_error

            raise SwMcpError(
                make_error(
                    "NO_ACTIVE_DOCUMENT",
                    "validation",
                    f"{self.spec.name} needs a document, but none is active.",
                    remediation=[
                        "Create or open a document first, "
                        "or name one explicitly in the document argument.",
                    ],
                )
            )
        return self.doc
