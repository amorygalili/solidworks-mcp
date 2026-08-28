"""Equations, configurations, and custom properties.

The theme is naming. A part whose values can only be reached by clicking on geometry is
not parametric to an agent; one whose driving values have names it can list, read, and
set is. So every operation here addresses things by name, and reports the value both
before and after, because "I set Width to 120" is a claim that has to be checked.

Circular-reference detection (PAR-002) is textual: the equation strings are parsed for
the ``"name"`` tokens they read and the resulting graph is searched for cycles. That is
reported as what it is — SOLIDWORKS's own solver status is reported alongside it, never
replaced by it.

Two things about ``IEquationMgr`` on SOLIDWORKS 2026 SP3.0 are worth knowing before
changing anything here, both measured rather than assumed:

* **There is no setter for an equation added with ``Add2``.** ``Equation`` is
  read-only through late binding, ``SetEquation`` does not exist, and
  ``SetEquationAndConfigurationOption`` returns -1 for every argument shape tried.
  That last one is documented rather than broken: it "modifies only equations added
  using ``Add3``", and ``Add3`` in turn "only works for parts having multiple
  configurations", which is why it too returns -1 on the single-configuration parts
  the tests build. On such a part ``Add2`` is both the documented choice and the only
  one that works, so an update is a delete plus an ``Add2``. ``Add2`` then refuses
  while the list holds a reference to an undefined name, so deleting a variable that
  something reads leaves a hole that cannot be refilled — which is why replacing an
  equation with dependents rewrites the whole list in order.
* **An equation is text, and SOLIDWORKS evaluates text in document units.** Every
  other path in this server speaks metres to the API and is unit-safe; this one is
  not. The stock part template here is in inches, so ``"Width" = 120`` sets 120
  inches. The expression belongs to the caller and cannot be rewritten, so the
  document's unit is reported and unit-less numbers are warned about.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, NonModelSideEffect, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import get_com_member, normalize_sequence, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import ArtifactEvidence, Check, Verification
from swmcp.errors import SwMcpError, make_error, validation_error
from swmcp.modeling import configuration_names
from swmcp.safety.overwrite import resolve_output_path
from swmcp.safety.paths import assert_output_path
from swmcp.schemas.parameter import (
    ConfigActivateArgs,
    ConfigActivateResult,
    ConfigCreateArgs,
    ConfigCreateResult,
    ConfigDeleteArgs,
    ConfigDeleteResult,
    ConfigListArgs,
    ConfigListResult,
    EquationListArgs,
    EquationListResult,
    EquationSetArgs,
    EquationSetResult,
    ParameterTableExportArgs,
    ParameterTableExportResult,
    ParameterTableImportArgs,
    ParameterTableImportResult,
    PropertyListArgs,
    PropertyListResult,
    PropertySetArgs,
    PropertySetResult,
)
from swmcp.units import from_meters, to_meters

#: ``"Width"`` inside an equation is a reference to another named value.
_QUOTED = re.compile(r'"([^"]+)"')

#: ``"Width" = 120`` — the left-hand side names what the equation drives.
_ASSIGNMENT = re.compile(r'^\s*"?(?P<lhs>[^"=]+)"?\s*=\s*(?P<rhs>.*)$')

#: A nanometre. Far below any CAD tolerance, but above the float noise a round trip
#: through COM introduces, so "the dimension did not move" is a real answer.
_DIMENSION_EPSILON_M = 1e-9


def _same(left: float, right: float) -> bool:
    return abs(left - right) <= _DIMENSION_EPSILON_M


_PROPERTY_TYPES = {
    "text": "swCustomInfoText",
    "date": "swCustomInfoDate",
    "number": "swCustomInfoNumber",
    "double": "swCustomInfoDouble",
    "yes_no": "swCustomInfoYesOrNo",
}


# --- shared helpers -----------------------------------------------------------


def _equation_manager(doc: Any) -> Any:
    manager = try_com_member(doc, "GetEquationMgr", default=None)
    if manager is None:
        raise SwMcpError(
            make_error(
                "NO_EQUATION_MANAGER",
                "solidworks",
                "This document does not expose an equation manager.",
                remediation=["Equations are available on parts and assemblies."],
            )
        )
    return manager


def _split_equation(text: str) -> tuple[str | None, str | None]:
    """``'"Width" = 120'`` -> ``("Width", "120")``. Returns ``(None, None)`` if unparsable."""
    match = _ASSIGNMENT.match(text or "")
    if not match:
        return None, None
    return match.group("lhs").strip().strip('"'), match.group("rhs").strip()


def _read_equations(manager: Any) -> list[dict[str, Any]]:
    count = int(try_com_member(manager, "GetCount", default=0) or 0)
    equations = []
    for index in range(count):
        text = str(try_com_member(manager, "Equation", index, default="") or "")
        name, expression = _split_equation(text)
        equations.append(
            {
                "index": index,
                "text": text,
                "name": name,
                "expression": expression,
                "value": try_com_member(manager, "Value", index, default=None),
                "global_variable": bool(
                    try_com_member(manager, "GlobalVariable", index, default=False)
                ),
                "suppressed": bool(try_com_member(manager, "Suppression", index, default=False)),
                "reads": sorted(set(_QUOTED.findall(expression or ""))),
            }
        )
    return equations


def _find_cycles(equations: list[dict[str, Any]]) -> list[list[str]]:
    """Every cycle in the "reads" graph, each reported once as its chain of names."""
    edges: dict[str, list[str]] = {}
    for entry in equations:
        if entry["name"]:
            edges.setdefault(entry["name"], []).extend(entry["reads"])

    cycles: list[list[str]] = []
    # The same loop is found once from each of its members, so it is keyed by the set of
    # names in it — reporting A->B->A and B->A->B as two problems would be noise.
    seen_cycles: set[frozenset[str]] = set()

    def walk(node: str, path: list[str], visiting: set[str]) -> None:
        for target in edges.get(node, ()):
            if target in visiting:
                cycle = [*path[path.index(target) :], target]
                key = frozenset(cycle)
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    cycles.append(cycle)
                continue
            if target in edges:
                walk(target, [*path, target], visiting | {target})

    for name in edges:
        walk(name, [name], {name})
    return cycles


def _dimension_names(doc: Any) -> set[str]:
    """Every driving dimension's full name, for spotting references to nothing."""
    from swmcp.handlers.constraint import _iter_dimensions

    return {
        str(try_com_member(dimension, "FullName", default="") or "")
        for _owner, dimension in _iter_dimensions(doc, None)
    }


