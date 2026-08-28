"""Live cover for the parameter domain: equations, configurations, properties, tables.

The claim these tools make is that a part can be driven by name. So each test changes
something by name and then reads the geometry or the value back — a configuration that
is "created" but not in the list, or a dimension "set" that did not move, is a failure
here rather than a success with a caveat.
"""

from __future__ import annotations

import csv

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

PLATE_X, PLATE_Y, PLATE_Z = 100.0, 60.0, 8.0


@pytest.fixture
def plate(call, scratch_root, unique_name):
    """A saved part with one extruded plate, so its dimensions have names."""
    for stale in scratch_root.glob(f"{unique_name}*"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"

    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_X, PLATE_Y]}]},
    )["result"]
    ids = [entry["sketch_local_id"] for entry in added["created"]]
    call(
        "sw_sketch_add_dimensions",
        {
            "dimensions": [
                {
                    "type": "distance",
                    "segment_ids": [ids[0]],
                    "value": PLATE_X,
                    "place_at": [0.05, -0.02, 0],
                    "name": "PlateLength",
                }
            ]
        },
    )
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": PLATE_Z, "name": "Plate"})
    return target


def _volume(call) -> float:
    return call("sw_measure")["result"]["mass_properties"]["volume_mm3"]


def _dimension_named(call, fragment: str) -> str:
    listed = call("sw_dimension_list")["result"]["dimensions"]
    for entry in listed:
        if fragment in entry["name"]:
            return entry["name"]
    raise AssertionError(f"no dimension name contains {fragment!r}: {[e['name'] for e in listed]}")


# --- PAR-001: named driving dimensions ----------------------------------------


def test_feature_dimensions_are_listed_not_just_sketch_ones(call, plate):
    """PAR-001: the extrude's depth is a driving dimension too."""
    listed = call("sw_dimension_list")["result"]
    owners = {entry["owner"] for entry in listed["dimensions"]}

    assert "Plate" in owners, f"the extrude's own dimension must be listed; saw {owners}"
    assert all(entry["value_m"] is not None for entry in listed["dimensions"])
    assert listed["unit"] == "mm"


def test_setting_a_dimension_moves_the_geometry(call, plate):
    """PAR-001 end to end: name in, measured change out."""
    name = _dimension_named(call, "PlateLength")
    before = _volume(call)
    assert before == pytest.approx(PLATE_X * PLATE_Y * PLATE_Z, rel=1e-6)

    changed = call("sw_dimension_set", {"name": name, "value": 150})["result"]

    assert changed["before_mm"] == pytest.approx(PLATE_X, rel=1e-6)
    assert changed["after_mm"] == pytest.approx(150.0, rel=1e-6)
    assert changed["rebuild_errors"] == []
    assert all(check["passed"] for check in changed["verification"]["checks"])
    assert _volume(call) == pytest.approx(150.0 * PLATE_Y * PLATE_Z, rel=1e-6)


# --- PAR-002: equations and global variables ----------------------------------


def test_a_global_variable_drives_a_dimension(call, plate):
    """PAR-002: the point of an equation is that changing one value moves geometry."""
    name = _dimension_named(call, "PlateLength")

    created = call(
        "sw_equation_set",
        {
            "equations": [
                {
                    "operation": "add",
                    "name": "Width",
                    # Unit-suffixed deliberately: an equation is text, and
                    # SOLIDWORKS reads a bare number in document units - inches on
                    # this template, which is 25.4x what the assertion below wants.
                    "expression": "120mm",
                    "global_variable": True,
                },
                {"operation": "add", "name": name, "expression": '"Width"'},
            ]
        },
    )["result"]

    assert created["failed"] == [], created["failed"]
    assert created["applied"] == 2
    assert created["circular_references"] == []
    assert _volume(call) == pytest.approx(120.0 * PLATE_Y * PLATE_Z, rel=1e-6)

    listed = call("sw_equation_list")["result"]
    assert listed["count"] == 2
    assert [entry["name"] for entry in listed["global_variables"]] == ["Width"]
    assert listed["circular_references"] == []
    assert listed["unresolved_references"] == []

    updated = call(
        "sw_equation_set",
        {"equations": [{"operation": "update", "name": "Width", "expression": "80mm"}]},
    )["result"]
    assert updated["failed"] == []
    assert _volume(call) == pytest.approx(80.0 * PLATE_Y * PLATE_Z, rel=1e-6)


