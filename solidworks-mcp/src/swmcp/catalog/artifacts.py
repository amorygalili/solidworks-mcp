"""Derive every published artifact from the catalog, and detect drift.

``build_artifacts`` is deterministic — the catalog and this package's own source in,
canonical bytes out — so the drift check is just a comparison. It runs inside
``pytest`` rather than only in a separate script, because a check you have to remember
to run is a check that rots.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, get_args

from swmcp.catalog.projection import project
from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.catalog.requirements import load_requirements
from swmcp.catalog.scope import DECLARED_PARTIAL, IN_SCOPE_REQUIREMENTS, PLATFORM_REQUIREMENTS
from swmcp.catalog.search import describe_tool, method_name
from swmcp.catalog.spec import Domain, OpSpec
from swmcp.com.apiver import build_usage

PACKAGE = Path(__file__).resolve().parent.parent
GENERATED = PACKAGE / "generated"
OPERATIONS_MODULE = PACKAGE / "operations.py"
SKILL_DIR = PACKAGE / "skill"
SKILL_TOOL_INDEX = SKILL_DIR / "reference" / "tools.md"

_DOC_WIDTH = 88


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_coverage() -> dict[str, Any]:
    """Requirement coverage, reported honestly rather than optimistically."""
    load_all_ops()
    requirements = load_requirements()
    full: dict[str, list[str]] = {}
    partial: dict[str, list[str]] = {}
    for spec in OPS.values():
        for rid in spec.satisfies:
            full.setdefault(rid, []).append(spec.name)
        for rid in spec.partially_satisfies:
            partial.setdefault(rid, []).append(spec.name)

    covered = set(full) | set(partial) | set(PLATFORM_REQUIREMENTS)
    uncovered = sorted(IN_SCOPE_REQUIREMENTS - covered)

    return {
        "totals": {
            "requirements_in_backlog": len(requirements),
            "in_scope": len(IN_SCOPE_REQUIREMENTS),
            "fully_covered_by_a_tool": len(set(full) & IN_SCOPE_REQUIREMENTS),
            "partially_covered": len(set(partial) & IN_SCOPE_REQUIREMENTS),
            "covered_by_platform": len(PLATFORM_REQUIREMENTS),
            "uncovered_in_scope": len(uncovered),
            "tools": len(OPS),
        },
        "fully_covered": {rid: sorted(names) for rid, names in sorted(full.items())},
        "partially_covered": {
            rid: {"tools": sorted(names), "limitation": DECLARED_PARTIAL.get(rid, "")}
            for rid, names in sorted(partial.items())
        },
        "covered_by_platform": dict(sorted(PLATFORM_REQUIREMENTS.items())),
        "uncovered_in_scope": uncovered,
        "note": (
            "A requirement listed under partially_covered is NOT done. The limitation "
            "field says what is missing."
        ),
    }


def _render_doc(spec: OpSpec) -> str:
    projection = project(spec.safety)
    lines = [
        f"# {spec.name}",
        "",
        spec.summary,
        "",
        "| | |",
        "|---|---|",
        f"| Tier | `{spec.tier}` |",
        f"| Domains | {', '.join(f'`{d}`' for d in spec.domains)} |",
        f"| Document precondition | `{spec.precondition}` |",
        f"| Safety | `{spec.safety.kind}` |",
        f"| Read-only | {projection.read_only} |",
        f"| Destructive | {projection.destructive} |",
        f"| Confirmation required | {projection.confirm_required} |",
        f"| Auto-checkpointed | {projection.auto_checkpoint} |",
        f"| Idempotent | {spec.idempotent} |",
        f"| Timeout | {spec.timeout_s:g}s |",
    ]
    if spec.fresh_checkpoint:
        lines.append(
            "| Checkpoint | Always fresh: the debounce is bypassed, because this "
            "operation restores its own snapshot. |"
        )
    if isinstance(spec.safety.model_dump().get("rationale"), str):
        lines.append(f"| Side-effect rationale | {spec.safety.model_dump()['rationale']} |")
    if spec.satisfies:
        lines.append(f"| Satisfies | {', '.join(f'`{r}`' for r in spec.satisfies)} |")
    if spec.partially_satisfies:
        lines.append(
            f"| Partially satisfies | {', '.join(f'`{r}`' for r in spec.partially_satisfies)} |"
        )

    lines += [
        "",
        "## Input schema",
        "",
        "```json",
        json.dumps(spec.args_model.model_json_schema(), indent=2, sort_keys=True),
        "```",
        "",
        "## Result schema",
        "",
        "```json",
        json.dumps(spec.result_model.model_json_schema(), indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def _safety_label(spec: OpSpec) -> str:
    """One short phrase for a reader choosing a tool, derived from the projection."""
    projection = project(spec.safety)
    if projection.read_only:
        return "read"
    kind = "mutation" if spec.safety.kind == "model_mutation" else "side effect"
    label = f"destructive {kind}" if projection.destructive else kind
    return f"{label}, confirm" if projection.confirm_required else label


def _first_sentence(text: str | None, limit: int = 220) -> str:
    collapsed = " ".join((text or "").split())
    end = collapsed.find(". ")
    sentence = collapsed if end < 0 else collapsed[: end + 1]
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "…"


def _docstring_safe(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')


def _wrap(text: str, indent: str) -> list[str]:
    return textwrap.wrap(
        text,
        width=_DOC_WIDTH,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [indent.rstrip()]


def _default_text(field: Any) -> str:
    if field.is_required():
        return "required"
    if field.default_factory is not None:
        return "optional"
    default = field.default
    if default is None or isinstance(default, (bool, int, float)):
        return f"default {default!r}"
    if isinstance(default, str) and len(default) <= 24:
        return f"default {default!r}"
    return "optional"


def _model_aliases(specs: list[OpSpec]) -> dict[type, str]:
    """The name each schema class is imported under in the generated module.

    Two schema modules may define a class of the same name; the later one is then
    imported under a module-qualified alias rather than shadowing the first.
    """
    taken: dict[str, type] = {}
    aliases: dict[type, str] = {}
    for spec in specs:
        for model in (spec.args_model, spec.result_model):
            if model in aliases:
                continue
            name = model.__name__
            if name in taken and taken[name] is not model:
                tail = model.__module__.rsplit(".", 1)[-1]
                name = f"{tail.title().replace('_', '')}{name}"
            taken[name] = model
            aliases[model] = name
    return aliases


def _render_operations(specs: list[OpSpec]) -> str:
    """The library's typed surface: one method per operation, nothing else.

    Arguments are not spelled out as typed parameters. The args model already is that
    signature, with validation attached, and restating its fields as annotations here
    would be a second copy free to disagree with it. A caller wanting static checking
    of arguments builds the args model; the return type is exact either way.
    """
    aliases = _model_aliases(specs)
    by_module: dict[str, list[str]] = {}
    for model, alias in aliases.items():
        entry = model.__name__ if alias == model.__name__ else f"{model.__name__} as {alias}"
        by_module.setdefault(model.__module__, []).append(entry)

    imports: list[str] = []
    for module in sorted(by_module):
        names = sorted(by_module[module], key=lambda entry: entry.split(" as ")[-1])
        single = f"    from {module} import {', '.join(names)}"
        if len(single) <= 100:
            imports.append(single)
        else:
            imports.append(f"    from {module} import (")
            imports.extend(f"        {name}," for name in names)
            imports.append("    )")

    lines = [
        '"""Every catalog operation as a typed method. GENERATED: do not edit by hand.',
        "",
        "Regenerate with ``uv run solidworks-mcp --write-artifacts``. ``pytest`` fails while",
        "this file is stale, so it cannot quietly fall behind the ``@op`` handlers it mirrors.",
        "",
        "Each method takes its arguments as keywords, as a dict, or as the operation's args",
        "model, and returns the operation's result model. All of them go through",
        ":meth:`swmcp.library.SolidWorks.call`, and from there through the same dispatch",
        "pipeline the MCP server uses.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import TYPE_CHECKING, Any",
        "",
        "if TYPE_CHECKING:",
        "    from pydantic import BaseModel",
        "",
        *imports,
        "",
        "",
        "class Operations:",
        f'    """Mixin: {len(specs)} operations, each a thin call into :meth:`call`."""',
        "",
        "    __slots__ = ()",
        "",
        "    def call(",
        "        self,",
        "        name: str,",
        "        args: BaseModel | dict[str, Any] | None = None,",
        "        /,",
        "        **kwargs: Any,",
        "    ) -> Any:",
        "        raise NotImplementedError",
    ]

    for spec in specs:
        args_alias = aliases[spec.args_model]
        result_alias = aliases[spec.result_model]
        body = "        "
        doc = [*_wrap(_docstring_safe(" ".join(spec.summary.split())), body)]
        doc[0] = body + '"""' + doc[0].strip()
        facts = (
            f"``{spec.name}``: tier {spec.tier}, {_safety_label(spec)}, "
            f"document {spec.precondition}."
        )
        doc += ["", *_wrap(facts, body)]
        fields = spec.args_model.model_fields
        if fields:
            doc += ["", f"{body}Arguments (keywords, a dict, or ``{args_alias}``):"]
            for field_name, field in fields.items():
                described = _first_sentence(field.description)
                entry = f"{field_name}: {_default_text(field)}."
                if described:
                    entry += f" {described}"
                wrapped = _wrap(_docstring_safe(entry), body + "    ")
                doc.append(wrapped[0])
                doc.extend("    " + line for line in wrapped[1:])
        doc.append(f'{body}"""')

        lines += [
            "",
            f"    def {method_name(spec.name)}(",
            "        self,",
            f"        args: {args_alias} | dict[str, Any] | None = None,",
            "        /,",
            "        **kwargs: Any,",
            f"    ) -> {result_alias}:",
            *doc,
            f'        return self.call("{spec.name}", args, **kwargs)',
        ]
    return "\n".join(lines) + "\n"


