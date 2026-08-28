"""An operation that undoes itself must not roll back to somebody else's snapshot.

The checkpoint debounce is there so a burst of edits does not write a file each time.
It is exactly wrong for ``sw_safe_execute``, whose promise is "restore the model to how
it was when this call started": a reused snapshot was taken before some earlier edit, so
restoring it would throw away work the caller never asked to lose.

``fresh_checkpoint`` on the operation is how that is declared, and this is where the
declaration is checked — no SOLIDWORKS required.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.config import SwmcpConfig
from swmcp.dispatch import Dispatcher
from swmcp.envelope import CheckpointRecord


class RecordingStore:
    """Stands in for the checkpoint store and remembers how it was called."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, source_path, *, saver=None, force=False, tag="") -> CheckpointRecord:
        self.calls.append({"source": source_path, "force": force, "tag": tag})
        return CheckpointRecord(
            method="file_copy",
            checkpoint_path=r"C:\cad\.checkpoints\part_20260101_000000.SLDPRT",
            source_path=source_path,
        )


class FakeInfo:
    path = r"C:\cad\part.SLDPRT"
    checkpointable = True
    warnings: tuple[str, ...] = ()


class FakeSession:
    def describe(self, _doc) -> FakeInfo:
        return FakeInfo()


class FakeDoc:
    """A document with no sketch open, so the SaveAs-Copy path is the one chosen."""

    SketchManager = None


@pytest.fixture(scope="module", autouse=True)
def _catalog():
    load_all_ops()


def _run_checkpoint(tool: str) -> RecordingStore:
    from swmcp.context import OpContext

    config = SwmcpConfig(worker_start_timeout_s=2.0)
    store = RecordingStore()

    class InertWorker:
        def call(self, *_args, **_kwargs):
            raise AssertionError("this test never reaches the worker")

        def stop(self, timeout: float = 5.0) -> None:
            pass

    dispatcher = Dispatcher(config, worker=InertWorker(), checkpoints=store)
    spec = OPS[tool]
    ctx = OpContext(
        session=FakeSession(),
        config=config,
        checkpoints=store,
        spec=spec,
        request_id="test",
        doc=FakeDoc(),
    )
    dispatcher._checkpoint(ctx, FakeSession())
    return store


def test_safe_execute_demands_a_fresh_checkpoint():
    store = _run_checkpoint("sw_safe_execute")

    assert len(store.calls) == 1
    assert store.calls[0]["force"] is True, (
        "a reused snapshot predates the sequence, so rolling back to it would undo more "
        "than the sequence did"
    )


def test_an_ordinary_mutation_lets_the_debounce_do_its_job():
    store = _run_checkpoint("sw_feature_fillet")

    assert len(store.calls) == 1
    assert store.calls[0]["force"] is False


def test_the_flag_is_declared_only_where_reuse_would_be_wrong():
    """A blanket fresh_checkpoint would write a file on every edit, which is what the
    debounce exists to prevent."""
    fresh = sorted(spec.name for spec in OPS.values() if spec.fresh_checkpoint)
    assert fresh == ["sw_safe_execute"], (
        f"only operations that restore their own checkpoint should force one: {fresh}"
    )


def test_the_flag_reaches_the_published_manifest():
    import json

    from swmcp.catalog.artifacts import build_artifacts

    manifest = None
    for path, text in build_artifacts().items():
        if path.name == "tool_manifest.json":
            manifest = json.loads(text)
    assert manifest is not None

    by_name = {tool["name"]: tool for tool in manifest["tools"]}
    assert by_name["sw_safe_execute"]["fresh_checkpoint"] is True
    assert by_name["sw_feature_fillet"]["fresh_checkpoint"] is False


def test_a_config_with_no_debounce_still_records_the_request(tmp_path):
    """Turning the debounce off globally must not change what an operation asked for."""
    config = SwmcpConfig(checkpoint_debounce_s=0.0, allowed_roots=(tmp_path,))
    assert replace(config, checkpoint_debounce_s=45.0).checkpoint_debounce_s == 45.0
    store = _run_checkpoint("sw_safe_execute")
    assert store.calls[0]["force"] is True
