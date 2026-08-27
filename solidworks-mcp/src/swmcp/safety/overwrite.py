"""SAFE-008: never silently replace an engineering deliverable.

Every write declares a policy. The default is ``version``, because the failure mode
this guards against — a regenerated STEP quietly clobbering the one that was already
sent to a supplier — is expensive and invisible.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from swmcp.errors import SwMcpError, validation_error

OverwritePolicy = Literal["forbid", "version", "allow"]

_VERSION_SUFFIX = re.compile(r"^(?P<stem>.+?)_v(?P<number>\d{3,})$")
_FIRST_VERSION = 2


def _split_version(stem: str) -> tuple[str, int]:
    """``bracket_v003`` -> ``("bracket", 3)``; an unversioned stem is version 1."""
    match = _VERSION_SUFFIX.match(stem)
    if not match:
        return stem, 1
    return match.group("stem"), int(match.group("number"))


def next_versioned_path(path: str | Path) -> str:
    """Propose the next free ``name_vNNN`` sibling of ``path``."""
    target = Path(path)
    base_stem, _ = _split_version(target.stem)
    directory, suffix = target.parent, target.suffix

    highest = 1
    if directory.is_dir():
        for sibling in directory.glob(f"{base_stem}_v*{suffix}"):
            _, number = _split_version(sibling.stem)
            highest = max(highest, number)
    if not target.exists() and highest == 1:
        return str(target)

    candidate_number = max(highest + 1, _FIRST_VERSION)
    while True:
        candidate = directory / f"{base_stem}_v{candidate_number:03d}{suffix}"
        if not candidate.exists():
            return str(candidate)
        candidate_number += 1


def resolve_output_path(
    path: str | Path,
    policy: OverwritePolicy = "version",
    *,
    field: str = "output_path",
) -> tuple[str, Literal["create", "overwrite", "versioned"]]:
    """Apply the overwrite policy, returning the path to write and what will happen."""
    target = Path(path)
    if not target.exists():
        return str(target), "create"

    if policy == "allow":
        return str(target), "overwrite"

    if policy == "version":
        return next_versioned_path(target), "versioned"

    proposed = next_versioned_path(target)
    raise SwMcpError(
        validation_error(
            "OUTPUT_EXISTS",
            f"{str(target)!r} already exists and the overwrite policy is 'forbid'.",
            context={"field": field, "path": str(target), "proposed_path": proposed},
            remediation=[
                f"Write to the proposed non-clobbering path instead: {proposed}",
                "Or pass overwrite='version' to version automatically, "
                "or overwrite='allow' to replace the existing file deliberately.",
            ],
        )
    )
