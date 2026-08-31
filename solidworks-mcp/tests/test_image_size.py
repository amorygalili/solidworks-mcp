"""Reading a capture's real pixel size out of the file it wrote.

``sw_view_capture`` reports the size it found in the written file rather than the size
that was asked for, because SOLIDWORKS clamps a capture to what the viewport can
produce. Repeating the request back would describe an image that does not exist, so the
header parsing is worth testing on bytes we control.
"""

from __future__ import annotations

import struct

from PIL import Image

from swmcp.handlers.view import _image_size, _write_png


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


# --- rendering a PNG at the size that was asked for ---------------------------


class _FakeDoc:
    """A document whose SaveBMP writes a real bitmap, so Pillow has something to read."""

    def __init__(self, *, bmp_works: bool = True, saveas_size: tuple[int, int] = (1204, 771)):
        self._bmp_works = bmp_works
        self._saveas_size = saveas_size
        self.bmp_calls: list[tuple[str, int, int]] = []
        self.saveas_calls = 0
        self.Extension = self

    def SaveBMP(self, path, width, height):  # noqa: N802 - the COM spelling
        self.bmp_calls.append((path, width, height))
        if not self._bmp_works:
            return False
        Image.new("RGB", (width, height), (30, 60, 90)).save(path, format="BMP")
        return True

    def SaveAs(self, path, *_rest):  # noqa: N802 - the COM spelling
        self.saveas_calls += 1
        Image.new("RGB", self._saveas_size, (10, 10, 10)).save(path, format="PNG")
        return True


def test_a_png_is_rendered_at_the_size_requested(tmp_path):
    """Not resampled: SaveBMP renders at that resolution and the bitmap is re-encoded."""
    doc = _FakeDoc()
    target = tmp_path / "shot.png"

    method, details = _write_png(doc, target, 1600, 1200)

    assert method == "SaveBMP+PIL"
    assert doc.bmp_calls == [(str(target.with_name("shot__swmcp_capture.bmp")), 1600, 1200)]
    assert doc.saveas_calls == 0
    assert _image_size(target) == [1600, 1200]
    assert details["rendered_via"]


def test_the_intermediate_bitmap_does_not_survive(tmp_path):
    """It lands beside the target, inside the caller's output root, so it must be swept."""
    doc = _FakeDoc()
    target = tmp_path / "shot.png"

    _write_png(doc, target, 800, 600)

    assert target.is_file()
    assert list(tmp_path.iterdir()) == [target]


def test_a_failed_bitmap_still_produces_an_image(tmp_path):
    """A capture at the wrong size beats no capture, and the reason is reported."""
    doc = _FakeDoc(bmp_works=False)
    target = tmp_path / "shot.png"

    method, details = _write_png(doc, target, 1600, 1200)

    assert method == "Extension.SaveAs"
    assert doc.saveas_calls == 1
    assert details["fallback_reason"]
    assert _image_size(target) == [1204, 771]
    assert list(tmp_path.iterdir()) == [target]


def test_the_fallback_survives_an_exception_from_the_bitmap_path(tmp_path):
    class _Exploding(_FakeDoc):
        def SaveBMP(self, path, width, height):  # noqa: N802
            raise RuntimeError("COM said no")

    doc = _Exploding()
    target = tmp_path / "shot.png"
    method, details = _write_png(doc, target, 640, 480)

    assert method == "Extension.SaveAs"
    assert "COM said no" in details["fallback_reason"]
    assert target.is_file()
