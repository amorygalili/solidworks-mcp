"""Which version of a versioned SOLIDWORKS API member exists, and how many arguments.

SOLIDWORKS never changes a published method; it adds a new one with the next number.
So an install offers ``FeatureExtrusion`` through ``FeatureExtrusion3`` and
``FeatureLinearPattern`` through ``FeatureLinearPattern5``, and a caller has to know
both which numbers exist and how many arguments each takes.

Nothing here picks a newer member automatically. A later version usually takes a
different argument list, so "call the highest number available" would turn a working
call into a silent misuse — the exact class of bug this module exists to surface. What
it does instead is answer two questions the type library can answer definitively:

* does the member this server calls exist on the installed release?
* does the call site pass the number of arguments the member declares?

Both are checked by :mod:`tests.test_api_versions` against the real type library, and
reported through ``sw_capabilities`` as DISC-005 evidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

_TABLE_PATH = Path(__file__).resolve().parent.parent / "generated" / "swapi.json"

#: ``FeatureExtrusion3`` -> family ``FeatureExtrusion``, version 3. An unsuffixed name
#: is version 1, because that is what the next number continues from.
_VERSIONED = re.compile(r"^(?P<family>.*?[A-Za-z])(?P<version>\d+)$")

_payload: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _payload
    if _payload is None:
        if not _TABLE_PATH.is_file():
            raise FileNotFoundError(
                f"{_TABLE_PATH} is missing. Run: uv run python scripts/gen_swapi.py"
            )
        _payload = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
    return _payload


def table_info() -> dict[str, Any]:
    """Provenance of the API table, for capability reporting."""
    payload = _load()
    return {
        "typelib_iid": payload["typelib_iid"],
        "typelib_major": payload["typelib_major"],
        "interface_count": payload["interface_count"],
        "member_count": payload["member_count"],
    }


def interface_names() -> list[str]:
    return sorted(_load()["interfaces"])


def members(interface: str) -> dict[str, dict[str, Any]]:
    interfaces = _load()["interfaces"]
    if interface not in interfaces:
        raise KeyError(f"{interface!r} is not in the API table; add it to scripts/gen_swapi.py")
    return dict(interfaces[interface])


def split_version(member: str) -> tuple[str, int]:
    """``("FeatureExtrusion", 3)``. An unsuffixed member is version 1."""
    match = _VERSIONED.match(member)
    if not match:
        return member, 1
    return match.group("family"), int(match.group("version"))


@cache
def _by_member() -> dict[str, tuple[str, ...]]:
    """``{member_name: (interfaces that declare it, ...)}``, for unqualified lookups."""
    index: dict[str, list[str]] = {}
    for interface, table in _load()["interfaces"].items():
        for member in table:
            index.setdefault(member, []).append(interface)
    return {member: tuple(sorted(names)) for member, names in index.items()}


def interfaces_declaring(member: str) -> tuple[str, ...]:
    """Which captured interfaces declare ``member``. Empty if the table has never seen it."""
    return _by_member().get(member, ())


#: ``PARAMFLAG_FOUT`` with no ``FIN``. pywin32 fills such a parameter in and hands it
#: back, so the caller may omit it — ``IFeature::GetErrorCode2(IsWarning)`` is called
#: with no arguments. An in/out parameter has ``FIN | FOUT`` and must still be passed,
#: which is what ``out_long()`` is for in :mod:`swmcp.com.marshal`.
_OUT_ONLY = 2


def arities(member: str) -> set[int]:
    """Every argument count that is legitimate for ``member``.

    A set, for two reasons: ``Select2`` is declared on many interfaces, and a member
    with pure-out parameters may be called either with them or without.
    """
    found: set[int] = set()
    for interface in interfaces_declaring(member):
        entry = members(interface)[member]
        flags = entry.get("flags") or [1] * len(entry["params"])
        total = len(entry["params"])
        found.add(total)
        found.add(sum(1 for flag in flags if flag != _OUT_ONLY))
    return found


@dataclass(frozen=True)
class CallSite:
    """One SOLIDWORKS API call found in this package's source."""

    member: str
    argument_count: int
    source: str
    line: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "member": self.member,
            "argument_count": self.argument_count,
            "source": self.source,
            "line": self.line,
        }


