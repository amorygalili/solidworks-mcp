"""Bill of materials export (IO-007).

The fake tree here is the one the probe actually built: a subassembly holding two copies
of a widget, plus a third copy at the top. Its widget carries ``Description`` in *both*
property sets with *different values*, because that is what the real part did and it is
the case a BOM gets wrong.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.com import swconst
from swmcp.config import SwmcpConfig
from swmcp.context import OpContext
from swmcp.errors import SwMcpError
from swmcp.handlers import bom as bom_handlers
from swmcp.schemas.bom import (
    BOM_COLUMNS,
    MATRIX_COLUMNS,
    MAX_PROPERTY_COLUMNS,
    SOURCE_SUFFIX,
    BomExportArgs,
    BomShape,
)

# --- the enum tables name real members ----------------------------------------


def test_every_part_number_source_is_a_real_enum_value():
    for value, name in bom_handlers._PART_NUMBER_SOURCES.items():
        assert isinstance(value, int)
        assert swconst.name_of("swBOMPartNumberSource_e", value)
        assert name.islower()


def test_the_part_number_sources_cover_the_whole_enum():
    """A source this tool cannot name would silently fall back to the document name."""
    assert set(bom_handlers._PART_NUMBER_SOURCES) == set(
        swconst.members("swBOMPartNumberSource_e").values()
    )


def test_the_shapes_are_a_subset_of_the_solidworks_bom_types():
    """The drawing BOM tool owns the full vocabulary; this one implements part of it."""
    from swmcp.handlers.drawing import _BOM_TYPES

    assert set(BomShape.__args__) < set(_BOM_TYPES), (
        "a shape with no swBomType_e counterpart would be an invented BOM mode"
    )
    assert "flattened" not in BomShape.__args__, "declared unimplemented; do not claim it"


def test_a_part_reports_a_child_display_value_that_is_not_in_its_own_enum():
    """The probe found 0, and swChildComponentInBOMOption_e has only 1, 2 and 3.

    Pinned because decoding it blindly would invent a name for a value that means
    'not applicable'.
    """
    assert 0 not in swconst.members("swChildComponentInBOMOption_e").values()


# --- the schema ---------------------------------------------------------------


def test_duplicate_property_columns_are_refused():
    with pytest.raises(ValidationError, match="named twice"):
        BomExportArgs(output_path="b.csv", properties=["Vendor", "vendor"])


def test_a_property_column_may_not_shadow_a_fixed_one():
    with pytest.raises(ValidationError, match="collides with a fixed BOM column"):
        BomExportArgs(output_path="b.csv", properties=["quantity"])


def test_a_blank_property_column_is_refused():
    with pytest.raises(ValidationError, match="blank"):
        BomExportArgs(output_path="b.csv", properties=["Vendor", "  "])


def test_naming_a_matrix_file_that_will_not_be_written_is_refused():
    with pytest.raises(ValidationError, match="drop one of them"):
        BomExportArgs(output_path="b.csv", matrix=False, matrix_path="m.csv")


def test_the_matrix_is_on_by_default():
    assert BomExportArgs(output_path="b.csv").matrix is True
    assert BomExportArgs(output_path="b.csv").shape == "parts_only"


def test_suppressed_and_excluded_are_left_out_by_default():
    """SOLIDWORKS' own BOM leaves them out, so the default matches it."""
    args = BomExportArgs(output_path="b.csv")
    assert args.include_suppressed is False
    assert args.include_excluded is False


def test_the_property_column_cap_is_enforced_by_the_schema():
    with pytest.raises(ValidationError):
        BomExportArgs(output_path="b.csv", properties=[f"p{n}" for n in range(MAX_PROPERTY_COLUMNS + 1)])


def test_the_default_matrix_path_sits_beside_the_bom():
    assert bom_handlers._default_matrix_path(Path("/out/order.csv")).name == (
        "order_traceability.csv"
    )


# --- the property merge, which is the whole correctness question ---------------


def test_the_configuration_value_wins_over_the_file_value():
    """The probe's exact case: Description is 'FILE LEVEL' and 'CONFIG LEVEL' at once."""
    merged = bom_handlers._merge_properties(
        {"Description": "CONFIG LEVEL", "Finish": "Anodised"},
        {"PartNo": "PN-FILE", "Description": "FILE LEVEL", "Vendor": "FileVendor"},
        ["Description", "PartNo", "Finish", "Weight"],
    )
    assert merged["Description"] == ("CONFIG LEVEL", "configuration")
    assert merged["PartNo"] == ("PN-FILE", "file"), "the file set fills what the config lacks"
    assert merged["Finish"] == ("Anodised", "configuration")
    assert merged["Weight"] == ("", "absent"), "not defined is not the same as blank"


