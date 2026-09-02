"""Every feature op must report whether SOLIDWORKS flagged what it built (FEAT-019).

This is a structural test, read off the source, because the failure it guards against
is *silence*. The check was written out by hand at four call sites and simply absent at
the rest, so a sweep or a loft that SOLIDWORKS had marked in error returned all-green
while an extrude in the same document did not. Folding it into ``_geometry_checks``
fixed those — and, in the same edit, removed it from fillet, chamfer, pattern and hole,
which build their own check lists and so gained nothing from the fold. Nothing failed:
the ops kept working and kept reporting success, with one fewer piece of evidence
behind it.

A live test cannot catch that cheaply. It would have to *provoke* a feature that
rebuilds in error, per op, and then notice an absent check rather than a wrong one. The
source says it in milliseconds.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SOURCE = Path(__file__).resolve().parents[1] / "src" / "swmcp" / "handlers" / "feature.py"

#: Ops that inspect or remove features rather than creating one. They have no feature
#: to ask about, so requiring the check of them would be noise.
_NOT_FEATURE_BUILDERS = {
    "sw_feature_list",
    "sw_feature_edit",
    "sw_feature_delete",
}


def _op_name(node: ast.FunctionDef) -> str | None:
    """The ``name=`` given to an ``@op`` decorator, if this is one."""
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        target = decorator.func
        if getattr(target, "id", None) != "op" and getattr(target, "attr", None) != "op":
            continue
        for keyword in decorator.keywords:
            if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value)
    return None


def _feature_building_ops() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        name = _op_name(node)
        if name and name.startswith("sw_feature_") and name not in _NOT_FEATURE_BUILDERS:
            found[name] = node
    return found


def _module_functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def _called_names(node: ast.FunctionDef) -> set[str]:
    names = set()
    for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
        callee = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
        if callee:
            names.add(callee)
    return names


def _reports_the_error_check(node: ast.FunctionDef, functions: dict, depth: int = 3) -> bool:
    """Whether this op asks GetErrorCode2, directly or through what it delegates to.

    The delegation matters: both extrudes route their whole result through ``_extrude``,
    and fillet and chamfer share one builder, so looking only at the decorated function
    reports four false gaps on code that is entirely correct.
    """
    for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
        callee = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
        if callee == "feature_error_check":
            return True
        if callee == "_geometry_checks" and any(k.arg == "feature" for k in call.keywords):
            return True
    if depth <= 0:
        return False
    return any(
        _reports_the_error_check(functions[name], functions, depth - 1)
        for name in _called_names(node)
        if name in functions and name != node.name
    )


def test_the_ops_under_test_were_actually_found():
    """A source-reading test that finds nothing would pass for the wrong reason."""
    ops = _feature_building_ops()
    assert len(ops) >= 8, sorted(ops)
    for expected in ("sw_feature_sweep", "sw_feature_loft", "sw_feature_pattern"):
        assert expected in ops


@pytest.mark.parametrize("op_name", sorted(_feature_building_ops()))
def test_every_feature_op_reports_whether_the_feature_is_in_error(op_name):
    node = _feature_building_ops()[op_name]
    assert _reports_the_error_check(node, _module_functions()), (
        f"{op_name} builds a feature but never asks GetErrorCode2 about it. "
        f"Call feature_error_check(feature), or pass feature= to _geometry_checks."
    )


def test_the_check_has_exactly_one_definition():
    """The duplication is what let four sites drift from the rest."""
    source = _SOURCE.read_text(encoding="utf-8")
    assert source.count('name="feature_has_no_error"') == 1, (
        "feature_has_no_error is spelled out more than once; it belongs in "
        "feature_error_check alone."
    )