def test_deleting_an_equation_releases_the_dimension(call, plate):
    name = _dimension_named(call, "PlateLength")
    call(
        "sw_equation_set",
        {"equations": [{"operation": "add", "name": name, "expression": "90"}]},
    )
    assert call("sw_equation_list")["result"]["count"] == 1

    removed = call(
        "sw_equation_set", {"equations": [{"operation": "delete", "name": name}]}
    )["result"]

    assert removed["failed"] == []
    assert call("sw_equation_list")["result"]["count"] == 0
    # With the equation gone the dimension is drivable again.
    call("sw_dimension_set", {"name": name, "value": 70})
    assert _volume(call) == pytest.approx(70.0 * PLATE_Y * PLATE_Z, rel=1e-6)


def test_a_bad_equation_does_not_lose_the_rest_of_the_batch(call, plate):
    name = _dimension_named(call, "PlateLength")
    outcome = call(
        "sw_equation_set",
        {
            "equations": [
                {"operation": "add", "name": name, "expression": "95mm"},
                {"operation": "update", "name": "NotAThing", "expression": "1"},
            ]
        },
    )["result"]

    assert outcome["applied"] == 1
    assert len(outcome["failed"]) == 1
    assert outcome["failed"][0]["name"] == "NotAThing"
    assert _volume(call) == pytest.approx(95.0 * PLATE_Y * PLATE_Z, rel=1e-6)


def test_an_equation_without_a_unit_is_warned_about(call, plate):
    """PAR-002: a bare number in an equation is read in document units, not mm.

    The server cannot rewrite the caller's formula, so the contract is that it says
    what the number will mean. Measured: this template is in inches, so an unsuffixed
    120 becomes 3048 mm.
    """
    name = _dimension_named(call, "PlateLength")

    outcome = call(
        "sw_equation_set",
        {"equations": [{"operation": "add", "name": name, "expression": "120"}]},
    )["result"]

    assert outcome["failed"] == []
    assert outcome["document_length_unit"] == "inches"
    assert any("no unit" in warning for warning in outcome["warnings"])
    # And the warning is telling the truth: 120 inches, not 120 millimetres.
    assert _volume(call) == pytest.approx(120.0 * 25.4 * PLATE_Y * PLATE_Z, rel=1e-6)

    suffixed = call(
        "sw_equation_set",
        {"equations": [{"operation": "update", "name": name, "expression": "120mm"}]},
    )["result"]
    assert suffixed["warnings"] == []
    assert _volume(call) == pytest.approx(120.0 * PLATE_Y * PLATE_Z, rel=1e-6)


def test_equation_preflight_changes_nothing(call, plate):
    """SAFE-007 for this domain."""
    name = _dimension_named(call, "PlateLength")
    planned = call(
        "sw_equation_set",
        {
            "equations": [{"operation": "add", "name": name, "expression": "42"}],
            "preflight": True,
        },
    )["result"]

    assert planned["applied"] == 0
    assert any("Preflight" in warning for warning in planned["warnings"])
    assert call("sw_equation_list")["result"]["count"] == 0
    assert _volume(call) == pytest.approx(PLATE_X * PLATE_Y * PLATE_Z, rel=1e-6)