def test_the_merge_is_case_insensitive_because_solidworks_property_names_are():
    merged = bom_handlers._merge_properties(
        {"description": "lower"}, {"DESCRIPTION": "upper"}, ["Description"]
    )
    assert merged["Description"] == ("lower", "configuration")


def test_a_component_with_no_model_document_yields_no_properties():
    assert bom_handlers._property_sets(None, "Default") == ({}, {})


# --- the fake tree ------------------------------------------------------------


class FakeConfig:
    def __init__(self, name: str, source: int | None = None, alternate: str = "",
                 use_alternate: bool = False) -> None:
        self.Name = name
        self.BOMPartNoSource = (
            source
            if source is not None
            else swconst.value("swBOMPartNumberSource_e", "swBOMPartNumber_DocumentName")
        )
        self.AlternateName = alternate
        self.UseAlternateNameInBOM = use_alternate


class FakePropertyManager:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def GetNames(self):  # noqa: N802
        return tuple(self.values)

    def Get5(self, name, use_cached):  # noqa: N802
        return (0, self.values.get(name, ""), self.values.get(name, ""), True)

    def Get(self, name):  # noqa: N802
        return self.values.get(name, "")


class FakeExtension:
    def __init__(self, by_config: dict[str, dict[str, str]]) -> None:
        self.by_config = by_config

    def CustomPropertyManager(self, configuration):  # noqa: N802
        return FakePropertyManager(self.by_config.get(configuration, {}))


class FakeModel:
    def __init__(self, doc_type: str, by_config: dict[str, dict[str, str]],
                 configs: dict[str, FakeConfig]) -> None:
        self.GetType = swconst.value(
            "swDocumentTypes_e", "swDocASSEMBLY" if doc_type == "assembly" else "swDocPART"
        )
        self.Extension = FakeExtension(by_config)
        self._configs = configs

    def GetConfigurationByName(self, name):  # noqa: N802
        return self._configs.get(name)


class FakeComponent:
    def __init__(self, name: str, path: str, model: FakeModel | None, *,
                 parent: FakeComponent | None = None, suppressed: bool = False,
                 excluded: bool = False, virtual: bool = False,
                 configuration: str = "Default") -> None:
        self.Name2 = name
        self._path = path
        self._model = model
        self._parent = parent
        self.ReferencedConfiguration = configuration
        self.ExcludeFromBOM = excluded
        self.IsVirtual = virtual
        self._suppressed = suppressed

    def GetPathName(self):  # noqa: N802
        return self._path

    def GetModelDoc2(self):  # noqa: N802
        return self._model

    def GetParent(self):  # noqa: N802
        return self._parent

    def IsSuppressed(self):  # noqa: N802
        return self._suppressed


class FakeAssembly:
    def __init__(self, components: list[FakeComponent]) -> None:
        self._components = components

    def GetComponents(self, top_level_only):  # noqa: N802
        if top_level_only:
            return tuple(c for c in self._components if c.GetParent() is None)
        return tuple(self._components)


WIDGET_PATH = r"C:\cad\widget.SLDPRT"
SUB_PATH = r"C:\cad\sub.SLDASM"


def _tree(**overrides: Any) -> FakeAssembly:
    """The probe's assembly: sub-1 holding two widgets, plus a third widget at the top."""
    widget_model = FakeModel(
        "part",
        {
            "": {"PartNo": "PN-FILE", "Description": "FILE LEVEL", "Vendor": "FileVendor"},
            "Default": {"Description": "CONFIG LEVEL", "Finish": "Anodised"},
        },
        {"Default": FakeConfig("Default")},
    )
    sub_model = FakeModel("assembly", {"": {}, "Default": {}}, {"Default": FakeConfig("Default")})

    sub = FakeComponent("sub-1", SUB_PATH, sub_model)
    return FakeAssembly(
        [
            sub,
            FakeComponent("sub-1/widget-1", WIDGET_PATH, widget_model, parent=sub, **overrides),
            FakeComponent("sub-1/widget-2", WIDGET_PATH, widget_model, parent=sub),
            FakeComponent("widget-1", WIDGET_PATH, widget_model),
        ]
    )


def _ctx(doc: Any, tmp_path: Path) -> OpContext:
    load_all_ops()
    return OpContext(
        session=object(),
        config=SwmcpConfig(allowed_roots=(tmp_path,)),
        checkpoints=None,
        spec=OPS["sw_bom_export"],
        request_id="test",
        doc=doc,
    )


