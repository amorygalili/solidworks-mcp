r"""SAFE-004: path canonicalization and root policy, enforced before any COM call.

Putting the guard in front of the COM boundary is what makes it testable on a machine
with no CAD installed at all — the negative security tests need no SOLIDWORKS.

Two classes of path, deliberately different in strictness:

``document_input``
    A document to look up or open. Normalized but not root-checked, because a document
    the user opened by hand outside the roots is still legitimately addressable.

``output``
    A file the server is about to create or overwrite. Must resolve under an allowed
    root. With ``SWMCP_ALLOWED_ROOTS`` unset there are no roots, so this **fails closed**.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

from swmcp.errors import SwMcpError, validation_error

PathClass = Literal["document_input", "output"]

_DRIVE_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_ENV_VAR = "SWMCP_ALLOWED_ROOTS"


def normalize_cad_path(raw: str | os.PathLike[str]) -> str:
    r"""Canonicalize a Windows path without mangling UNC roots.

    ``os.path.abspath`` rewrites ``\\server\share`` into ``C:\server\share`` because
    it joins against the cwd. UNC and drive-absolute paths therefore go through
    ``normpath`` only; genuinely relative paths still need the cwd join.
    """
    text = os.fspath(raw).strip()
    if not text:
        raise SwMcpError(
            validation_error("PATH_REQUIRED", "A path is required but an empty string was given.")
        )
    text = text.replace("/", "\\")
    if text.startswith("\\\\") or _DRIVE_ABSOLUTE.match(text):
        return os.path.normpath(text)
    return os.path.abspath(text)


def _real(path: str) -> str:
    """Resolve junctions and symlinks; a missing path resolves to itself."""
    try:
        return os.path.realpath(path)
    except OSError:  # pragma: no cover - realpath is total on Windows in practice
        return path


def path_under_root(candidate: str, root: str) -> bool:
    r"""Containment test that is not fooled by a shared name prefix.

    Appending the separator is what stops ``C:\cad-other`` counting as inside ``C:\cad``.
    """
    left = candidate.casefold().rstrip("\\")
    right = root.casefold().rstrip("\\")
    return left == right or left.startswith(right + "\\")


def prepare_document_path(raw: str | os.PathLike[str]) -> str:
    """Normalize a path that names an existing or already-open document."""
    return normalize_cad_path(raw)


def assert_output_path(
    raw: str | os.PathLike[str],
    roots: tuple[Path, ...],
    *,
    field: str = "output_path",
) -> str:
    """Normalize a path the server is about to write, and require it under a root."""
    normalized = normalize_cad_path(raw)

    if not roots:
        raise SwMcpError(
            validation_error(
                "PATH_NOT_ALLOWED",
                f"No output roots are configured, so writing {normalized!r} is refused.",
                context={"field": field, "path": normalized, "allowed_roots": []},
                remediation=[
                    f"Set {_ENV_VAR} to one or more semicolon-separated directories, "
                    rf"for example {_ENV_VAR}=C:\cad\work;D:\exports",
                    "Paths are matched after canonicalization, so '..' segments cannot escape.",
                ],
            )
        )

    normalized_roots = [normalize_cad_path(root) for root in roots]
    lexically_ok = any(path_under_root(normalized, root) for root in normalized_roots)
    # Check the real path too, so a junction inside an allowed root cannot redirect a
    # write outside it.
    real_candidate = _real(normalized)
    really_ok = any(path_under_root(real_candidate, _real(root)) for root in normalized_roots)

    if not (lexically_ok and really_ok):
        detail = (
            "the path resolves outside the allowed roots through a link or junction"
            if lexically_ok
            else "the path is not under any allowed root"
        )
        raise SwMcpError(
            validation_error(
                "PATH_NOT_ALLOWED",
                f"Refusing to write {normalized!r}: {detail}.",
                context={
                    "field": field,
                    "path": normalized,
                    "resolved_path": real_candidate,
                    "allowed_roots": normalized_roots,
                },
                remediation=[
                    "Choose an output path under one of the allowed roots listed in context.",
                    f"Or widen {_ENV_VAR} if this location is genuinely intended.",
                ],
            )
        )
    return normalized


def classify_document_path(raw: str | None) -> tuple[str | None, bool]:
    """Return ``(normalized_path, is_local_file)`` for a document path from SOLIDWORKS.

    An unsaved document reports an empty path, and a platform-managed document may
    report a URI rather than a file. Both mean "there is nothing here to snapshot",
    which the checkpoint layer must report rather than silently skip.
    """
    if not raw or not raw.strip():
        return None, False
    text = raw.strip()
    if "://" in text:
        return text, False
    try:
        normalized = normalize_cad_path(text)
    except SwMcpError:
        return text, False
    is_local = bool(normalized.startswith("\\\\") or _DRIVE_ABSOLUTE.match(normalized))
    return normalized, is_local