#: The two shims every duality-safe call goes through. Their first argument is the COM
#: object and their second is the member name, so the COM arguments start at index 2.
_SHIMS = ("try_com_member", "get_com_member")


def _member_of(node: Any) -> str | None:
    import ast

    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


#: Modules that reach Windows rather than SOLIDWORKS — the registry, WMI, and the
#: process mutex. Their PascalCase calls are real, just not SOLIDWORKS API members.
_NOT_SOLIDWORKS = ("com/install.py",)


def _imported_modules(tree: Any) -> set[str]:
    """Names bound by ``import x`` / ``import x as y`` in one module.

    A call through one of these is ``csv.DictReader`` or ``types.TextContent`` — a
    Python call that merely looks like a COM member because of its capital letter.
    """
    import ast

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def scan_unknown_members(root: Path | None = None) -> list[CallSite]:
    """PascalCase calls that look like SOLIDWORKS members the type library has never heard of.

    This is the half of the check that catches a member which does not exist at all —
    ``SketchMove`` was called for months and is on no interface in the library. Skipping
    unknown names, which the arity scan must do, would make that invisible forever.
    """
    import ast

    root = root or Path(__file__).resolve().parent.parent
    known = _by_member()
    found: list[CallSite] = []

    for path in sorted(root.rglob("*.py")):
        if path.name == "apiver.py" or "generated" in path.parts:
            continue
        relative = path.relative_to(root.parent).as_posix()
        if any(relative.endswith(tail) for tail in _NOT_SOLIDWORKS):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        modules = _imported_modules(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            member = node.func.attr
            if not member[:1].isupper() or member in known:
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.Name) and receiver.id in modules:
                continue
            found.append(
                CallSite(
                    member=member,
                    argument_count=len(node.args),
                    source=relative,
                    line=node.lineno,
                )
            )

    return sorted(found, key=lambda site: (site.source, site.line))


def returns_void(member: str) -> bool:
    """Is every interface that declares this member declaring it ``void``?

    Answered conservatively: if any overload on any interface returns a value, a
    caller testing the result may well be right, and this says nothing.
    """
    declaring = interfaces_declaring(member)
    if not declaring:
        return False
    return all(
        members(interface)[member].get("returns_void", False) for interface in declaring
    )


def scan_void_results(root: Path | None = None) -> list[CallSite]:
    """Calls whose result is kept, on members the type library declares ``void``.

    ``IFeatureManager::InsertRib`` is declared void, so its ``None`` return is its
    signature and not a complaint. Reading it as failure reported ``RIB_FAILED`` for a
    rib that had built correctly. Nothing about that is visible at the call site, and
    it cannot be caught by counting arguments — only by knowing the return type.

    A call whose value is discarded (a bare expression statement) is fine; this looks
    for results that are assigned, returned, tested, or passed onward.
    """
    import ast

    root = root or Path(__file__).resolve().parent.parent
    found: list[CallSite] = []

    for path in sorted(root.rglob("*.py")):
        if path.name == "apiver.py" or "generated" in path.parts:
            continue
        relative = path.relative_to(root.parent).as_posix()
        if any(relative.endswith(tail) for tail in _NOT_SOLIDWORKS):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        discarded = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        }

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or node in discarded:
                continue
            member = _member_of(node)
            if member is None or not member[:1].isupper():
                continue
            if not returns_void(member):
                continue
            found.append(
                CallSite(
                    member=member,
                    argument_count=len(node.args),
                    source=relative,
                    line=node.lineno,
                )
            )

    return sorted(found, key=lambda site: (site.source, site.line))


def scan_source(root: Path | None = None) -> list[CallSite]:
    """Find every call in ``swmcp`` that reaches a member the API table knows about.

    Deliberately conservative: a call with ``*args`` has no countable arity and is
    skipped, and a name the type library has never heard of is not a COM call at all.
    Everything this package writes is snake_case, so a PascalCase attribute call that
    matches a type-library member is a SOLIDWORKS call and not a coincidence.
    """
    import ast

    root = root or Path(__file__).resolve().parent.parent
    known = _by_member()
    found: list[CallSite] = []

    for path in sorted(root.rglob("*.py")):
        if path.name == "apiver.py" or "generated" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(root.parent).as_posix()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if any(isinstance(argument, ast.Starred) for argument in node.args):
                continue

            member: str | None = None
            count = 0

            called = node.func
            if isinstance(called, ast.Name) and called.id in _SHIMS:
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    name = node.args[1].value
                    if isinstance(name, str):
                        member, count = name, len(node.args) - 2
            else:
                attribute = _member_of(node)
                if attribute and attribute in known:
                    member, count = attribute, len(node.args)

            if member is None or member not in known:
                continue
            found.append(
                CallSite(
                    member=member, argument_count=count, source=relative, line=node.lineno
                )
            )

    return sorted(found, key=lambda site: (site.source, site.line))


