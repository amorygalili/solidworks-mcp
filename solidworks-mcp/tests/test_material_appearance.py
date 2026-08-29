"""Mass, appearance, and visibility decoding — the parts that need no SOLIDWORKS.

Gate 1 in `CLAUDE.md`. Each test here corresponds to a mistake that was actually made
and cost a live run to find, so they are regression cover rather than decoration.
"""

from __future__ import annotations

import pytest

from swmcp.com import swconst
from swmcp.modeling import body_mass_properties, document_mass_properties
from swmcp.schemas.material import DEFAULT_DATABASE, MaterialSetArgs
from swmcp.schemas.view import APPEARANCE_FIELDS, AppearanceSetArgs, VisibilitySetArgs

STEEL_DENSITY = 7800.0
VOLUME_M3 = 2.4e-5


class FakeExtension:
    """``GetMassProperties(Accuracy, out Status)`` returning thirteen doubles."""

    def __init__(self, values):
        self._values = values
        self.calls: list[tuple] = []

    def GetMassProperties(self, accuracy, status):  # noqa: N802
        self.calls.append((accuracy, status))
        return self._values


class FakeDoc:
    def __init__(self, extension):
        self.Extension = extension


def _thirteen(volume: float, mass: float) -> list[float]:
    return [0.02, 0.015, 0.01, volume, 0.0052, mass, 0, 0, 0, 0, 0, 0, 2]


# --- the mass bug -------------------------------------------------------------


def test_document_mass_properties_derives_density_from_mass_over_volume():
    doc = FakeDoc(FakeExtension(_thirteen(VOLUME_M3, VOLUME_M3 * STEEL_DENSITY)))

    reported = document_mass_properties(doc)

    assert reported["volume_m3"] == pytest.approx(VOLUME_M3)
    assert reported["mass_kg"] == pytest.approx(0.1872)
    assert reported["density_kg_m3"] == pytest.approx(STEEL_DENSITY)


def test_a_short_array_is_reported_as_unavailable_not_as_zero():
    assert document_mass_properties(FakeDoc(FakeExtension([1.0, 2.0, 3.0]))) == {}


def test_density_of_zero_volume_is_none_rather_than_a_division_error():
    doc = FakeDoc(FakeExtension(_thirteen(0.0, 0.0)))
    assert document_mass_properties(doc)["density_kg_m3"] is None


class FakeBody:
    """``IBody2::GetMassProperties(Density)`` — index 5 is volume times the argument.

    ``GetType`` is part of the contract too: the reader picks its array layout from the
    body type, because a sheet body fills the same slots with different quantities.
    """

    def __init__(self, volume: float, body_type: int = 0):
        self._volume = volume
        self._type = body_type
        self.densities: list[float] = []

    def GetType(self):  # noqa: N802
        return self._type

    def GetMassProperties(self, density):  # noqa: N802
        self.densities.append(density)
        return [0.0, 0.0, 0.0, self._volume, 0.005, self._volume * density, 0, 0, 0, 0, 0, 0]


class FakeSheetBody:
    """A sheet body: slot 3 is its area and slot 4 its perimeter, not volume and area.

    The numbers are the 40 x 30 mm planar surface that exposed the defect — 1200 mm² of
    area and a 140 mm perimeter, which the solid layout reported as 1 200 000 mm³ of
    material and 140 000 mm² of area.
    """

    AREA_M2 = 0.0012
    PERIMETER_M = 0.14

    def GetType(self):  # noqa: N802
        return 1  # swSheetBody

    def GetMassProperties(self, density):  # noqa: N802
        _ = density
        return [0.02, 0.015, 0.0, self.AREA_M2, self.PERIMETER_M, self.AREA_M2, 0, 0, 0, 0, 0, 0]


def test_body_mass_uses_the_density_it_is_given():
    """The heart of the bug: this call computes volume x whatever it is handed.

    Passing 0.0, as the shipped code did, made a steel part and an aluminium one report
    the same mass. Callers now pass the document's real density.
    """
    body = FakeBody(VOLUME_M3)

    assert body_mass_properties(body, STEEL_DENSITY)["mass_kg"] == pytest.approx(0.1872)
    assert body_mass_properties(body, 2700.0)["mass_kg"] == pytest.approx(0.0648)
    assert body.densities == [STEEL_DENSITY, 2700.0]


def test_body_mass_reports_the_density_it_used():
    """So a reader can tell whether the figure came from a material or a default."""
    reported = body_mass_properties(FakeBody(VOLUME_M3), STEEL_DENSITY)
    assert reported["density_kg_m3"] == STEEL_DENSITY


def test_the_old_default_is_visibly_wrong():
    """Guards the regression directly: density 1.0 makes mass equal to volume."""
    reported = body_mass_properties(FakeBody(VOLUME_M3), 1.0)
    assert reported["mass_kg"] == pytest.approx(reported["volume_m3"])


# --- a sheet body fills the same slots with different quantities ----------------


def test_a_sheet_body_reports_no_volume_and_no_mass():
    """The defect: a 40 x 30 surface was reported as 1 200 000 mm³ of material."""
    reported = body_mass_properties(FakeSheetBody(), STEEL_DENSITY)

    assert reported["body_type"] == "sheetbody"
    assert reported["volume_m3"] is None, "a sheet body encloses no volume"
    assert reported["mass_kg"] is None, "a body with no volume has no mass"