def test_an_equation_can_be_scoped_once_a_second_configuration_exists(call, plate):
    """PAR-004: IEquationMgr::Add3 scopes an equation, and needs multiple configurations.

    Add3 is documented to work "only for parts having multiple configurations", and
    measured returning -1 on a single-configuration part. So the same call is refused
    with a readable reason before the second configuration exists, and accepted after.
    """
    name = _dimension_named(call, "PlateLength")

    # A batch reports each item's outcome rather than failing as a whole, so the
    # refusal arrives inside failed[] and the call itself is still ok.
    refused = call(
        "sw_equation_set",
        {
            "equations": [
                {
                    "operation": "add",
                    "name": name,
                    "expression": "90mm",
                    "configuration_scope": "this",
                }
            ]
        },
    )["result"]
    assert refused["applied"] == 0
    assert len(refused["failed"]) == 1
    assert refused["failed"][0]["code"] == "ONE_CONFIGURATION_ONLY"
    assert any("sw_config_create" in step for step in refused["failed"][0]["remediation"])

    call("sw_config_create", {"name": "Large", "activate": True})

    scoped = call(
        "sw_equation_set",
        {
            "equations": [
                {
                    "operation": "add",
                    "name": name,
                    "expression": "90mm",
                    "configuration_scope": "this",
                }
            ]
        },
    )["result"]

    assert scoped["failed"] == [], scoped["failed"]
    assert scoped["applied"] == 1
    assert _volume(call) == pytest.approx(90.0 * PLATE_Y * PLATE_Z, rel=1e-6)


def test_a_scoped_equation_updates_in_place(call, plate):
    """An Add3 equation has a working setter, so the update disturbs nothing else."""
    name = _dimension_named(call, "PlateLength")
    call("sw_config_create", {"name": "Large", "activate": True})
    call(
        "sw_equation_set",
        {
            "equations": [
                {
                    "operation": "add",
                    "name": name,
                    "expression": "90mm",
                    "configuration_scope": "this",
                }
            ]
        },
    )

    updated = call(
        "sw_equation_set",
        {
            "equations": [
                {
                    "operation": "update",
                    "name": name,
                    "expression": "70mm",
                    "configuration_scope": "this",
                }
            ]
        },
    )["result"]

    assert updated["failed"] == []
    assert updated["warnings"] == [], "an in-place update passes its own read-back"
    assert call("sw_equation_list")["result"]["count"] == 1
    assert _volume(call) == pytest.approx(70.0 * PLATE_Y * PLATE_Z, rel=1e-6)


def test_a_global_variable_may_not_be_scoped(call, plate):
    """SOLIDWORKS requires global variables to apply to every configuration."""
    refused = call(
        "sw_equation_set",
        {
            "equations": [
                {
                    "operation": "add",
                    "name": "Width",
                    "expression": "120mm",
                    "global_variable": True,
                    "configuration_scope": "this",
                }
            ]
        },
        expect_ok=False,
    )
    assert refused["error"]["code"] == "INVALID_ARGUMENTS"


# --- PAR-003 and PAR-004: configurations --------------------------------------


def test_a_configuration_is_created_activated_and_deleted(call, plate):
    """PAR-003, each step confirmed by reading the list back."""
    before = call("sw_config_list")["result"]
    assert before["count"] == 1
    default = before["active"]

    created = call("sw_config_create", {"name": "Large", "activate": True})["result"]
    assert created["name"] == "Large"
    assert created["count_after"] == created["count_before"] + 1
    assert all(check["passed"] for check in created["verification"]["checks"])

    listed = call("sw_config_list")["result"]
    assert listed["count"] == 2
    assert listed["active"] == "Large"
    assert {entry["name"] for entry in listed["configurations"]} == {default, "Large"}

    back = call("sw_config_activate", {"name": default})["result"]
    assert back["active"] == default
    assert back["previous"] == "Large"

    removed = call("sw_config_delete", {"name": "Large", "confirm": True})["result"]
    assert removed["deleted"] is True
    assert call("sw_config_list")["result"]["count"] == 1


def test_deleting_a_configuration_requires_confirmation(call, plate):
    call("sw_config_create", {"name": "Spare", "activate": False})
    refused = call("sw_config_delete", {"name": "Spare"}, expect_ok=False)

    assert refused["error"]["code"] == "CONFIRM_REQUIRED"
    assert call("sw_config_list")["result"]["count"] == 2, "the configuration must survive"


