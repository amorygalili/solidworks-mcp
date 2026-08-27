"""Unit normalization — the only place in ``src/`` that converts to API units.

The SOLIDWORKS API is always metres and radians regardless of the document's display
units, so conversion belongs at the request boundary and nowhere else. A test scans the
tree and fails on ``/ 1000.0`` or ``* 0.001`` outside this module (SYS-006).

Three input forms are accepted for every length and angle field:

* a bare number, interpreted in the default unit (mm for length, degrees for angle);
* a string with a unit suffix — ``"50mm"``, ``"2 in"``, ``"1.5m"``, ``"45deg"``;
* an object — ``{"value": 2, "unit": "inch"}``.

The validated value is always stored in metres or radians.
"""

from __future__ import annotations

import math
import re
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, WithJsonSchema

# --- length -----------------------------------------------------------------

LENGTH_TO_METERS: dict[str, float] = {
    "m": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "metre": 1.0,
    "metres": 1.0,
    "cm": 0.01,
    "centimeter": 0.01,
    "centimeters": 0.01,
    "mm": 0.001,
    "millimeter": 0.001,
    "millimeters": 0.001,
    "in": 0.0254,
    "inch": 0.0254,
    "inches": 0.0254,
    '"': 0.0254,
    "ft": 0.3048,
    "foot": 0.3048,
    "feet": 0.3048,
    "'": 0.3048,
}

ANGLE_TO_RADIANS: dict[str, float] = {
    "deg": math.pi / 180.0,
    "degree": math.pi / 180.0,
    "degrees": math.pi / 180.0,
    "°": math.pi / 180.0,
    "rad": 1.0,
    "radian": 1.0,
    "radians": 1.0,
    "rev": 2.0 * math.pi,
    "revolution": 2.0 * math.pi,
    "revolutions": 2.0 * math.pi,
    "turn": 2.0 * math.pi,
}

DEFAULT_LENGTH_UNIT = "mm"
DEFAULT_ANGLE_UNIT = "deg"

_QUANTITY = re.compile(
    r"^\s*(?P<value>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(?P<unit>.*?)\s*$"
)


class UnitError(ValueError):
    """Raised for an unknown unit or a non-finite quantity."""


def _finite(value: float, raw: Any) -> float:
    if not math.isfinite(value):
        raise UnitError(f"non-finite quantity is not a valid dimension: {raw!r}")
    return value


def _split(raw: Any, default_unit: str) -> tuple[float, str]:
    """Reduce any accepted input form to ``(magnitude, unit)``."""
    if isinstance(raw, bool):
        raise UnitError(f"boolean is not a quantity: {raw!r}")
    if isinstance(raw, (int, float)):
        return float(raw), default_unit
    if isinstance(raw, str):
        match = _QUANTITY.match(raw)
        if not match:
            raise UnitError(f"could not parse quantity from {raw!r}")
        unit = match.group("unit") or default_unit
        return float(match.group("value")), unit
    if isinstance(raw, dict):
        if "value" not in raw:
            raise UnitError(f"quantity object requires a 'value' key: {raw!r}")
        unknown = set(raw) - {"value", "unit"}
        if unknown:
            raise UnitError(f"quantity object has unexpected keys {sorted(unknown)}")
        magnitude = raw["value"]
        if isinstance(magnitude, bool) or not isinstance(magnitude, (int, float)):
            raise UnitError(f"quantity 'value' must be a number, got {magnitude!r}")
        return float(magnitude), str(raw.get("unit") or default_unit)
    raise UnitError(f"unsupported quantity form {type(raw).__name__}: {raw!r}")


def _lookup(unit: str, table: dict[str, float], kind: str) -> float:
    key = unit.strip()
    factor = table.get(key) or table.get(key.lower())
    if factor is None:
        raise UnitError(
            f"unknown {kind} unit {unit!r}; supported: {', '.join(sorted(set(table)))}"
        )
    return factor


def to_meters(raw: Any, *, default_unit: str = DEFAULT_LENGTH_UNIT) -> float:
    """Normalize any accepted length form to metres."""
    magnitude, unit = _split(raw, default_unit)
    return _finite(magnitude * _lookup(unit, LENGTH_TO_METERS, "length"), raw)


def to_radians(raw: Any, *, default_unit: str = DEFAULT_ANGLE_UNIT) -> float:
    """Normalize any accepted angle form to radians."""
    magnitude, unit = _split(raw, default_unit)
    return _finite(magnitude * _lookup(unit, ANGLE_TO_RADIANS, "angle"), raw)


def from_meters(meters: float, unit: str = DEFAULT_LENGTH_UNIT) -> float:
    """Convert metres back into a display unit for the response envelope."""
    return meters / _lookup(unit, LENGTH_TO_METERS, "length")


def from_radians(radians: float, unit: str = DEFAULT_ANGLE_UNIT) -> float:
    return radians / _lookup(unit, ANGLE_TO_RADIANS, "angle")


_QUANTITY_JSON_SCHEMA = {
    "anyOf": [
        {"type": "number"},
        {"type": "string", "pattern": r"^\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\s*\S*\s*$"},
        {
            "type": "object",
            "properties": {"value": {"type": "number"}, "unit": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    ]
}


def _length_schema(description: str) -> dict[str, Any]:
    return {**_QUANTITY_JSON_SCHEMA, "description": description}


Length = Annotated[
    float,
    BeforeValidator(to_meters),
    WithJsonSchema(
        _length_schema(
            "Length. A bare number is millimetres; or use '50mm' / '2in' / "
            "{'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
        )
    ),
]
"""A length in any supported unit, normalized to **metres**."""

Angle = Annotated[
    float,
    BeforeValidator(to_radians),
    WithJsonSchema(
        _length_schema(
            "Angle. A bare number is degrees; or use '45deg' / '1.57rad' / "
            "{'value': 45, 'unit': 'degrees'}."
        )
    ),
]
"""An angle in any supported unit, normalized to **radians**."""


def area_to_m2(value: float, unit: str = "mm") -> float:
    """Convert an area expressed in ``unit`` squared into square metres."""
    factor = _lookup(unit, LENGTH_TO_METERS, "length")
    return _finite(float(value) * factor * factor, value)


def area_from_m2(value_m2: float, unit: str = "mm") -> float:
    """Convert square metres into ``unit`` squared, for the response envelope."""
    factor = _lookup(unit, LENGTH_TO_METERS, "length")
    return float(value_m2) / (factor * factor)


def positive_length(description: str) -> Any:
    """A :data:`Length` field constrained to be strictly positive."""
    return Field(gt=0.0, description=description)
