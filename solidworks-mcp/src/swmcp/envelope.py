"""Result contracts that make SAFE-010 a type error rather than a discipline problem.

The requirements doc is explicit: an operation is not complete merely because a COM
call returned without throwing. So the catalog refuses to register:

* a ``model_mutation`` whose result is not a :class:`MutationResult` — it must carry
  before/after evidence read back out of the model;
* a ``non_model_side_effect`` whose result is not a :class:`SideEffectResult` — it must
  carry filesystem evidence for whatever left the process.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ResultBase(BaseModel):
    """Common base: strict, and always able to carry non-fatal warnings."""

    model_config = ConfigDict(extra="forbid")

    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal problems the caller should see (degraded evidence, fallbacks used).",
    )


class ReadResult(ResultBase):
    """Marker base for read-only operations."""


class Check(BaseModel):
    """One named invariant asserted after a mutation."""

    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    detail: str | None = None


class Verification(BaseModel):
    """Evidence that a mutation actually happened, read back out of the model."""

    model_config = ConfigDict(extra="forbid")

    read_back: bool = Field(
        description="True only when the post-state was re-read from SOLIDWORKS, not assumed."
    )
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    checks: list[Check] = Field(
        min_length=1, description="At least one invariant must be asserted."
    )

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


class CheckpointRecord(BaseModel):
    """What the auto-checkpoint layer did before a mutation ran."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["save_as_copy", "file_copy", "skipped", "reused"] = Field(
        description="Never optional: the caller must be able to tell a real snapshot "
        "from a skipped one. 'file_copy' does not capture unsaved session state."
    )
    checkpoint_path: str | None = None
    source_path: str | None = None
    reason: str | None = Field(
        default=None, description="Why the checkpoint was skipped or reused."
    )
    created_utc: str | None = None
    size_bytes: int | None = None


class MutationResult(ResultBase):
    """Base for every operation that changes the model."""

    verification: Verification
    checkpoint: CheckpointRecord | None = Field(
        default=None, description="Populated by the dispatch pipeline, not by handlers."
    )
    rebuild_errors: list[str] = Field(default_factory=list)


class ArtifactEvidence(BaseModel):
    """Proof that a file the operation claims to have written actually exists."""

    model_config = ConfigDict(extra="forbid")

    path: str
    exists: bool
    size_bytes: int
    modified_utc: str | None = None
    sha256: str | None = None


#: Files above this size are reported without a digest. Hashing is not the expensive
#: part — reading a multi-gigabyte export into memory to hash it is.
MAX_DIGEST_BYTES = 64 * 1024 * 1024


def file_evidence(path: str | Path, *, digest: bool = True) -> ArtifactEvidence:
    """Measure a file that was just written, or record that it is not there.

    Every operation that writes something needs the same four facts — that it exists,
    how big it is, when it was written, and what it hashes to — and each one that built
    them itself got to choose its own digest cut-off. This is the constructor.
    """
    target = Path(path)
    if not target.is_file():
        return ArtifactEvidence(path=str(target), exists=False, size_bytes=0)
    stat = target.stat()
    return ArtifactEvidence(
        path=str(target),
        exists=True,
        size_bytes=stat.st_size,
        modified_utc=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        sha256=hashlib.sha256(target.read_bytes()).hexdigest()
        if digest and stat.st_size <= MAX_DIGEST_BYTES
        else None,
    )


class SideEffectResult(ResultBase):
    """Base for operations whose effect is outside the model (files, UI, process)."""

    artifacts: list[ArtifactEvidence] = Field(default_factory=list)


class UnitEcho(BaseModel):
    """Echoes back the units a request was interpreted in (SYS-006)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    length: str = "mm"
    angle: str = "deg"
    mass: str = "kg"
    note: str = "SOLIDWORKS API values are metres/radians; conversion happens at the boundary."
