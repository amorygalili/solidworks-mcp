"""The SOLIDWORKS ProgID, derived rather than spelled out.

SOLIDWORKS registers a version-suffixed ProgID alongside the version-independent one,
where the suffix is a major number that tracks the release year as ``(year - 2000) + 8``.
Verified on this machine: ``RevisionNumber`` ``34.3.0`` → major 34 → SOLIDWORKS 2026 →
``SldWorks.Application.34``.

This is the one module allowed to name the ProgID; a test enforces that, because a
hardcoded ``SldWorks.Application.N`` scattered through call sites is a version trap.
"""

from __future__ import annotations

BASE_PROGID = "SldWorks.Application"

#: The major used by SOLIDWORKS 2008, the anchor of the year mapping.
_MAJOR_EPOCH = 8
_YEAR_EPOCH = 2000

#: Plausible majors to probe when the running version is not yet known, newest first.
PROBE_MAJORS: tuple[int, ...] = tuple(range(40, 19, -1))


def major_from_revision(revision: str | None) -> int | None:
    """``"34.3.0"`` → ``34``."""
    if not revision:
        return None
    head = str(revision).strip().split(".")[0]
    try:
        return int(head)
    except ValueError:
        return None


def year_from_major(major: int | None) -> int | None:
    """``34`` → ``2026``."""
    if major is None:
        return None
    return _YEAR_EPOCH + (major - _MAJOR_EPOCH)


def major_from_year(year: int | None) -> int | None:
    """``2026`` → ``34``."""
    if year is None:
        return None
    return (year - _YEAR_EPOCH) + _MAJOR_EPOCH


def progid_for_major(major: int | None) -> str:
    """``34`` → ``"SldWorks.Application.34"``; ``None`` → the unsuffixed ProgID."""
    if major is None:
        return BASE_PROGID
    return f"{BASE_PROGID}.{major}"


def progid_for_year(year: int | None) -> str:
    return progid_for_major(major_from_year(year))


def candidate_progids(major: int | None = None) -> list[str]:
    """ProgIDs to try when attaching, most specific first.

    The version-independent ProgID is always included as a fallback so a release whose
    major does not follow the formula is still reachable.
    """
    candidates: list[str] = []
    if major is not None:
        candidates.append(progid_for_major(major))
    candidates.append(BASE_PROGID)
    seen: set[str] = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


def describe_version(revision: str | None) -> dict[str, object]:
    """Version facts for the system-info report (SYS-002)."""
    major = major_from_revision(revision)
    return {
        "revision": revision,
        "major": major,
        "year": year_from_major(major),
        "prog_id": progid_for_major(major),
        "base_prog_id": BASE_PROGID,
    }