@dataclass(frozen=True)
class FamilyReport:
    """What one versioned family looks like on the installed release."""

    interface: str
    family: str
    used: str
    used_version: int
    available: tuple[str, ...]
    newest: str
    newest_version: int
    parameter_count: int
    is_newest: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "interface": self.interface,
            "family": self.family,
            "used": self.used,
            "available": list(self.available),
            "newest": self.newest,
            "is_newest": self.is_newest,
            "parameter_count": self.parameter_count,
        }


def family_report(interface: str, member: str) -> FamilyReport:
    """Where ``member`` sits among the versions this install actually offers."""
    table = members(interface)
    if member not in table:
        raise KeyError(f"{interface}.{member} is not on this release")

    family, version = split_version(member)
    siblings = {}
    for candidate in table:
        candidate_family, candidate_version = split_version(candidate)
        if candidate_family == family:
            siblings[candidate] = candidate_version

    newest = max(siblings, key=lambda name: siblings[name])
    return FamilyReport(
        interface=interface,
        family=family,
        used=member,
        used_version=version,
        available=tuple(sorted(siblings, key=lambda name: siblings[name])),
        newest=newest,
        newest_version=siblings[newest],
        parameter_count=len(table[member]["params"]),
        is_newest=member == newest,
    )


def build_usage() -> dict[str, Any]:
    """The canonical contents of ``generated/api_usage.json``.

    Deliberately free of line numbers: this file is committed, and a record that churns
    on every unrelated edit is one people stop reading.
    """
    grouped: dict[str, dict[str, set]] = {}
    for site in scan_source():
        entry = grouped.setdefault(site.member, {"counts": set(), "sources": set()})
        entry["counts"].add(site.argument_count)
        entry["sources"].add(site.source)

    calls = [
        {
            "member": member,
            "argument_counts": sorted(entry["counts"]),
            "sources": sorted(entry["sources"]),
        }
        for member, entry in sorted(grouped.items())
    ]
    return {
        "generated_from": "swmcp.com.apiver.scan_source",
        "note": (
            "Every SOLIDWORKS API member this package calls, found by walking its own "
            "source. Checked against the installed type library by tests/"
            "test_api_versions.py."
        ),
        "call_count": len(calls),
        "calls": calls,
    }


def usage_report() -> dict[str, Any]:
    """DISC-005 evidence: the versioned API members this server calls, and their status.

    The call list comes from ``generated/api_usage.json``, which is derived from the
    handlers themselves, so it cannot drift away from what the code does without the
    artifact check failing.
    """
    usage_path = _TABLE_PATH.parent / "api_usage.json"
    if not usage_path.is_file():
        return {
            "table": table_info(),
            "families": [],
            "warnings": [
                "api_usage.json is missing; run: uv run solidworks-mcp --write-artifacts"
            ],
        }

    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    families: list[dict[str, Any]] = []
    warnings: list[str] = []

    for entry in usage["calls"]:
        member = entry["member"]
        declaring = interfaces_declaring(member)
        if not declaring:
            warnings.append(
                f"{member} is called by {', '.join(entry['sources'])} but is not on this release."
            )
            continue
        report = family_report(declaring[0], member)
        if len(report.available) > 1:
            families.append({**report.as_dict(), "called_by": entry["sources"]})

    behind = [entry for entry in families if not entry["is_newest"]]
    return {
        "table": table_info(),
        "families": sorted(families, key=lambda entry: (entry["interface"], entry["family"])),
        "newer_available": sorted(f"{entry['used']} -> {entry['newest']}" for entry in behind),
        "warnings": warnings,
        "note": (
            "A newer member is reported, never selected: SOLIDWORKS versioned members "
            "take different argument lists, so moving to one is a code change with its "
            "own test, not something to decide at runtime."
        ),
    }