def _run(tmp_path: Path, doc: Any = None, **kwargs: Any):
    return bom_handlers.bom_export(
        _ctx(doc if doc is not None else _tree(), tmp_path),
        BomExportArgs(output_path=str(tmp_path / "bom.csv"), **kwargs),
    )


def _rows(path: str) -> list[dict[str, str]]:
    return list(csv.DictReader(Path(path).read_text(encoding="utf-8").splitlines()))


# --- roll-up ------------------------------------------------------------------


def test_parts_only_rolls_every_widget_in_the_tree_into_one_line(tmp_path):
    result = _run(tmp_path)
    assert result.shape == "parts_only"
    assert [(line.part_number, line.quantity) for line in result.lines] == [("widget", 3)]
    assert result.instance_count == 4, "the subassembly is still an instance"
    assert result.counted_instances == 3, "and it is not a part, so it is not a line"


def test_top_level_only_lists_the_subassembly_and_not_its_contents(tmp_path):
    result = _run(tmp_path, shape="top_level_only")
    assert sorted((line.part_number, line.quantity) for line in result.lines) == [
        ("sub", 1),
        ("widget", 1),
    ]


def test_indented_numbers_by_position_and_groups_siblings(tmp_path):
    result = _run(tmp_path, shape="indented")
    numbered = [(line.item_number, line.part_number, line.quantity) for line in result.lines]
    assert numbered == [("1", "sub", 1), ("1.1", "widget", 2), ("2", "widget", 1)], numbered


def test_a_suppressed_component_is_left_out_of_the_quantity_but_not_the_matrix(tmp_path):
    result = _run(tmp_path, doc=_tree(suppressed=True))
    assert [line.quantity for line in result.lines] == [2]
    assert result.excluded_instances == 2, "the suppressed widget and the subassembly"

    matrix = _rows(result.matrix_path)
    suppressed = next(r for r in matrix if r["instance_name"] == "sub-1/widget-1")
    assert suppressed["in_bom"] == "False"
    assert suppressed["excluded_reason"] == "suppressed"
    assert suppressed["suppression"] == "suppressed"


def test_a_suppressed_component_can_be_counted_on_request(tmp_path):
    result = _run(tmp_path, doc=_tree(suppressed=True), include_suppressed=True)
    assert [line.quantity for line in result.lines] == [3]


def test_exclude_from_bom_is_honoured_and_the_reason_recorded(tmp_path):
    result = _run(tmp_path, doc=_tree(excluded=True))
    assert [line.quantity for line in result.lines] == [2]
    matrix = _rows(result.matrix_path)
    row = next(r for r in matrix if r["instance_name"] == "sub-1/widget-1")
    assert row["excluded_reason"] == "excluded_from_bom"
    assert row["excluded_from_bom"] == "True"


def test_an_assembly_left_out_of_a_parts_only_bill_says_so(tmp_path):
    result = _run(tmp_path)
    row = next(r for r in _rows(result.matrix_path) if r["instance_name"] == "sub-1")
    assert row["in_bom"] == "False"
    assert row["excluded_reason"] == "not part of a parts_only bill"


# --- the files ----------------------------------------------------------------


def test_the_bom_csv_carries_the_fixed_columns_then_the_discovered_ones(tmp_path):
    result = _run(tmp_path)
    header = _rows(result.saved_path)[0].keys()
    assert list(header)[: len(BOM_COLUMNS)] == list(BOM_COLUMNS)
    assert result.property_columns == ["Description", "Finish", "PartNo", "Vendor"]
    assert set(result.property_columns) <= set(header)


def test_the_bom_prints_the_configuration_value_not_the_file_one(tmp_path):
    """The row a person reads has to agree with what a native BOM would print."""
    result = _run(tmp_path)
    row = _rows(result.saved_path)[0]
    assert row["Description"] == "CONFIG LEVEL"
    assert row["PartNo"] == "PN-FILE"
    assert row["quantity"] == "3"


def test_the_matrix_names_every_instance_and_where_each_value_came_from(tmp_path):
    result = _run(tmp_path)
    matrix = _rows(result.matrix_path)
    assert len(matrix) == 4, "every instance, including the ones left out of the bill"
    assert list(matrix[0].keys())[: len(MATRIX_COLUMNS)] == list(MATRIX_COLUMNS)

    widget = next(r for r in matrix if r["instance_name"] == "widget-1")
    assert widget[f"Description{SOURCE_SUFFIX}"] == "configuration"
    assert widget[f"PartNo{SOURCE_SUFFIX}"] == "file"
    assert widget["Description"] == "CONFIG LEVEL"
    assert widget["depth"] == "0"

    nested = next(r for r in matrix if r["instance_name"] == "sub-1/widget-2")
    assert nested["depth"] == "1"
    assert nested["parent_instance"] == "sub-1"