def test_the_last_configuration_cannot_be_deleted(call, plate):
    only = call("sw_config_list")["result"]["active"]
    refused = call("sw_config_delete", {"name": only, "confirm": True}, expect_ok=False)

    assert refused["error"]["code"] == "LAST_CONFIGURATION"
    assert call("sw_config_list")["result"]["count"] == 1


def test_a_dimension_can_hold_a_different_value_per_configuration(call, plate):
    """PAR-004, and the reason configuration_scope defaults to 'all'."""
    name = _dimension_named(call, "PlateLength")
    default = call("sw_config_list")["result"]["active"]

    call("sw_config_create", {"name": "Long", "activate": True})
    scoped = call(
        "sw_dimension_set", {"name": name, "value": 200, "configuration_scope": "this"}
    )["result"]

    assert scoped["configuration_scope"] == "this"
    assert scoped["after_mm"] == pytest.approx(200.0, rel=1e-6)
    assert _volume(call) == pytest.approx(200.0 * PLATE_Y * PLATE_Z, rel=1e-6)

    call("sw_config_activate", {"name": default})
    assert _volume(call) == pytest.approx(PLATE_X * PLATE_Y * PLATE_Z, rel=1e-6), (
        "scope 'this' must not have touched the other configuration"
    )

    in_long = call("sw_dimension_list", {"configuration": "Long"})["result"]
    value = next(entry for entry in in_long["dimensions"] if entry["name"] == name)
    assert value["value_mm"] == pytest.approx(200.0, rel=1e-6), (
        "reading one configuration must report that configuration's own value"
    )


def test_naming_a_configuration_that_does_not_exist_is_refused(call, plate):
    name = _dimension_named(call, "PlateLength")
    refused = call(
        "sw_dimension_set",
        {
            "name": name,
            "value": 120,
            "configuration_scope": "specify",
            "configurations": ["NoSuchConfig"],
        },
        expect_ok=False,
    )
    assert refused["error"]["code"] == "CONFIGURATION_NOT_FOUND"


# --- PAR-006: custom properties -----------------------------------------------


def test_custom_properties_round_trip_at_file_level(call, plate):
    """PAR-006."""
    written = call(
        "sw_property_set",
        {
            "properties": [
                {"name": "PartNumber", "value": "BRK-001"},
                {"name": "Revision", "value": "A"},
                {"name": "Approved", "value": "Yes", "type": "yes_no"},
            ]
        },
    )["result"]

    assert written["failed"] == []
    assert sorted(written["written"]) == ["Approved", "PartNumber", "Revision"]
    assert all(check["passed"] for check in written["verification"]["checks"])

    listed = call("sw_property_list")["result"]
    by_name = {entry["name"]: entry for entry in listed["file_properties"]}
    assert by_name["PartNumber"]["raw"] == "BRK-001"
    assert by_name["Revision"]["raw"] == "A"
    assert by_name["PartNumber"]["type"] == "swCustomInfoText"

    removed = call(
        "sw_property_set", {"properties": [{"name": "Revision", "delete": True}]}
    )["result"]
    assert removed["deleted"] == ["Revision"]
    remaining = call("sw_property_list")["result"]
    assert "Revision" not in {entry["name"] for entry in remaining["file_properties"]}


def test_configuration_properties_are_separate_from_file_properties(call, plate):
    call("sw_config_create", {"name": "Blue", "activate": False})
    call("sw_property_set", {"properties": [{"name": "Finish", "value": "raw"}]})
    call(
        "sw_property_set",
        {"properties": [{"name": "Finish", "value": "anodised"}], "configuration": "Blue"},
    )

    everything = call("sw_property_list", {"configuration": "*"})["result"]
    file_level = {entry["name"]: entry["raw"] for entry in everything["file_properties"]}
    blue = {entry["name"]: entry["raw"] for entry in everything["configuration_properties"]["Blue"]}

    assert file_level["Finish"] == "raw"
    assert blue["Finish"] == "anodised"


