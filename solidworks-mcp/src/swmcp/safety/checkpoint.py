"""SAFE-005: a snapshot before every risky mutation, and a way back.

Two properties matter more than the mechanism:

*Never block.* A checkpoint that fails must not abort the mutation — it returns
``method="skipped"`` with a reason. Staging problems should not wedge an agent.

*Never over-claim.* ``CheckpointRecord.method`` is required, because
``save_as_copy`` captures unsaved session state and ``file_copy`` does not. A caller
deciding whether a rollback is trustworthy has to be able to tell the two apart.

The COM call is injected as a ``saver`` callable so everything here is testable with
no SOLIDWORKS present.
"""

from __future__ import annotations

import re
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from swmcp.config import SwmcpConfig, get_config
from swmcp.envelope import CheckpointRecord
from swmcp.errors import SwMcpError, validation_error
from swmcp.safety.paths import classify_document_path

CHECKPOINT_DIRNAME = ".checkpoints"
STAMP_FORMAT = "%Y%m%d_%H%M%S"
_STAMPED = re.compile(r"^(?P<stem>.+)_(?P<date>\d{8})_(?P<time>\d{6})(?:_(?P<seq>\d+))?$")

#: A saver takes a destination path and returns True if it wrote the file itself.
Saver = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class CheckpointInfo:
    checkpoint_path: str
    size_bytes: int
    modified_utc: str


@dataclass(frozen=True, slots=True)
class _DebounceEntry:
    record: CheckpointRecord
    at: float


