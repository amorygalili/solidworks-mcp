"""Live document lifecycle (DOC-001..007) plus the safety gates around it.

Everything here writes only into the scratch root and closes what it opens.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.live


def _cleanup(scratch_root, stem: str) -> None:
    for stale in scratch_root.glob(f"{stem}*.SLDPRT"):
        stale.unlink(missing_ok=True)


def test_full_lifecycle(call, scratch_root, unique_name):
    """new -> list -> save -> rebuild -> close -> open -> activate."""
    _cleanup(scratch_root, unique_name)
    target = scratch_root / f"{unique_name}.SLDPRT"

    created = call("sw_doc_new", {"doc_type": "part"})["result"]
    assert created["template_source"] == "default_preference"
    assert Path(created["template_used"]).is_file()
    assert created["document"]["doc_type"] == "part"
    assert created["document"]["path"] is None, "a new document is not on disk yet"

    listed = call("sw_doc_list")["result"]
    titles = [doc["title"] for doc in listed["documents"]]
    assert listed["active"]["title"] in titles

    saved = call("sw_doc_save", {"output_path": str(target)})["result"]
    assert saved["saved_path"] == str(target)
    assert saved["action"] == "create"
    evidence = saved["artifacts"][0]
    assert evidence["exists"] and evidence["size_bytes"] > 0
    assert evidence["sha256"], "a saved artifact must carry a verifiable digest"
    assert target.is_file()

    rebuilt = call("sw_doc_rebuild", {"force": True})["result"]
    assert rebuilt["succeeded"]
    assert rebuilt["feature_errors"] == []
    assert rebuilt["verification"]["read_back"] is True

    closed = call("sw_doc_close", {"save_first": "discard", "confirm": True})["result"]
    assert closed["verification"]["read_back"] is True
    assert all(check["passed"] for check in closed["verification"]["checks"])

    reopened = call("sw_doc_open", {"path": str(target)})["result"]
    assert reopened["load_errors"]["value"] == 0
    assert reopened["document"]["path"] == str(target)
    assert reopened["document"]["checkpointable"] is True

    activated = call("sw_doc_activate", {"document": {"path": str(target)}})["result"]
    assert activated["document"]["path"] == str(target)

    call("sw_doc_close", {"save_first": "discard", "confirm": True})
    _cleanup(scratch_root, unique_name)


def test_saving_twice_versions_instead_of_overwriting(call, scratch_root, unique_name):
    """SAFE-008: an existing deliverable is never replaced silently."""
    _cleanup(scratch_root, unique_name)
    target = scratch_root / f"{unique_name}.SLDPRT"

    call("sw_doc_new", {"doc_type": "part"})
    first = call("sw_doc_save", {"output_path": str(target)})["result"]
    assert first["action"] == "create"
    original_bytes = target.read_bytes()

    second = call("sw_doc_save", {"output_path": str(target)})["result"]
    assert second["action"] == "versioned"
    assert second["saved_path"].endswith(f"{unique_name}_v002.SLDPRT")
    assert any("rather than the requested path" in w for w in second["warnings"])
    assert target.read_bytes() == original_bytes, "the first file must be untouched"

    call("sw_doc_close", {"save_first": "discard", "confirm": True})
    _cleanup(scratch_root, unique_name)


def test_overwriting_deliberately_requires_confirmation(call, scratch_root, unique_name):
    _cleanup(scratch_root, unique_name)
    target = scratch_root / f"{unique_name}.SLDPRT"

    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})

    refused = call(
        "sw_doc_save",
        {"output_path": str(target), "overwrite": "allow"},
        expect_ok=False,
    )
    assert refused["ok"] is False
    assert refused["error"]["code"] == "CONFIRM_REQUIRED"

    allowed = call(
        "sw_doc_save",
        {"output_path": str(target), "overwrite": "allow", "confirm": True},
    )["result"]
    assert allowed["action"] == "overwrite"
    assert allowed["saved_path"] == str(target)

    call("sw_doc_close", {"save_first": "discard", "confirm": True})
    _cleanup(scratch_root, unique_name)


def test_forbid_policy_proposes_a_free_name(call, scratch_root, unique_name):
    _cleanup(scratch_root, unique_name)
    target = scratch_root / f"{unique_name}.SLDPRT"

    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})

    refused = call(
        "sw_doc_save", {"output_path": str(target), "overwrite": "forbid"}, expect_ok=False
    )
    assert refused["error"]["code"] == "OUTPUT_EXISTS"
    assert refused["error"]["context"]["proposed_path"].endswith("_v002.SLDPRT")

    call("sw_doc_close", {"save_first": "discard", "confirm": True})
    _cleanup(scratch_root, unique_name)


def test_saving_outside_the_allowed_roots_is_refused(call):
    """SAFE-004, checked before any COM call happens."""
    refused = call("sw_doc_save", {"output_path": r"C:\windows\system32\evil.SLDPRT"}, expect_ok=False)
    assert refused["error"]["code"] == "PATH_NOT_ALLOWED"
    assert any("SWMCP_ALLOWED_ROOTS" in step for step in refused["error"]["remediation"])


def test_opening_a_missing_file_is_a_clear_error(call, scratch_root):
    refused = call("sw_doc_open", {"path": str(scratch_root / "does_not_exist.SLDPRT")}, expect_ok=False)
    assert refused["error"]["code"] == "FILE_NOT_FOUND"
    assert refused["error"]["remediation"]


def test_closing_needs_an_explicit_decision_about_unsaved_work(call, scratch_root, unique_name):
    _cleanup(scratch_root, unique_name)
    call("sw_doc_new", {"doc_type": "part"})

    missing_confirm = call("sw_doc_close", {"save_first": "discard"}, expect_ok=False)
    assert missing_confirm["error"]["code"] == "CONFIRM_REQUIRED"

    missing_policy = call("sw_doc_close", {"confirm": True}, expect_ok=False)
    assert missing_policy["error"]["code"] == "INVALID_ARGUMENTS"

    call("sw_doc_close", {"save_first": "discard", "confirm": True})


def test_unknown_arguments_are_refused_not_ignored(call):
    """SAFE-001: a typo must not be silently dropped."""
    refused = call("sw_doc_list", {"limitt": 5}, expect_ok=False)
    assert refused["error"]["code"] == "INVALID_ARGUMENTS"
    assert refused["error"]["context"]["errors"]


def test_checkpoint_captures_unsaved_state(call, scratch_root, unique_name):
    """SAFE-005: SaveAs-Copy is preferred precisely because a file copy would not."""
    _cleanup(scratch_root, unique_name)
    target = scratch_root / f"{unique_name}.SLDPRT"

    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})

    record = call("sw_checkpoint_create")["result"]["checkpoint"]
    assert record["method"] == "save_as_copy", (
        "a file copy would miss edits made since the last save"
    )
    assert Path(record["checkpoint_path"]).is_file()
    assert Path(record["checkpoint_path"]).parent.name == ".checkpoints"

    listed = call("sw_checkpoint_list")["result"]
    assert any(c["checkpoint_path"] == record["checkpoint_path"] for c in listed["checkpoints"])

    call("sw_doc_close", {"save_first": "discard", "confirm": True})
    _cleanup(scratch_root, unique_name)


def test_an_unsaved_document_reports_that_it_cannot_be_checkpointed(call):
    call("sw_doc_new", {"doc_type": "part"})
    result = call("sw_checkpoint_create")["result"]
    assert result["checkpoint"]["method"] == "skipped"
    assert result["checkpoint"]["reason"] == "no_document_path"
    assert any("never been saved" in w or "checkpoint" in w for w in result["warnings"])
    call("sw_doc_close", {"save_first": "discard", "confirm": True})


def test_mutations_are_audited_with_their_checkpoint(call, scratch_root, unique_name):
    """SAFE-006."""
    _cleanup(scratch_root, unique_name)
    target = scratch_root / f"{unique_name}.SLDPRT"
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    call("sw_doc_rebuild", {"force": True})

    entries = call("sw_audit_tail", {"limit": 50})["result"]["entries"]
    tools = [entry["tool"] for entry in entries]
    assert "sw_doc_rebuild" in tools
    assert "sw_doc_save" in tools
    assert "sw_doc_list" not in tools, "read-only operations are not audited"

    rebuild = next(entry for entry in entries if entry["tool"] == "sw_doc_rebuild")
    assert rebuild["ok"] is True
    assert rebuild["checkpoint_method"] in {"save_as_copy", "file_copy", "reused"}

    call("sw_doc_close", {"save_first": "discard", "confirm": True})
    _cleanup(scratch_root, unique_name)


def test_path_policy_answers_before_a_write_is_attempted(call, scratch_root, unique_name):
    inside = call(
        "sw_path_policy", {"path": str(scratch_root / f"{unique_name}.step")}
    )["result"]
    assert inside["allowed"] is True
    assert inside["action"] == "create"

    outside = call("sw_path_policy", {"path": r"D:\nowhere\x.step"})["result"]
    assert outside["allowed"] is False
    assert outside["remediation"]


def test_explain_error_decodes_a_real_hresult(call):
    explained = call("sw_explain_error", {"hresult": 0x8001010A})["result"]["explanations"][0]
    assert explained["code"] == "COM_SERVER_BUSY"
    assert any("dialog" in step for step in explained["remediation"])


def test_explain_error_decodes_a_solidworks_status(call):
    explained = call(
        "sw_explain_error", {"sw_enum": "swFileLoadError_e", "sw_value": 2}
    )["result"]["explanations"][0]
    assert "swFileNotFoundError" in explained["names"]
    assert explained["remediation"]
