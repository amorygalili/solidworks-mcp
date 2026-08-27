"""Invariants every operation must satisfy, enforced for the whole catalog at once.

These are the checks that make the "definition of done" in the requirements document
mechanical instead of aspirational.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from swmcp.catalog.projection import project
from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.catalog.requirements import known_requirement_ids
from swmcp.catalog.scope import DECLARED_PARTIAL, IN_SCOPE_REQUIREMENTS, PLATFORM_REQUIREMENTS
from swmcp.catalog.spec import TIER_ORDER
from swmcp.envelope import MutationResult, ReadResult, SideEffectResult


@pytest.fixture(scope="module")
def specs():
    load_all_ops()
    assert OPS, "no operations registered; the integrity checks would pass vacuously"
    return list(OPS.values())


def test_names_are_prefixed_and_unique(specs):
    names = [spec.name for spec in specs]
    assert len(names) == len(set(names))
    for name in names:
        assert name.startswith("sw_"), f"{name} does not use the sw_ prefix"
        assert name.islower()


def test_every_args_model_is_strict(specs):
    """SAFE-001: an unknown key is a typo, and must be an error rather than ignored."""
    for spec in specs:
        assert spec.args_model.model_config.get("extra") == "forbid", (
            f"{spec.name} would silently ignore unknown arguments"
        )


def test_mutations_return_verification(specs):
    """SAFE-010: success is not claimed until the change is read back from the model."""
    for spec in specs:
        if spec.safety.kind == "model_mutation":
            assert issubclass(spec.result_model, MutationResult), (
                f"{spec.name} mutates the model but its result carries no verification"
            )


def test_side_effects_return_artifact_evidence(specs):
    for spec in specs:
        if spec.safety.kind == "non_model_side_effect":
            assert issubclass(spec.result_model, SideEffectResult), (
                f"{spec.name} has an effect outside the model but returns no evidence"
            )


def test_reads_return_a_read_result(specs):
    for spec in specs:
        if spec.safety.kind == "read":
            assert issubclass(spec.result_model, ReadResult), f"{spec.name} is not a ReadResult"


def test_destructive_operations_have_a_confirm_field(specs):
    """SAFE-003: the requirement is visible in the schema, not only in the rejection."""
    for spec in specs:
        if project(spec.safety).confirm_required:
            assert "confirm" in spec.args_model.model_fields, (
                f"{spec.name} is destructive but its schema has no confirm field"
            )


def test_non_destructive_operations_do_not_demand_confirmation(specs):
    """A non-destructive op may offer an optional confirm for a conditional path, but
    must never make it mandatory — that would put friction where there is no risk."""
    for spec in specs:
        if project(spec.safety).confirm_required:
            continue
        field = spec.args_model.model_fields.get("confirm")
        if field is None:
            continue
        assert not field.is_required(), (
            f"{spec.name} is not destructive but demands confirmation"
        )


def test_side_effect_rationales_are_substantive(specs):
    for spec in specs:
        if spec.safety.kind == "non_model_side_effect":
            rationale = spec.safety.model_dump()["rationale"]
            assert len(rationale) > 30, f"{spec.name}'s rationale is too vague: {rationale!r}"


def test_summaries_are_useful(specs):
    for spec in specs:
        assert spec.summary, f"{spec.name} has no summary"
        assert spec.summary[0].isupper(), f"{spec.name}'s summary should read as a sentence"
        assert 40 <= len(spec.summary) <= 500, (
            f"{spec.name}'s summary is {len(spec.summary)} chars; aim for 40-500"
        )


def test_metadata_is_well_formed(specs):
    for spec in specs:
        assert spec.tier in TIER_ORDER
        assert spec.domains, f"{spec.name} has no domain"
        assert spec.timeout_s > 0
        assert spec.handler_ref.startswith("swmcp.handlers."), spec.handler_ref


def test_every_cited_requirement_exists(specs):
    known = known_requirement_ids()
    for spec in specs:
        for rid in (*spec.satisfies, *spec.partially_satisfies):
            assert rid in known, f"{spec.name} cites unknown requirement {rid}"


def test_every_operation_cites_at_least_one_requirement(specs):
    for spec in specs:
        assert spec.satisfies or spec.partially_satisfies, (
            f"{spec.name} is not traceable to any requirement"
        )


def test_partial_coverage_is_declared_with_a_reason(specs):
    """Claiming a requirement partially is fine; claiming it silently is not."""
    for spec in specs:
        for rid in spec.partially_satisfies:
            assert rid in DECLARED_PARTIAL, (
                f"{spec.name} partially satisfies {rid} without recording what is missing "
                f"in swmcp.catalog.scope.DECLARED_PARTIAL"
            )


def test_a_requirement_is_never_both_full_and_partial(specs):
    full = {rid for spec in specs for rid in spec.satisfies}
    partial = {rid for spec in specs for rid in spec.partially_satisfies}
    overlap = full & partial
    assert not overlap, f"these are claimed both fully and partially: {sorted(overlap)}"


def test_platform_requirements_name_a_proving_test():
    """A requirement covered "by the architecture" must name a test that actually runs.

    Checking only that the string looks like a path would let this claim rot into
    exactly the kind of unverified assertion the rest of the catalog forbids, so the
    file and the test function are both resolved on disk.
    """
    root = Path(__file__).resolve().parent.parent
    problems = []

    for rid, proof in PLATFORM_REQUIREMENTS.items():
        path_part, _, test_name = proof.partition("::")
        path = root / path_part
        if not path.is_file():
            problems.append(f"{rid}: {path_part} does not exist")
            continue
        if test_name and f"def {test_name}(" not in path.read_text(encoding="utf-8"):
            problems.append(f"{rid}: {path_part} has no test named {test_name}")

    assert not problems, "platform coverage claims point at tests that do not exist:\n" + "\n".join(
        problems
    )


def test_read_only_operations_are_not_audited_or_checkpointed(specs):
    for spec in specs:
        projection = project(spec.safety)
        if projection.read_only:
            assert not projection.auto_checkpoint
            assert not projection.audited
            assert not projection.destructive


def test_in_scope_coverage_is_reported_honestly():
    """Whatever is still uncovered must be visible, not quietly absent."""
    from swmcp.catalog.artifacts import build_coverage

    coverage = build_coverage()
    reported = set(coverage["uncovered_in_scope"])
    covered = (
        set(coverage["fully_covered"])
        | set(coverage["partially_covered"])
        | set(coverage["covered_by_platform"])
    )
    assert reported == IN_SCOPE_REQUIREMENTS - covered
    assert coverage["totals"]["tools"] == len(OPS)
