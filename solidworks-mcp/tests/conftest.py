"""Shared fixtures.

Live tests are deselected by default (``-m "not live"`` in ``pyproject.toml``). Run
them with ``uv run pytest -m live``. They attach to a running SOLIDWORKS and write
**only** into the scratch root — they never touch documents that were already open.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRATCH_ROOT = REPO_ROOT / ".scratch"


@pytest.fixture(scope="session")
def scratch_root() -> Path:
    root = Path(os.environ.get("SWMCP_SCRATCH_ROOT", SCRATCH_ROOT))
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(scope="session")
def live_config(scratch_root):
    from swmcp.config import SwmcpConfig

    return SwmcpConfig(
        allowed_roots=(scratch_root,),
        checkpoint_debounce_s=0.0,
        call_timeout_s=180.0,
    )


@pytest.fixture(scope="session")
def live_worker(live_config):
    """One STA worker for the whole live session."""
    from swmcp.com.session import SwSession
    from swmcp.com.worker import StaWorker

    worker = StaWorker(live_config, session_factory=lambda: SwSession(live_config))
    worker.start()
    try:
        yield worker
    finally:
        worker.stop()


@pytest.fixture(scope="session")
def live_session(live_worker):
    """Proves SOLIDWORKS is reachable, and skips the live suite cleanly if not."""
    from swmcp.errors import SwMcpError

    try:
        live_worker.call(lambda s: s.ensure(), label="attach", timeout_s=60.0)
    except SwMcpError as exc:
        pytest.skip(f"SOLIDWORKS is not available: {exc.envelope.code}")
    return live_worker


@pytest.fixture
def unique_name(request) -> str:
    """A per-test document stem, so live runs never collide."""
    return f"swmcp_{request.node.name[:40].replace('[', '_').replace(']', '')}"
