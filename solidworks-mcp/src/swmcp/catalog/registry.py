"""The ``@op`` decorator and the global operation registry.

Spec and implementation live in one place, so they cannot drift. The handler function
*is* the implementation reference and its annotations *are* the schemas — there is no
schema key string and no handler name string to mistype, which is where a table-driven
catalog normally rots.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, get_type_hints

from pydantic import BaseModel

from swmcp.catalog.spec import (
    DocPrecondition,
    Domain,
    OpSpec,
    SafetyUnion,
    Tier,
)

OPS: dict[str, OpSpec] = {}

F = TypeVar("F", bound=Callable[..., Any])


def _model_from_hint(
    fn: Callable[..., Any], hints: dict[str, Any], key: str, what: str
) -> type[BaseModel]:
    if key not in hints:
        raise TypeError(f"{fn.__qualname__}: missing annotation for {what}")
    candidate = hints[key]
    if not (isinstance(candidate, type) and issubclass(candidate, BaseModel)):
        raise TypeError(
            f"{fn.__qualname__}: {what} must be annotated with a pydantic BaseModel, "
            f"got {candidate!r}"
        )
    return candidate


def op(
    *,
    name: str,
    tier: Tier,
    domains: tuple[Domain, ...],
    summary: str,
    safety: SafetyUnion,
    satisfies: tuple[str, ...] = (),
    partially_satisfies: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    precondition: DocPrecondition = "any",
    idempotent: bool = False,
    timeout_s: float = 120.0,
) -> Callable[[F], F]:
    """Register one operation. The decorated function stays directly callable in tests."""

    def wrap(fn: F) -> F:
        hints = get_type_hints(fn)
        args_model = _model_from_hint(fn, hints, "args", "the `args` parameter")
        result_model = _model_from_hint(fn, hints, "return", "the return value")

        spec = OpSpec(
            name=name,
            tier=tier,
            domains=domains,
            tags=tags,
            summary=summary,
            safety=safety,
            satisfies=satisfies,
            partially_satisfies=partially_satisfies,
            precondition=precondition,
            idempotent=idempotent,
            args_model=args_model,
            result_model=result_model,
            handler=fn,
            handler_ref=f"{fn.__module__}:{fn.__qualname__}",
            timeout_s=timeout_s,
        )
        existing = OPS.get(name)
        if existing is not None and existing.handler_ref != spec.handler_ref:
            raise ValueError(
                f"duplicate op name {name!r}: {existing.handler_ref} vs {spec.handler_ref}"
            )
        OPS[name] = spec
        fn.__op_spec__ = spec  # type: ignore[attr-defined]
        return fn

    return wrap


def load_all_ops() -> dict[str, OpSpec]:
    """Import every handler module so the ``@op`` side effects populate :data:`OPS`."""
    import swmcp.handlers  # noqa: F401  (import side effect is the point)

    return OPS


def get_op(name: str) -> OpSpec | None:
    return OPS.get(name)
