"""Classify a COM failure structurally, by HRESULT — never by message text.

Two things here that neither sibling project does:

``DISP_E_EXCEPTION`` is unwrapped. A large share of real SOLIDWORKS failures arrive as
``0x80020009`` with the meaningful code hidden in ``excepinfo[5]``; reporting the
wrapper instead of the cause turns a specific diagnosis into a generic one.

Retry is scoped to reads. A non-idempotent CAD mutation must be attempted at most
once, because a retried extrude can leave a second body behind. The worker turns a
mutation timeout into an explicit "outcome unknown" instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from swmcp.decode.hresult import (
    DISP_E_EXCEPTION,
    HResultInfo,
    decode_hresult,
    format_hresult,
    is_disconnected,
    is_retryable,
    normalize_hresult,
)
from swmcp.errors import ErrorCategory, ErrorEnvelope, make_error


@dataclass(frozen=True, slots=True)
class ComVerdict:
    hresult: int | None
    code: str
    category: ErrorCategory
    message: str
    retryable: bool
    disconnected: bool
    info: HResultInfo | None = None
    wrapped_hresult: int | None = None
    source: str | None = None
    description: str | None = None

    @property
    def formatted_hresult(self) -> str | None:
        return format_hresult(self.hresult)


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _excepinfo_scode(exc: BaseException) -> int | None:
    """The real code hidden inside a ``DISP_E_EXCEPTION`` wrapper."""
    info = getattr(exc, "excepinfo", None)
    if info is None and getattr(exc, "args", None) and len(exc.args) > 2:
        info = exc.args[2]
    if not isinstance(info, (tuple, list)) or len(info) < 6:
        return None
    return normalize_hresult(_int_or_none(info[5]))


def _excepinfo_text(exc: BaseException) -> tuple[str | None, str | None]:
    info = getattr(exc, "excepinfo", None)
    if info is None and getattr(exc, "args", None) and len(exc.args) > 2:
        info = exc.args[2]
    if not isinstance(info, (tuple, list)) or len(info) < 3:
        return None, None
    source = info[1] if isinstance(info[1], str) else None
    description = info[2] if isinstance(info[2], str) else None
    return source, description


def raw_hresult(exc: BaseException) -> int | None:
    """The HRESULT as reported, without unwrapping."""
    direct = _int_or_none(getattr(exc, "hresult", None))
    if direct is None and getattr(exc, "args", None):
        direct = _int_or_none(exc.args[0])
    return normalize_hresult(direct)


def hresult_of(exc: BaseException) -> int | None:
    """The most specific HRESULT available, unwrapping ``DISP_E_EXCEPTION``."""
    outer = raw_hresult(exc)
    if outer == DISP_E_EXCEPTION:
        inner = _excepinfo_scode(exc)
        if inner:
            return inner
    return outer


def classify(exc: BaseException) -> ComVerdict:
    """Reduce any exception to a stable code, a category, and a retry decision."""
    outer = raw_hresult(exc)
    effective = hresult_of(exc)
    wrapped = outer if (outer == DISP_E_EXCEPTION and effective != outer) else None
    source, description = _excepinfo_text(exc)

    if effective is None:
        return ComVerdict(
            hresult=None,
            code="WORKER_ERROR",
            category="worker",
            message=str(exc) or exc.__class__.__name__,
            retryable=False,
            disconnected=False,
        )

    info = decode_hresult(effective)
    message = description or (info.message if info else None) or str(exc)
    return ComVerdict(
        hresult=effective,
        code=info.code if info else "COM_ERROR",
        category="com",
        message=message,
        retryable=is_retryable(effective),
        disconnected=is_disconnected(effective),
        info=info,
        wrapped_hresult=wrapped,
        source=source,
        description=description,
    )


def to_envelope(
    exc: BaseException,
    *,
    com_interface: str | None = None,
    context: dict[str, Any] | None = None,
) -> ErrorEnvelope:
    """Build the wire error for a COM failure."""
    verdict = classify(exc)
    extra = dict(context or {})
    if verdict.source:
        extra.setdefault("com_source", verdict.source)
    if verdict.wrapped_hresult is not None:
        extra.setdefault("wrapped_hresult", format_hresult(verdict.wrapped_hresult))
        extra.setdefault(
            "note",
            "SOLIDWORKS reported DISP_E_EXCEPTION; the code above is the underlying cause.",
        )
    return make_error(
        verdict.code,
        verdict.category,
        verdict.message,
        hresult=verdict.formatted_hresult,
        com_interface=com_interface,
        context=extra,
        remediation=list(verdict.info.remediation) if verdict.info else [],
    )
