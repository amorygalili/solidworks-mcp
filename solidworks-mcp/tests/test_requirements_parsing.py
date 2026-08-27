"""The backlog is parsed, so coverage claims are checked against a real document."""

from __future__ import annotations

from collections import Counter

from swmcp.catalog.requirements import find_requirements_doc, load_requirements, parse_requirements
from swmcp.catalog.scope import DECLARED_PARTIAL, IN_SCOPE_REQUIREMENTS, PLATFORM_REQUIREMENTS


def test_backlog_has_the_documented_shape():
    requirements = load_requirements()
    assert len(requirements) == 152
    counts = Counter(r.priority for r in requirements.values())
    # These totals are stated in the requirements document's own summary table.
    assert counts == {"P1": 57, "P2": 47, "P0": 29, "P3": 19}


def test_every_p0_requirement_is_in_scope():
    requirements = load_requirements()
    p0 = {rid for rid, r in requirements.items() if r.priority == "P0"}
    assert p0 <= IN_SCOPE_REQUIREMENTS, f"P0 requirements left out of scope: {sorted(p0 - IN_SCOPE_REQUIREMENTS)}"


def test_scope_sets_only_reference_real_requirements():
    known = set(load_requirements())
    for label, ids in (
        ("IN_SCOPE_REQUIREMENTS", IN_SCOPE_REQUIREMENTS),
        ("PLATFORM_REQUIREMENTS", set(PLATFORM_REQUIREMENTS)),
        ("DECLARED_PARTIAL", set(DECLARED_PARTIAL)),
    ):
        unknown = ids - known
        assert not unknown, f"{label} cites requirement ids absent from the doc: {sorted(unknown)}"


def test_continuation_lines_are_joined():
    doc = find_requirements_doc()
    assert doc is not None
    parsed = parse_requirements(doc.read_text(encoding="utf-8"))
    # SYS-001 wraps across two lines in the source document.
    assert parsed["SYS-001"].text.endswith("visible instance.")
    assert "\n" not in parsed["SYS-001"].text


def test_parser_ignores_crosswalk_table_references():
    """Table cells mention ids like `DOC-001`-`DOC-006`; only checklist lines count."""
    parsed = parse_requirements(
        "## P0 x\n"
        "- [ ] **SYS-001** Real requirement.\n"
        "\n"
        "| `list_documents` | `DOC-001`-`DOC-006`: lifecycle. |\n"
    )
    assert set(parsed) == {"SYS-001"}