def test_a_sheet_bodys_area_comes_from_the_volume_slot():
    """Slot 3 is the area for a sheet body, and slot 4 the perimeter."""
    reported = body_mass_properties(FakeSheetBody())

    assert reported["surface_area_m2"] == pytest.approx(FakeSheetBody.AREA_M2)
    assert reported["perimeter_m"] == pytest.approx(FakeSheetBody.PERIMETER_M)


def test_a_sheet_body_says_why_its_layout_differs():
    """A missing volume has to read as "not applicable", not as a failed measurement."""
    note = body_mass_properties(FakeSheetBody())["measurement_note"]

    assert "no volume" in note.lower()


def test_an_unverified_body_type_reports_no_figures():
    """Only the solid and sheet layouts were measured; the rest must not be guessed."""
    reported = body_mass_properties(FakeBody(VOLUME_M3, body_type=2))  # swWireBody

    assert reported["body_type"] == "wirebody"
    assert reported["volume_m3"] is None
    assert reported["surface_area_m2"] is None
    assert reported["raw_mass_properties"][3] == pytest.approx(VOLUME_M3)


def test_a_solid_body_is_unaffected():
    """The fix must not move the numbers for the case that was always right."""
    reported = body_mass_properties(FakeBody(VOLUME_M3), STEEL_DENSITY)

    assert reported["body_type"] == "solidbody"
    assert reported["volume_m3"] == pytest.approx(VOLUME_M3)
    assert reported["surface_area_m2"] == pytest.approx(0.005)
    assert reported["mass_kg"] == pytest.approx(VOLUME_M3 * STEEL_DENSITY)


# --- visibility decoding ------------------------------------------------------


def test_feature_visibility_is_an_enum_not_a_boolean():
    """``bool(1)`` and ``bool(2)`` are both True, which is why hiding read back wrong.

    ``IFeature::Visible`` is swVisibilityState_e; ``IBody2::Visible`` really is a bool.
    """
    shown = swconst.value("swVisibilityState_e", "swVisibilityStateShown")
    hidden = swconst.value("swVisibilityState_e", "swVisibilityStateHide")

    assert shown == 2
    assert hidden == 1
    assert bool(hidden) is True, "the trap: a hidden feature is truthy"
    assert (hidden == shown) is False, "comparing against the enum is what works"


# --- appearance ----------------------------------------------------------------


def test_the_appearance_fields_are_the_nine_solidworks_expects():
    assert len(APPEARANCE_FIELDS) == 9
    assert APPEARANCE_FIELDS[:3] == ("red", "green", "blue")
    assert APPEARANCE_FIELDS[7] == "transparency"


def test_appearance_values_are_bounded_to_zero_and_one():
    for field in ("ambient", "diffuse", "specular", "shininess", "transparency", "emission"):
        with pytest.raises(ValueError):
            AppearanceSetArgs(**{field: 1.5})
        with pytest.raises(ValueError):
            AppearanceSetArgs(**{field: -0.1})


def test_a_colour_needs_exactly_three_channels():
    with pytest.raises(ValueError):
        AppearanceSetArgs(color=[1.0, 0.0])
    with pytest.raises(ValueError):
        AppearanceSetArgs(color=[1.0, 0.0, 0.0, 0.0])
    assert AppearanceSetArgs(color=[1.0, 0.0, 0.0]).color == [1.0, 0.0, 0.0]


def test_appearance_defaults_to_the_document():
    assert AppearanceSetArgs().target == "document"


# --- material schema ------------------------------------------------------------


def test_the_default_database_is_the_stock_library():
    assert MaterialSetArgs(name="6061 Alloy").database == DEFAULT_DATABASE


def test_an_empty_material_name_is_allowed_because_it_clears():
    assert MaterialSetArgs(name="").name == ""


def test_visibility_needs_a_name():
    with pytest.raises(ValueError):
        VisibilitySetArgs(target="body", name="", visible=False)


# --- measuring a mixture of solids and surfaces ---------------------------------


def test_measuring_surfaces_reports_no_volume_and_counts_them():
    """A volume of zero must be distinguishable from a measurement that failed."""
    from swmcp.handlers.feature import _aggregate_bodies

    totals = _aggregate_bodies([FakeBody(VOLUME_M3), FakeSheetBody()], STEEL_DENSITY)

    assert totals["volume_m3"] == pytest.approx(VOLUME_M3), "the sheet adds no volume"
    assert totals["mass_kg"] == pytest.approx(VOLUME_M3 * STEEL_DENSITY)
    assert totals["volumeless_body_count"] == 1


def test_measuring_only_solids_flags_nothing():
    from swmcp.handlers.feature import _aggregate_bodies

    totals = _aggregate_bodies([FakeBody(VOLUME_M3), FakeBody(VOLUME_M3)], STEEL_DENSITY)

    assert totals["volumeless_body_count"] == 0
    assert totals["volume_m3"] == pytest.approx(2 * VOLUME_M3)
