"""Live cover for materials (FEAT-020), appearance (VIEW-001), and visibility (VIEW-002).

Module-scoped document, per the cost policy in ``CLAUDE.md``: one 40 x 30 x 20 mm block
serves every test, so the numbers below are all arithmetic against 24 000 mm3.

The regression test in here matters more than the new tools. ``IBody2::GetMassProperties``
computes ``volume * density`` from the density *passed to it*, so it knows nothing about
the assigned material — the shipped code passed 0.0 and reported a "mass" numerically
equal to the volume, identical for steel and aluminium, with ``density_kg_m3`` stuck at
1.0. ``test_measure_reports_the_material_mass_not_the_volume`` is what stops that coming
back.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

WIDTH, DEPTH, HEIGHT = 40.0, 30.0, 20.0
VOLUME_M3 = (WIDTH / 1000) * (DEPTH / 1000) * (HEIGHT / 1000)  # 2.4e-5

STEEL = "Plain Carbon Steel"
ALUMINIUM = "6061 Alloy"
STEEL_DENSITY = 7800.0
ALUMINIUM_DENSITY = 2700.0


@pytest.fixture(scope="module")
def block(dispatcher, scratch_root):
    """One saved part holding a single block, shared by every test in the file."""
    target = scratch_root / "swmcp_material.SLDPRT"
    for stale in scratch_root.glob("swmcp_material*.SLDPRT"):
        stale.unlink(missing_ok=True)

    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_doc_save", {"output_path": str(target)})
    title = target.name
    document = {"title": title}

    dispatcher.call("sw_sketch_start", {"document": document, "on": {"standard_plane": "front"}})
    dispatcher.call(
        "sw_sketch_add_geometry",
        {
            "document": document,
            "entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [WIDTH, DEPTH]}],
        },
    )
    dispatcher.call("sw_sketch_exit", {"document": document})
    built = dispatcher.call(
        "sw_feature_extrude_boss",
        {"document": document, "depth": HEIGHT, "name": "Block"},
    )
    assert built.get("ok"), built.get("error")

    yield title

    dispatcher.call(
        "sw_doc_close",
        {"document": document, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def call(call, block):
    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        args = dict(arguments or {})
        args.setdefault("document", {"title": block})
        return call(name, args, expect_ok=expect_ok)

    return _call


@pytest.fixture
def steel(call):
    """Leaves the block made of steel, for tests that need a known density."""
    call("sw_material_set", {"name": STEEL})
    return STEEL_DENSITY


# --- materials (FEAT-020) -----------------------------------------------------


@pytest.mark.parametrize(
    ("material", "density"), [(STEEL, STEEL_DENSITY), (ALUMINIUM, ALUMINIUM_DENSITY)]
)
def test_a_material_sets_the_density_the_library_says(call, material, density):
    applied = call("sw_material_set", {"name": material})["result"]

    assert applied["material"] == material
    assert applied["density_kg_m3"] == pytest.approx(density, rel=1e-6)
    assert applied["mass_kg"] == pytest.approx(VOLUME_M3 * density, rel=1e-6)
    assert all(check["passed"] for check in applied["verification"]["checks"])


def test_removing_the_material_is_accepted_and_read_back(call, steel):
    """Clearing does not reset the density to 1.0 - SOLIDWORKS keeps its own default.

    Measured at 1000 kg/m3 on this install. The test asserts the material is gone and
    the density is no longer steel's, rather than pinning a number the library owns.
    """
    cleared = call("sw_material_set", {"name": ""})["result"]

    assert cleared["material"] == ""
    assert cleared["density_kg_m3"] is not None
    assert cleared["density_kg_m3"] != pytest.approx(STEEL_DENSITY, rel=1e-6)
    assert all(check["passed"] for check in cleared["verification"]["checks"])


def test_a_material_that_is_not_in_the_library_is_refused(call):
    payload = call("sw_material_set", {"name": "Unobtainium"}, expect_ok=False)

    assert payload["error"]["code"] == "MATERIAL_NOT_APPLIED"
    assert payload["error"]["context"]["requested"] == "Unobtainium"
    assert any("exactly" in step for step in payload["error"]["remediation"])


def test_material_get_reports_what_set_applied(call, steel):
    read = call("sw_material_get")["result"]

    assert read["material"] == STEEL
    assert read["database"]
    assert read["density_kg_m3"] == pytest.approx(STEEL_DENSITY, rel=1e-6)
    assert read["volume_m3"] == pytest.approx(VOLUME_M3, rel=1e-6)
    assert read["warnings"] == []


def test_material_get_says_so_when_there_is_no_material(call):
    call("sw_material_set", {"name": ""})
    read = call("sw_material_get")["result"]

    assert read["material"] is None
    assert read["density_kg_m3"] is not None
    assert any("No material is assigned" in warning for warning in read["warnings"]), (
        "a mass that follows a default density rather than a material must say so"
    )


# --- the regression this batch exists to prevent ------------------------------


def test_measure_reports_the_material_mass_not_the_volume(call):
    """The bug: steel and aluminium used to measure identically.

    ``sw_measure`` summed ``IBody2::GetMassProperties(0.0)``, whose index 5 is
    ``Mass(Volume*density)`` computed from the density argument — so it reported the
    volume as the mass and a density of 1.0 whatever the part was made of.
    """
    call("sw_material_set", {"name": STEEL})
    as_steel = call("sw_measure")["result"]["mass_properties"]

    call("sw_material_set", {"name": ALUMINIUM})
    as_aluminium = call("sw_measure")["result"]["mass_properties"]

    assert as_steel["density_kg_m3"] == pytest.approx(STEEL_DENSITY, rel=1e-6)
    assert as_aluminium["density_kg_m3"] == pytest.approx(ALUMINIUM_DENSITY, rel=1e-6)
    assert as_steel["mass_kg"] == pytest.approx(VOLUME_M3 * STEEL_DENSITY, rel=1e-6)
    assert as_aluminium["mass_kg"] == pytest.approx(VOLUME_M3 * ALUMINIUM_DENSITY, rel=1e-6)

    assert as_steel["mass_kg"] > as_aluminium["mass_kg"], "steel must outweigh aluminium"
    assert as_steel["volume_m3"] == pytest.approx(as_aluminium["volume_m3"], rel=1e-9), (
        "changing material must not change the volume"
    )
    assert as_steel["mass_kg"] != pytest.approx(as_steel["volume_m3"], rel=1e-6), (
        "mass equal to the volume is the old bug"
    )


def test_body_list_reports_the_material_mass_too(call, steel):
    listed = call("sw_body_list")["result"]
    body = listed["bodies"][0]

    assert body["mass_kg"] == pytest.approx(VOLUME_M3 * STEEL_DENSITY, rel=1e-6)
    assert body["density_kg_m3"] == pytest.approx(STEEL_DENSITY, rel=1e-6)


# --- appearance (VIEW-001) ----------------------------------------------------


def test_a_document_colour_round_trips(call):
    applied = call(
        "sw_appearance_set",
        {"target": "document", "color": [1.0, 0.0, 0.0], "transparency": 0.25},
    )["result"]

    assert applied["appearance"]["red"] == pytest.approx(1.0)
    assert applied["appearance"]["green"] == pytest.approx(0.0)
    assert applied["appearance"]["transparency"] == pytest.approx(0.25)
    assert "transparency" in applied["changed"]

    read = call("sw_appearance_get", {"target": "document"})["result"]
    assert read["appearance"]["red"] == pytest.approx(1.0)
    assert read["appearance"]["transparency"] == pytest.approx(0.25)


def test_setting_one_field_leaves_the_others_alone(call):
    call("sw_appearance_set", {"target": "document", "color": [0.2, 0.4, 0.6]})
    call("sw_appearance_set", {"target": "document", "transparency": 0.5})

    read = call("sw_appearance_get", {"target": "document"})["result"]["appearance"]
    assert read["red"] == pytest.approx(0.2)
    assert read["green"] == pytest.approx(0.4)
    assert read["blue"] == pytest.approx(0.6)
    assert read["transparency"] == pytest.approx(0.5)


def test_a_body_can_carry_its_own_appearance(call):
    applied = call(
        "sw_appearance_set",
        {"target": "body", "body_name": "Block", "color": [0.0, 1.0, 0.0]},
    )["result"]

    assert applied["target"] == "body"
    assert applied["applied_to"] == "Block"
    assert applied["appearance"]["green"] == pytest.approx(1.0)


def test_an_unknown_body_is_named_in_the_error(call):
    payload = call(
        "sw_appearance_set",
        {"target": "body", "body_name": "NoSuchBody", "color": [1.0, 1.0, 1.0]},
        expect_ok=False,
    )
    assert payload["error"]["code"] == "BODY_NOT_FOUND"


def test_a_body_target_without_a_name_is_refused(call):
    payload = call("sw_appearance_set", {"target": "body", "color": [1, 1, 1]}, expect_ok=False)
    assert payload["error"]["code"] == "MISSING_ARGUMENT"


# --- visibility (VIEW-002) ----------------------------------------------------


def test_a_body_can_be_hidden_and_shown_again(call):
    hidden = call(
        "sw_visibility_set", {"target": "body", "name": "Block", "visible": False}
    )["result"]
    assert hidden["visible"] is False
    assert hidden["method"] == "IBody2::HideBody"

    shown = call(
        "sw_visibility_set", {"target": "body", "name": "Block", "visible": True}
    )["result"]
    assert shown["visible"] is True


def test_a_hidden_body_is_still_measured(call, steel):
    """Hiding changes what is drawn, never what exists. The safety note says so; prove it."""
    before = call("sw_measure")["result"]["mass_properties"]["mass_kg"]
    call("sw_visibility_set", {"target": "body", "name": "Block", "visible": False})
    try:
        during = call("sw_measure")["result"]["mass_properties"]["mass_kg"]
    finally:
        call("sw_visibility_set", {"target": "body", "name": "Block", "visible": True})

    assert during == pytest.approx(before, rel=1e-9)


def test_a_reference_plane_blanks_through_a_different_call(call):
    """Datums do not use IBody2::HideBody at all; they blank."""
    call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "front", "distance": 30, "name": "Hideable"},
    )

    hidden = call(
        "sw_visibility_set", {"target": "feature", "name": "Hideable", "visible": False}
    )["result"]
    assert hidden["visible"] is False
    assert hidden["method"] == "IModelDoc2::BlankRefGeom"

    shown = call(
        "sw_visibility_set", {"target": "feature", "name": "Hideable", "visible": True}
    )["result"]
    assert shown["visible"] is True
    assert shown["method"] == "IModelDoc2::UnBlankRefGeom"


def test_an_unknown_feature_is_named_in_the_error(call):
    payload = call(
        "sw_visibility_set", {"target": "feature", "name": "Ghost", "visible": False},
        expect_ok=False,
    )
    assert payload["error"]["code"] == "FEATURE_NOT_FOUND"
