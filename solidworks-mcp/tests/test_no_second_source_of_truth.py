"""Structurally prevent the facts that must live in one place from being forked.

This is the strongest idea in ``solidworks-mcp-jay/scripts/check-safety.mjs``, ported
and extended. A catalog stays honest only if a second copy of its metadata is a test
failure rather than a code review question.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "swmcp"


def _prose_lines(source: str) -> set[int]:
    """Line numbers occupied by docstrings and whole-line comments.

    Documentation that *describes* a banned pattern is not a second source of truth,
    and the alternative — weakening the patterns so prose slips past — would weaken
    the check against real code too.
    """
    skip: set[int] = set()
    for number, line in enumerate(source.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            skip.add(number)
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - a broken file fails elsewhere
        return skip
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        is_docstring = isinstance(first, ast.Expr) and isinstance(
            getattr(first, "value", None), ast.Constant
        )
        if is_docstring and isinstance(first.value.value, str):
            skip.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return skip


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    owner: str | None
    why: str


RULES = [
    Rule(
        name="safety booleans",
        pattern=re.compile(r"\b(read_only|confirm_required|auto_checkpoint)\s*[:=][^=]"),
        owner="catalog/projection.py",
        why=(
            "Safety booleans are a projection of the safety union. Defining or assigning "
            "them elsewhere lets a destructive op drift out of its confirmation gate."
        ),
    ),
    Rule(
        name="unit conversion",
        pattern=re.compile(
            r"(/\s*1000(\.0)?\b|\*\s*1000(\.0)?\b|\*\s*0\.001\b|\b1e6\b|\b1e-6\b"
            r"|\b0\.0254\b|\b0\.3048\b|math\.pi\s*/\s*180)"
        ),
        owner="units.py",
        why=(
            "SYS-006 requires one normalization boundary. Both directions count: a "
            "stray '* 1000.0' formatting metres as millimetres is the same leak as a "
            "stray '/ 1000.0' on the way in."
        ),
    ),
    Rule(
        name="hardcoded ProgID",
        pattern=re.compile(r'"SldWorks\.Application'),
        owner="com/progid.py",
        why="The ProgID is version-suffixed and must be derived, not spelled out per call site.",
    ),
    Rule(
        name="hardcoded install path",
        pattern=re.compile(r"SOLIDWORKS Corp"),
        owner=None,
        why=(
            "This machine installs to 'Dassault Systemes/SOLIDWORKS 3DEXPERIENCE R2026x'. "
            "Install discovery must come from the registry or GetExecutablePath."
        ),
    ),
    Rule(
        name="bare except",
        pattern=re.compile(r"^\s*except\s*:"),
        owner=None,
        why="A bare except swallows KeyboardInterrupt and hides COM failures.",
    ),
    Rule(
        name="localized error text matching",
        pattern=re.compile(r'"(Member not found|\u627e\u4e0d\u5230\u6210\u5458)"'),
        owner=None,
        why="Classify COM failures by HRESULT; message text is localized and unreliable.",
    ),
]

GENERATED = {"swconst.py"}


def _python_sources() -> list[Path]:
    return [p for p in SRC.rglob("*.py") if p.name not in GENERATED]


def test_src_tree_is_present():
    assert _python_sources(), "no sources found; the scan would vacuously pass"


def test_no_forbidden_duplication():
    violations: list[str] = []
    for path in _python_sources():
        relative = path.relative_to(SRC).as_posix()
        text = path.read_text(encoding="utf-8")
        prose = _prose_lines(text)
        for rule in RULES:
            if rule.owner is not None and relative == rule.owner:
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if number in prose:
                    continue
                if rule.pattern.search(line):
                    owner = f" (belongs in {rule.owner})" if rule.owner else ""
                    violations.append(
                        f"{relative}:{number}: {rule.name}{owner}\n"
                        f"    {line.strip()}\n"
                        f"    why: {rule.why}"
                    )
    assert not violations, "second source of truth detected:\n\n" + "\n\n".join(violations)


def test_rules_actually_match_something():
    """Guard against a rule that can never fire because its regex is wrong."""
    samples = {
        "safety booleans": "    read_only = True",
        "unit conversion": "    millimetres = value * 1000.0",
        "hardcoded ProgID": '    sw = Dispatch("SldWorks.Application")',
        "hardcoded install path": r"    root = 'C:/Program Files/SOLIDWORKS Corp'",
        "bare except": "    except:",
        "localized error text matching": '    if "Member not found" in str(exc):',
    }
    for rule in RULES:
        assert rule.pattern.search(samples[rule.name]), f"rule {rule.name!r} matches nothing"


def test_prose_is_skipped_but_code_is_not():
    """Docstrings that document a banned pattern must not trip the scan."""
    source = (
        '"""Module docstring mentioning read_only = True and / 1000.0."""\n'
        "# a comment mentioning SOLIDWORKS Corp\n"
        "def f():\n"
        '    """Docstring mentioning / 1000.0."""\n'
        "    return 1\n"
    )
    prose = _prose_lines(source)
    assert prose == {1, 2, 4}

    live = "x = 1\nread_only = True\n"
    assert _prose_lines(live) == set()


def test_the_readme_names_every_declared_limitation():
    """Prose may restate a fact; it may not quietly fall behind it.

    ``DECLARED_PARTIAL`` is the machine-readable record and drives the generated
    coverage file. The README's "Known limitations" section exists so a reader meets
    the same caveats without opening JSON, which is only useful while the two agree.
    """
    from swmcp.catalog.scope import DECLARED_PARTIAL

    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    limitations = readme.split("## Known limitations", 1)
    assert len(limitations) == 2, "the README has no Known limitations section"

    missing = [rid for rid in sorted(DECLARED_PARTIAL) if rid not in limitations[1]]
    assert not missing, (
        "these requirements are declared partial but the README does not mention them: "
        f"{missing}"
    )
