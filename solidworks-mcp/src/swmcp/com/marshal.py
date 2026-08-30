"""pywin32 marshalling shims for the SOLIDWORKS API.

Three pathologies, all confirmed against SOLIDWORKS 2026 on this machine, that every
call site would otherwise have to handle:

1. **Property-or-method duality.** ``model.GetTitle()`` raises
   ``TypeError: 'str' object is not callable`` under late binding, because pywin32
   already resolved the property. Under a generated proxy the same name is a method.
   :func:`get_com_member` accepts both.

2. **By-ref out-parameters.** ``OpenDoc6`` reports errors and warnings through
   ``[out]`` longs. Depending on binding, pywin32 either mutates the ``VARIANT`` in
   place or returns a tuple of ``(retval, out1, out2)``. :func:`call_with_outparams`
   handles both and reports the same result either way.

3. **Null IDispatch arguments.** Passing Python ``None`` for an optional Callout or
   ExportData parameter raises ``TypeError: Objects of type 'NoneType' can not be
   converted to a COM VARIANT``. :func:`null_dispatch` is the accepted value.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Sequence
from typing import Any

from swmcp.com.classify import hresult_of
from swmcp.decode.hresult import HRESULT_TABLE  # noqa: F401  (documents the code space)

DISP_E_MEMBERNOTFOUND = 0x80020003

try:  # pragma: no cover - exercised on Windows only
    import pythoncom
    from win32com.client import VARIANT

    COM_AVAILABLE = True
except ImportError:  # pragma: no cover - keeps the module importable off Windows
    pythoncom = None  # type: ignore[assignment]
    VARIANT = None  # type: ignore[assignment]
    COM_AVAILABLE = False


class MissingComSupport(RuntimeError):
    """Raised when a COM-only helper is used without pywin32 present."""


def _require_com() -> None:
    if not COM_AVAILABLE:  # pragma: no cover - Windows-only path
        raise MissingComSupport(
            "pywin32 is not importable; COM marshalling helpers are unavailable."
        )


# --- member access ------------------------------------------------------------

_UNSET = object()


def _resolve(member: Any) -> Any:
    """Invoke a member if it really is a method; otherwise it is already the value."""
    if not callable(member):
        # pywin32 already resolved this as a property; the value is the answer.
        return member
    try:
        return member()
    except TypeError:
        # A value that is not really callable; the attribute itself is the answer.
        return member
    except Exception as exc:
        if hresult_of(exc) == DISP_E_MEMBERNOTFOUND:
            # Callable, but SOLIDWORKS says there is no such method: it was a property.
            return member
        raise


def get_com_member(obj: Any, name: str, *args: Any, default: Any = _UNSET) -> Any:
    """Read a SOLIDWORKS member that may be a property or a method.

    Classification is by HRESULT. Matching on ``"Member not found"`` — as one sibling
    project does — breaks on a non-English Windows, which is covered by a test.
    """
    try:
        member = getattr(obj, name)
        return member(*args) if args else _resolve(member)
    except Exception:
        if default is not _UNSET:
            return default
        raise


def try_com_member(obj: Any, name: str, *args: Any, default: Any = None) -> Any:
    """:func:`get_com_member` that degrades to ``default`` instead of raising.

    For evidence gathering, where a missing optional property should become a warning
    rather than fail the whole read.
    """
    try:
        return get_com_member(obj, name, *args, default=default)
    except Exception:
        return default


# --- out-parameters -----------------------------------------------------------


def out_long(initial: int = 0) -> Any:
    """A ``[out] long`` slot, e.g. the errors/warnings of ``OpenDoc6``."""
    _require_com()
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, initial)


def out_bstr(initial: str = "") -> Any:
    _require_com()
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, initial)


def out_bool(initial: bool = False) -> Any:
    _require_com()
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, initial)


def out_double(initial: float = 0.0) -> Any:
    _require_com()
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, initial)


def null_dispatch() -> Any:
    """A null ``IDispatch`` argument — Python ``None`` is rejected by the marshaller."""
    _require_com()
    return VARIANT(pythoncom.VT_DISPATCH, None)


def out_dispatch() -> Any:
    """An ``[out] IDispatch*`` slot, e.g. the geometry ``GetRemainingDOFs`` hands back.

    Distinct from :func:`null_dispatch`: that is a null *input*, this is an empty
    *output*. ``GetRemainingDOFs`` rejects ``VT_BYREF | VT_VARIANT`` with "Type
    mismatch" at its second parameter and accepts only this form, which is not
    something the type library says — it declares the parameter as a plain ``[out]``.
    """
    _require_com()
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_DISPATCH, None)


def array_of_doubles(values: Sequence[float]) -> Any:
    _require_com()
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in values])


def array_of_strings(values: Sequence[str]) -> Any:
    _require_com()
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [str(v) for v in values])


def array_of_dispatch(values: Sequence[Any]) -> Any:
    _require_com()
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(values))


def call_with_outparams(
    method: Callable[..., Any],
    *args: Any,
    outparams: Sequence[Any],
) -> tuple[Any, list[Any]]:
    """Call a COM method whose trailing arguments are ``[out]`` slots.

    Returns ``(return_value, [out_values])`` regardless of whether pywin32 mutated the
    ``VARIANT`` objects in place or returned them appended to the return value.
    """
    result = method(*args)
    count = len(outparams)

    if isinstance(result, (tuple, list)) and count and len(result) == count + 1:
        values = list(result)
        primary = values[0]
        collected = values[1:]
        # Keep the VARIANTs consistent with what the caller may inspect directly.
        for slot, value in zip(outparams, collected, strict=False):
            # A caller may pass a plain value rather than a VARIANT slot.
            with contextlib.suppress(AttributeError):
                slot.value = value
        return primary, collected

    return result, [getattr(slot, "value", slot) for slot in outparams]


# --- SAFEARRAY normalization --------------------------------------------------


def normalize_bytes(value: Any) -> bytes | None:
    """Coerce a byte SAFEARRAY into ``bytes``.

    ``GetPersistReference3`` returns ``bytes`` under one binding and a tuple of small
    integers under another. Both must produce the same base64 blob, or a reference
    captured in one session will not resolve in the next.
    """
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, (tuple, list)):
        try:
            return bytes(int(item) & 0xFF for item in value)
        except (TypeError, ValueError):
            return None
    return None


def normalize_sequence(value: Any) -> list[Any]:
    """Coerce a COM SAFEARRAY (or a lone object, or ``None``) into a list."""
    if value is None:
        return []
    if isinstance(value, (tuple, list)):
        return list(value)
    return [value]
