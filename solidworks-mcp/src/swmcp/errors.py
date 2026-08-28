"""Structured error envelope shared by every layer.

Every failure that reaches a caller is an ``ErrorEnvelope``: a stable machine code, a
category, and — the part that matters for an agent — a list of imperative next steps.
A bare message is not an error report; ``remediation`` is required to be useful.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ErrorCategory = Literal[
    "validation",  # the request was malformed or violated policy before any COM call
    "policy",  # the request was well-formed but refused by a safety gate
    "com",  # the COM layer failed (HRESULT)
    "solidworks",  # SOLIDWORKS returned a documented error code
    "reference",  # an entity reference was stale, ambiguous, or unresolvable
    "worker",  # the STA worker or session could not service the call
    "timeout",  # the call did not complete in time; outcome may be unknown
]


class ErrorEnvelope(BaseModel):
    """The single wire shape for every failure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(description="Stable machine-readable code, e.g. PATH_NOT_ALLOWED.")
    category: ErrorCategory
    message: str
    hresult: str | None = Field(
        default=None, description="Formatted HRESULT such as '0x800706BA', when COM-sourced."
    )
    sw_error_code: int | None = Field(
        default=None, description="Raw SOLIDWORKS enum value, e.g. swFileLoadError_e."
    )
    sw_error_name: str | None = Field(
        default=None, description="Decoded SOLIDWORKS enum name for sw_error_code."
    )
    com_interface: str | None = Field(
        default=None, description="COM interface and member that failed, e.g. 'IModelDoc2.Save3'."
    )
    context: dict[str, Any] = Field(default_factory=dict)
    remediation: list[str] = Field(
        default_factory=list, description="Imperative next steps the caller can act on."
    )
    doc_link: str | None = None
    caused_by: ErrorEnvelope | None = None


ErrorEnvelope.model_rebuild()


class SwMcpError(Exception):
    """Carries an :class:`ErrorEnvelope` through the call stack."""

    def __init__(self, envelope: ErrorEnvelope) -> None:
        super().__init__(f"[{envelope.code}] {envelope.message}")
        self.envelope = envelope


def _doc_link(code: str) -> str:
    return f"swmcp://errors/{code}"


def make_error(
    code: str,
    category: ErrorCategory,
    message: str,
    *,
    remediation: list[str] | None = None,
    context: dict[str, Any] | None = None,
    hresult: str | None = None,
    sw_error_code: int | None = None,
    sw_error_name: str | None = None,
    com_interface: str | None = None,
    caused_by: ErrorEnvelope | None = None,
) -> ErrorEnvelope:
    return ErrorEnvelope(
        code=code,
        category=category,
        message=message,
        hresult=hresult,
        sw_error_code=sw_error_code,
        sw_error_name=sw_error_name,
        com_interface=com_interface,
        context=context or {},
        remediation=remediation or [],
        doc_link=_doc_link(code),
        caused_by=caused_by,
    )


def raise_error(code: str, category: ErrorCategory, message: str, **kwargs: Any) -> None:
    """Raise a :class:`SwMcpError` built from :func:`make_error`."""
    raise SwMcpError(make_error(code, category, message, **kwargs))


def validation_error(code: str, message: str, **kwargs: Any) -> ErrorEnvelope:
    return make_error(code, "validation", message, **kwargs)


def policy_error(code: str, message: str, **kwargs: Any) -> ErrorEnvelope:
    return make_error(code, "policy", message, **kwargs)


def worker_error(code: str, message: str, **kwargs: Any) -> ErrorEnvelope:
    return make_error(code, "worker", message, **kwargs)


def reference_error(code: str, message: str, **kwargs: Any) -> ErrorEnvelope:
    return make_error(code, "reference", message, **kwargs)


def timeout_error(code: str, message: str, **kwargs: Any) -> ErrorEnvelope:
    return make_error(code, "timeout", message, **kwargs)


def wire_safe_validation_errors(error: Any) -> list[dict[str, Any]]:
    """Reduce a pydantic ``ValidationError`` to something that can leave the process.

    ``ValidationError.errors()`` looks JSON-safe and is not: when a ``model_validator``
    raises, pydantic puts the original ``ValueError`` **object** into each entry's
    ``ctx``, and the input value can be any Python object at all. Handing that straight
    to the error envelope means the envelope cannot be serialized, so a schema
    rejection — the most ordinary failure there is — turns into an exception escaping
    the server instead of a clean INVALID_ARGUMENTS payload.

    Only the four fields a caller can act on survive, each coerced to text.
    """
    reduced: list[dict[str, Any]] = []
    for entry in error.errors(include_url=False):
        location = entry.get("loc") or ()
        item: dict[str, Any] = {
            "loc": [str(part) for part in location],
            "type": str(entry.get("type", "")),
            "msg": str(entry.get("msg", "")),
        }
        if "input" in entry:
            item["input"] = _describe_input(entry["input"])
        reduced.append(item)
    return reduced


def _describe_input(value: Any) -> Any:
    """Keep JSON primitives as they are; describe anything else without embedding it."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_describe_input(item) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key): _describe_input(item) for key, item in list(value.items())[:20]}
    return f"<{type(value).__name__}>"
