"""Fake COM objects that reproduce pywin32 *pathologies*, not just happy paths.

A double that always behaves is useless here: every bug this layer exists to absorb is
a binding-mode difference. So each fake can be put into the awkward mode on purpose.
"""

from __future__ import annotations

from typing import Any


class FakeComError(Exception):
    """Stands in for ``pywintypes.com_error``, including its attribute shape."""

    def __init__(
        self,
        hresult: int,
        strerror: str = "COM error",
        excepinfo: tuple[Any, ...] | None = None,
        argerror: Any = None,
    ):
        signed = hresult if hresult < 0x80000000 else hresult - 0x100000000
        self.hresult = signed
        self.strerror = strerror
        self.excepinfo = excepinfo
        self.argerror = argerror
        super().__init__(signed, strerror, excepinfo, argerror)


def disp_exception(inner_hresult: int, description: str = "SOLIDWORKS raised an error") -> FakeComError:
    """A ``DISP_E_EXCEPTION`` wrapper with the real code buried in ``excepinfo[5]``."""
    signed_inner = inner_hresult if inner_hresult < 0x80000000 else inner_hresult - 0x100000000
    return FakeComError(
        0x80020009,
        "Exception occurred.",
        (0, "SolidWorks", description, None, 0, signed_inner),
    )


class ByRefVariant:
    """Stands in for ``win32com.client.VARIANT(VT_BYREF | ..., seed)``."""

    def __init__(self, value: Any = 0):
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ByRefVariant({self.value!r})"


class PropertyModeDoc:
    """Late binding: ``GetTitle`` is already a value, so calling it raises TypeError.

    This is the exact failure observed on SOLIDWORKS 2026:
    ``TypeError: 'str' object is not callable``.
    """

    GetTitle = "bracket.SLDPRT"
    GetPathName = r"C:\cad\bracket.SLDPRT"
    GetType = 1


class MethodModeDoc:
    """Generated-proxy binding: the same names are real methods."""

    def GetTitle(self) -> str:
        return "bracket.SLDPRT"

    def GetPathName(self) -> str:
        return r"C:\cad\bracket.SLDPRT"

    def GetType(self) -> int:
        return 1


class PseudoCallableValue(str):
    """A resolved property value that is still callable, and refuses to be called.

    This is what pywin32 hands back for some SOLIDWORKS members: the object already
    *is* the value, but invoking it raises ``DISP_E_MEMBERNOTFOUND``. Returning the
    object itself is therefore the correct recovery, and the reason ``get_com_member``
    hands back the attribute rather than a sentinel.
    """

    message: str

    def __new__(cls, value: str, message: str) -> PseudoCallableValue:
        instance = super().__new__(cls, value)
        instance.message = message
        return instance

    def __call__(self, *_args: Any, **_kwargs: Any):
        raise FakeComError(0x80020003, self.message)


class MemberNotFoundDoc:
    """Callable, but invoking it reports DISP_E_MEMBERNOTFOUND — a property after all.

    The message is deliberately localized to prove classification does not read text.
    """

    def __init__(self, message: str = "\u627e\u4e0d\u5230\u6210\u5458\u3002"):
        self._message = message

    @property
    def GetTitle(self) -> PseudoCallableValue:  # noqa: N802 - mirrors the COM member name
        return PseudoCallableValue("bracket.SLDPRT", self._message)


class VariantMutatingApp:
    """``OpenDoc6`` writes into the by-ref VARIANTs and returns only the document."""

    def __init__(self, document: Any = "MODEL", errors: int = 0, warnings: int = 0):
        self._document = document
        self._errors = errors
        self._warnings = warnings
        self.calls: list[tuple[Any, ...]] = []

    def OpenDoc6(self, path, doc_type, options, configuration, errors, warnings):  # noqa: N802
        self.calls.append((path, doc_type, options, configuration))
        errors.value = self._errors
        warnings.value = self._warnings
        return self._document


class TupleReturningApp:
    """The other binding mode: out-params come back appended to the return value."""

    def __init__(self, document: Any = "MODEL", errors: int = 0, warnings: int = 0):
        self._document = document
        self._errors = errors
        self._warnings = warnings
        self.calls: list[tuple[Any, ...]] = []

    def OpenDoc6(self, path, doc_type, options, configuration, _errors, _warnings):  # noqa: N802
        self.calls.append((path, doc_type, options, configuration))
        return (self._document, self._errors, self._warnings)