def test_writing_into_an_unknown_configuration_is_refused(call, plate):
    refused = call(
        "sw_property_set",
        {"properties": [{"name": "X", "value": "1"}], "configuration": "Nope"},
        expect_ok=False,
    )
    assert refused["error"]["code"] == "CONFIGURATION_NOT_FOUND"


# --- PAR-005: the parameter table ---------------------------------------------


def test_the_parameter_table_round_trips_a_dimension_change(
    call, plate, scratch_root, unique_name
):
    """PAR-005: export, edit the file, import, and measure the result."""
    name = _dimension_named(call, "PlateLength")
    call("sw_property_set", {"properties": [{"name": "PartNumber", "value": "BRK-002"}]})
    table = scratch_root / f"{unique_name}.csv"
    table.unlink(missing_ok=True)

    exported = call(
        "sw_parameter_table_export", {"output_path": str(table), "unit": "mm"}
    )["result"]

    assert exported["row_count"] > 0
    assert exported["kinds"]["dimension"] >= 2, "sketch and feature dimensions both appear"
    assert exported["kinds"]["property"] >= 1
    assert exported["artifacts"][0]["exists"] is True
    assert exported["artifacts"][0]["sha256"]

    written = table.read_text(encoding="utf-8")
    rows = list(csv.DictReader(written.splitlines()))
    lengths = [row for row in rows if row["name"] == name]
    assert len(lengths) == 1
    assert float(lengths[0]["value"]) == pytest.approx(PLATE_X, rel=1e-6)

    # Edit the file the way a person would, then feed it back.
    edited = written.replace(
        f"dimension,{name},{float(lengths[0]['value']):.6f}",
        f"dimension,{name},175.000000",
    )
    assert edited != written, "the substitution must actually change the file"
    table.write_text(edited, encoding="utf-8")

    planned = call(
        "sw_parameter_table_import", {"input_path": str(table), "preflight": True}
    )["result"]
    assert planned["applied"] == 0
    assert any("Preflight" in warning for warning in planned["warnings"])
    assert _volume(call) == pytest.approx(PLATE_X * PLATE_Y * PLATE_Z, rel=1e-6)

    applied = call("sw_parameter_table_import", {"input_path": str(table)})["result"]

    assert applied["failed"] == []
    assert applied["applied"] == 1
    assert applied["unchanged"] >= 1, "rows already at their value must not be rewritten"
    assert all(check["passed"] for check in applied["verification"]["checks"])
    assert _volume(call) == pytest.approx(175.0 * PLATE_Y * PLATE_Z, rel=1e-6)


def test_exporting_twice_versions_rather_than_replacing(
    call, plate, scratch_root, unique_name
):
    """SAFE-008 applies to this deliverable too."""
    table = scratch_root / f"{unique_name}.csv"
    for stale in scratch_root.glob(f"{unique_name}*.csv"):
        stale.unlink(missing_ok=True)

    first = call("sw_parameter_table_export", {"output_path": str(table)})["result"]
    second = call("sw_parameter_table_export", {"output_path": str(table)})["result"]

    assert first["overwrite_action"] == "create"
    assert second["overwrite_action"] == "versioned"
    assert second["saved_path"] != first["saved_path"]
    assert second["warnings"], "writing somewhere else than asked must be said out loud"


def test_importing_a_missing_file_is_refused(call, plate, scratch_root):
    refused = call(
        "sw_parameter_table_import",
        {"input_path": str(scratch_root / "not_here.csv")},
        expect_ok=False,
    )
    assert refused["error"]["code"] == "INPUT_NOT_FOUND"


def test_the_export_path_is_root_checked(call, plate):
    refused = call(
        "sw_parameter_table_export",
        {"output_path": "C:\\Windows\\System32\\swmcp_params.csv"},
        expect_ok=False,
    )
    assert refused["error"]["code"] == "PATH_NOT_ALLOWED"
