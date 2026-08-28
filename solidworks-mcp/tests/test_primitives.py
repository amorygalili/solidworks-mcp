"""Primitive profiles, checked without SOLIDWORKS.

``_primitive_profile`` is a pure function from dimensions to sketch entities, so the
trap it fell into is catchable here: its inputs are already normalised to metres, while
a bare number inside a sketch entity means *millimetres*. Passing one straight through
built every primitive a thousand times too small — and still produced a valid solid, so
only a volume comparison would ever have noticed.

The check that matters is the round trip: the profile is fed through the real
``SketchAddGeometryArgs`` model, exactly as the handler does, and the metres that come
out the far side must be the metres that went in.
"""

from __future__ import annotations

import math

import pytest

from swmcp.handlers.solid import _primitive_profile
from swmcp.modeling import volume_to_display
from swmcp.schemas.sketch import SketchAddGeometryArgs
from swmcp.schemas.solid import PRIMITIVE_REQUIREMENTS, PrimitiveArgs

#: Dimensions in the input form a caller uses: bare numbers, meaning millimetres.
CASES = {
    "box": {"width": 40, "depth": 30, "height": 20},
    "cylinder": {"radius": 15, "height": 50},
    "sphere": {"radius": 20},
    "cone": {"radius": 18, "height": 40},
    "frustum": {"radius": 20, "top_radius": 10, "height": 30},
    "torus": {"radius": 30, "tube_radius": 8},
    "wedge": {"width": 40, "depth": 30, "height": 25},
    "prism": {"radius": 20, "sides": 6, "height": 15},
}

EXPECTED_MM3 = {
    "box": 40 * 30 * 20,
    "cylinder": math.pi * 15**2 * 50,
    "sphere": 4 / 3 * math.pi * 20**3,
    "cone": math.pi * 18**2 * 40 / 3,
    "frustum": math.pi * 30 / 3 * (20**2 + 20 * 10 + 10**2),
    "torus": 2 * math.pi**2 * 30 * 8**2,
    "wedge": 0.5 * 40 * 30 * 25,
    "prism": 0.5 * 6 * 20**2 * math.sin(2 * math.pi / 6) * 15,
}


def _args(kind: str, **overrides) -> PrimitiveArgs:
    return PrimitiveArgs(kind=kind, **{**CASES[kind], **overrides})


def _coordinates(entities: list[dict]) -> list[float]:
    """Every length in a profile, in metres, after the sketch model has parsed it."""
    parsed = SketchAddGeometryArgs(entities=entities)
    found: list[float] = []
    for entity in parsed.entities:
        for field in ("start", "end", "center", "corner", "opposite", "at", "through"):
            point = getattr(entity, field, None)
            if isinstance(point, list):
                found.extend(float(value) for value in point)
        for field in ("radius", "circumradius", "width"):
            value = getattr(entity, field, None)
            if isinstance(value, (int, float)):
                found.append(float(value))
    return found


@pytest.mark.parametrize("kind", sorted(CASES))
def test_a_profile_survives_the_sketch_model_unchanged(kind):
    """The regression: metres in, the same metres out the other side."""
    entities, _method, _volume = _primitive_profile(_args(kind))
    metres = _coordinates(entities)

    assert metres, f"the {kind} profile has no coordinates at all"
    largest = max(abs(value) for value in metres)
    assert 0.001 <= largest <= 1.0, (
        f"the {kind} profile's largest coordinate is {largest} m; a value near 1e-5 "
        "means metres were re-read as millimetres"
    )


@pytest.mark.parametrize("kind", sorted(CASES))
def test_the_closed_form_volume_matches_the_dimensions(kind):
    """The formula the live test compares against is itself worth checking."""
    _entities, _method, volume_m3 = _primitive_profile(_args(kind))

    assert volume_to_display(volume_m3, "mm") == pytest.approx(EXPECTED_MM3[kind], rel=1e-9)


@pytest.mark.parametrize("kind", sorted(CASES))
def test_every_primitive_declares_how_it_is_built(kind):
    _entities, method, _volume = _primitive_profile(_args(kind))
    assert method in {"extrude", "revolve"}


