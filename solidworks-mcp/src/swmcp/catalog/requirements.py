"""Parse the requirement backlog so coverage claims are checked, not asserted.

``docs/solidworks-target-requirements.md`` owns the 152 stable requirement IDs. This
module parses them, and :mod:`swmcp.catalog.artifacts` snapshots the result into
``generated/requirements.json`` so an installed package works without the repo. A test
re-parses the live doc and fails on drift, so adding a requirement is never silent.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

REQ_LINE = re.compile(r"^- \[[ xX]\] \*\*(?P<id>[A-Z]+-\d{3})\*\* (?P<text>.*)$")
PRIORITY_HEADING = re.compile(r"^## (?P<priority>P[0-3]) ")
DOC_RELATIVE = Path("docs") / "solidworks-target-requirements.md"
SNAPSHOT = Path(__file__).resolve().parent.parent / "generated" / "requirements.json"


@dataclass(frozen=True, slots=True)
class Requirement:
    id: str
    priority: str
    text: str


def find_requirements_doc(start: Path | None = None) -> Path | None:
    """Locate the backlog: explicit env override, else walk up looking for ``docs/``."""
    override = os.environ.get("SWMCP_REQUIREMENTS_DOC")
    if override:
        candidate = Path(override)
        return candidate if candidate.is_file() else None

    here = (start or Path(__file__).resolve()).parent
    for directory in [here, *here.parents]:
        candidate = directory / DOC_RELATIVE
        if candidate.is_file():
            return candidate
    return None


def parse_requirements(markdown: str) -> dict[str, Requirement]:
    """Extract ``- [ ] **XXX-000** text`` entries, keeping continuation lines."""
    requirements: dict[str, Requirement] = {}
    priority = "P0"
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current, buffer
        if current is not None:
            requirements[current] = Requirement(
                id=current, priority=priority, text=" ".join(buffer).strip()
            )
        current, buffer = None, []

    for raw in markdown.splitlines():
        heading = PRIORITY_HEADING.match(raw)
        if heading:
            flush()
            priority = heading.group("priority")
            continue

        match = REQ_LINE.match(raw)
        if match:
            flush()
            current = match.group("id")
            buffer = [match.group("text").strip()]
            continue

        if current is not None:
            stripped = raw.strip()
            # A continuation line is indented and not the start of a new list item.
            if stripped and raw.startswith("  ") and not stripped.startswith("- "):
                buffer.append(stripped)
            else:
                flush()

    flush()
    return requirements


def load_requirements() -> dict[str, Requirement]:
    """Prefer the live doc; fall back to the committed snapshot."""
    doc = find_requirements_doc()
    if doc is not None:
        return parse_requirements(doc.read_text(encoding="utf-8"))
    if SNAPSHOT.is_file():
        payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        return {
            key: Requirement(id=key, priority=value["priority"], text=value["text"])
            for key, value in payload["requirements"].items()
        }
    return {}


def known_requirement_ids() -> frozenset[str]:
    return frozenset(load_requirements())
