"""Format verification, checked on bytes rather than on SOLIDWORKS.

``SaveAs`` reports success through out-parameters that frequently say nothing useful,
so ``sw_export`` opens the file it wrote and checks it against the format's own
signature. Those checks are pure functions of the bytes, so the interesting cases — a
truncated mesh, a file that is empty, a STEP file that is really something else — can
be built here instead of hoping SOLIDWORKS produces one.
"""

from __future__ import annotations

import struct

import pytest

from swmcp.handlers.exchange import _verify
from swmcp.schemas.exchange import BY_EXTENSION, format_for_extension


def _binary_stl(triangles: int, *, truncate: int = 0) -> bytes:
    """A binary STL: 80-byte header, a triangle count, then 50 bytes per triangle."""
    body = b"\x00" * (50 * triangles)
    return (b"swmcp test header".ljust(80, b"\x00") + struct.pack("<I", triangles) + body)[
        : None if not truncate else -truncate
    ]


def _write(tmp_path, name: str, data: bytes):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_a_well_formed_binary_stl_verifies(tmp_path):
    ok, detail = _verify("stl", _write(tmp_path, "a.stl", _binary_stl(12)))
    assert ok, detail
    assert "12 triangles" in detail


def test_a_truncated_binary_stl_is_caught(tmp_path):
    """The check no other test would catch: the header promises more than is there."""
    ok, detail = _verify("stl", _write(tmp_path, "a.stl", _binary_stl(100, truncate=500)))

    assert not ok
    assert "100 triangles" in detail
    assert "but the file is" in detail


def test_an_ascii_stl_verifies(tmp_path):
    text = b"solid part\n facet normal 0 0 1\n  outer loop\n  endloop\n endfacet\nendsolid\n"
    ok, detail = _verify("stl", _write(tmp_path, "a.stl", text))
    assert ok, detail
    assert "ASCII" in detail


def test_something_that_is_not_an_stl_at_all_is_rejected(tmp_path):
    ok, _detail = _verify("stl", _write(tmp_path, "a.stl", b"just some text, honestly"))
    assert not ok


def test_an_empty_file_never_verifies(tmp_path):
    for fmt in ("step", "stl", "3mf", "pdf", "iges"):
        ok, detail = _verify(fmt, _write(tmp_path, f"a.{fmt}", b""))
        assert not ok
        assert detail == "the file is empty"


def test_a_step_file_is_recognised_by_its_part_21_header(tmp_path):
    good = b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(());\nENDSEC;\n"
    ok, _detail = _verify("step", _write(tmp_path, "a.step", good))
    assert ok

    ok, detail = _verify("step", _write(tmp_path, "b.step", b"solid something\n"))
    assert not ok
    assert "ISO-10303-21" in detail


def test_an_iges_file_is_recognised_by_its_section_letter(tmp_path):
    line = b" " * 72 + b"S      1\n"
    ok, _detail = _verify("iges", _write(tmp_path, "a.igs", line))
    assert ok

    ok, _detail = _verify("iges", _write(tmp_path, "b.igs", b"not iges at all\n"))
    assert not ok


def test_a_3mf_is_recognised_as_a_zip(tmp_path):
    ok, _detail = _verify("3mf", _write(tmp_path, "a.3mf", b"PK\x03\x04rest of a zip"))
    assert ok

    ok, _detail = _verify("3mf", _write(tmp_path, "b.3mf", b"<model/>"))
    assert not ok


def test_a_pdf_is_recognised_by_its_header(tmp_path):
    ok, _detail = _verify("pdf", _write(tmp_path, "a.pdf", b"%PDF-1.7\n%..\n"))
    assert ok


def test_a_parasolid_text_file_is_recognised(tmp_path):
    header = b"**ABCDEFGHIJKLMNOPQRSTUVWXYZ**\n**PARASOLID !\n"
    ok, _detail = _verify("parasolid_text", _write(tmp_path, "a.x_t", header))
    assert ok


def test_an_unchecked_format_says_so_rather_than_claiming_success(tmp_path):
    """A format with no signature check must report that, not a bare False."""
    ok, detail = _verify("parasolid_binary", _write(tmp_path, "a.x_b", b"anything at all"))

    assert not ok
    assert "no signature check is implemented" in detail
    assert "parasolid_binary" in detail


@pytest.mark.parametrize(("path", "expected"), sorted(BY_EXTENSION.items()))
def test_every_supported_extension_maps_to_a_format(path, expected):
    assert format_for_extension(f"C:/cad/part{path}") == expected
    assert format_for_extension(f"C:/cad/PART{path.upper()}") == expected, "case must not matter"


def test_an_unknown_extension_maps_to_nothing():
    assert format_for_extension("C:/cad/part.xyz") is None
    assert format_for_extension("C:/cad/part") is None
