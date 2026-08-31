"""Bill of materials export (IO-007).

Five things a probe settled before any of this was written, none of which the type
library says:

* ``GetComponents(False)`` returns the whole tree **flat**, and each component's
  ``Name2`` already encodes its path — ``sub-1/widget-2``. ``GetParent`` returns the
  parent component for a nested one and ``None`` at the top, so the tree is
  reconstructable without recursing through ``GetChildren``.
* A component's **configuration-specific property set and its file-level set are
  different places, both routinely populated, and they disagree.** The same part
  reported ``Description = "FILE LEVEL"`` at file level and ``"CONFIG LEVEL"`` in its
  configuration. A BOM that reads one set is silently wrong; the first version of this
  read the configuration set alone and would have printed blanks for everything, because
  properties written without a configuration land at file level only.
* ``BOMPartNoSource`` works and decodes, ``ExcludeFromBOM`` is a real bool, and
  ``AlternateName`` is ``''`` when ``UseAlternateNameInBOM`` is False.
* ``ChildComponentDisplayInBOM`` returns **0 for a part**, which is not a member of
  ``swChildComponentInBOMOption_e`` (1, 2, 3). Decoding it blindly would invent a name.
* ``IConfiguration::Description`` defaults to the *configuration name*, not a part
  description. Using it as the BOM description column prints "Default" for every row;
  the description a person means is the custom property called Description.

What this is not is a SOLIDWORKS BOM. Every number here is computed from the component
tree, and the requirement is explicit that it stays labelled a precursor until somebody
has checked it against a native table. So ``precursor`` is hard-wired true and the
warning is unconditional.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import NonModelSideEffect
from swmcp.com import swconst
from swmcp.com.marshal import normalize_sequence, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import file_evidence
from swmcp.errors import SwMcpError, validation_error
from swmcp.modeling import configuration_names
from swmcp.safety.overwrite import resolve_output_path
from swmcp.safety.paths import assert_output_path
from swmcp.schemas.bom import (
    BOM_COLUMNS,
    MATRIX_COLUMNS,
    MAX_PROPERTY_COLUMNS,
    SOURCE_SUFFIX,
    BomExportArgs,
    BomExportResult,
    BomLine,
)

#: ``swBOMPartNumberSource_e``, which decides what a BOM prints in its part-number
#: column. Every configuration on this machine reported ``DocumentName``; the other
#: three are implemented from the enum and only that one is observed.
_PART_NUMBER_SOURCES = {
    swconst.value("swBOMPartNumberSource_e", "swBOMPartNumber_DocumentName"): "document_name",
    swconst.value(
        "swBOMPartNumberSource_e", "swBOMPartNumber_ConfigurationName"
    ): "configuration_name",
    swconst.value("swBOMPartNumberSource_e", "swBOMPartNumber_ParentName"): "parent_name",
    swconst.value("swBOMPartNumberSource_e", "swBOMPartNumber_UserSpecified"): "user_specified",
}

_DOC_TYPES = {
    swconst.value("swDocumentTypes_e", "swDocPART"): "part",
    swconst.value("swDocumentTypes_e", "swDocASSEMBLY"): "assembly",
    swconst.value("swDocumentTypes_e", "swDocDRAWING"): "drawing",
}

#: The warning the requirement asks to be retained, added unconditionally and not
#: clearable by any argument.
#:
#: It lives in the result rather than inside the CSV. A comment row would break every
#: plain ``csv`` reader that opens the file, and a bill of materials that cannot be
#: parsed is worse than one carrying its caveat next to it — so the files stay data, and
#: the caveat travels with the call that produced them.
PRECURSOR_WARNING = (
    "This is a precursor to a bill of materials, not a checked one. Every line is "
    "computed by walking the component tree, not read from a SOLIDWORKS BOM table, and "
    "the two can legitimately differ: child-component display rules, quantity "
    "properties, weldment cut lists, and derived-configuration part numbers are not "
    "implemented here. Reconcile it against a native BOM before anyone orders from it."
)


# --- one component instance ---------------------------------------------------


@dataclass(slots=True, eq=False)
class _Instance:
    """One component, as it appears in the tree.

    ``eq=False`` on purpose. The roll-up asks whether a particular instance is in a
    list, and two instances of the same part in the same configuration have identical
    fields — with generated equality, ``in`` would answer yes for the wrong one and the
    quantities would be wrong in a way no column would show.
    """

    name: str
    path: str
    depth: int
    parent: str | None
    document_type: str
    configuration: str
    suppression: str
    suppressed: bool
    excluded_from_bom: bool
    virtual: bool
    reference_ok: bool
    part_number: str
    part_number_source: str
    properties: dict[str, tuple[str, str]] = field(default_factory=dict)
    item_number: str = ""
    in_bom: bool = True
    excluded_reason: str = ""
    #: The referenced document, kept so the property pass does not walk the tree twice.
    model: Any = None


def _document_type(model: Any, component: Any) -> str:
    """'part' or 'assembly', from the referenced document rather than from the name."""
    code = try_com_member(model, "GetType", default=None) if model is not None else None
    if isinstance(code, int) and code in _DOC_TYPES:
        return _DOC_TYPES[code]
    # A suppressed or unloaded component has no model document to ask, so fall back to
    # the file it references. This is the only place the extension decides anything.
    suffix = Path(str(try_com_member(component, "GetPathName", default="") or "")).suffix.lower()
    if suffix == ".sldasm":
        return "assembly"
    if suffix == ".sldprt":
        return "part"
    return "unknown"


def _property_sets(model: Any, configuration: str) -> tuple[dict[str, str], dict[str, str]]:
    """The configuration-specific set and the file-level set, in that order.

    Both are read because they are different places that disagree. Reading only one is
    the mistake this function exists to make impossible.
    """

    def read(which: str) -> dict[str, str]:
        manager = try_com_member(
            getattr(model, "Extension", None), "CustomPropertyManager", which, default=None
        )
        if manager is None:
            return {}
        names = [
            str(name)
            for name in normalize_sequence(try_com_member(manager, "GetNames", default=None))
        ]
        found: dict[str, str] = {}
        for name in names:
            # Get5 resolves an expression such as "$PRP:Description"; Get returns it raw.
            # A BOM prints the resolved value, so that is what is preferred here.
            detail = try_com_member(manager, "Get5", name, False, default=None)
            resolved = detail[2] if isinstance(detail, (tuple, list)) and len(detail) >= 3 else None
            if isinstance(resolved, str):
                found[name] = resolved
                continue
            raw = try_com_member(manager, "Get", name, default=None)
            found[name] = raw if isinstance(raw, str) else ""
        return found

    if model is None:
        return {}, {}
    return read(configuration or ""), read("")


def _merge_properties(
    configuration_set: dict[str, str], file_set: dict[str, str], wanted: list[str]
) -> dict[str, tuple[str, str]]:
    """Resolve each wanted column to (value, where it came from).

    Configuration first, file second — the order a SOLIDWORKS BOM resolves in. A column
    nobody has is reported as absent rather than as an empty value, because "blank" and
    "not defined here" are different answers and only one of them is a data problem.
    """
    merged: dict[str, tuple[str, str]] = {}
    by_folded_config = {name.casefold(): name for name in configuration_set}
    by_folded_file = {name.casefold(): name for name in file_set}
    for column in wanted:
        key = column.casefold()
        if key in by_folded_config:
            merged[column] = (configuration_set[by_folded_config[key]], "configuration")
        elif key in by_folded_file:
            merged[column] = (file_set[by_folded_file[key]], "file")
        else:
            merged[column] = ("", "absent")
    return merged


def _part_number_rule(config: Any) -> str:
    """Which ``swBOMPartNumberSource_e`` rule this configuration uses.

    Read rather than assumed. Every configuration on this machine reported
    ``document_name``; the others are implemented from the enum, and a row says which
    rule produced its number so a wrong one is visible in the CSV instead of silent.
    """
    raw = try_com_member(config, "BOMPartNoSource", default=None)
    if not isinstance(raw, int):
        return "document_name"
    return _PART_NUMBER_SOURCES.get(raw, "document_name")


def _apply_rule(rule: str, *, stem: str, configuration: str, alternate: str) -> tuple[str, str]:
    """The part number that rule produces, and the rule actually applied."""
    if rule == "configuration_name":
        return (configuration or stem), rule
    if rule == "user_specified":
        # The source says user-specified but UseAlternateNameInBOM left nothing to
        # print. Falling back is right; hiding that it fell back is not.
        return (alternate or stem), ("user_specified" if alternate else "document_name")
    if rule == "parent_name":
        # A derived configuration inherits its parent's number. No such configuration
        # was available to measure against, so the fallback is named, not guessed.
        return stem, "parent_name_unresolved"
    return stem, "document_name"


def _part_number(component: Any, model: Any, configuration: str, path: str) -> tuple[str, str]:
    """What a BOM would print in the part-number column, and which rule produced it."""
    stem = Path(path).stem if path else str(try_com_member(component, "Name2", default="") or "")
    config = (
        try_com_member(model, "GetConfigurationByName", configuration or "", default=None)
        if model is not None
        else None
    )
    if config is None:
        return stem, "document_name"

    alternate = str(try_com_member(config, "AlternateName", default="") or "")
    if bool(try_com_member(config, "UseAlternateNameInBOM", default=False)) and alternate:
        return alternate, "user_specified"

    return _apply_rule(
        _part_number_rule(config),
        stem=stem,
        configuration=configuration,
        alternate=alternate,
    )


def _instance_depth(component: Any, limit: int) -> tuple[int, str | None]:
    """Depth and immediate parent, walked through ``GetParent``.

    The parent chain is used rather than counting the slashes in ``Name2``, even though
    the name does encode the path: a component can be renamed, and a name is not a
    structure.
    """
    depth = 0
    parent = try_com_member(component, "GetParent", default=None)
    first = parent
    while parent is not None and depth < limit:
        depth += 1
        parent = try_com_member(parent, "GetParent", default=None)
    parent_name = (
        str(try_com_member(first, "Name2", default="") or "") if first is not None else None
    )
    return depth, parent_name


def _collect(doc: Any, args: BomExportArgs) -> list[_Instance]:
    """Every component in the tree, described but not yet rolled up."""
    components = [
        component
        for component in normalize_sequence(
            try_com_member(doc, "GetComponents", False, default=None)
        )
        if component is not None
    ]

    instances: list[_Instance] = []
    for component in components:
        depth, parent = _instance_depth(component, args.max_depth)
        if depth >= args.max_depth:
            continue
        path = str(try_com_member(component, "GetPathName", default="") or "")
        model = try_com_member(component, "GetModelDoc2", default=None)
        configuration = str(
            try_com_member(component, "ReferencedConfiguration", default="") or ""
        )
        virtual = bool(try_com_member(component, "IsVirtual", default=False))
        number, rule = _part_number(component, model, configuration, path)
        instances.append(
            _Instance(
                name=str(try_com_member(component, "Name2", default="") or ""),
                path=path,
                depth=depth,
                parent=parent,
                document_type=_document_type(model, component),
                configuration=configuration,
                suppression="suppressed"
                if try_com_member(component, "IsSuppressed", default=False)
                else "resolved",
                suppressed=bool(try_com_member(component, "IsSuppressed", default=False)),
                excluded_from_bom=bool(try_com_member(component, "ExcludeFromBOM", default=False)),
                virtual=virtual,
                reference_ok=bool(virtual or (path and Path(path).exists())),
                part_number=number,
                part_number_source=rule,
                model=model,
            )
        )
    return instances


def _resolve_properties(
    instances: list[_Instance], requested: list[str] | None
) -> tuple[list[str], dict[str, int]]:
    """Decide the property columns and fill every instance's values.

    Discovery is the union of both property sets across every component, which is the
    only way a caller who does not already know the schema gets a useful file.
    """
    sets = [_property_sets(instance.model, instance.configuration) for instance in instances]

    if requested is not None:
        columns = list(requested)
    else:
        discovered: dict[str, None] = {}
        for configuration_set, file_set in sets:
            for name in list(configuration_set) + list(file_set):
                discovered.setdefault(name, None)
        columns = sorted(discovered, key=str.casefold)[:MAX_PROPERTY_COLUMNS]

    tally = {"configuration": 0, "file": 0, "absent": 0}
    for instance, (configuration_set, file_set) in zip(instances, sets, strict=True):
        instance.properties = _merge_properties(configuration_set, file_set, columns)
        for _value, source in instance.properties.values():
            tally[source] += 1
    return columns, tally


# --- roll-up ------------------------------------------------------------------


def _countable(instance: _Instance, args: BomExportArgs) -> bool:
    """Whether this instance contributes to a quantity, recording why if it does not."""
    if instance.suppressed and not args.include_suppressed:
        instance.excluded_reason = "suppressed"
        return False
    if instance.excluded_from_bom and not args.include_excluded:
        instance.excluded_reason = "excluded_from_bom"
        return False
    return True


def _eligible(instances: list[_Instance], shape: str) -> list[_Instance]:
    """The instances this shape considers, before exclusions."""
    if shape == "top_level_only":
        return [i for i in instances if i.depth == 0]
    if shape == "parts_only":
        return [i for i in instances if i.document_type != "assembly"]
    return list(instances)


def _grouped(instances: list[_Instance]) -> list[tuple[tuple[str, str], list[_Instance]]]:
    """Group by part number and configuration, in a deterministic order.

    Sorted rather than left in ``GetComponents`` order, because that order is not the
    feature tree's and is not stable: two assemblies built by the same sequence of
    inserts returned their top-level components in different orders, which made the
    item numbers depend on something no caller can see. A bill of materials whose item
    numbers shuffle between runs cannot be diffed against the last one, which is most
    of what a delivered BOM is for.
    """
    groups: dict[tuple[str, str], list[_Instance]] = {}
    for instance in instances:
        groups.setdefault((instance.part_number, instance.configuration), []).append(instance)
    for members in groups.values():
        members.sort(key=lambda i: i.name)
    return sorted(groups.items(), key=lambda pair: (pair[0][0].casefold(), pair[0][1].casefold()))


def _roll_up(
    instances: list[_Instance], args: BomExportArgs, columns: list[str]
) -> list[BomLine]:
    """Group the eligible instances into lines and number them.

    ``indented`` numbers by position — 1, 1.1, 1.2, 2 — so a line's number says where in
    the tree it sits. The other two shapes number sequentially, because a flat list has
    no position to describe.
    """
    considered = _eligible(instances, args.shape)
    eligible = {id(instance) for instance in considered}
    for instance in instances:
        if id(instance) not in eligible:
            instance.in_bom = False
            instance.excluded_reason = f"not part of a {args.shape} bill"
            continue
        instance.in_bom = _countable(instance, args)

    counted = [i for i in considered if i.in_bom]
    if args.shape == "indented":
        return _roll_up_indented(counted, columns)

    lines: list[BomLine] = []
    for position, (_key, members) in enumerate(_grouped(counted), start=1):
        item = str(position)
        for member in members:
            member.item_number = item
        lines.append(_line(item, members, columns))
    return lines


def _roll_up_indented(counted: list[_Instance], columns: list[str]) -> list[BomLine]:
    """Number by position in the tree, grouping identical siblings under one parent."""
    by_parent: dict[str | None, list[_Instance]] = {}
    for instance in counted:
        by_parent.setdefault(instance.parent, []).append(instance)

    lines: list[BomLine] = []

    def walk(parent: str | None, prefix: str) -> None:
        for position, (_key, members) in enumerate(_grouped(by_parent.get(parent, [])), start=1):
            item = f"{prefix}{position}" if not prefix else f"{prefix}.{position}"
            for member in members:
                member.item_number = item
            lines.append(_line(item, members, columns))
            for member in members:
                walk(member.name, item)

    walk(None, "")
    return lines


def _line(item: str, members: list[_Instance], columns: list[str]) -> BomLine:
    first = members[0]
    return BomLine(
        item_number=item,
        part_number=first.part_number,
        part_number_source=first.part_number_source,
        configuration=first.configuration,
        quantity=len(members),
        document_type=first.document_type,
        file_name=Path(first.path).name if first.path else "",
        path=first.path,
        properties={column: first.properties.get(column, ("", "absent"))[0] for column in columns},
    )


# --- the two files ------------------------------------------------------------


def _bom_csv(lines: list[BomLine], columns: list[str]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=[*BOM_COLUMNS, *columns], lineterminator="\n", extrasaction="ignore"
    )
    writer.writeheader()
    for line in lines:
        row = line.model_dump(exclude={"properties"})
        row.update({column: line.properties.get(column, "") for column in columns})
        writer.writerow(row)
    return buffer.getvalue()


def _matrix_csv(instances: list[_Instance], columns: list[str]) -> str:
    headings = [
        *MATRIX_COLUMNS,
        *[f"{column}{SOURCE_SUFFIX}" for column in columns],
        *columns,
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headings, lineterminator="\n")
    writer.writeheader()
    for instance in sorted(instances, key=lambda i: (i.depth, i.name)):
        row: dict[str, Any] = {
            "item_number": instance.item_number,
            "part_number": instance.part_number,
            "instance_name": instance.name,
            "parent_instance": instance.parent or "",
            "depth": instance.depth,
            "document_type": instance.document_type,
            "configuration": instance.configuration,
            "path": instance.path,
            "suppression": instance.suppression,
            "excluded_from_bom": instance.excluded_from_bom,
            "virtual": instance.virtual,
            "reference_ok": instance.reference_ok,
            "in_bom": instance.in_bom,
            "excluded_reason": instance.excluded_reason,
        }
        for column in columns:
            value, source = instance.properties.get(column, ("", "absent"))
            row[column] = value
            row[f"{column}{SOURCE_SUFFIX}"] = source
        writer.writerow(row)
    return buffer.getvalue()


def _default_matrix_path(bom_path: Path) -> Path:
    return bom_path.with_name(f"{bom_path.stem}_traceability{bom_path.suffix}")


def _write(path: Path, text: str, policy: str) -> tuple[Path, str]:
    resolved, action = resolve_output_path(path, policy)  # type: ignore[arg-type]
    target = Path(resolved)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target, action


def _activate(doc: Any, name: str) -> str | None:
    known = configuration_names(doc)
    if name not in known:
        raise SwMcpError(
            validation_error(
                "CONFIGURATION_NOT_FOUND",
                f"No configuration named {name!r}.",
                context={"existing": known},
                remediation=["Use sw_config_list to see this assembly's configurations."],
            )
        )
    active = try_com_member(doc, "GetActiveConfiguration", default=None)
    previous = str(try_com_member(active, "Name", default="") or "") or None if active else None
    try_com_member(doc, "ShowConfiguration2", name, default=None)
    return previous


# --- the operation ------------------------------------------------------------


@op(
    name="sw_bom_export",
    tier="core",
    domains=("exchange", "assembly"),
    tags=("bom", "csv", "traceability", "components", "properties", "delivery"),
    summary=(
        "Write a component and property bill of materials to CSV, with a traceability "
        "matrix naming every instance behind each quantity and whether each property "
        "value came from the configuration or the file. Labelled a precursor, always."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Writes one or two CSV files under an allowed output root, each reported "
            "with its size, timestamp, and SHA-256. If a configuration is named it is "
            "activated to read quantities from and the previous one is restored. No "
            "model is modified."
        ),
    ),
    partially_satisfies=("IO-007",),
    precondition="assembly",
    idempotent=False,
    timeout_s=600.0,
)
def bom_export(ctx: OpContext, args: BomExportArgs) -> BomExportResult:
    """IO-007.

    The quantities come from walking the component tree, so this is a precursor to a
    bill of materials rather than one. ``precursor`` is true and the warning is
    unconditional — the requirement asks for exactly that, and it is the honest position:
    a native BOM applies rules this does not implement.
    """
    doc = ctx.require_doc()

    bom_target = Path(assert_output_path(args.output_path, ctx.config.allowed_roots))
    matrix_target = None
    if args.matrix:
        matrix_target = Path(
            assert_output_path(
                args.matrix_path or str(_default_matrix_path(bom_target)),
                ctx.config.allowed_roots,
                field="matrix_path",
            )
        )

    previous = _activate(doc, args.configuration) if args.configuration else None
    try:
        instances = _collect(doc, args)
        columns, tally = _resolve_properties(instances, args.properties)
        lines = _roll_up(instances, args, columns)
    finally:
        if previous and previous != args.configuration:
            try_com_member(doc, "ShowConfiguration2", previous, default=None)

    bom_written, action = _write(bom_target, _bom_csv(lines, columns), args.overwrite)
    artifacts = [file_evidence(bom_written)]
    matrix_written = None
    if matrix_target is not None:
        matrix_written, _ = _write(
            matrix_target, _matrix_csv(instances, columns), args.overwrite
        )
        artifacts.append(file_evidence(matrix_written))

    counted = sum(1 for instance in instances if instance.in_bom)
    warnings = [PRECURSOR_WARNING]
    if not lines:
        warnings.append(
            "No line qualified for this bill. Every component was suppressed, excluded, "
            f"or not part of a {args.shape} bill; the matrix says which for each."
        )
    if action == "versioned":
        warnings.append(
            f"Wrote {bom_written.name} rather than the requested name, to avoid "
            "replacing an existing file."
        )
    if not args.matrix:
        warnings.append(
            "No traceability matrix was written, so the quantities in this file cannot "
            "be attributed to the instances behind them."
        )
    if any(line.part_number_source.endswith("unresolved") for line in lines):
        warnings.append(
            "Some part numbers come from a configuration whose number is inherited from "
            "its parent, which this release does not resolve; those rows fall back to "
            "the document name and say so in part_number_source."
        )

    return BomExportResult(
        saved_path=str(bom_written),
        matrix_path=str(matrix_written) if matrix_written else None,
        overwrite_action=action,
        shape=args.shape,
        line_count=len(lines),
        instance_count=len(instances),
        counted_instances=counted,
        excluded_instances=len(instances) - counted,
        property_columns=columns,
        lines=lines,
        configuration=args.configuration,
        property_sources=tally,
        warnings=warnings,
        artifacts=artifacts,
    )
