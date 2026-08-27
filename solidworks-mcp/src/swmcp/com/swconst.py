"""Access to the SOLIDWORKS constant tables generated from ``swconst.tlb``.

Roughly 980 enums are available, so they are loaded from JSON on first use and turned
into ``IntEnum`` classes only when something actually asks for one. Importing this
module is cheap.

Nothing here hardcodes a constant: the values come from the type library registered on
the machine, which is the only copy guaranteed to match the installed release.
"""

from __future__ import annotations

import json
from enum import IntEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

_TABLE_PATH = Path(__file__).resolve().parent.parent / "generated" / "swconst.json"

_payload: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _payload
    if _payload is None:
        if not _TABLE_PATH.is_file():
            raise FileNotFoundError(
                f"{_TABLE_PATH} is missing. Run: uv run python scripts/gen_swconst.py"
            )
        _payload = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
    return _payload


def table_info() -> dict[str, Any]:
    """Provenance of the constant table, for capability reporting."""
    payload = _load()
    return {
        "typelib_iid": payload["typelib_iid"],
        "typelib_major": payload["typelib_major"],
        "enum_count": payload["enum_count"],
    }


def enum_names() -> list[str]:
    return sorted(_load()["enums"])


def members(enum_name: str) -> dict[str, int]:
    """Raw ``{member_name: value}`` for one enum."""
    enums = _load()["enums"]
    if enum_name not in enums:
        raise KeyError(f"unknown SOLIDWORKS enum {enum_name!r}")
    return dict(enums[enum_name])


@lru_cache(maxsize=None)
def get_enum(enum_name: str) -> type[IntEnum]:
    """Build (and cache) an ``IntEnum`` for one SOLIDWORKS enum."""
    return IntEnum(enum_name, members(enum_name))  # type: ignore[return-value]


def value(enum_name: str, member: str) -> int:
    """Look up one constant, e.g. ``value("swDocumentTypes_e", "swDocPART")``."""
    found = members(enum_name)
    if member not in found:
        raise KeyError(f"{enum_name} has no member {member!r}")
    return found[member]


def name_of(enum_name: str, raw: int) -> str | None:
    """Reverse lookup. Returns ``None`` when the value is not a defined member."""
    for member, candidate in members(enum_name).items():
        if candidate == raw:
            return member
    return None


@lru_cache(maxsize=None)
def is_bitfield(enum_name: str) -> bool:
    """Whether an enum's values combine as flags.

    Detected rather than declared: an enum is a bitfield when every non-zero member is
    a distinct power of two. Guessing wrong in the other direction is what makes a
    sequential enum like ``swAddMateError_e`` (0..6) decode into nonsense — bitwise
    matching would report value 3 as two separate conditions.
    """
    values = [v for v in members(enum_name).values() if v]
    if len(values) < 2:
        return False
    return all(v > 0 and (v & (v - 1)) == 0 for v in values) and len(set(values)) == len(values)


def decode_flags(enum_name: str, raw: int) -> tuple[list[str], int]:
    """Decode a status integer into member names.

    Returns the matched names and any bits left unaccounted for, so an undocumented
    value is reported rather than silently dropped. Bitfield enums can match several
    names at once; sequential enums match at most one.
    """
    found = members(enum_name)
    if raw == 0:
        return [name for name, candidate in found.items() if candidate == 0], 0

    if not is_bitfield(enum_name):
        exact = name_of(enum_name, raw)
        return ([exact], 0) if exact else ([], raw)

    matched: list[str] = []
    remaining = raw
    for name, candidate in sorted(found.items(), key=lambda item: -item[1]):
        if candidate > 0 and (remaining & candidate) == candidate:
            matched.append(name)
            remaining &= ~candidate
    return matched, remaining


def __getattr__(name: str) -> Any:
    """Allow ``swconst.swSelectType_e`` to resolve to a built ``IntEnum``."""
    if name.startswith("sw") or name.endswith("_e"):
        try:
            return get_enum(name)
        except KeyError as exc:
            raise AttributeError(str(exc)) from exc
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
