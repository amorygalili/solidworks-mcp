"""SAFE-006: an append-only record of every write, that never breaks the caller."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from swmcp.config import SwmcpConfig
from swmcp.safety.audit import append_audit, audit_path, normalize_args, read_recent


@pytest.fixture
def config(tmp_path):
    return SwmcpConfig(audit_path=tmp_path / "audit" / "audit.jsonl")


def test_entries_are_appended_never_rewritten(config):
    for index in range(3):
        assert append_audit(tool=f"sw_doc_save_{index}", ok=True, config=config)
    lines = audit_path(config).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert [json.loads(line)["tool"] for line in lines] == [
        "sw_doc_save_0",
        "sw_doc_save_1",
        "sw_doc_save_2",
    ]


def test_every_line_is_valid_json_with_the_required_fields(config):
    append_audit(
        tool="sw_feature_delete",
        ok=False,
        destructive=True,
        args={"feature": "Fillet1", "confirm": True},
        document=r"C:\cad\bracket.SLDPRT",
        checkpoint_path=r"C:\cad\.checkpoints\bracket_20260826_120000.SLDPRT",
        checkpoint_method="save_as_copy",
        error_code="FEATURE_DELETE_FAILED",
        error_message="Feature is referenced by a later feature.",
        duration_ms=812.5,
        config=config,
    )
    entry = json.loads(audit_path(config).read_text(encoding="utf-8").strip())
    for field in (
        "timestamp",
        "tool",
        "ok",
        "destructive",
        "document",
        "args",
        "checkpoint_path",
        "checkpoint_method",
        "error_code",
        "duration_ms",
    ):
        assert field in entry, f"audit entry is missing {field}"
    assert entry["ok"] is False
    assert entry["destructive"] is True
    assert entry["args"]["confirm"] is True


def test_read_recent_returns_newest_first_and_respects_the_limit(config):
    for index in range(10):
        append_audit(tool=f"op{index}", ok=True, config=config)
    recent = read_recent(3, config=config)
    assert [e["tool"] for e in recent] == ["op9", "op8", "op7"]


def test_reading_an_absent_log_is_empty_not_an_error(config):
    assert read_recent(5, config=config) == []


def test_timestamps_are_non_decreasing(config):
    for index in range(5):
        append_audit(tool=f"op{index}", ok=True, config=config)
    stamps = [
        json.loads(line)["timestamp"]
        for line in audit_path(config).read_text(encoding="utf-8").splitlines()
    ]
    assert stamps == sorted(stamps)


def test_a_corrupt_line_does_not_poison_the_read(config):
    append_audit(tool="good", ok=True, config=config)
    with audit_path(config).open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    append_audit(tool="also_good", ok=True, config=config)

    recent = read_recent(10, config=config)
    assert [e.get("tool") for e in recent] == ["also_good", None, "good"]
    assert recent[1]["parse_error"] is True


def test_auditing_is_best_effort_and_never_raises(config, monkeypatch):
    """Losing an audit line must not lose the operation that already happened."""

    def explode(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.mkdir", explode)
    assert append_audit(tool="sw_doc_save", ok=True, config=config) is False


def test_unserializable_arguments_are_reduced_not_dropped(config):
    class Opaque:
        def __repr__(self):
            return "<COM object IFace2>"

    append_audit(tool="sw_feature_fillet", ok=True, args={"edge": Opaque()}, config=config)
    entry = json.loads(audit_path(config).read_text(encoding="utf-8").strip())
    assert entry["args"]["edge"] == "<COM object IFace2>"


def test_bulky_arguments_are_elided_and_bounded():
    normalized = normalize_args(
        {
            "entities": [{"type": "line"}] * 500,
            "note": "x" * 5000,
            "many": list(range(100)),
        }
    )
    assert normalized["entities"].startswith("<elided ")
    assert normalized["note"].endswith("<truncated>")
    assert normalized["many"][-1] == "<+80 more>"


def test_default_audit_location_is_used_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert audit_path(SwmcpConfig()) == tmp_path / ".mcp-audit" / "audit.jsonl"


def test_config_override_wins(tmp_path):
    config = replace(SwmcpConfig(), audit_path=tmp_path / "custom.jsonl")
    assert audit_path(config) == tmp_path / "custom.jsonl"
