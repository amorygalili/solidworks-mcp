"""The Python library: every operation as a method, through the one dispatch pipeline.

The MCP server and the skill's CLI are both thin front ends over this same pipeline,
so a script gets exactly what an MCP client gets — the same validation, the same path
policy, the same confirmation gate, checkpoints, audit and read-back verification —
with typed results instead of JSON::

    from swmcp import SolidWorks

    with SolidWorks(allowed_roots=[r"C:\\cad\\work"]) as sw:
        sw.doc_new(doc_type="part")
        sw.sketch_start(plane="Front")
        ...

There is one difference, and it is deliberate. An MCP client reads the warnings and
the verification block; a script that only looks at a return value would build on
geometry that was never made. So by default a mutation whose read-back checks did not
hold raises :class:`VerificationFailed` rather than returning quietly. Pass
``strict=False`` to get the result back and judge it yourself.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.catalog.search import describe_tool, method_name, resolve_op_name, search_tools
from swmcp.config import SwmcpConfig, get_config
from swmcp.dispatch import Dispatcher, Outcome
from swmcp.envelope import Check, MutationResult
from swmcp.errors import ErrorEnvelope, SwMcpError
from swmcp.operations import Operations


class OperationError(SwMcpError):
    """An operation failed. Carries the envelope the MCP server would have sent."""

    def __init__(self, envelope: ErrorEnvelope, *, tool: str | None, request_id: str) -> None:
        super().__init__(envelope)
        self.tool = tool
        self.request_id = request_id

    @property
    def code(self) -> str:
        return self.envelope.code

    @property
    def remediation(self) -> list[str]:
        return list(self.envelope.remediation)


class VerificationFailed(Exception):
    """A mutation ran, but reading the model back did not confirm it.

    The result is attached, because the model *has* changed in some way and the caller
    needs the evidence — and the checkpoint — to decide what to do next.
    """

    def __init__(self, tool: str, result: MutationResult) -> None:
        self.tool = tool
        self.result = result
        self.failed_checks: list[Check] = [c for c in result.verification.checks if not c.passed]
        detail = "; ".join(
            f"{c.name} ({c.detail})" if c.detail else c.name for c in self.failed_checks
        )
        super().__init__(f"{tool}: read-back verification did not hold: {detail}")


class SolidWorks(Operations):
    """A SOLIDWORKS session, driven through the same pipeline as the MCP server.

    Every catalog operation is a method named for it without the ``sw_`` prefix —
    ``sw_feature_extrude_boss`` is :meth:`feature_extrude_boss` — taking keywords, a
    dict, or the operation's args model, and returning its result model. Tiers do not
    apply here: they exist to keep an MCP client's tool list short, and a script calls
    whatever it names.

    One worker thread owns every COM call, so a ``SolidWorks`` is used from one thread
    at a time and closed when done; it is a context manager for that reason.
    """

    def __init__(
        self,
        config: SwmcpConfig | None = None,
        *,
        allowed_roots: Iterable[str | Path] | None = None,
        strict: bool = True,
        dispatcher: Dispatcher | None = None,
        **overrides: Any,
    ) -> None:
        """
        ``config`` defaults to the ``SWMCP_*`` environment, exactly as the server reads
        it. ``allowed_roots`` and any other :class:`~swmcp.config.SwmcpConfig` field
        given as a keyword override it. ``dispatcher`` is for tests that need to inject
        a worker; when given, the configuration is taken from it.
        """
        #: Only a dispatcher this client built is stopped by :meth:`close`. One handed
        #: in belongs to someone else, and a stopped worker thread cannot be restarted.
        self._owns_dispatcher = dispatcher is None
        if dispatcher is not None:
            if config is not None or allowed_roots is not None or overrides:
                raise TypeError("pass either a dispatcher or configuration, not both")
            self._dispatcher = dispatcher
        else:
            resolved = config or get_config()
            if allowed_roots is not None:
                overrides["allowed_roots"] = tuple(Path(root) for root in allowed_roots)
            if overrides:
                resolved = dataclasses.replace(resolved, **overrides)
            self._dispatcher = Dispatcher(resolved)
        self.strict = strict
        #: The outcome of the most recent call, including its request id and duration.
        self.last: Outcome | None = None

    # -- calling -----------------------------------------------------------

    @property
    def config(self) -> SwmcpConfig:
        return self._dispatcher.config

    @property
    def dispatcher(self) -> Dispatcher:
        return self._dispatcher

    def execute(
        self, name: str, args: BaseModel | dict[str, Any] | None = None, /, **kwargs: Any
    ) -> Outcome:
        """Run an operation and return its outcome without raising on failure.

        ``name`` may be the wire name (``sw_doc_new``), the bare name, or the method
        name. ``outcome.payload()`` is the exact JSON the MCP server would have sent.
        """
        outcome = self._dispatcher.execute(resolve_op_name(name), _raw_arguments(args, kwargs))
        self.last = outcome
        return outcome

    def call(
        self, name: str, args: BaseModel | dict[str, Any] | None = None, /, **kwargs: Any
    ) -> Any:
        """Run an operation and return its result model.

        Raises :class:`OperationError` when the operation fails, and — while
        :attr:`strict` is set — :class:`VerificationFailed` when a mutation's
        read-back checks did not hold.
        """
        outcome = self.execute(name, args, **kwargs)
        if outcome.error is not None:
            raise OperationError(
                outcome.error, tool=outcome.tool, request_id=outcome.request_id
            )
        result = outcome.result
        if (
            self.strict
            and isinstance(result, MutationResult)
            and not result.verification.all_passed
        ):
            raise VerificationFailed(outcome.tool or name, result)
        return result

    # -- finding operations ------------------------------------------------

    def search_tools(
        self, query: str = "", domain: str | None = None, limit: int = 20
    ) -> dict[str, Any]:
        """Search the catalog by name, summary, tag, domain, or requirement id."""
        return search_tools(
            query, domain, limit, config=dataclasses.replace(self.config, tool_tier="all")
        )

    @staticmethod
    def describe(name: str) -> dict[str, Any]:
        """Everything published about one operation, including its input schema."""
        resolved = resolve_op_name(name)
        spec = OPS.get(resolved)
        if spec is None:
            raise KeyError(f"there is no operation named {name!r}")
        return {"method": method_name(spec.name), **describe_tool(spec)}

    @staticmethod
    def operations() -> list[str]:
        """Every operation's wire name, sorted."""
        return sorted(load_all_ops())

    # -- lifecycle ---------------------------------------------------------

    def close(self, timeout: float = 5.0) -> None:
        """Stop the worker thread.

        Pass a longer ``timeout`` after an operation timed out: the worker is a daemon
        thread, so a process that exits while a COM call is still running inside
        SOLIDWORKS abandons that call mid-flight, which can leave SOLIDWORKS
        unresponsive. Waiting lets the call finish first.

        A client given someone else's ``dispatcher`` leaves it running.
        """
        if self._owns_dispatcher:
            self._dispatcher.worker.stop(timeout)

    def __enter__(self) -> SolidWorks:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _raw_arguments(
    args: BaseModel | dict[str, Any] | None, kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Reduce every accepted argument form to the JSON an MCP client would send.

    A model is dumped back to JSON and validated again by the dispatcher, rather than
    passed through. That costs a round trip and buys a guarantee: the library and the
    server validate identical input, so there is no second path through the gates.
    """
    if args is None:
        raw: dict[str, Any] = {}
    elif isinstance(args, BaseModel):
        raw = args.model_dump(mode="json", exclude_unset=True)
    elif isinstance(args, dict):
        raw = dict(args)
    else:
        raise TypeError(
            f"arguments must be a dict or a pydantic model, not {type(args).__name__}"
        )
    raw.update(kwargs)
    return raw
