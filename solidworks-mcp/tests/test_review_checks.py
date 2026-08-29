"""Review logic that needs no SOLIDWORKS: outcome ranking, matching, and rendering."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from swmcp.handlers.review_checks import _markdown, _match_expectation, _worst
from swmcp.schemas.review_checks import (
    HoleExpectation,
    ReviewFinding,
    ReviewHolesArgs,
    ReviewInspectArgs,
    ReviewPolicy,
    ReviewValidateResult,
)


def _finding(name: str, outcome: str) -> ReviewFinding:
    return ReviewFinding(name=name, outcome=outcome, detail="d", source="s")


# --- outcome ranking ------------------------------------------------------------


def test_the_worst_outcome_wins():
    """A review is only as good as its worst finding; averaging would hide a blocker."""
    assert _worst([]) == "pass"
    assert _worst([_finding("a", "pass"), _finding("b", "pass")]) == "pass"
    assert _worst([_finding("a", "pass"), _finding("b", "warn")]) == "warn"
    assert _worst([_finding("a", "warn"), _finding("b", "block")]) == "block"
    assert _worst([_finding("a", "block"), _finding("b", "pass")]) == "block"


# --- hole matching ---------------------------------------------------------------


def _group(diameter: float, count: int) -> dict:
    return {"diameter_mm": diameter, "count": count, "faces": []}


def test_an_exact_hole_count_matches():
    result = _match_expectation(
        HoleExpectation(diameter_mm=8.0, count=4), [_group(8.0, 4), _group(20.0, 1)]
    )
    assert result["satisfied"] is True
    assert result["found_count"] == 4


def test_a_wrong_count_does_not_match():
    result = _match_expectation(HoleExpectation(diameter_mm=8.0, count=4), [_group(8.0, 3)])
    assert result["satisfied"] is False
    assert result["found_count"] == 3
    assert "expected 4" in result["detail"]


def test_a_diameter_inside_tolerance_still_matches():
    """A measured bore is never exactly nominal, so the tolerance has to do real work."""
    result = _match_expectation(
        HoleExpectation(diameter_mm=8.0, count=2, tolerance_mm=0.05), [_group(8.03, 2)]
    )
    assert result["satisfied"] is True


def test_a_diameter_outside_tolerance_does_not_match():
    result = _match_expectation(
        HoleExpectation(diameter_mm=8.0, count=2, tolerance_mm=0.01), [_group(8.5, 2)]
    )
    assert result["satisfied"] is False
    assert result["found_count"] == 0


def test_groups_inside_tolerance_are_summed():
    """Two near-identical diameters are one hole family, not two half-matches."""
    result = _match_expectation(
        HoleExpectation(diameter_mm=8.0, count=4, tolerance_mm=0.05),
        [_group(7.99, 2), _group(8.02, 2)],
    )
    assert result["found_count"] == 4
    assert result["satisfied"] is True


# --- report rendering -------------------------------------------------------------


def _result(findings: list[ReviewFinding]) -> ReviewValidateResult:
    counts = {"pass": 0, "warn": 0, "block": 0}
    for finding in findings:
        counts[finding.outcome] += 1
    return ReviewValidateResult(
        outcome=_worst(findings),
        findings=findings,
        blocked=counts["block"],
        warned=counts["warn"],
        passed=counts["pass"],
    )


def test_the_markdown_report_has_a_table_and_the_outcome():
    text = _markdown("Plate review", None, _result([_finding("non_zero_volume", "pass")]))

    assert text.startswith("# Plate review")
    assert "| Check | Outcome | Detail | Source |" in text
    assert "`non_zero_volume`" in text
    assert "**PASS**" in text


def test_a_pipe_in_a_detail_cannot_break_the_table():
    """An unescaped pipe would silently split a cell and misreport the finding."""
    finding = ReviewFinding(
        name="odd", outcome="warn", detail="a | b", source="x | y"
    )
    text = _markdown("T", None, _result([finding]))

    row = next(line for line in text.splitlines() if "`odd`" in line)
    # An escaped pipe still contains the character, so count only the delimiters —
    # pipes not preceded by a backslash.
    delimiters = len(re.findall(r"(?<!\\)\|", row))
    assert delimiters == 5, f"the row has extra unescaped pipes: {row}"
    assert r"a \| b" in row


def test_the_report_names_every_finding_it_lists():
    findings = [_finding("a", "pass"), _finding("b", "block")]
    text = _markdown("T", None, _result(findings))
    assert "`a`" in text and "`b`" in text
    assert "**BLOCK**" in text


# --- policy ------------------------------------------------------------------------


def test_the_default_policy_checks_something():
    """A default that checked nothing would make a bare review meaningless."""
    policy = ReviewPolicy()
    assert policy.require_no_feature_errors is True
    assert policy.forbid_zero_volume is True
    assert policy.require_bodies_min == 1
    assert policy.forbid_dangling_relations is True


def test_every_rule_can_be_switched_off():
    """REV-007: a check that cannot be disabled is a policy pretending to be a fact."""
    policy = ReviewPolicy(
        require_no_feature_errors=False,
        require_bodies_min=None,
        forbid_zero_volume=False,
        require_fully_defined_sketches=False,
        forbid_dangling_relations=False,
        forbid_suppressed_features=False,
        require_material=False,
    )
    assert policy.require_bodies_min is None
    assert policy.forbid_zero_volume is False


def test_severity_overrides_are_caller_supplied():
    policy = ReviewPolicy(severity={"volume_at_least": "warn"})
    assert policy.severity["volume_at_least"] == "warn"


def test_an_unknown_severity_level_is_rejected():
    with pytest.raises(ValidationError):
        ReviewPolicy(severity={"volume_at_least": "catastrophe"})


# --- schema guards -------------------------------------------------------------------


def test_a_hole_expectation_needs_a_positive_diameter_and_count():
    with pytest.raises(ValidationError):
        HoleExpectation(diameter_mm=0, count=1)
    with pytest.raises(ValidationError):
        HoleExpectation(diameter_mm=8, count=0)


def test_a_reversed_diameter_filter_is_refused():
    with pytest.raises(ValidationError, match="must not exceed"):
        ReviewHolesArgs(min_diameter_mm=20, max_diameter_mm=5)


def test_an_inspection_defaults_to_every_section():
    args = ReviewInspectArgs()
    assert args.sections == []
    assert args.max_items == 200


def test_the_inspection_cap_is_bounded():
    with pytest.raises(ValidationError):
        ReviewInspectArgs(max_items=0)
    with pytest.raises(ValidationError):
        ReviewInspectArgs(max_items=99_999)
