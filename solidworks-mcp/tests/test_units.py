"""SYS-006: one normalization boundary, mm/cm/m/inch/foot, metres on the inside."""

from __future__ import annotations

import math

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from swmcp.units import Angle, Length, UnitError, from_meters, to_meters, to_radians


class Sample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    depth: Length
    sweep: Angle = 0.0


@pytest.mark.parametrize(
    ("raw", "meters"),
    [
        (50, 0.050),
        (50.0, 0.050),
        ("50mm", 0.050),
        ("50 mm", 0.050),
        ("5cm", 0.050),
        ("0.05m", 0.050),
        ("2in", 0.0508),
        ('2"', 0.0508),
        ("2 inches", 0.0508),
        ("1ft", 0.3048),
        ("1'", 0.3048),
        ({"value": 2, "unit": "inch"}, 0.0508),
        ({"value": 50}, 0.050),
        ("1e2mm", 0.1),
        (-25, -0.025),
    ],
)
def test_every_supported_length_form_reaches_meters(raw, meters):
    assert to_meters(raw) == pytest.approx(meters)
    assert Sample(depth=raw).depth == pytest.approx(meters)


@pytest.mark.parametrize(
    ("raw", "radians"),
    [
        (90, math.pi / 2),
        ("90deg", math.pi / 2),
        ("90 degrees", math.pi / 2),
        ("1.5707963267948966rad", math.pi / 2),
        ({"value": 0.25, "unit": "turn"}, math.pi / 2),
    ],
)
def test_every_supported_angle_form_reaches_radians(raw, radians):
    assert to_radians(raw) == pytest.approx(radians)
    assert Sample(depth=1, sweep=raw).sweep == pytest.approx(radians)


def test_bare_numbers_use_the_documented_defaults():
    assert to_meters(1) == pytest.approx(0.001), "a bare length number is millimetres"
    assert to_radians(180) == pytest.approx(math.pi), "a bare angle number is degrees"


@pytest.mark.parametrize("raw", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_quantities_are_rejected(raw):
    with pytest.raises(UnitError):
        to_meters(raw)
    with pytest.raises(ValidationError):
        Sample(depth=raw)


@pytest.mark.parametrize("raw", ["50 furlongs", "furlongs", "", {"unit": "mm"}, True, None, [1]])
def test_unparseable_quantities_are_rejected(raw):
    with pytest.raises(UnitError):
        to_meters(raw)


def test_unknown_unit_error_lists_what_is_supported():
    with pytest.raises(UnitError) as caught:
        to_meters("50 furlongs")
    message = str(caught.value)
    for unit in ("mm", "cm", "in", "ft"):
        assert unit in message


def test_quantity_object_rejects_stray_keys():
    with pytest.raises(UnitError):
        to_meters({"value": 1, "unit": "mm", "tolerance": 0.1})


def test_round_trip_back_to_display_units():
    for unit, value in (("mm", 50.0), ("inch", 2.0), ("ft", 1.0), ("cm", 5.0)):
        assert from_meters(to_meters({"value": value, "unit": unit}), unit) == pytest.approx(value)


def test_json_schema_advertises_all_three_input_forms():
    schema = Sample.model_json_schema()["properties"]["depth"]
    kinds = {branch.get("type") for branch in schema["anyOf"]}
    assert kinds == {"number", "string", "object"}
    assert "millimetres" in schema["description"]