def test_the_matrix_ties_each_instance_to_the_line_it_rolled_into(tmp_path):
    result = _run(tmp_path, shape="indented")
    matrix = {r["instance_name"]: r["item_number"] for r in _rows(result.matrix_path)}
    assert matrix["sub-1"] == "1"
    assert matrix["sub-1/widget-1"] == matrix["sub-1/widget-2"] == "1.1"
    assert matrix["widget-1"] == "2"


def test_the_property_source_tally_adds_up(tmp_path):
    result = _run(tmp_path)
    total = sum(result.property_sources.values())
    assert total == result.instance_count * len(result.property_columns)
    assert result.property_sources["configuration"] > 0
    assert result.property_sources["file"] > 0


def test_named_columns_are_used_verbatim_even_when_nothing_has_them(tmp_path):
    """A template has to stay stable across runs, so a missing column is still a column."""
    result = _run(tmp_path, properties=["Vendor", "Mass"])
    assert result.property_columns == ["Vendor", "Mass"]
    row = _rows(result.saved_path)[0]
    assert row["Vendor"] == "FileVendor"
    assert row["Mass"] == ""
    matrix = _rows(result.matrix_path)[0]
    assert matrix[f"Mass{SOURCE_SUFFIX}"] == "absent"


def test_the_matrix_can_be_turned_off_and_the_loss_is_stated(tmp_path):
    result = _run(tmp_path, matrix=False)
    assert result.matrix_path is None
    assert len(result.artifacts) == 1
    assert any("cannot be attributed" in w for w in result.warnings)


def test_both_files_are_reported_as_artifacts_with_hashes(tmp_path):
    result = _run(tmp_path)
    assert len(result.artifacts) == 2
    assert {a.path for a in result.artifacts} == {result.saved_path, result.matrix_path}
    assert all(a.sha256 and a.exists for a in result.artifacts)


def test_a_second_run_versions_rather_than_replacing(tmp_path):
    first = _run(tmp_path)
    second = _run(tmp_path)
    assert first.saved_path != second.saved_path
    assert Path(first.saved_path).is_file()
    assert "_v002" in Path(second.saved_path).name
    assert any("rather than the requested name" in w for w in second.warnings)


def test_an_output_outside_the_allowed_roots_is_refused(tmp_path):
    with pytest.raises(SwMcpError) as caught:
        bom_handlers.bom_export(
            _ctx(_tree(), tmp_path),
            BomExportArgs(output_path=r"C:\Windows\Temp\bom.csv"),
        )
    assert caught.value.envelope.code == "PATH_NOT_ALLOWED"


# --- part numbers -------------------------------------------------------------


def test_an_alternate_name_overrides_the_source_rule():
    config = FakeConfig("Default", alternate="PN-CUSTOM", use_alternate=True)
    model = FakeModel("part", {}, {"Default": config})
    number, rule = bom_handlers._part_number(
        FakeComponent("w-1", WIDGET_PATH, model), model, "Default", WIDGET_PATH
    )
    assert (number, rule) == ("PN-CUSTOM", "user_specified")


def test_the_configuration_name_rule_prints_the_configuration():
    config = FakeConfig(
        "Long", source=swconst.value("swBOMPartNumberSource_e", "swBOMPartNumber_ConfigurationName")
    )
    model = FakeModel("part", {}, {"Long": config})
    number, rule = bom_handlers._part_number(
        FakeComponent("w-1", WIDGET_PATH, model, configuration="Long"), model, "Long", WIDGET_PATH
    )
    assert (number, rule) == ("Long", "configuration_name")


def test_an_inherited_part_number_falls_back_and_says_it_did():
    """Never observed live, so it is labelled unresolved rather than reported as a fact."""
    config = FakeConfig(
        "Derived", source=swconst.value("swBOMPartNumberSource_e", "swBOMPartNumber_ParentName")
    )
    model = FakeModel("part", {}, {"Derived": config})
    number, rule = bom_handlers._part_number(
        FakeComponent("w-1", WIDGET_PATH, model, configuration="Derived"),
        model, "Derived", WIDGET_PATH,
    )
    assert (number, rule) == ("widget", "parent_name_unresolved")


def test_a_user_specified_source_with_no_alternate_name_reports_the_fallback():
    config = FakeConfig(
        "Default", source=swconst.value("swBOMPartNumberSource_e", "swBOMPartNumber_UserSpecified")
    )
    model = FakeModel("part", {}, {"Default": config})
    number, rule = bom_handlers._part_number(
        FakeComponent("w-1", WIDGET_PATH, model), model, "Default", WIDGET_PATH
    )
    assert (number, rule) == ("widget", "document_name"), "the applied rule, not the asked one"