def test_a_revolved_primitive_carries_exactly_one_centerline():
    """The axis is found by being the only centerline; two would be ambiguous."""
    for kind in ("sphere", "cone", "frustum", "torus"):
        entities, method, _volume = _primitive_profile(_args(kind))
        assert method == "revolve"
        centerlines = [entity for entity in entities if entity["type"] == "centerline"]
        assert len(centerlines) == 1, f"{kind} has {len(centerlines)} centerlines"


def test_the_sphere_is_an_open_arc_and_its_axis():
    """The sphere must not close its semicircle with a line over the centerline.

    It used to, and FeatureRevolve2 returned None for it: measured, the failure holds
    for both arc directions and for a two-quarter-arc profile, while the same profile
    left open revolves into a sphere measuring 4/3 pi r^3 exactly. The rule is not
    general — the cone closes itself with a line along its axis and builds perfectly —
    so this pins the sphere rather than pretending to a wider invariant.
    """
    entities, method, _volume = _primitive_profile(_args("sphere"))

    assert method == "revolve"
    assert [entity["type"] for entity in entities] == ["centerline", "arc_center"]


def test_placement_moves_the_profile_without_resizing_it():
    at_origin = _coordinates(_primitive_profile(_args("cylinder"))[0])
    moved = _coordinates(_primitive_profile(_args("cylinder", at=[60, 0]))[0])

    assert max(moved) > max(at_origin), "the profile should have moved along +x"
    _entities, _method, first = _primitive_profile(_args("cylinder"))
    _entities, _method, second = _primitive_profile(_args("cylinder", at=[60, 0]))
    assert first == second, "moving a primitive must not change its volume"


def test_every_kind_has_its_requirements_declared():
    from typing import get_args

    from swmcp.schemas.solid import PrimitiveKind

    assert set(get_args(PrimitiveKind)) == set(PRIMITIVE_REQUIREMENTS)
    assert set(CASES) == set(PRIMITIVE_REQUIREMENTS), "this file covers every kind"


def test_the_extrusion_depth_is_handed_over_in_metres(monkeypatch):
    """The trap bit twice: once in the profile coordinates, once in the depth.

    ``_primitive_profile`` returning correct metres is not enough — the height also
    travels through a ``Length`` field on its way to the boss, where a bare number
    means millimetres. So the composition is checked, not just its first half.
    """
    from swmcp.handlers import solid
    from swmcp.schemas.feature import ExtrudeArgs, RevolveArgs

    captured: dict[str, object] = {}

    class Result:
        feature_name = "Body"
        sketch_name = "Sketch1"

    snapshot = {"body_count": 0, "face_count": 0, "volume_m3": 0.0, "volume_mm3": 0.0}
    monkeypatch.setattr(solid, "model_snapshot", lambda _doc: dict(snapshot))
    monkeypatch.setattr(
        "swmcp.handlers.sketch.sketch_start", lambda _ctx, _args: Result()
    )
    monkeypatch.setattr(
        "swmcp.handlers.sketch.sketch_add_geometry",
        lambda _ctx, _args: type("Added", (), {"failed": []})(),
    )
    monkeypatch.setattr("swmcp.handlers.sketch.sketch_exit", lambda _ctx, _args: None)

    def fake_extrude(_ctx, args: ExtrudeArgs):
        captured["depth_m"] = args.depth
        return Result()

    def fake_revolve(_ctx, args: RevolveArgs):
        captured["angle_rad"] = args.angle
        return Result()

    monkeypatch.setattr("swmcp.handlers.feature.feature_extrude_boss", fake_extrude)
    monkeypatch.setattr("swmcp.handlers.feature.feature_revolve", fake_revolve)

    class Ctx:
        def require_doc(self):
            return object()

    solid.body_primitive(Ctx(), _args("box"))
    assert captured["depth_m"] == pytest.approx(0.020), (
        f"a 20 mm box was extruded {captured['depth_m']} m deep"
    )

    captured.clear()
    solid.body_primitive(Ctx(), _args("sphere"))
    assert captured["angle_rad"] == pytest.approx(math.tau), "a revolve sweeps a full turn"
