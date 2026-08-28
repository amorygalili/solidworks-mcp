"""Reading a capture's real pixel size out of the file it wrote.

``sw_view_capture`` reports the size it found in the written file rather than the size
that was asked for, because SOLIDWORKS clamps a capture to what the viewport can
produce. Repeating the request back would describe an image that does not exist, so the
header parsing is worth testing on bytes we control.
"""

from __future__ import annotations

import struct

from swmcp.handlers.view import _image_size


def _png(width: int, height: int) -> bytes:
    """A PNG signature and IHDR chunk, which is where the size lives."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x06\x00\x00\x00"
    )


def _bmp(width: int, height: int, *, bottom_up: bool = True) -> bytes:
    """A BMP file header and the start of its info header."""
    return (
        b"BM"
        + struct.pack("<I", 1024)
        + b"\x00\x00\x00\x00"
        + struct.pack("<I", 54)
        + struct.pack("<I", 40)
        + struct.pack("<ii", width, height if bottom_up else -height)
    )


def test_a_png_reports_its_own_size(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(_png(1280, 960))
    assert _image_size(path) == [1280, 960]


def test_a_bmp_reports_its_own_size(tmp_path):
    path = tmp_path / "a.bmp"
    path.write_bytes(_bmp(640, 480))
    assert _image_size(path) == [640, 480]


def test_a_top_down_bmp_reports_a_positive_height(tmp_path):
    """A negative height means the rows are stored top-down, not that it is -480 tall."""
    path = tmp_path / "a.bmp"
    path.write_bytes(_bmp(640, 480, bottom_up=False))
    assert _image_size(path) == [640, 480]


def test_a_file_that_is_neither_returns_nothing_rather_than_guessing(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"this is not an image")
    assert _image_size(path) is None


def test_a_truncated_header_returns_nothing(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4)
    assert _image_size(path) is None


def test_a_missing_file_returns_nothing(tmp_path):
    assert _image_size(tmp_path / "never_written.png") is None
