"""Live cover for the BOM precursor (IO-007).

The tree is the one the probe built, because it is the one that exposes the mistakes: a
subassembly holding two copies of a widget plus a third copy at the top, and a widget
whose ``Description`` exists in *both* property sets with *different values*. A tool
reading one set prints the wrong description; a tool reading only the configuration set
prints nothing at all, since a property written without a configuration lands at file
level only.

The component files are built once into their own subdirectory — the autouse cleanup in
``conftest.py`` sweeps exports out of the scratch root after every test — and each test
opens the top assembly fresh rather than depending on a document surviving teardown.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

pytestmark = [pytest.mark.live]

W, D, H = 40.0, 25.0, 8.0


def _ok(payload, label):
    assert payload.get("ok"), f"{label}: {payload.get('error')}"
    return payload


@pytest.fixture(scope="module")
def tree(dispatcher, scratch_root):
    """widget.SLDPRT, sub.SLDASM (2 widgets), top.SLDASM (sub + 1 widget)."""
    home = scratch_root / "bom_fixtures"
    home.mkdir(parents=True, exist_ok=True)
    for stale in home.glob("*"):
        try:
            stale.unlink()
        except OSError:
            continue

    widget, sub, top = home / "widget.SLDPRT", home / "sub.SLDASM", home / "top.SLDASM"

    _ok(dispatcher.call("sw_doc_new", {"doc_type": "part"}), "new part")
    dispatcher.call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    dispatcher.call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [W, D]}]},
    )
    dispatcher.call("sw_sketch_exit", {})
    _ok(dispatcher.call("sw_feature_extrude_boss", {"depth": H, "name": "Body"}), "extrude")
    # The two property sets, deliberately disagreeing on Description.
    _ok(dispatcher.call("sw_property_set", {"properties": [
        {"name": "PartNo", "value": "PN-FILE"},
        {"name": "Description", "value": "FILE LEVEL"},
        {"name": "Vendor", "value": "Acme"},
    ]}), "file properties")
    _ok(dispatcher.call("sw_property_set", {
        "configuration": "Default",
        "properties": [
            {"name": "Description", "value": "CONFIG LEVEL"},
            {"name": "Finish", "value": "Anodised"},
        ],
    }), "configuration properties")
    _ok(dispatcher.call("sw_doc_save", {"output_path": str(widget)}), "save widget")

    _ok(dispatcher.call("sw_doc_new", {"doc_type": "assembly"}), "new sub")
    _ok(dispatcher.call("sw_doc_save", {"output_path": str(sub)}), "save sub")
    # AddComponent5 returns None for a part that is on disk but not loaded, so the
    # widget above is left open on purpose.
    _ok(dispatcher.call("sw_asm_insert", {"component_path": str(widget), "at": [0, 0, 0]}), "s1")
    _ok(dispatcher.call("sw_asm_insert", {"component_path": str(widget), "at": [80, 0, 0]}), "s2")
    _ok(dispatcher.call("sw_doc_save", {"output_path": str(sub), "overwrite": "allow",
                                        "confirm": True}), "resave sub")

    _ok(dispatcher.call("sw_doc_new", {"doc_type": "assembly"}), "new top")
    _ok(dispatcher.call("sw_doc_save", {"output_path": str(top)}), "save top")
    _ok(dispatcher.call("sw_asm_insert", {"component_path": str(sub), "at": [0, 0, 0]}), "t1")
    _ok(dispatcher.call("sw_asm_insert", {"component_path": str(widget), "at": [0, 120, 0]}), "t2")
    _ok(dispatcher.call("sw_doc_save", {"output_path": str(top), "overwrite": "allow",
                                        "confirm": True}), "resave top")
    return {"home": home, "widget": widget, "sub": sub, "top": top}


@pytest.fixture
def assembly(call, tree):
    """The top assembly, open and active for this test."""
    call("sw_doc_open", {"path": str(tree["top"])})
    call("sw_doc_activate", {"document": {"path": str(tree["top"])}})
    return tree


@pytest.fixture
def out_dir(scratch_root, unique_name):
    directory = scratch_root / "bom_out" / unique_name
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.iterdir():
        try:
            stale.unlink()
        except OSError:
            continue
    return directory


def _rows(path: str) -> list[dict[str, str]]:
    return list(csv.DictReader(Path(path).read_text(encoding="utf-8").splitlines()))


def _export(call, out_dir, **kwargs):
    return call(
        "sw_bom_export", {"output_path": str(out_dir / "bom.csv"), **kwargs}
    )["result"]


# --- the merge, which is what a probe cannot prove on its own ------------------


def test_the_bom_prints_the_configuration_description_not_the_file_one(
    call, assembly, out_dir
):
    """The finding this tool exists around, end to end through the CSV on disk."""
    result = _export(call, out_dir)

    rows = _rows(result["saved_path"])
    widget = next(r for r in rows if r["part_number"] == "widget")
    assert widget["Description"] == "CONFIG LEVEL", (
        "the file-level value is FILE LEVEL; printing it would be the classic BOM bug"
    )
    assert widget["PartNo"] == "PN-FILE", "and the file set still fills what the config lacks"


def test_the_matrix_says_where_every_value_came_from(call, assembly, out_dir):
    result = _export(call, out_dir)
    matrix = _rows(result["matrix_path"])

    widget = next(r for r in matrix if r["instance_name"] == "widget-1")
    assert widget["Description__source"] == "configuration"
    assert widget["PartNo__source"] == "file"
    assert widget["Finish__source"] == "configuration"
    assert result["property_sources"]["configuration"] > 0
    assert result["property_sources"]["file"] > 0


# --- the roll-up --------------------------------------------------------------


def test_parts_only_counts_every_widget_in_the_tree(call, assembly, out_dir):
    result = _export(call, out_dir)
    assert result["shape"] == "parts_only"
    lines = {line["part_number"]: line for line in result["lines"]}
    assert set(lines) == {"widget"}, "the subassembly is not a part"
    assert lines["widget"]["quantity"] == 3, "two inside the subassembly, one at the top"
    assert result["instance_count"] == 4


def test_top_level_only_lists_the_subassembly_as_one_line(call, assembly, out_dir):
    result = _export(call, out_dir, shape="top_level_only")
    assert sorted((line["part_number"], line["quantity"]) for line in result["lines"]) == [
        ("sub", 1),
        ("widget", 1),
    ]


def test_indented_numbers_by_position_in_the_tree(call, assembly, out_dir):
    result = _export(call, out_dir, shape="indented")
    numbered = [(line["item_number"], line["part_number"], line["quantity"])
                for line in result["lines"]]
    assert numbered == [("1", "sub", 1), ("1.1", "widget", 2), ("2", "widget", 1)], numbered

    matrix = {r["instance_name"]: r["item_number"] for r in _rows(result["matrix_path"])}
    assert matrix["sub-1/widget-1"] == matrix["sub-1/widget-2"] == "1.1"
    assert matrix["widget-1"] == "2"


def test_the_part_number_rule_is_read_rather_than_assumed(call, assembly, out_dir):
    """Every configuration on this machine reports DocumentName; the column proves it."""
    result = _export(call, out_dir)
    assert {line["part_number_source"] for line in result["lines"]} == {"document_name"}


def test_a_suppressed_component_leaves_the_quantity_but_not_the_record(
    call, assembly, out_dir
):
    call("sw_asm_component_set", {"component_name": "widget-1", "suppression": "suppressed"})
    try:
        result = _export(call, out_dir)
        widget = next(line for line in result["lines"] if line["part_number"] == "widget")
        assert widget["quantity"] == 2, "the suppressed instance is not ordered"

        row = next(r for r in _rows(result["matrix_path"]) if r["instance_name"] == "widget-1")
        assert row["in_bom"] == "False"
        assert row["excluded_reason"] == "suppressed"
        assert result["excluded_instances"] >= 1
    finally:
        call("sw_asm_component_set", {"component_name": "widget-1", "suppression": "resolved"})


def test_a_suppressed_component_can_be_counted_when_asked(call, assembly, out_dir):
    call("sw_asm_component_set", {"component_name": "widget-1", "suppression": "suppressed"})
    try:
        result = _export(call, out_dir, include_suppressed=True)
        widget = next(line for line in result["lines"] if line["part_number"] == "widget")
        assert widget["quantity"] == 3
    finally:
        call("sw_asm_component_set", {"component_name": "widget-1", "suppression": "resolved"})


# --- the files ----------------------------------------------------------------


def test_both_files_land_with_hashes_and_the_matrix_beside_the_bom(call, assembly, out_dir):
    result = _export(call, out_dir)
    assert Path(result["matrix_path"]).name == "bom_traceability.csv"
    assert len(result["artifacts"]) == 2
    for artifact in result["artifacts"]:
        written = Path(artifact["path"])
        assert written.is_file()
        assert artifact["size_bytes"] == written.stat().st_size
        assert artifact["sha256"]


def test_named_columns_survive_even_when_nothing_carries_them(call, assembly, out_dir):
    result = _export(call, out_dir, properties=["Vendor", "Mass"])
    assert result["property_columns"] == ["Vendor", "Mass"]
    row = _rows(result["saved_path"])[0]
    assert row["Vendor"] == "Acme"
    assert row["Mass"] == ""
    matrix = _rows(result["matrix_path"])[0]
    assert matrix["Mass__source"] == "absent"


def test_a_second_run_versions_both_files(call, assembly, out_dir):
    first = _export(call, out_dir)
    second = _export(call, out_dir)
    assert first["saved_path"] != second["saved_path"]
    assert Path(first["saved_path"]).is_file()
    assert "_v002" in Path(second["saved_path"]).name
    assert "_v002" in Path(second["matrix_path"]).name


def test_an_output_outside_the_allowed_roots_is_refused(call, assembly):
    payload = call(
        "sw_bom_export",
        {"output_path": r"C:\Windows\Temp\swmcp_bom.csv"},
        expect_ok=False,
    )
    assert payload["ok"] is False
    assert payload["error"]["code"] == "PATH_NOT_ALLOWED"


def test_a_part_is_refused_because_a_part_has_no_components(call, tree, out_dir):
    call("sw_doc_open", {"path": str(tree["widget"])})
    payload = call(
        "sw_bom_export",
        {"output_path": str(out_dir / "bom.csv"),
         "document": {"path": str(tree["widget"])}},
        expect_ok=False,
    )
    assert payload["ok"] is False
    assert payload["error"]["code"] == "WRONG_DOCUMENT_TYPE"


# --- the claim it refuses to drop ---------------------------------------------


def test_the_precursor_warning_travels_with_every_result(call, assembly, out_dir):
    """IO-007 asks for it to be retained, so no argument clears it."""
    for kwargs in ({}, {"shape": "indented"}, {"include_suppressed": True}):
        result = _export(call, out_dir, **kwargs)
        assert result["precursor"] is True
        assert any("precursor to a bill of materials" in w for w in result["warnings"])
        assert any("native BOM" in w for w in result["warnings"])
