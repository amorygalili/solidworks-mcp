"""SAFE-009: turn an HRESULT into a stable code and an actionable next step.

Classification is structural — by numeric HRESULT — never by message text. Error
strings from COM are localized, so matching on ``"Member not found"`` silently stops
working on a non-English Windows. That regression is covered by a test.

``DISP_E_EXCEPTION`` gets special handling: a large share of real SOLIDWORKS failures
arrive as ``0x80020009`` with the meaningful code buried in ``excepinfo[5]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DISP_E_EXCEPTION = 0x80020009

RETRYABLE_HRESULTS: frozenset[int] = frozenset({0x8001010A, 0x80010001})
DISCONNECTED_HRESULTS: frozenset[int] = frozenset({0x800706BA, 0x800706BE, 0x80010108, 0x800401E5})


@dataclass(frozen=True, slots=True)
class HResultInfo:
    code: str
    symbol: str
    message: str
    remediation: list[str] = field(default_factory=list)


_BUSY_REMEDIATION = [
    "Check SOLIDWORKS for an open dialog box; a modal dialog blocks every API call.",
    "Retry once the dialog is dismissed. Read-only calls are retried automatically.",
]

HRESULT_TABLE: dict[int, HResultInfo] = {
    0x8001010A: HResultInfo(
        "COM_SERVER_BUSY",
        "RPC_E_SERVERCALL_RETRYLATER",
        "SOLIDWORKS rejected the call because it is busy or showing a dialog.",
        _BUSY_REMEDIATION,
    ),
    0x80010001: HResultInfo(
        "COM_CALL_REJECTED",
        "RPC_E_CALL_REJECTED",
        "SOLIDWORKS rejected the call.",
        _BUSY_REMEDIATION,
    ),
    0x800706BA: HResultInfo(
        "COM_RPC_SERVER_UNAVAILABLE",
        "RPC_S_SERVER_UNAVAILABLE",
        "The SOLIDWORKS process is no longer reachable; it may have exited or crashed.",
        [
            "Confirm SLDWORKS.exe is still running.",
            "Reconnect with the connect operation, then re-open the document.",
            "Check for a checkpoint of any document that was mid-edit.",
        ],
    ),
    0x800706BE: HResultInfo(
        "COM_RPC_FAILED",
        "RPC_S_CALL_FAILED",
        "The remote call to SOLIDWORKS failed part-way through.",
        [
            "The operation's outcome is unknown; inspect the model before repeating it.",
            "Reconnect and re-read the document state.",
        ],
    ),
    0x80010108: HResultInfo(
        "COM_OBJECT_DISCONNECTED",
        "RPC_E_DISCONNECTED",
        "The COM object is disconnected from its server; the session was replaced or closed.",
        ["Reconnect and re-resolve any entity references you were holding."],
    ),
    0x800401E3: HResultInfo(
        "SOLIDWORKS_NOT_RUNNING",
        "MK_E_UNAVAILABLE",
        "No running SOLIDWORKS instance is registered in the running object table.",
        [
            "Start SOLIDWORKS, or call the connect operation with start_if_missing=true.",
            "If SOLIDWORKS is running as a different user or elevation level, "
            "COM cannot attach to it.",
        ],
    ),
    0x800401E5: HResultInfo(
        "SOLIDWORKS_NO_OBJECT",
        "MK_E_NOOBJECT",
        "The requested object is not present in the running object table.",
        ["Reconnect to SOLIDWORKS and retry."],
    ),
    0x80040154: HResultInfo(
        "COM_CLASS_NOT_REGISTERED",
        "REGDB_E_CLASSNOTREG",
        "The SOLIDWORKS COM class is not registered for this Python process.",
        [
            "A 32-bit Python cannot drive a 64-bit SOLIDWORKS; check the interpreter bitness.",
            "Repairing the SOLIDWORKS installation re-registers the COM classes.",
        ],
    ),
    0x800401F3: HResultInfo(
        "COM_INVALID_CLASS_STRING",
        "CO_E_CLASSSTRING",
        "The SOLIDWORKS ProgID is not registered on this machine.",
        ["Confirm SOLIDWORKS is installed; the version-suffixed ProgID may differ."],
    ),
    0x80080005: HResultInfo(
        "COM_SERVER_EXEC_FAILED",
        "CO_E_SERVER_EXEC_FAILURE",
        "Windows could not start the SOLIDWORKS executable that COM activation points at.",
        [
            "A 3DEXPERIENCE-managed install refuses to start this way: COM resolves the "
            "ProgID to sldworks.exe, and that build must be launched from the "
            "3DEXPERIENCE Platform. Start SOLIDWORKS from the Platform, or from the "
            "desktop shortcut it created, then connect again.",
            "The server launches such an install through its Platform shortcut when it "
            "can find one; sw_system_info reports the launch_mode it will use.",
            "COM also cannot start a server across elevation levels.",
        ],
    ),
    0x80020003: HResultInfo(
        "COM_MEMBER_NOT_FOUND",
        "DISP_E_MEMBERNOTFOUND",
        "The COM member does not exist, or is a property being called as a method.",
        [
            "SOLIDWORKS members are property-or-method depending on binding; "
            "the marshalling layer retries the other form automatically.",
            "If it persists, the installed version may not expose this API signature.",
        ],
    ),
    0x80020006: HResultInfo(
        "COM_UNKNOWN_NAME",
        "DISP_E_UNKNOWNNAME",
        "The COM interface has no member with that name.",
        ["Check the member name against the installed version's API."],
    ),
    0x80020009: HResultInfo(
        "COM_EXCEPTION",
        "DISP_E_EXCEPTION",
        "SOLIDWORKS raised an exception during the call.",
        ["The underlying cause is reported in caused_by when SOLIDWORKS supplied one."],
    ),
    0x8002802B: HResultInfo(
        "COM_ELEMENT_NOT_FOUND",
        "TYPE_E_ELEMENTNOTFOUND",
        "The requested type library element was not found.",
        ["The installed SOLIDWORKS version may not provide this interface."],
    ),
    0x80004005: HResultInfo(
        "COM_FAILED",
        "E_FAIL",
        "SOLIDWORKS reported an unspecified failure.",
        [
            "Check the document for rebuild errors and confirm the operation's "
            "preconditions were met.",
        ],
    ),
    0x80070005: HResultInfo(
        "COM_ACCESS_DENIED",
        "E_ACCESSDENIED",
        "Access was denied.",
        [
            "A file may be read-only or locked by another process.",
            "SOLIDWORKS running elevated while this process is not (or the reverse) "
            "blocks COM attachment.",
        ],
    ),
    0x80070057: HResultInfo(
        "COM_INVALID_ARG",
        "E_INVALIDARG",
        "SOLIDWORKS rejected an argument.",
        [
            "Check units: the API takes metres and radians.",
            "Check that entity references still resolve in the current document.",
        ],
    ),
    0x8000FFFF: HResultInfo(
        "COM_UNEXPECTED",
        "E_UNEXPECTED",
        "An unexpected COM failure occurred.",
        ["Reconnect and re-read the document state before repeating the operation."],
    ),
}


def normalize_hresult(raw: int | None) -> int | None:
    """COM error codes arrive as signed 32-bit ints; compare them unsigned."""
    if raw is None:
        return None
    return raw & 0xFFFFFFFF


def format_hresult(raw: int | None) -> str | None:
    normalized = normalize_hresult(raw)
    return None if normalized is None else f"0x{normalized:08X}"


def decode_hresult(raw: int | None) -> HResultInfo | None:
    normalized = normalize_hresult(raw)
    if normalized is None:
        return None
    return HRESULT_TABLE.get(normalized)


def is_retryable(raw: int | None) -> bool:
    return normalize_hresult(raw) in RETRYABLE_HRESULTS


def is_disconnected(raw: int | None) -> bool:
    return normalize_hresult(raw) in DISCONNECTED_HRESULTS
