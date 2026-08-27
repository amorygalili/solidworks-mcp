"""SAFE-004.

These run with no SOLIDWORKS installed, because the guard sits in front of the COM
boundary rather than behind it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from swmcp.config import parse_roots
from swmcp.errors import SwMcpError
from swmcp.safety.paths import (
    assert_output_path,
    classify_document_path,
    normalize_cad_path,
    path_under_root,
    prepare_document_path,
)

ROOTS = (Path(r"C:\cad\work"), Path(r"D:\exports"))


def test_unc_roots_survive_normalization():
    r"""``os.path.abspath`` rewrites ``\\server\share`` into ``C:\server\share``.

    That mangling is the bug this guard exists to prevent.
    """
    assert normalize_cad_path(r"\\server\share\a\..\b") == r"\\server\share\b"
    assert normalize_cad_path(r"\\wsl$\Ubuntu\home\a") == r"\\wsl$\Ubuntu\home\a"


def test_forward_slashes_and_traversal_are_canonicalized():
    assert normalize_cad_path("C:/cad/sub/../x.SLDPRT") == r"C:\cad\x.SLDPRT"
    assert normalize_cad_path(r"C:\cad\..\..\windows\system32\x") == r"C:\windows\system32\x"


def test_relative_paths_resolve_against_cwd():
    assert normalize_cad_path("bracket.SLDPRT").endswith("\\bracket.SLDPRT")
    assert Path(normalize_cad_path("bracket.SLDPRT")).is_absolute()


def test_empty_path_is_rejected():
    for raw in ("", "   "):
        with pytest.raises(SwMcpError) as caught:
            normalize_cad_path(raw)
        assert caught.value.envelope.code == "PATH_REQUIRED"


def test_prefix_confusion_is_not_containment():
    assert path_under_root(r"C:\cad\a.sldprt", r"C:\cad")
    assert path_under_root(r"C:\cad", r"C:\cad")
    assert not path_under_root(r"C:\cad-other\a.sldprt", r"C:\cad")
    assert not path_under_root(r"C:\cadastre", r"C:\cad")


def test_containment_is_case_insensitive():
    assert path_under_root(r"c:\CAD\Work\A.SLDPRT", r"C:\cad\work")


def test_output_paths_fail_closed_when_no_roots_configured():
    with pytest.raises(SwMcpError) as caught:
        assert_output_path(r"C:\anywhere\out.step", ())
    envelope = caught.value.envelope
    assert envelope.code == "PATH_NOT_ALLOWED"
    assert any("SWMCP_ALLOWED_ROOTS" in step for step in envelope.remediation), (
        "the error must name the variable that would fix it"
    )


def test_output_paths_inside_a_root_are_accepted():
    assert assert_output_path(r"C:\cad\work\sub\part.step", ROOTS) == r"C:\cad\work\sub\part.step"
    assert assert_output_path("D:/exports/a.pdf", ROOTS) == r"D:\exports\a.pdf"


@pytest.mark.parametrize(
    "candidate",
    [r"C:\elsewhere\a.step", r"C:\cad\work\..\..\windows\a.step", r"C:\cad-other\a.step"],
)
def test_output_paths_outside_the_roots_are_refused(candidate):
    with pytest.raises(SwMcpError) as caught:
        assert_output_path(candidate, ROOTS)
    envelope = caught.value.envelope
    assert envelope.code == "PATH_NOT_ALLOWED"
    assert envelope.context["allowed_roots"] == [r"C:\cad\work", r"D:\exports"]


def test_document_inputs_are_normalized_but_not_root_checked():
    """A document the user opened by hand outside the roots is still addressable."""
    assert prepare_document_path("C:/elsewhere/legacy.SLDPRT") == r"C:\elsewhere\legacy.SLDPRT"


def test_junction_escape_is_caught(tmp_path):
    """A link inside an allowed root must not redirect a write outside it."""
    root = tmp_path / "allowed"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("creating a symlink requires privilege on this machine")

    with pytest.raises(SwMcpError) as caught:
        assert_output_path(str(link / "sneaky.step"), (root,))
    assert caught.value.envelope.code == "PATH_NOT_ALLOWED"
    assert "link or junction" in caught.value.envelope.message


def test_roots_are_semicolon_separated_because_of_drive_letters():
    assert parse_roots(r"C:\cad;D:\exports") == (Path(r"C:\cad"), Path(r"D:\exports"))
    assert parse_roots(r" C:\cad ; ; D:\exports ") == (Path(r"C:\cad"), Path(r"D:\exports"))
    assert parse_roots("") == ()
    assert parse_roots(None) == ()


@pytest.mark.parametrize(
    ("raw", "expected_local"),
    [
        ("", False),
        (None, False),
        ("   ", False),
        (r"C:\cad\bracket.SLDPRT", True),
        (r"\\server\share\bracket.SLDPRT", True),
        ("3dexperience://doc/1234", False),
    ],
)
def test_document_paths_are_classified_for_checkpointability(raw, expected_local):
    _, is_local = classify_document_path(raw)
    assert is_local is expected_local