def _render_tool_index(specs: list[OpSpec]) -> str:
    """The skill's map of the catalog: every operation, grouped by what it acts on."""
    order = list(get_args(Domain))
    grouped: dict[str, list[OpSpec]] = {}
    for spec in specs:
        grouped.setdefault(spec.domains[0], []).append(spec)

    lines = [
        "# Tool index",
        "",
        "Generated from the catalog by `solidworks-mcp --write-artifacts`; do not edit.",
        "",
        f"{len(specs)} operations. Call one from the shell with "
        "`python -m swmcp call <operation> '<json>'`, or from Python as "
        "`sw.<method>(...)`. `python -m swmcp describe <operation>` prints its full "
        "input schema.",
        "",
        "Safety: **read** changes nothing. **mutation** changes the model and is "
        "checkpointed first. **side effect** writes a file, opens a document, or changes "
        "the UI. **confirm** means the call is refused unless it carries `confirm: true`.",
        "",
        "Tier only decides which operations an MCP client is shown. The library and the "
        "CLI can call every operation at every tier.",
    ]
    # Domain is a Literal, but nothing enforces it at registration, so a domain in use
    # may be missing from it. Those sort after the declared ones rather than failing.
    def rank(domain: str) -> tuple[bool, int, str]:
        declared = domain in order
        return (not declared, order.index(domain) if declared else 0, domain)

    for domain in sorted(grouped, key=rank):
        lines += [
            "",
            f"## {domain}",
            "",
            "| Operation | Method | Tier | Safety | What it does |",
            "|---|---|---|---|---|",
        ]
        for spec in grouped[domain]:
            summary = " ".join(spec.summary.split()).replace("|", "\\|")
            lines.append(
                f"| `{spec.name}` | `{method_name(spec.name)}` | {spec.tier} | "
                f"{_safety_label(spec)} | {summary} |"
            )
    return "\n".join(lines) + "\n"