class CheckpointStore:
    """Creates, lists, prunes, and restores document snapshots."""

    def __init__(
        self,
        config: SwmcpConfig | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._config = config or get_config()
        self._clock = clock
        self._recent: dict[str, _DebounceEntry] = {}
        self._lock = threading.Lock()

    # -- locations ---------------------------------------------------------

    def checkpoint_dir(self, source_path: str | Path) -> Path:
        """Beside the document by default, so a human can find the snapshot."""
        if self._config.checkpoint_dir is not None:
            return self._config.checkpoint_dir
        return Path(source_path).parent / CHECKPOINT_DIRNAME

    def _stamped_path(self, source: Path, *, when: datetime, tag: str = "") -> Path:
        """A free path in the checkpoint directory.

        The stamp has one-second resolution, so two mutations inside the same second
        would collide and the second would silently overwrite the first snapshot. A
        sequence suffix keeps both.
        """
        stamp = when.strftime(STAMP_FORMAT)
        tag_part = f"_{tag}" if tag else ""
        directory = self.checkpoint_dir(source)
        candidate = directory / f"{source.stem}{tag_part}_{stamp}{source.suffix}"
        sequence = 2
        while candidate.exists():
            candidate = directory / f"{source.stem}{tag_part}_{stamp}_{sequence}{source.suffix}"
            sequence += 1
        return candidate

    # -- create ------------------------------------------------------------

    def create(
        self,
        source_path: str | None,
        *,
        saver: Saver | None = None,
        force: bool = False,
        tag: str = "",
    ) -> CheckpointRecord:
        """Snapshot ``source_path``. Never raises for an expected failure."""
        normalized, is_local = classify_document_path(source_path)
        if normalized is None:
            return CheckpointRecord(
                method="skipped",
                reason="no_document_path",
            )
        if not is_local:
            return CheckpointRecord(
                method="skipped",
                source_path=normalized,
                reason="not_a_local_file",
            )

        source = Path(normalized)
        if not force:
            reused = self._reuse(normalized)
            if reused is not None:
                return reused

        try:
            self.checkpoint_dir(source).mkdir(parents=True, exist_ok=True)
            destination = self._stamped_path(source, when=datetime.now(UTC), tag=tag)
            method = self._write(source, destination, saver)
        except (OSError, RuntimeError) as exc:
            return CheckpointRecord(
                method="skipped",
                source_path=normalized,
                reason=f"checkpoint_failed: {exc}",
            )

        if not destination.is_file():
            return CheckpointRecord(
                method="skipped",
                source_path=normalized,
                reason="checkpoint_failed: destination was not written",
            )

        record = CheckpointRecord(
            method=method,
            checkpoint_path=str(destination),
            source_path=normalized,
            created_utc=datetime.now(UTC).isoformat(),
            size_bytes=destination.stat().st_size,
        )
        with self._lock:
            self._recent[normalized.casefold()] = _DebounceEntry(record, self._clock())
        self.prune(normalized)
        return record

    def _reuse(self, normalized: str) -> CheckpointRecord | None:
        window = self._config.checkpoint_debounce_s
        if window <= 0:
            return None
        with self._lock:
            entry = self._recent.get(normalized.casefold())
        if entry is None or (self._clock() - entry.at) >= window:
            return None
        return entry.record.model_copy(
            update={
                "method": "reused",
                "reason": f"a checkpoint was taken {self._clock() - entry.at:.1f}s ago "
                f"(debounce window {window:.0f}s)",
            }
        )

    def _write(self, source: Path, destination: Path, saver: Saver | None) -> str:
        """Prefer SaveAs-Copy: only that captures edits not yet written to disk."""
        if saver is not None:
            try:
                if saver(str(destination)) and destination.is_file():
                    return "save_as_copy"
            except Exception:
                # Any COM failure here is expected to fall back to a plain copy.
                pass
        if not source.is_file():
            raise OSError(f"source document {str(source)!r} does not exist on disk")
        shutil.copy2(source, destination)
        return "file_copy"

    # -- list and prune ----------------------------------------------------

    def list(self, source_path: str | Path) -> list[CheckpointInfo]:
        """Newest first."""
        source = Path(source_path)
        directory = self.checkpoint_dir(source)
        if not directory.is_dir():
            return []
        found = [
            candidate
            for candidate in directory.glob(f"{source.stem}*{source.suffix}")
            if _STAMPED.match(candidate.stem)
        ]
        found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [
            CheckpointInfo(
                checkpoint_path=str(candidate),
                size_bytes=candidate.stat().st_size,
                modified_utc=datetime.fromtimestamp(candidate.stat().st_mtime, UTC).isoformat(),
            )
            for candidate in found
        ]

    def prune(self, source_path: str | Path) -> list[str]:
        """Keep the newest ``SWMCP_CHECKPOINT_KEEP`` snapshots; delete the rest."""
        keep = self._config.checkpoint_keep
        removed: list[str] = []
        for stale in self.list(source_path)[keep:]:
            try:
                Path(stale.checkpoint_path).unlink()
                removed.append(stale.checkpoint_path)
            except OSError:  # pragma: no cover - a locked file simply survives
                continue
        return removed

    # -- restore -----------------------------------------------------------

    @staticmethod
    def infer_target(checkpoint_path: str | Path) -> Path | None:
        """Recover the document a checkpoint belongs to from its name and location."""
        candidate = Path(checkpoint_path)
        match = _STAMPED.match(candidate.stem)
        if not match:
            return None
        parent = candidate.parent
        if parent.name != CHECKPOINT_DIRNAME:
            return None
        stem = match.group("stem")
        # Strip a tag suffix such as "_pre_restore" that this module added.
        stem = re.sub(r"_pre_restore$", "", stem)
        return parent.parent / f"{stem}{candidate.suffix}"

    def restore(
        self,
        checkpoint_path: str | Path,
        *,
        confirm: bool,
        target_path: str | Path | None = None,
        saver: Saver | None = None,
    ) -> dict[str, str]:
        """Copy a checkpoint back over its document, reversibly.

        A snapshot of the *current* state is staged first, so a restore performed by
        mistake is itself undoable.
        """
        if not confirm:
            raise SwMcpError(
                validation_error(
                    "CONFIRM_REQUIRED",
                    "Restoring a checkpoint overwrites the current document.",
                    remediation=["Re-send the request with confirm=true once you are sure."],
                )
            )

        source = Path(checkpoint_path)
        if not source.is_file():
            raise SwMcpError(
                validation_error(
                    "CHECKPOINT_NOT_FOUND",
                    f"No checkpoint file at {str(source)!r}.",
                    remediation=["Call the checkpoint list operation to see what exists."],
                )
            )

        target = Path(target_path) if target_path else self.infer_target(source)
        if target is None:
            raise SwMcpError(
                validation_error(
                    "RESTORE_TARGET_UNKNOWN",
                    f"Could not infer which document {str(source)!r} belongs to.",
                    context={"checkpoint_path": str(source)},
                    remediation=[
                        "Pass target_path explicitly.",
                        "Checkpoints are recognised as "
                        "<docdir>/.checkpoints/<stem>_<yyyymmdd>_<hhmmss><ext>.",
                    ],
                )
            )

        pre = self.create(str(target), saver=saver, force=True, tag="pre_restore")
        shutil.copy2(source, target)
        return {
            "restored_from": str(source),
            "restored_to": str(target),
            "pre_restore_checkpoint": pre.checkpoint_path or "",
            "pre_restore_method": pre.method,
        }
