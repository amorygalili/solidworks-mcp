"""Live-test fixtures that drive the real dispatch pipeline.

These tests run against whatever SOLIDWORKS session is on the machine, so they are
written to be good neighbours: they only ever close documents they created themselves,
addressed by title, and they never fall back to "the active document".
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def dispatcher(live_config, scratch_root):
    """A Dispatcher wired to the scratch root, sharing one STA worker for the session."""
    from dataclasses import replace

    from swmcp.com.session import SwSession
    from swmcp.com.worker import StaWorker
    from swmcp.config import set_config
    from swmcp.dispatch import Dispatcher
    from swmcp.errors import SwMcpError

    config = replace(live_config, audit_path=scratch_root / "audit.jsonl")
    set_config(config)

    worker = StaWorker(config, session_factory=lambda: SwSession(config))
    made = Dispatcher(config, worker=worker)
    try:
        worker.call(lambda s: s.ensure(), label="attach", timeout_s=60.0)
    except SwMcpError as exc:
        made.close()
        pytest.skip(f"SOLIDWORKS is not available: {exc.envelope.code}")
    try:
        yield made
    finally:
        made.close()
        set_config(None)


@pytest.fixture(scope="session")
def pre_existing_titles(dispatcher) -> set[str]:
    """Documents that were already open before the suite started.

    Recorded so the cleanup fixture can leave them completely alone: a stray
    ``sw_doc_close`` with no explicit target would otherwise close whatever happened to
    be active, which could be someone's unsaved work.
    """
    payload = dispatcher.call("sw_doc_list", {})
    if not payload.get("ok"):
        return set()
    return {doc["title"] for doc in payload["result"]["documents"]}


@pytest.fixture
def call(dispatcher):
    """Call an operation and fail the test with a readable message if it errors."""

    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        payload = dispatcher.call(name, arguments or {})
        if expect_ok and not payload.get("ok"):
            error = payload["error"]
            raise AssertionError(
                f"{name} failed: [{error['code']}] {error['message']}\n"
                f"remediation: {error.get('remediation')}"
            )
        return payload

    return _call


@pytest.fixture(autouse=True)
def close_documents_this_test_opened(dispatcher, pre_existing_titles, scratch_root):
    """Close only what the test itself created, addressed explicitly by title.

    This runs after any test-local fixture teardown, which is why the scratch files are
    removed here too: SOLIDWORKS keeps a lock on an open document, so deleting the file
    before closing it fails.
    """
    before = _open_titles(dispatcher) | pre_existing_titles
    yield

    for title in _open_titles(dispatcher) - before:
        dispatcher.call(
            "sw_doc_close",
            {"document": {"title": title}, "save_first": "discard", "confirm": True},
        )

    for stale in scratch_root.glob("swmcp_*.SLDPRT"):
        try:
            stale.unlink()
        except OSError:
            # Still locked by SOLIDWORKS; a later test's pre-run sweep will get it.
            continue


def _open_titles(dispatcher) -> set[str]:
    payload = dispatcher.call("sw_doc_list", {})
    if not payload.get("ok"):
        return set()
    return {doc["title"] for doc in payload["result"]["documents"]}