def _equation_status(manager: Any) -> dict[str, Any]:
    # The type library registers no enum for IEquationMgr::Status, so the raw code is
    # reported as a raw code rather than decoded against a name that might be invented.
    return {
        "code": try_com_member(manager, "Status", default=None),
        "code_note": "0 means the equations solved; the type library names no enum for this.",
        "disabled_count": try_com_member(manager, "GetDisabledEquationCount", default=None),
        "automatic_solve_order": try_com_member(manager, "AutomaticSolveOrder", default=None),
        "automatic_rebuild": try_com_member(manager, "AutomaticRebuild", default=None),
        "linked_file": try_com_member(manager, "FilePath", default=None) or None,
    }


def _rebuild_errors(ctx: OpContext, doc: Any, rebuild: bool) -> list[str]:
    if not rebuild:
        return []
    ok = get_com_member(doc, "EditRebuild3", default=None)
    if callable(ok):
        ok = ok()
    _ = ctx
    return [] if ok in (True, None) else ["The rebuild reported a failure."]


# --- equations ----------------------------------------------------------------


@op(
    name="sw_equation_list",
    tier="core",
    domains=("parameter",),
    tags=("equation", "global variable", "parametric", "dependency"),
    summary=(
        "List equations and global variables with their values, what each one reads, "
        "and any circular chain, so a parametric change can be planned before it is made."
    ),
    safety=ReadSafety(),
    satisfies=("PAR-002",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=120.0,
)
def equation_list(ctx: OpContext, args: EquationListArgs) -> EquationListResult:
    doc = ctx.require_doc()
    manager = _equation_manager(doc)
    equations = _read_equations(manager)

    cycles: list[list[str]] = []
    unresolved: list[dict[str, Any]] = []
    if args.include_dependencies:
        cycles = _find_cycles(equations)
        defined = {entry["name"] for entry in equations if entry["name"]} | _dimension_names(doc)
        for entry in equations:
            missing = [name for name in entry["reads"] if name not in defined]
            if missing:
                unresolved.append({"equation": entry["text"], "missing": missing})

    warnings = []
    if cycles:
        warnings.append(
            f"{len(cycles)} circular reference(s) found by reading the equation text; "
            "SOLIDWORKS's own status is reported separately."
        )

    return EquationListResult(
        document_length_unit=_document_length_unit(doc),
        count=len(equations),
        equations=[entry for entry in equations if not entry["global_variable"]],
        global_variables=[entry for entry in equations if entry["global_variable"]],
        status=_equation_status(manager),
        circular_references=cycles,
        unresolved_references=unresolved,
        warnings=warnings,
    )


#: A number in an equation that carries no unit of its own. SOLIDWORKS evaluates it in
#: the document's units, which on the stock part template here is inches — so
#: ``"Width" = 120`` sets 120 **inches** while every API path in this server speaks
#: metres. The suffix must have no space before it: ``120mm`` is accepted and ``120 mm``
#: is rejected outright by SOLIDWORKS.
_NUMBER = re.compile(r"(?<![\w.\"])(\d+(?:\.\d+)?)(?![\w.])")

#: Either side of these, a number is a dimensionless factor rather than a length:
#: ``"Thickness" * 1.5`` is a ratio and wants no unit at all.
_SCALING = frozenset("*/^")


def _document_length_unit(doc: Any) -> str:
    """The unit a unit-less number in an equation is measured in."""
    preference = swconst.value("swUserPreferenceIntegerValue_e", "swUnitsLinear")
    raw = try_com_member(doc, "GetUserPreferenceIntegerValue", preference, default=None)
    name = swconst.name_of("swLengthUnit_e", raw) if isinstance(raw, int) else None
    return (name or "unknown").replace("sw", "").lower()


def _has_unitless_quantity(expression: str) -> bool:
    """Is there a number here that stands for a length but does not say in what unit?"""
    for match in _NUMBER.finditer(expression or ""):
        before = expression[: match.start()].rstrip()
        after = expression[match.end() :].lstrip()
        if (before and before[-1] in _SCALING) or (after and after[0] in _SCALING):
            continue  # a factor, not a measurement
        return True
    return False


def _unit_warnings(expressions: list[str], unit: str) -> list[str]:
    """Name every expression whose bare number silently inherits the document unit."""
    bare = sorted({text for text in expressions if _has_unitless_quantity(text or "")})
    if not bare:
        return []
    return [
        f"{len(bare)} expression(s) contain a number with no unit, so SOLIDWORKS reads "
        f"them in this document's units ({unit}), not millimetres: "
        f"{', '.join(repr(text) for text in bare[:5])}. Write the unit into the "
        "expression itself (120mm, no space) to say what you mean."
    ]


@op(
    name="sw_equation_set",
    tier="core",
    domains=("parameter",),
    tags=("equation", "global variable", "parametric", "edit"),
    summary=(
        "Add, update, or delete equations and global variables as a batch, reporting "
        "each item's outcome and the solver status the change left behind."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("PAR-002",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def equation_set(ctx: OpContext, args: EquationSetArgs) -> EquationSetResult:
    doc = ctx.require_doc()
    manager = _equation_manager(doc)
    before = _read_equations(manager)

    applied = 0
    failed: list[dict[str, Any]] = []
    unit = _document_length_unit(doc)
    warnings: list[str] = _unit_warnings(
        [spec.expression or "" for spec in args.equations if spec.operation != "delete"], unit
    )

    for position, spec in enumerate(args.equations):
        try:
            # Re-read every time: a delete shifts every index after it, so a batch
            # working from one snapshot would edit the wrong equations from item two on.
            current = _read_equations(manager)
            _apply_equation(
                manager,
                doc,
                spec,
                position=position,
                equations=current,
                by_name={entry["name"]: entry for entry in current if entry["name"]},
                preflight=args.preflight,
            )
            applied += 1
        except SwMcpError as error:
            # The code and remediation travel with the item, not just the prose: a
            # batch failure is the one place a caller cannot read the top-level error,
            # so without these it has nothing to branch on but a message string.
            failed.append(
                {
                    "index": position,
                    "name": spec.name,
                    "code": error.envelope.code,
                    "reason": error.envelope.message,
                    "remediation": list(error.envelope.remediation or []),
                }
            )

    if args.preflight:
        warnings.append("Preflight only: no equations were changed.")
    else:
        try_com_member(manager, "EvaluateAll", default=None)

    after = _read_equations(manager)
    cycles = _find_cycles(after)
    if cycles:
        warnings.append(f"{len(cycles)} circular reference(s) remain after this change.")

    return EquationSetResult(
        document_length_unit=unit,
        applied=0 if args.preflight else applied,
        failed=failed,
        status=_equation_status(manager),
        circular_references=cycles,
        rebuild_errors=_rebuild_errors(ctx, doc, args.rebuild and not args.preflight),
        warnings=warnings,
        verification=Verification(
            read_back=True,
            before={"equation_count": len(before)},
            after={"equation_count": len(after)},
            checks=[
                Check(
                    name="every_item_applied",
                    passed=not failed,
                    detail=f"{len(failed)} of {len(args.equations)} item(s) failed"
                    if failed
                    else "all items applied",
                ),
                Check(
                    name="equation_list_changed",
                    passed=args.preflight or len(after) != len(before) or after != before,
                    detail=f"{len(before)} -> {len(after)} equations",
                ),
                Check(
                    name="no_circular_reference",
                    passed=not cycles,
                    detail=f"cycles: {cycles}" if cycles else "no cycle found in the text",
                ),
            ],
        ),
    )


def _apply_equation(
    manager: Any,
    doc: Any,
    spec: Any,
    *,
    position: int,
    equations: list[dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
    preflight: bool,
) -> None:
    """Validate one edit and, unless this is a preflight, make it."""
    _require_name(spec, position)

    if spec.operation == "delete":
        target = _existing(by_name, spec.name, "delete")
        if not preflight:
            try_com_member(manager, "Delete", target["index"], default=None)
        return

    if not spec.expression:
        raise SwMcpError(
            validation_error(
                "MISSING_ARGUMENT",
                f"equations[{position}] needs an expression to {spec.operation}.",
            )
        )

    text = _compose(spec)

    if spec.operation == "update":
        target = _existing(by_name, spec.name, "update")
        if not preflight:
            _update(manager, equations, int(target["index"]), text, spec)
        return

    if preflight:
        return

    # Add2 is the documented choice when configurations are not involved, and the
    # only one that works on a single-configuration part. Add3 is what scopes an
    # equation, and needs more than one configuration to exist.
    if spec.configuration_scope == "all":
        index = _add(manager, -1, text)
    else:
        index = _add_scoped(manager, doc, -1, text, spec)
    if index < 0:
        raise SwMcpError(
            make_error(
                "EQUATION_REJECTED",
                "solidworks",
                f"SOLIDWORKS rejected the equation {text!r}.",
                context={"returned": index},
                remediation=[
                    "Quote every name it reads, for example: \"Width\" * 2",
                    "A dimension equation's left side is a full dimension name "
                    "such as D1@Sketch1.",
                    "The name on the left must be a dimension that exists, or a new "
                    "global variable.",
                    "Some names are reserved: SOLIDWORKS refuses \"Thickness\" as a "
                    "global variable while accepting \"MyThickness\". If the name "
                    "looks like a SOLIDWORKS parameter, try a different one.",
                    "A global variable that already exists cannot be added twice; "
                    "update it instead.",
                ],
            )
        )


def _add(manager: Any, index: int, text: str) -> int:
    """``Add2``, returning the index it landed at or -1 if SOLIDWORKS refused it."""
    return _as_index(try_com_member(manager, "Add2", index, text, True, default=-1))


def _as_index(returned: Any) -> int:
    try:
        return int(returned)
    except (TypeError, ValueError):
        return -1


def _config_scope(scope: str, names: list[str]) -> tuple[int, Any]:
    """Translate the friendly scope onto ``swInConfigurationOpts_e`` plus its names."""
    if scope == "specify":
        return (
            swconst.value("swInConfigurationOpts_e", "swSpecifyConfiguration"),
            list(names),
        )
    member = "swThisConfiguration" if scope == "this" else "swAllConfiguration"
    return swconst.value("swInConfigurationOpts_e", member), None


def _empty_string_array() -> Any:
    """A zero-length BSTR array, which the API wants where no names apply."""
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [])


def _add_scoped(manager: Any, doc: Any, index: int, text: str, spec: Any) -> int:
    """``Add3``, the only call that scopes an equation to configurations.

    Documented to work "only for parts having multiple configurations", and
    measured returning -1 on a single-configuration part - so the precondition is
    checked and reported here rather than surfacing as a bare -1.
    """
    available = configuration_names(doc)
    if len(available) < 2:
        raise SwMcpError(
            validation_error(
                "ONE_CONFIGURATION_ONLY",
                "configuration_scope needs a part with more than one configuration.",
                context={"configurations": available},
                remediation=[
                    "Create a second configuration with sw_config_create first.",
                    "Leave configuration_scope at 'all' to apply it everywhere.",
                ],
            )
        )
    scope, names = _config_scope(spec.configuration_scope, spec.configurations)
    return _as_index(
        try_com_member(
            manager,
            "Add3",
            index,
            text,
            True,
            scope,
            names if names is not None else _empty_string_array(),
            default=-1,
        )
    )


def _update(
    manager: Any, equations: list[dict[str, Any]], index: int, text: str, spec: Any
) -> None:
    """Change one equation's text, in place where SOLIDWORKS allows it.

    ``SetEquationAndConfigurationOption`` "modifies only equations added using
    ``Add3``", so on a multi-configuration part it edits in place and disturbs
    nothing. It returns -1 for anything added with ``Add2`` - which is every
    equation on a single-configuration part - and that is when the replacement
    below is needed.
    """
    scope, names = _config_scope(spec.configuration_scope, spec.configurations)
    in_place = _as_index(
        try_com_member(
            manager,
            "SetEquationAndConfigurationOption",
            index,
            text,
            scope,
            names if names is not None else _empty_string_array(),
            default=-1,
        )
    )
    if in_place >= 0:
        return
    _replace(manager, equations, index, text)


def _replace(manager: Any, equations: list[dict[str, Any]], index: int, text: str) -> None:
    """Rewrite the equation at ``index``, keeping its position in the solve order.

    An equation added with ``Add2`` has no setter. ``IEquationMgr::Equation`` is
    read-only through late binding, ``SetEquation`` does not exist, and
    ``SetEquationAndConfigurationOption`` modifies only equations added with ``Add3``
    — measured returning -1 for every argument shape tried here, which matches its
    documentation rather than contradicting it. So a replacement is a delete followed
    by an ``Add2``.

    That is not enough on its own, because ``Add2`` refuses — returning -1 and adding
    nothing — while the list holds a reference to a name that is not defined. Deleting
    a global variable that another equation reads therefore leaves a hole that cannot
    be filled again: measured, the variable stays gone and its dependents dangle. When
    anything reads the equation being replaced, the whole list is rewritten instead, in
    its original order, which does work.
    """
    name = equations[index]["name"] if index < len(equations) else None
    read_by_others = [
        entry
        for entry in equations
        if entry["index"] != index and name and name in entry["reads"]
    ]

    if not read_by_others:
        try_com_member(manager, "Delete", index, default=None)
        if _add(manager, index, text) < 0:
            raise SwMcpError(_replace_rejected(text, equations, restored=False))
        return

    wanted = [entry["text"] for entry in equations]
    wanted[index] = text
    for position in range(len(wanted) - 1, -1, -1):
        try_com_member(manager, "Delete", position, default=None)

    # Re-added in the original order, so each definition is in place before whatever
    # reads it. An order that was already circular would not come back; that is what
    # the retry pass is for, and what the error below reports if it still will not.
    pending = list(wanted)
    while pending:
        stuck = []
        for item in pending:
            if _add(manager, -1, item) < 0:
                stuck.append(item)
        if len(stuck) == len(pending):
            raise SwMcpError(_replace_rejected(text, equations, restored=False, lost=stuck))
        pending = stuck


def _replace_rejected(
    text: str,
    equations: list[dict[str, Any]],
    *,
    restored: bool,
    lost: list[str] | None = None,
) -> Any:
    return make_error(
        "EQUATION_REJECTED",
        "solidworks",
        f"SOLIDWORKS refused the replacement equation {text!r}.",
        context={
            "restored": restored,
            "equations_before": [entry["text"] for entry in equations],
            "not_re_added": lost or [],
        },
        remediation=[
            "Check the expression: every name it reads must be quoted and defined.",
            "sw_checkpoint_restore returns the document to its state before this call.",
        ],
    )


def _existing(by_name: dict[str, dict[str, Any]], name: str, operation: str) -> dict[str, Any]:
    target = by_name.get(name)
    if target is None:
        raise SwMcpError(
            validation_error(
                "EQUATION_NOT_FOUND",
                f"No equation defines {name!r} to {operation}.",
                context={"known": sorted(by_name)[:20]},
                remediation=["List the equations to see the names that exist."],
            )
        )
    return target


def _require_name(spec: Any, position: int) -> None:
    if not spec.name:
        raise SwMcpError(
            validation_error(
                "MISSING_ARGUMENT",
                f"equations[{position}] needs a name for {spec.operation}.",
            )
        )


def _compose(spec: Any) -> str:
    """SOLIDWORKS wants the whole assignment as one quoted string."""
    return f'"{spec.name}" = {spec.expression}'


# --- configurations -----------------------------------------------------------





def _describe_config(doc: Any, name: str, *, include_properties: bool) -> dict[str, Any]:
    configuration = try_com_member(doc, "GetConfigurationByName", name, default=None)
    entry: dict[str, Any] = {"name": name}
    if configuration is None:
        entry["readable"] = False
        return entry

    parent = try_com_member(configuration, "GetParent", default=None)
    entry.update(
        {
            "readable": True,
            "comment": try_com_member(configuration, "Comment", default=None),
            "description": try_com_member(configuration, "Description", default=None),
            "alternate_name": try_com_member(configuration, "AlternateName", default=None),
            "derived": bool(try_com_member(configuration, "IsDerived", default=False)),
            "parent": try_com_member(parent, "Name", default=None) if parent else None,
            "needs_rebuild": bool(try_com_member(configuration, "NeedsRebuild", default=False)),
            "suppress_new_features": bool(
                try_com_member(configuration, "SuppressNewFeatures", default=False)
            ),
            "property_count": try_com_member(
                configuration, "GetCustomPropertiesCount", default=None
            ),
        }
    )
    if include_properties:
        entry["properties"] = _read_properties(doc, name)
    return entry


@op(
    name="sw_config_list",
    tier="core",
    domains=("parameter",),
    tags=("configuration", "variant", "family"),
    summary=(
        "List the document's configurations with their parent, derived state, rebuild "
        "state, and which one is active, so a variant can be addressed by name."
    ),
    safety=ReadSafety(),
    satisfies=("PAR-003",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=120.0,
)
def config_list(ctx: OpContext, args: ConfigListArgs) -> ConfigListResult:
    doc = ctx.require_doc()
    names = configuration_names(doc)
    active = try_com_member(doc, "GetActiveConfiguration", default=None)
    return ConfigListResult(
        count=len(names),
        active=str(try_com_member(active, "Name", default="") or "") or None if active else None,
        configurations=[
            _describe_config(doc, name, include_properties=args.include_properties)
            for name in names
        ],
    )


@op(
    name="sw_config_create",
    tier="core",
    domains=("parameter",),
    tags=("configuration", "variant", "derive"),
    summary=(
        "Create a configuration, optionally derived from an existing one, and read the "
        "configuration list back to confirm it exists."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("PAR-003",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def config_create(ctx: OpContext, args: ConfigCreateArgs) -> ConfigCreateResult:
    doc = ctx.require_doc()
    before = configuration_names(doc)
    if args.name in before:
        raise SwMcpError(
            validation_error(
                "CONFIGURATION_EXISTS",
                f"A configuration named {args.name!r} already exists.",
                context={"existing": before},
                remediation=["Pick a different name, or activate the existing one."],
            )
        )
    if args.parent and args.parent not in before:
        raise SwMcpError(
            validation_error(
                "CONFIGURATION_NOT_FOUND",
                f"No configuration named {args.parent!r} to derive from.",
                context={"existing": before},
            )
        )

    options = 0
    if args.suppress_new_features:
        options |= swconst.value("swConfigurationOptions2_e", "swConfigOption_SuppressByDefault")
    if args.alternate_name:
        options |= swconst.value("swConfigurationOptions2_e", "swConfigOption_UseAlternateName")
    if not args.activate:
        options |= swconst.value("swConfigurationOptions2_e", "swConfigOption_DontActivate")

    manager = doc.ConfigurationManager
    created = try_com_member(
        manager,
        "AddConfiguration2",
        args.name,
        args.comment,
        args.alternate_name,
        options,
        args.parent or "",
        args.description,
        True,
        default=None,
    )

    after = configuration_names(doc)
    if created is None and args.name not in after:
        raise SwMcpError(
            make_error(
                "CONFIGURATION_CREATE_FAILED",
                "solidworks",
                f"SOLIDWORKS did not create a configuration named {args.name!r}.",
                remediation=[
                    "A derived configuration needs an existing parent name.",
                    "Configuration names must be unique within the document.",
                ],
            )
        )

    active = try_com_member(doc, "GetActiveConfiguration", default=None)
    return ConfigCreateResult(
        name=args.name,
        parent=args.parent,
        derived=bool(args.parent),
        active=str(try_com_member(active, "Name", default="") or "") or None if active else None,
        count_before=len(before),
        count_after=len(after),
        verification=Verification(
            read_back=True,
            before={"configuration_count": len(before), "configurations": before},
            after={"configuration_count": len(after), "configurations": after},
            checks=[
                Check(
                    name="configuration_exists",
                    passed=args.name in after,
                    detail=f"{args.name} in {after}",
                ),
                Check(
                    name="configuration_count_grew",
                    passed=len(after) == len(before) + 1,
                    detail=f"{len(before)} -> {len(after)}",
                ),
            ],
        ),
    )


@op(
    name="sw_config_activate",
    tier="core",
    domains=("parameter",),
    tags=("configuration", "variant", "activate"),
    summary=(
        "Switch the active configuration and read back which one is active afterwards, "
        "since a mis-typed name leaves the previous configuration in place."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("PAR-003",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=180.0,
)
def config_activate(ctx: OpContext, args: ConfigActivateArgs) -> ConfigActivateResult:
    doc = ctx.require_doc()
    names = configuration_names(doc)
    if args.name not in names:
        raise SwMcpError(
            validation_error(
                "CONFIGURATION_NOT_FOUND",
                f"No configuration named {args.name!r}.",
                context={"existing": names},
                remediation=["List the document's configurations to see what exists."],
            )
        )

    previous_config = try_com_member(doc, "GetActiveConfiguration", default=None)
    previous = (
        str(try_com_member(previous_config, "Name", default="") or "") or None
        if previous_config
        else None
    )

    try_com_member(doc, "ShowConfiguration2", args.name, default=None)
    errors = _rebuild_errors(ctx, doc, args.rebuild)

    now_config = try_com_member(doc, "GetActiveConfiguration", default=None)
    now = (
        str(try_com_member(now_config, "Name", default="") or "") or None if now_config else None
    )

    return ConfigActivateResult(
        active=now,
        previous=previous,
        rebuild_errors=errors,
        verification=Verification(
            read_back=True,
            before={"active": previous},
            after={"active": now},
            checks=[
                Check(
                    name="requested_configuration_is_active",
                    passed=now == args.name,
                    detail=f"active is {now!r}, requested {args.name!r}",
                )
            ],
        ),
    )


@op(
    name="sw_config_delete",
    tier="extended",
    domains=("parameter",),
    tags=("configuration", "variant", "delete"),
    summary=(
        "Delete a configuration. Destructive: the configuration's own dimension values "
        "and property overrides go with it, so it requires confirmation."
    ),
    safety=ModelMutation(destructive=True),
    satisfies=("PAR-003",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def config_delete(ctx: OpContext, args: ConfigDeleteArgs) -> ConfigDeleteResult:
    doc = ctx.require_doc()
    before = configuration_names(doc)
    if args.name not in before:
        raise SwMcpError(
            validation_error(
                "CONFIGURATION_NOT_FOUND",
                f"No configuration named {args.name!r}.",
                context={"existing": before},
            )
        )
    if len(before) == 1:
        raise SwMcpError(
            validation_error(
                "LAST_CONFIGURATION",
                "A document must keep at least one configuration.",
                context={"existing": before},
            )
        )

    try_com_member(doc, "DeleteConfiguration2", args.name, default=None)
    after = configuration_names(doc)
    active = try_com_member(doc, "GetActiveConfiguration", default=None)

    return ConfigDeleteResult(
        deleted=args.name not in after,
        name=args.name,
        count_before=len(before),
        count_after=len(after),
        active=str(try_com_member(active, "Name", default="") or "") or None if active else None,
        verification=Verification(
            read_back=True,
            before={"configuration_count": len(before), "configurations": before},
            after={"configuration_count": len(after), "configurations": after},
            checks=[
                Check(
                    name="configuration_gone",
                    passed=args.name not in after,
                    detail=f"remaining: {after}",
                )
            ],
        ),
    )


# --- custom properties --------------------------------------------------------


def _property_manager(doc: Any, configuration: str | None) -> Any:
    return doc.Extension.CustomPropertyManager(configuration or "")


def _read_properties(doc: Any, configuration: str | None) -> list[dict[str, Any]]:
    """Raw and evaluated values for one property set.

    Both are reported because they answer different questions: the raw value says how
    the property is defined, and the evaluated one says what a drawing would print.
    """
    manager = _property_manager(doc, configuration)
    names = [str(name) for name in normalize_sequence(
        try_com_member(manager, "GetNames", default=None)
    )]

    found = []
    for name in names:
        raw = try_com_member(manager, "Get", name, default=None)
        entry: dict[str, Any] = {
            "name": name,
            "raw": raw if isinstance(raw, str) else None,
            "evaluated": None,
            "type_code": try_com_member(manager, "GetType2", name, default=None),
        }
        # Get5 returns the raw and resolved values through out-parameters; pywin32 hands
        # them back as a tuple, so the shape is checked rather than assumed.
        detail = try_com_member(manager, "Get5", name, False, default=None)
        if isinstance(detail, (tuple, list)) and len(detail) >= 3:
            entry["raw"] = detail[1] if isinstance(detail[1], str) else entry["raw"]
            entry["evaluated"] = detail[2] if isinstance(detail[2], str) else None
            entry["resolved"] = bool(detail[3]) if len(detail) > 3 else None
        if isinstance(entry["type_code"], int):
            entry["type"] = swconst.name_of("swCustomInfoType_e", entry["type_code"])
        found.append(entry)
    return found


@op(
    name="sw_property_list",
    tier="core",
    domains=("parameter",),
    tags=("custom property", "metadata", "bom"),
    summary=(
        "List custom properties at file level or per configuration, reporting both the "
        "raw definition and the evaluated value a drawing or BOM would print."
    ),
    safety=ReadSafety(),
    satisfies=("PAR-006",),
    precondition="any",
    idempotent=True,
    timeout_s=120.0,
)
def property_list(ctx: OpContext, args: PropertyListArgs) -> PropertyListResult:
    doc = ctx.require_doc()

    file_properties: list[dict[str, Any]] = []
    per_configuration: dict[str, list[dict[str, Any]]] = {}

    if args.configuration in (None, "*"):
        file_properties = _read_properties(doc, None)
    if args.configuration == "*":
        for name in configuration_names(doc):
            per_configuration[name] = _read_properties(doc, name)
    elif args.configuration:
        if args.configuration not in configuration_names(doc):
            raise SwMcpError(
                validation_error(
                    "CONFIGURATION_NOT_FOUND",
                    f"No configuration named {args.configuration!r}.",
                    context={"existing": configuration_names(doc)},
                )
            )
        per_configuration[args.configuration] = _read_properties(doc, args.configuration)

    total = len(file_properties) + sum(len(values) for values in per_configuration.values())
    return PropertyListResult(
        count=total,
        file_properties=file_properties,
        configuration_properties=per_configuration,
    )


@op(
    name="sw_property_set",
    tier="core",
    domains=("parameter",),
    tags=("custom property", "metadata", "bom", "write"),
    summary=(
        "Write or delete custom properties at file level or in one configuration, and "
        "read every one of them back to confirm the value that was actually stored."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("PAR-006",),
    precondition="any",
    idempotent=True,
    timeout_s=180.0,
)
def property_set(ctx: OpContext, args: PropertySetArgs) -> PropertySetResult:
    doc = ctx.require_doc()
    if args.configuration and args.configuration not in configuration_names(doc):
        raise SwMcpError(
            validation_error(
                "CONFIGURATION_NOT_FOUND",
                f"No configuration named {args.configuration!r}.",
                context={"existing": configuration_names(doc)},
            )
        )

    manager = _property_manager(doc, args.configuration)
    before = {entry["name"]: entry for entry in _read_properties(doc, args.configuration)}

    written: list[str] = []
    deleted: list[str] = []
    failed: list[dict[str, Any]] = []

    for position, spec in enumerate(args.properties):
        if spec.delete:
            if spec.name not in before:
                failed.append(
                    {"index": position, "name": spec.name, "reason": "no such property"}
                )
                continue
            try_com_member(manager, "Delete2", spec.name, default=None)
            deleted.append(spec.name)
            continue

        if spec.value is None:
            failed.append(
                {"index": position, "name": spec.name, "reason": "a value is required"}
            )
            continue

        type_code = swconst.value("swCustomInfoType_e", _PROPERTY_TYPES[spec.type])
        outcome = try_com_member(
            manager, "Add3", spec.name, type_code, spec.value, 1 if args.overwrite else 0,
            default=None,
        )
        if outcome is not None and int(outcome) < 0:
            failed.append(
                {"index": position, "name": spec.name, "reason": f"Add3 returned {outcome}"}
            )
            continue
        written.append(spec.name)

    after = {entry["name"]: entry for entry in _read_properties(doc, args.configuration)}
    mismatched = [
        name
        for name, spec in ((s.name, s) for s in args.properties if not s.delete and s.value)
        if name in after and after[name]["raw"] != spec.value
    ]

    return PropertySetResult(
        written=written,
        deleted=deleted,
        failed=failed,
        configuration=args.configuration,
        verification=Verification(
            read_back=True,
            before={"property_count": len(before), "names": sorted(before)},
            after={"property_count": len(after), "names": sorted(after)},
            checks=[
                Check(
                    name="every_item_applied",
                    passed=not failed,
                    detail=f"{len(failed)} item(s) failed" if failed else "all items applied",
                ),
                Check(
                    name="written_values_read_back",
                    passed=not mismatched,
                    detail=f"stored value differs for {mismatched}"
                    if mismatched
                    else f"{len(written)} value(s) match what was sent",
                ),
                Check(
                    name="deleted_properties_are_gone",
                    passed=all(name not in after for name in deleted),
                    detail=f"deleted: {deleted}",
                ),
            ],
        ),
    )


# --- parameter table ----------------------------------------------------------


_TABLE_COLUMNS = ("kind", "name", "value", "unit", "configuration", "note")


def _table_rows(ctx: OpContext, doc: Any, args: ParameterTableExportArgs) -> list[dict[str, str]]:
    from swmcp.handlers.constraint import _iter_dimensions

    rows: list[dict[str, str]] = []
    configuration = args.configuration or ""

    if "dimensions" in args.include:
        for owner, dimension in _iter_dimensions(doc, None):
            value_m = try_com_member(dimension, "SystemValue", default=None)
            if not isinstance(value_m, (int, float)):
                continue
            rows.append(
                {
                    "kind": "dimension",
                    "name": str(try_com_member(dimension, "FullName", default="") or ""),
                    "value": f"{from_meters(float(value_m), args.unit):.6f}",
                    "unit": args.unit,
                    "configuration": configuration,
                    "note": owner,
                }
            )

    if "equations" in args.include:
        for entry in _read_equations(_equation_manager(doc)):
            rows.append(
                {
                    "kind": "global_variable" if entry["global_variable"] else "equation",
                    "name": entry["name"] or "",
                    "value": str(entry["expression"] or ""),
                    "unit": "",
                    "configuration": configuration,
                    "note": entry["text"],
                }
            )

    if "properties" in args.include:
        for entry in _read_properties(doc, args.configuration):
            rows.append(
                {
                    "kind": "property",
                    "name": entry["name"],
                    "value": str(entry["raw"] or ""),
                    "unit": "",
                    "configuration": configuration,
                    "note": str(entry.get("evaluated") or ""),
                }
            )

    _ = ctx
    return rows


@op(
    name="sw_parameter_table_export",
    tier="extended",
    domains=("parameter",),
    tags=("table", "csv", "export", "parameters"),
    summary=(
        "Write every driving dimension, equation, and custom property to a CSV that "
        "the import tool reads back, so a design's parameters can be reviewed or "
        "edited outside SOLIDWORKS."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Writes a CSV file under an allowed output root. Nothing in the model "
            "changes, but a file leaves the process and is reported with its size, "
            "timestamp, and SHA-256."
        ),
    ),
    satisfies=("PAR-005",),
    precondition="part_or_assembly",
    idempotent=False,
    timeout_s=180.0,
)
def parameter_table_export(
    ctx: OpContext, args: ParameterTableExportArgs
) -> ParameterTableExportResult:
    doc = ctx.require_doc()
    rows = _table_rows(ctx, doc, args)

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_TABLE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    checked = assert_output_path(args.output_path, ctx.config.allowed_roots)
    resolved, action = resolve_output_path(checked, args.overwrite)
    target = Path(resolved)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(buffer.getvalue(), encoding="utf-8")

    kinds: dict[str, int] = {}
    for row in rows:
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1

    stat = target.stat()
    warnings = []
    if action == "versioned":
        warnings.append(
            f"Wrote {target.name} rather than the requested name, to avoid replacing an "
            "existing file. Pass overwrite='allow' with confirm to replace it."
        )

    return ParameterTableExportResult(
        row_count=len(rows),
        kinds=kinds,
        saved_path=str(target),
        overwrite_action=action,
        warnings=warnings,
        artifacts=[
            ArtifactEvidence(
                path=str(target),
                exists=True,
                size_bytes=stat.st_size,
                modified_utc=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            )
        ],
    )


@op(
    name="sw_parameter_table_import",
    tier="extended",
    domains=("parameter",),
    tags=("table", "csv", "import", "parameters"),
    summary=(
        "Apply dimension values from a CSV written by the export tool, reporting every "
        "row's before and after value and leaving unchanged rows alone."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("PAR-005",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=300.0,
)
def parameter_table_import(
    ctx: OpContext, args: ParameterTableImportArgs
) -> ParameterTableImportResult:
    from swmcp.handlers.constraint import _iter_dimensions

    doc = ctx.require_doc()
    source = Path(args.input_path)
    if not source.is_file():
        raise SwMcpError(
            validation_error(
                "INPUT_NOT_FOUND",
                f"No file at {str(source)!r}.",
                context={"field": "input_path", "path": str(source)},
                remediation=["Export a table first, or check the path."],
            )
        )

    rows = list(csv.DictReader(io.StringIO(source.read_text(encoding="utf-8"))))
    if not rows:
        raise SwMcpError(
            validation_error(
                "EMPTY_TABLE",
                f"{source.name} has no rows.",
                remediation=["The file needs the header written by sw_parameter_table_export."],
            )
        )

    dimensions = {
        str(try_com_member(dimension, "FullName", default="") or ""): dimension
        for _owner, dimension in _iter_dimensions(doc, None)
    }

    applied = 0
    unchanged = 0
    failed: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []

    for number, row in enumerate(rows, start=2):
        if (row.get("kind") or "").strip() != "dimension":
            continue
        name = (row.get("name") or "").strip()
        dimension = dimensions.get(name)
        if dimension is None:
            failed.append({"row": number, "name": name, "reason": "no such dimension"})
            continue
        try:
            wanted_m = to_meters(
                row.get("value"), default_unit=row.get("unit") or args.unit
            )
        except (SwMcpError, ValueError, TypeError) as error:
            failed.append({"row": number, "name": name, "reason": str(error)})
            continue

        current_m = try_com_member(dimension, "SystemValue", default=None)
        if isinstance(current_m, (int, float)) and _same(float(current_m), wanted_m):
            unchanged += 1
            continue

        if not args.preflight:
            dimension.SystemValue = wanted_m
        after_m = try_com_member(dimension, "SystemValue", default=None)
        # Comparison stays in metres, the API's own unit; the display values beside it
        # are for the reader, and are never what the check is made against.
        changes.append(
            {
                "row": number,
                "name": name,
                "before_m": current_m if isinstance(current_m, (int, float)) else None,
                "requested_m": wanted_m,
                "after_m": after_m if isinstance(after_m, (int, float)) else None,
                "before": from_meters(float(current_m), args.unit)
                if isinstance(current_m, (int, float))
                else None,
                "requested": from_meters(wanted_m, args.unit),
                "after": from_meters(float(after_m), args.unit)
                if isinstance(after_m, (int, float))
                else None,
                "unit": args.unit,
            }
        )
        applied += 1

    warnings = []
    if args.preflight:
        warnings.append("Preflight only: no dimension was changed.")

    errors = _rebuild_errors(ctx, doc, args.rebuild and not args.preflight and bool(applied))
    stuck = [
        change
        for change in changes
        if not args.preflight
        and change["after_m"] is not None
        and not _same(float(change["after_m"]), float(change["requested_m"]))
    ]

    return ParameterTableImportResult(
        applied=0 if args.preflight else applied,
        unchanged=unchanged,
        failed=failed,
        changes=changes,
        rebuild_errors=errors,
        warnings=warnings,
        verification=Verification(
            read_back=True,
            before={"rows_read": len(rows), "dimensions_in_model": len(dimensions)},
            after={"applied": 0 if args.preflight else applied, "unchanged": unchanged},
            checks=[
                Check(
                    name="every_row_resolved",
                    passed=not failed,
                    detail=f"{len(failed)} row(s) did not resolve"
                    if failed
                    else "every dimension row matched a dimension",
                ),
                Check(
                    name="values_took_effect",
                    passed=not stuck,
                    detail=f"{len(stuck)} dimension(s) did not move to the requested value"
                    if stuck
                    else f"{len(changes)} change(s) read back correctly",
                ),
            ],
        ),
    )