def build_artifacts() -> dict[Path, str]:
    """Pure: the catalog in, the canonical file contents out."""
    load_all_ops()
    specs = sorted(OPS.values(), key=lambda s: s.name)

    artifacts: dict[Path, str] = {
        GENERATED
        / "tool_manifest.json": _json(
            {
                "version": 1,
                "generated_from": "swmcp.catalog.registry.OPS",
                "tool_count": len(specs),
                "tools": [describe_tool(spec) for spec in specs],
            }
        ),
        GENERATED
        / "command_safety_policy.json": _json(
            {
                "note": (
                    "Derived from the safety union by swmcp.catalog.projection.project. "
                    "Do not edit; edit the safety declaration on the handler instead."
                ),
                "policies": {
                    spec.name: {
                        "safety": spec.safety.model_dump(),
                        **project(spec.safety).model_dump(),
                    }
                    for spec in specs
                },
            }
        ),
        GENERATED / "requirements_coverage.json": _json(build_coverage()),
        GENERATED / "api_usage.json": _json(build_usage()),
        GENERATED
        / "requirements.json": _json(
            {
                "note": "Snapshot of the parsed backlog so an installed package is self-contained.",
                "requirements": {
                    rid: {"priority": r.priority, "text": r.text}
                    for rid, r in sorted(load_requirements().items())
                },
            }
        ),
    }

    for spec in specs:
        artifacts[GENERATED / "docs" / f"{spec.name}.md"] = _render_doc(spec)

    artifacts[OPERATIONS_MODULE] = _render_operations(specs)
    artifacts[SKILL_TOOL_INDEX] = _render_tool_index(specs)

    return artifacts


def stale_artifacts() -> list[str]:
    """Paths whose committed contents differ from what the catalog would produce."""
    stale = []
    for path, expected in build_artifacts().items():
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(str(path))
    return sorted(stale)


def write_artifacts() -> list[str]:
    written = []
    for path, contents in build_artifacts().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_text(encoding="utf-8") != contents:
            path.write_text(contents, encoding="utf-8")
            written.append(str(path))
    _prune_orphan_docs()
    return sorted(written)


def _prune_orphan_docs() -> None:
    """Remove docs for operations that no longer exist."""
    docs_dir = GENERATED / "docs"
    if not docs_dir.is_dir():
        return
    expected = {f"{name}.md" for name in OPS}
    for existing in docs_dir.glob("*.md"):
        if existing.name not in expected:
            existing.unlink()
