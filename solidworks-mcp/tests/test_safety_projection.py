"""SAFE-002: safety is a union, and its boolean projection has exactly one home."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.catalog.projection import project
from swmcp.catalog.spec import ModelMutation, NonModelSideEffect, ReadSafety, tier_allowed

ALL_VARIANTS = [
    ReadSafety(),
    ModelMutation(destructive=False),
    ModelMutation(destructive=True),
    NonModelSideEffect(destructive=False, rationale="Writes a preview PNG."),
    NonModelSideEffect(destructive=True, rationale="Overwrites a deliverable on disk."),
]


def test_projection_covers_every_variant():
    for safety in ALL_VARIANTS:
        projection = project(safety)
        assert isinstance(projection.read_only, bool)


def test_reads_need_no_gates():
    p = project(ReadSafety())
    assert p.read_only and not p.destructive
    assert not p.confirm_required and not p.auto_checkpoint and not p.audited


def test_model_mutations_always_checkpoint():
    for destructive in (False, True):
        p = project(ModelMutation(destructive=destructive))
        assert p.auto_checkpoint, "every model mutation must be checkpointed (SAFE-005)"
        assert p.audited


def test_confirmation_tracks_destructiveness_exactly():
    """SAFE-003 can never drift away from the destructive flag."""
    for safety in ALL_VARIANTS:
        p = project(safety)
        assert p.confirm_required == p.destructive


def test_side_effects_are_not_checkpointable():
    p = project(NonModelSideEffect(destructive=True, rationale="Writes a STEP file."))
    assert not p.auto_checkpoint, "a file write has no model state to snapshot"
    assert p.audited


@pytest.mark.parametrize("rationale", ["", "   ", "\n\t"])
def test_side_effect_requires_a_written_rationale(rationale):
    with pytest.raises(ValidationError):
        NonModelSideEffect(destructive=False, rationale=rationale)


def test_safety_variants_are_frozen_and_strict():
    with pytest.raises(ValidationError):
        ModelMutation(destructive=True, extra_field=1)
    safety = ModelMutation(destructive=True)
    with pytest.raises(ValidationError):
        safety.destructive = False


def test_tier_gating_is_progressive():
    assert tier_allowed("core", "core")
    assert not tier_allowed("extended", "core")
    assert tier_allowed("extended", "advanced")
    assert tier_allowed("debug", "all")
