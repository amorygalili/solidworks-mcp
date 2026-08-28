"""Reference-geometry logic that needs no SOLIDWORKS: transforms and schema guards.

The live suite proves these tools build the right geometry. What it cannot easily reach
is the degraded path — a coordinate system whose transform SOLIDWORKS declines to hand
back — and the argument combinations the schema is supposed to reject before any COM
call happens at all.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.handlers.feature import _read_csys_transform
from swmcp.schemas.feature import DatumCsysCreateArgs, DatumPointCreateArgs

#: Nine row-major rotation terms, three translation terms in metres, scale, three unused.
IDENTITY_AT_60_40 = [
    -1.0, 0.0, 0.0,
    0.0, 1.0, 0.0,
    0.0, 0.0, -1.0,
    0.060, 0.040, 0.0,
    1.0,
    0.0, 0.0, 0.0,
]


class FakeTransform:
    def __init__(self, array):
        self.ArrayData = array


class FakeExtension:
    """Answers ``GetCoordinateSystemTransformByName`` for one known name."""

    def __init__(self, known: dict[str, object]):
        self._known = known
        self.asked: list[str] = []

    def GetCoordinateSystemTransformByName(self, name):  # noqa: N802
        self.asked.append(name)
        return self._known.get(name)


class FakeDoc:
    def __init__(self, extension):
        self.Extension = extension


def _doc(known: dict[str, object]) -> FakeDoc:
    return FakeDoc(FakeExtension(known))


# --- transform decoding -------------------------------------------------------


def test_the_transform_is_decoded_into_rotation_translation_and_scale():
    doc = _doc({"Csys1": FakeTransform(IDENTITY_AT_60_40)})

    transform = _read_csys_transform(doc, "Csys1")

    assert transform is not None
    assert transform.rotation == [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]
    assert transform.translation_mm == pytest.approx([60.0, 40.0, 0.0])
    assert transform.scale == 1.0


def test_the_translation_is_converted_out_of_metres():
    """SOLIDWORKS answers in metres; every length this server publishes is millimetres."""
    doc = _doc({"Csys1": FakeTransform(IDENTITY_AT_60_40)})

    transform = _read_csys_transform(doc, "Csys1")

    assert transform.translation_mm[0] == pytest.approx(60.0), "0.060 m is 60 mm, not 0.06"


def test_a_short_array_reports_no_transform_rather_than_a_partial_one():
    """A truncated array would still index cleanly into rotation and lie about it."""
    doc = _doc({"Csys1": FakeTransform([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])})

    assert _read_csys_transform(doc, "Csys1") is None


def test_a_missing_transform_is_reported_as_none():
    assert _read_csys_transform(_doc({}), "Csys1") is None


def test_an_empty_name_never_reaches_solidworks():
    extension = FakeExtension({})
    assert _read_csys_transform(FakeDoc(extension), "") is None
    assert extension.asked == [], "an unnamed system must not be looked up"


# --- schema guards ------------------------------------------------------------


def _ref() -> dict:
    return {"kind": "edge", "document": {"path": r"C:\cad\part.SLDPRT"}}


def test_a_coordinate_system_needs_at_least_one_reference():
    """With nothing selected SOLIDWORKS builds a system at the model origin."""
    with pytest.raises(ValidationError, match="at least one of origin"):
        DatumCsysCreateArgs()


def test_a_coordinate_system_accepts_any_single_reference():
    for field in ("origin", "x_axis", "y_axis", "z_axis"):
        assert DatumCsysCreateArgs(**{field: _ref()})


@pytest.mark.parametrize(
    ("mode", "missing"),
    [("distance", "distance"), ("percentage", "percent")],
)
def test_a_placement_mode_without_its_value_is_rejected(mode, missing):
    """Otherwise the missing value defaults to zero and the point lands at the start."""
    with pytest.raises(ValidationError, match=missing):
        DatumPointCreateArgs(method="along_curve", along_curve=mode, refs=[_ref()])


def test_evenly_distributed_needs_no_placement_value():
    args = DatumPointCreateArgs(method="along_curve", along_curve="evenly", count=4, refs=[_ref()])
    assert args.count == 4


def test_a_point_method_other_than_along_curve_ignores_the_placement_check():
    assert DatumPointCreateArgs(method="arc_center", refs=[_ref()])


def test_a_point_needs_at_least_one_reference():
    with pytest.raises(ValidationError):
        DatumPointCreateArgs(method="face_center", refs=[])
