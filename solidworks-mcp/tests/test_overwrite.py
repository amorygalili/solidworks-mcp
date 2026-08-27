"""SAFE-008: engineering deliverables are never silently replaced."""

from __future__ import annotations

import pytest

from swmcp.errors import SwMcpError
from swmcp.safety.overwrite import next_versioned_path, resolve_output_path


def test_a_free_path_is_used_as_given(tmp_path):
    target = tmp_path / "bracket.step"
    path, action = resolve_output_path(target)
    assert path == str(target)
    assert action == "create"


def test_versioning_starts_at_v002(tmp_path):
    target = tmp_path / "bracket.step"
    target.write_text("original")
    path, action = resolve_output_path(target, "version")
    assert path == str(tmp_path / "bracket_v002.step")
    assert action == "versioned"
    assert target.read_text() == "original", "the original must be left untouched"


def test_versioning_continues_past_existing_versions(tmp_path):
    (tmp_path / "bracket.step").write_text("v1")
    (tmp_path / "bracket_v002.step").write_text("v2")
    (tmp_path / "bracket_v003.step").write_text("v3")
    path, _ = resolve_output_path(tmp_path / "bracket.step", "version")
    assert path == str(tmp_path / "bracket_v004.step")


def test_versioning_an_already_versioned_name_does_not_nest(tmp_path):
    (tmp_path / "bracket_v002.step").write_text("v2")
    path, _ = resolve_output_path(tmp_path / "bracket_v002.step", "version")
    assert path == str(tmp_path / "bracket_v003.step")
    assert "_v002_v" not in path


def test_forbid_refuses_and_proposes_a_safe_name(tmp_path):
    target = tmp_path / "bracket.step"
    target.write_text("delivered to the supplier")
    with pytest.raises(SwMcpError) as caught:
        resolve_output_path(target, "forbid")
    envelope = caught.value.envelope
    assert envelope.code == "OUTPUT_EXISTS"
    assert envelope.context["proposed_path"] == str(tmp_path / "bracket_v002.step")
    assert any("bracket_v002.step" in step for step in envelope.remediation)
    assert target.read_text() == "delivered to the supplier"


def test_allow_overwrites_deliberately(tmp_path):
    target = tmp_path / "bracket.step"
    target.write_text("old")
    path, action = resolve_output_path(target, "allow")
    assert path == str(target)
    assert action == "overwrite"


def test_versioning_is_independent_per_extension(tmp_path):
    (tmp_path / "bracket.step").write_text("step")
    (tmp_path / "bracket.pdf").write_text("pdf")
    step, _ = resolve_output_path(tmp_path / "bracket.step", "version")
    pdf, _ = resolve_output_path(tmp_path / "bracket.pdf", "version")
    assert step.endswith("bracket_v002.step")
    assert pdf.endswith("bracket_v002.pdf")


def test_next_versioned_path_leaves_a_free_name_alone(tmp_path):
    assert next_versioned_path(tmp_path / "fresh.step") == str(tmp_path / "fresh.step")
