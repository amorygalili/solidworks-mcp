"""Live session verification (SYS-001/002/005/007). Read-only: nothing is modified."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.live


def test_attach_reports_a_real_version_and_install(live_session):
    info = live_session.call(lambda s: s.system_info(), label="sw_system_info")

    assert info["attached"] is True
    assert info["revision"], "RevisionNumber must be reported"
    assert info["major"] == int(str(info["revision"]).split(".")[0])
    assert info["year"] == 2000 + (info["major"] - 8), "the (year-2000)+8 mapping"
    assert info["prog_id"] == f"SldWorks.Application.{info['major']}"


def test_the_install_comes_from_the_registry_not_a_path_guess(live_session):
    info = live_session.call(lambda s: s.system_info(), label="sw_system_info")
    install = info["install"]

    assert install["found"] is True
    assert Path(install["executable"]).is_file()
    assert install["clsid"], "the CLSID is the registry evidence"
    assert install["notes"] == []
    assert "SOLIDWORKS Corp" not in (install["install_root"] or ""), (
        "the sibling projects' hardcoded install root does not exist on this machine"
    )


def test_the_attached_progid_is_one_that_is_actually_registered(live_session):
    info = live_session.call(lambda s: s.system_info(), label="sw_system_info")
    assert info["attached_prog_id"] in info["install"]["registered_prog_ids"]


def test_attaching_does_not_launch_anything(live_session):
    info = live_session.call(lambda s: s.system_info(), label="sw_system_info")
    assert info["launched_by_this_server"] is False
    assert info["process_running"] is True


def test_constants_came_from_the_installed_typelib(live_session):
    info = live_session.call(lambda s: s.system_info(), label="sw_system_info")
    assert info["constants"]["typelib_major"] == info["major"], (
        "the constant table must match the running release"
    )


def test_standard_planes_resolve_by_tree_position(live_session):
    """SYS-007: never string-match 'Front Plane'; a localized tree has other names."""
    planes = live_session.call(
        lambda s: s.standard_planes(s.active_doc()) if s.active_doc() else [],
        label="planes",
    )
    if not planes:
        pytest.skip("no document is open to inspect")

    assert [p["standard"] for p in planes[:3]] == ["front", "top", "right"]
    for plane in planes[:3]:
        assert plane["type_name"] == "RefPlane", "the invariant token, not the display name"


def test_health_is_immediate_and_needs_no_document(live_session):
    started = time.monotonic()
    snapshot = live_session.health_snapshot()
    elapsed = time.monotonic() - started

    assert elapsed < 0.05, "the health snapshot must never queue behind COM"
    assert snapshot["apartment"] == "STA"
    assert snapshot["thread_alive"] is True
    assert snapshot["session_attached"] is True


def test_com_runs_on_the_worker_thread_not_the_caller(live_session):
    import threading

    ident = live_session.call(lambda _s: threading.get_ident(), label="ident")
    assert ident == live_session.thread_ident
    assert ident != threading.get_ident()


def test_an_unsaved_document_is_reported_as_not_checkpointable(live_session):
    """The 3DEXPERIENCE / never-saved case must be visible, not silently skipped."""
    described = live_session.call(
        lambda s: s.describe(s.active_doc()).as_dict() if s.active_doc() else None,
        label="describe",
    )
    if described is None:
        pytest.skip("no document is open to inspect")

    if described["path"] is None:
        assert described["checkpointable"] is False
        assert any("checkpoint" in w for w in described["warnings"])
    else:
        assert Path(described["path"]).drive, "a saved document must report a real path"
