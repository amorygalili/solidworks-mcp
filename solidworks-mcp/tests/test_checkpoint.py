"""SAFE-005. The COM saver is injected, so every path here runs without SOLIDWORKS."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from swmcp.config import SwmcpConfig
from swmcp.errors import SwMcpError
from swmcp.safety.checkpoint import CheckpointStore


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def document(tmp_path) -> Path:
    path = tmp_path / "bracket.SLDPRT"
    path.write_bytes(b"saved-on-disk")
    return path


@pytest.fixture
def store(tmp_path):
    return CheckpointStore(SwmcpConfig(), clock=Clock())


def test_checkpoint_lands_beside_the_document_with_a_timestamp(store, document):
    record = store.create(str(document))
    assert record.method == "file_copy"
    checkpoint = Path(record.checkpoint_path)
    assert checkpoint.parent == document.parent / ".checkpoints"
    assert re.match(r"^bracket_\d{8}_\d{6}\.SLDPRT$", checkpoint.name)
    assert checkpoint.read_bytes() == b"saved-on-disk"


def test_save_as_copy_is_preferred_because_it_captures_unsaved_state(store, document):
    def saver(destination: str) -> bool:
        Path(destination).write_bytes(b"includes-unsaved-edits")
        return True

    record = store.create(str(document), saver=saver)
    assert record.method == "save_as_copy"
    assert Path(record.checkpoint_path).read_bytes() == b"includes-unsaved-edits"


def test_a_failing_saver_falls_back_to_a_file_copy(store, document):
    def saver(_destination: str) -> bool:
        raise RuntimeError("COM refused SaveAs on a platform-managed document")

    record = store.create(str(document), saver=saver)
    assert record.method == "file_copy", "the fallback must still produce a snapshot"
    assert Path(record.checkpoint_path).is_file()


def test_method_distinguishes_a_real_snapshot_from_a_skipped_one(store):
    assert store.create(None).method == "skipped"
    assert store.create("").method == "skipped"
    assert store.create("   ").method == "skipped"


def test_an_unsaved_document_is_reported_not_silently_skipped(store):
    record = store.create(None)
    assert record.method == "skipped"
    assert record.reason == "no_document_path"


def test_a_platform_managed_document_is_reported_as_not_a_local_file(store):
    record = store.create("3dexperience://doc/1234")
    assert record.method == "skipped"
    assert record.reason == "not_a_local_file"


def test_a_missing_source_file_never_raises(store, tmp_path):
    record = store.create(str(tmp_path / "never-saved.SLDPRT"))
    assert record.method == "skipped"
    assert "checkpoint_failed" in record.reason


def test_debounce_reuses_a_recent_snapshot(tmp_path, document):
    clock = Clock()
    store = CheckpointStore(SwmcpConfig(checkpoint_debounce_s=45.0), clock=clock)

    first = store.create(str(document))
    assert first.method == "file_copy"

    clock.advance(10.0)
    second = store.create(str(document))
    assert second.method == "reused"
    assert second.checkpoint_path == first.checkpoint_path
    assert "debounce" in second.reason

    clock.advance(40.0)  # now 50s since the first
    third = store.create(str(document))
    assert third.method == "file_copy"
    assert third.checkpoint_path != first.checkpoint_path


def test_force_bypasses_the_debounce(tmp_path, document):
    clock = Clock()
    store = CheckpointStore(SwmcpConfig(checkpoint_debounce_s=45.0), clock=clock)
    store.create(str(document))
    clock.advance(1.0)
    forced = store.create(str(document), force=True)
    assert forced.method == "file_copy"


def test_listing_is_newest_first(tmp_path, document):
    store = CheckpointStore(SwmcpConfig(checkpoint_debounce_s=0.0))
    made = []
    for index in range(3):
        document.write_bytes(f"revision-{index}".encode())
        record = store.create(str(document))
        Path(record.checkpoint_path).touch()
        made.append(record.checkpoint_path)
        # Space the mtimes so ordering is unambiguous.
        import os

        os.utime(record.checkpoint_path, (1_700_000_000 + index, 1_700_000_000 + index))

    listed = [info.checkpoint_path for info in store.list(document)]
    assert listed == list(reversed(made))


def test_retention_prunes_the_oldest(tmp_path, document):
    store = CheckpointStore(SwmcpConfig(checkpoint_debounce_s=0.0, checkpoint_keep=3))
    import os

    for index in range(6):
        record = store.create(str(document))
        os.utime(record.checkpoint_path, (1_700_000_000 + index, 1_700_000_000 + index))
        store.prune(document)

    remaining = store.list(document)
    assert len(remaining) == 3, "retention must bound unbounded disk growth"


def test_listing_ignores_unrelated_files(store, document):
    store.create(str(document))
    stray = document.parent / ".checkpoints" / "notes.txt"
    stray.write_text("not a checkpoint")
    (document.parent / ".checkpoints" / "bracket_backup.SLDPRT").write_bytes(b"unstamped")
    assert len(store.list(document)) == 1


def test_checkpoint_dir_can_be_relocated(tmp_path, document):
    elsewhere = tmp_path / "snapshots"
    store = CheckpointStore(replace(SwmcpConfig(), checkpoint_dir=elsewhere))
    record = store.create(str(document))
    assert Path(record.checkpoint_path).parent == elsewhere


def test_restore_target_is_inferred_from_the_checkpoint_name():
    inferred = CheckpointStore.infer_target(r"C:\cad\.checkpoints\bracket_20260826_120000.SLDPRT")
    assert inferred == Path(r"C:\cad\bracket.SLDPRT")


def test_restore_target_inference_refuses_a_stray_file():
    assert CheckpointStore.infer_target(r"C:\cad\.checkpoints\bracket.SLDPRT") is None
    assert CheckpointStore.infer_target(r"C:\cad\bracket_20260826_120000.SLDPRT") is None


def test_restore_requires_confirmation(store, document):
    record = store.create(str(document))
    with pytest.raises(SwMcpError) as caught:
        store.restore(record.checkpoint_path, confirm=False)
    assert caught.value.envelope.code == "CONFIRM_REQUIRED"


def test_restore_is_itself_reversible(tmp_path, document):
    store = CheckpointStore(SwmcpConfig(checkpoint_debounce_s=0.0))
    original = store.create(str(document))

    document.write_bytes(b"work-i-might-still-want")
    outcome = store.restore(original.checkpoint_path, confirm=True)

    assert document.read_bytes() == b"saved-on-disk"
    pre = Path(outcome["pre_restore_checkpoint"])
    assert pre.is_file()
    assert pre.read_bytes() == b"work-i-might-still-want", (
        "restoring by mistake must itself be undoable"
    )


def test_restore_rejects_a_missing_checkpoint(store, tmp_path):
    with pytest.raises(SwMcpError) as caught:
        store.restore(tmp_path / "nope.SLDPRT", confirm=True)
    assert caught.value.envelope.code == "CHECKPOINT_NOT_FOUND"


def test_restore_rejects_an_unresolvable_target(store, tmp_path):
    stray = tmp_path / "loose_20260826_120000.SLDPRT"
    stray.write_bytes(b"x")
    with pytest.raises(SwMcpError) as caught:
        store.restore(stray, confirm=True)
    assert caught.value.envelope.code == "RESTORE_TARGET_UNKNOWN"
    assert any("target_path" in step for step in caught.value.envelope.remediation)


def test_two_checkpoints_in_the_same_second_do_not_collide(tmp_path, document):
    """A one-second stamp is not unique enough; the second snapshot must not clobber."""
    store = CheckpointStore(SwmcpConfig(checkpoint_debounce_s=0.0))
    document.write_bytes(b"state-a")
    first = store.create(str(document), force=True)
    document.write_bytes(b"state-b")
    second = store.create(str(document), force=True)

    assert first.checkpoint_path != second.checkpoint_path
    assert Path(first.checkpoint_path).read_bytes() == b"state-a"
    assert Path(second.checkpoint_path).read_bytes() == b"state-b"
    assert len(store.list(document)) == 2