def test_the_unresolved_fallback_reaches_the_result_as_a_warning(tmp_path):
    parent_rule = swconst.value("swBOMPartNumberSource_e", "swBOMPartNumber_ParentName")
    model = FakeModel(
        "part", {"": {}, "Default": {}}, {"Default": FakeConfig("Default", source=parent_rule)}
    )
    doc = FakeAssembly([FakeComponent("widget-1", WIDGET_PATH, model)])
    result = _run(tmp_path, doc=doc)
    assert any("inherited from" in w for w in result.warnings)


# --- the claim ----------------------------------------------------------------


def test_the_precursor_warning_is_unconditional(tmp_path):
    """IO-007 asks for it to be retained, so it is not a flag the caller can clear."""
    for kwargs in ({}, {"shape": "indented"}, {"matrix": False}, {"include_suppressed": True}):
        result = _run(tmp_path, **kwargs)
        assert result.precursor is True
        assert bom_handlers.PRECURSOR_WARNING in result.warnings


def test_the_warning_says_what_would_make_it_differ_from_a_native_bom():
    """A warning that only says "may be wrong" gives the reader nothing to check."""
    for topic in ("weldment", "quantity", "child-component", "native BOM"):
        assert topic in bom_handlers.PRECURSOR_WARNING


def test_an_empty_bill_is_reported_rather_than_written_silently(tmp_path):
    doc = FakeAssembly([FakeComponent("widget-1", WIDGET_PATH, None, excluded=True)])
    result = _run(tmp_path, doc=doc)
    assert result.line_count == 0
    assert any("No line qualified" in w for w in result.warnings)
    assert Path(result.saved_path).is_file(), "the header still lands, so the run is auditable"


def test_the_operation_is_a_read_only_side_effect_needing_an_assembly():
    spec = load_all_ops()["sw_bom_export"]
    assert spec.safety.kind == "non_model_side_effect"
    assert spec.safety.destructive is False
    assert spec.precondition == "assembly"
    assert spec.partially_satisfies == ("IO-007",)


def test_io_007_is_in_scope_and_its_limits_are_declared():
    from swmcp.catalog.scope import DECLARED_PARTIAL, IN_SCOPE_REQUIREMENTS

    assert "IO-007" in IN_SCOPE_REQUIREMENTS
    limitation = DECLARED_PARTIAL["IO-007"]
    assert "precursor" in limitation
    assert "Flattened" in limitation


def test_both_files_stay_plain_csv_that_any_reader_can_open(tmp_path):
    """The caveat lives in the result, not in a comment row.

    A leading '#' line would carry the warning into the artifact at the cost of breaking
    every plain csv reader that opens it, and an unparseable bill of materials is worse
    than one whose caveat sits beside it.
    """
    result = _run(tmp_path)
    for path in (result.saved_path, result.matrix_path):
        text = Path(path).read_text(encoding="utf-8")
        assert not text.startswith("#")
        rows = list(csv.DictReader(text.splitlines()))
        assert rows and all(None not in row for row in rows), "no ragged or commented rows"


def test_the_item_numbering_does_not_depend_on_the_order_components_arrive_in(tmp_path):
    """A live run caught this: GetComponents order is neither the tree's nor stable.

    Two assemblies built by the same sequence of inserts returned their top-level
    components in different orders, so the item numbers depended on something no caller
    can see. A BOM whose numbering shuffles between runs cannot be diffed against the
    last one, which is most of what a delivered BOM is for.
    """
    forward = _tree()
    backward = FakeAssembly(list(reversed(forward._components)))

    first = _run(tmp_path, doc=forward, shape="indented")
    second = _run(tmp_path, doc=backward, shape="indented")

    numbering = [(line.item_number, line.part_number, line.quantity) for line in first.lines]
    assert numbering == [("1", "sub", 1), ("1.1", "widget", 2), ("2", "widget", 1)]
    assert numbering == [
        (line.item_number, line.part_number, line.quantity) for line in second.lines
    ]


def test_a_flat_bill_is_ordered_by_part_number_too(tmp_path):
    forward = _run(tmp_path, shape="top_level_only")
    backward = _run(
        tmp_path,
        doc=FakeAssembly(list(reversed(_tree()._components))),
        shape="top_level_only",
    )
    assert [line.part_number for line in forward.lines] == ["sub", "widget"]
    assert [line.part_number for line in backward.lines] == ["sub", "widget"]
