"""Live cover for drawings (DRW-001 to DRW-003).

The sheet is measured in every test that creates one, because a sheet of zero area is
accepted silently by ``NewDocument`` and only bites at the next call — where it presents
as SOLIDWORKS hanging rather than as an error. Asserting the size at creation is what
turns that into a test failure instead of a wedged session.

One part is built for the whole module. Drawings reference the model on disk, so it has
to be saved, and rebuilding it per test would pay the save cost every time.
"""

from __future__ import annotations

import pytest

# Not marked slow: the whole module runs in ~41s, because it places views on a
# saved part rather than building geometry per test. It belongs in the quick pass.
pytestmark = [pytest.mark.live]

WIDTH, DEPTH, HEIGHT = 60.0, 40.0, 20.0

#: A-size in millimetres, which is what SOLIDWORKS reports for swDwgPaperAsize here.
A_SIZE_MM = (279.4, 215.9)


@pytest.fixture(scope="module")
def model_file(dispatcher, scratch_root):
    """One saved part for every drawing below to reference."""
    target = scratch_root / "swmcp_drw_model.SLDPRT"
    for stale in scratch_root.glob("swmcp_drw_model*.SLDPRT"):
        stale.unlink(missing_ok=True)

    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    dispatcher.call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [WIDTH, DEPTH]}]},
    )
    dispatcher.call("sw_sketch_exit", {})
    built = dispatcher.call("sw_feature_extrude_boss", {"depth": HEIGHT, "name": "Block"})
    assert built.get("ok"), built.get("error")
    saved = dispatcher.call("sw_doc_save", {"output_path": str(target)})
    assert saved.get("ok"), saved.get("error")

    yield str(target)

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": target.name}, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def drawing(call, model_file):
    """A fresh A-size drawing, with its sheet measured before anything is placed on it."""
    result = call("sw_drawing_new", {"model_path": model_file})["result"]
    assert result["width_mm"] == pytest.approx(A_SIZE_MM[0], abs=0.1)
    assert result["height_mm"] == pytest.approx(A_SIZE_MM[1], abs=0.1)
    title = result["document"]["title"]
    yield result
    call("sw_doc_close", {"document": {"title": title}, "save_first": "discard",
                          "confirm": True}, expect_ok=False)


@pytest.fixture(scope="module")
def dimensioned_model(dispatcher, scratch_root):
    """A part whose sketch carries a named dimension, so DRW-004 has something to find.

    The plain model_file deliberately has none: importing from it is what proves the
    "nothing to import" path is reported rather than passed over as success.
    """
    target = scratch_root / "swmcp_drw_dimensioned.SLDPRT"
    for stale in scratch_root.glob("swmcp_drw_dimensioned*.SLDPRT"):
        stale.unlink(missing_ok=True)

    assert dispatcher.call("sw_doc_new", {"doc_type": "part"}).get("ok")
    dispatcher.call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = dispatcher.call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [WIDTH, DEPTH]}]},
    )
    ids = [entry["sketch_local_id"] for entry in added["result"]["created"]]
    dispatcher.call(
        "sw_sketch_add_dimensions",
        {
            "dimensions": [
                {
                    "type": "distance",
                    "segment_ids": [ids[0]],
                    "value": WIDTH,
                    "place_at": [0.05, -0.02, 0],
                    "name": "BlockWidth",
                }
            ]
        },
    )
    dispatcher.call("sw_sketch_exit", {})
    assert dispatcher.call(
        "sw_feature_extrude_boss", {"depth": HEIGHT, "name": "Block"}
    ).get("ok")
    assert dispatcher.call("sw_doc_save", {"output_path": str(target)}).get("ok")

    yield str(target)

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": target.name}, "save_first": "discard", "confirm": True},
    )

# --- DRW-001: creating the drawing ----------------------------------------------


def test_a_new_drawing_reports_a_sheet_with_real_dimensions(call, model_file):
    """The check that would have caught the zero-by-zero sheet immediately."""
    result = call("sw_drawing_new", {"model_path": model_file})["result"]

    assert result["paper_size"] == "a"
    assert result["width_mm"] > 0 and result["height_mm"] > 0
    assert result["width_mm"] == pytest.approx(A_SIZE_MM[0], abs=0.1)
    assert result["height_mm"] == pytest.approx(A_SIZE_MM[1], abs=0.1)
    assert result["scale"] == [1.0, 1.0]
    assert result["document"]["doc_type"] == "drawing"
    assert result["template_source"] == "default_preference"

    call("sw_doc_close", {"document": {"title": result["document"]["title"]},
                          "save_first": "discard", "confirm": True})


@pytest.mark.parametrize("paper,expected", [("a4", (297.0, 210.0)), ("a3", (420.0, 297.0))])
def test_the_requested_paper_size_is_the_one_measured_back(call, paper, expected):
    """A size that was asked for but not applied is the failure this catches."""
    result = call("sw_drawing_new", {"paper_size": paper})["result"]

    assert result["paper_size"] == paper
    assert result["width_mm"] == pytest.approx(expected[0], abs=1.0)
    assert result["height_mm"] == pytest.approx(expected[1], abs=1.0)

    call("sw_doc_close", {"document": {"title": result["document"]["title"]},
                          "save_first": "discard", "confirm": True})


def test_a_custom_sheet_is_created_at_the_size_it_was_given(call):
    result = call(
        "sw_drawing_new", {"paper_size": "custom", "width": 400, "height": 300}
    )["result"]

    assert result["width_mm"] == pytest.approx(400.0, abs=1.0)
    assert result["height_mm"] == pytest.approx(300.0, abs=1.0)

    call("sw_doc_close", {"document": {"title": result["document"]["title"]},
                          "save_first": "discard", "confirm": True})


def test_a_custom_sheet_without_dimensions_is_refused_by_the_schema(call):
    """Never reaches SOLIDWORKS: this is the argument that spins it."""
    payload = call("sw_drawing_new", {"paper_size": "custom"}, expect_ok=False)

    assert payload["error"]["category"] == "validation"


def test_a_missing_model_is_refused_before_a_drawing_is_made(call):
    payload = call(
        "sw_drawing_new", {"model_path": "C:/nowhere/absent.SLDPRT"}, expect_ok=False
    )
    assert payload["error"]["code"] == "MODEL_NOT_FOUND"


def test_the_sheet_can_be_named(call, model_file):
    result = call(
        "sw_drawing_new", {"model_path": model_file, "sheet_name": "Detail"}
    )["result"]

    assert result["sheet_name"] == "Detail"

    call("sw_doc_close", {"document": {"title": result["document"]["title"]},
                          "save_first": "discard", "confirm": True})


# --- DRW-002: placing views ------------------------------------------------------


def test_a_model_view_lands_on_the_sheet_and_references_the_model(call, drawing, model_file):
    placed = call(
        "sw_drawing_view_add",
        {"view_type": "model", "orientation": "front", "model_path": model_file},
    )["result"]

    assert placed["views_before"] == 0
    assert placed["views_after"] == 1
    assert len(placed["views_created"]) == 1

    view = placed["views_created"][0]
    assert view["type"] == "named"
    assert view["referenced_document"].lower() == model_file.lower()
    assert view["referenced_configuration"] == "Default"
    assert all(check["passed"] for check in placed["verification"]["checks"])


def test_a_view_goes_where_it_was_asked_to_go(call, drawing, model_file):
    placed = call(
        "sw_drawing_view_add",
        {"view_type": "model", "orientation": "top", "at": [100, 80],
         "model_path": model_file},
    )["result"]

    position = placed["views_created"][0]["position_mm"]
    assert position[0] == pytest.approx(100.0, abs=0.5)
    assert position[1] == pytest.approx(80.0, abs=0.5)


def test_an_unplaced_view_would_fail_the_on_sheet_check(call, drawing, model_file):
    """A view placed past the sheet edge is not an error SOLIDWORKS reports itself."""
    placed = call(
        "sw_drawing_view_add",
        {"view_type": "model", "orientation": "front", "at": [5000, 5000],
         "model_path": model_file},
    )["result"]

    on_sheet = [c for c in placed["verification"]["checks"] if c["name"] == "views_land_on_the_sheet"]
    assert on_sheet and on_sheet[0]["passed"] is False, (
        "a view 5 m off the sheet must be reported, not silently accepted"
    )


def test_a_standard_three_view_places_exactly_three(call, drawing, model_file):
    placed = call(
        "sw_drawing_view_add", {"view_type": "standard_3", "model_path": model_file}
    )["result"]

    assert len(placed["views_created"]) == 3
    assert placed["views_after"] == 3
    types = sorted(view["type"] for view in placed["views_created"])
    assert types == ["named", "projected", "projected"], types
    assert all(
        view["referenced_document"].lower() == model_file.lower()
        for view in placed["views_created"]
    )
    assert all(check["passed"] for check in placed["verification"]["checks"])


def test_every_standard_orientation_is_accepted(call, drawing, model_file):
    """Ten named views, each of which must exist in the model under that exact name."""
    for orientation in ("front", "back", "left", "right", "top", "bottom",
                        "isometric", "trimetric", "dimetric"):
        placed = call(
            "sw_drawing_view_add",
            {"view_type": "model", "orientation": orientation, "model_path": model_file},
        )["result"]
        assert len(placed["views_created"]) == 1, orientation


def test_a_view_on_an_empty_sheet_needs_a_model(call, drawing):
    """With no view to inherit the model from, the argument is required, not guessed."""
    payload = call("sw_drawing_view_add", {"view_type": "model"}, expect_ok=False)

    assert payload["error"]["code"] == "MODEL_NOT_GIVEN"


def test_the_model_is_inherited_from_an_existing_view(call, drawing, model_file):
    call("sw_drawing_view_add", {"view_type": "model", "orientation": "front",
                                 "model_path": model_file})
    placed = call("sw_drawing_view_add", {"view_type": "model", "orientation": "top"})[
        "result"
    ]

    assert placed["model_path"].lower() == model_file.lower()
    assert placed["views_after"] == 2


def test_a_standard_three_view_refuses_a_position(call, drawing):
    payload = call(
        "sw_drawing_view_add", {"view_type": "standard_3", "at": [100, 100]},
        expect_ok=False,
    )
    assert payload["error"]["category"] == "validation"


# --- DRW-003: inspecting the drawing ---------------------------------------------


def test_an_empty_drawing_lists_its_sheet_and_no_views(call, drawing):
    listed = call("sw_drawing_list")["result"]

    assert listed["sheet_count"] == 1
    assert listed["view_count"] == 0
    sheet = listed["sheets"][0]
    assert sheet["active"] is True
    assert sheet["width_mm"] == pytest.approx(A_SIZE_MM[0], abs=0.1)
    assert sheet["paper_size"] == "a"


def test_the_listing_reports_every_view_with_its_evidence(call, drawing, model_file):
    call("sw_drawing_view_add", {"view_type": "standard_3", "model_path": model_file})
    listed = call("sw_drawing_list")["result"]

    assert listed["sheet_count"] == 1
    assert listed["view_count"] == 3
    for view in listed["sheets"][0]["views"]:
        assert view["name"]
        assert view["type"] in {"named", "projected"}
        assert view["referenced_document"].lower() == model_file.lower()
        assert view["referenced_configuration"] == "Default"
        assert len(view["position_mm"]) == 2
        assert len(view["outline_mm"]) == 4
        assert view["scale_decimal"] > 0


def test_the_sheet_is_never_reported_as_one_of_the_views(call, drawing, model_file):
    """GetFirstView returns the sheet; listing it as a view would be wrong."""
    call(
        "sw_drawing_view_add",
        {"view_type": "model", "orientation": "front", "model_path": model_file},
    )
    listed = call("sw_drawing_list")["result"]

    assert listed["view_count"] == 1
    assert all(view["type"] != "sheet" for view in listed["sheets"][0]["views"])
    assert all(view["referenced_document"] for view in listed["sheets"][0]["views"])


def test_listing_refuses_a_part(call, model_file):
    """The precondition is a drawing; a part must be refused rather than half-answered."""
    call("sw_doc_open", {"path": model_file})
    payload = call("sw_drawing_list", expect_ok=False)
    assert payload["error"]["category"] in {"validation", "precondition"}


# --- DRW-007: extra sheets --------------------------------------------------------


def test_a_second_sheet_is_added_and_measured(call, drawing):
    added = call("sw_drawing_sheet_add", {"name": "Sheet2", "paper_size": "a4"})["result"]

    assert added["sheet_name"] == "Sheet2"
    assert added["sheets_before"] == 1
    assert added["sheets_after"] == 2
    assert added["sheet_names"] == ["Sheet1", "Sheet2"]
    assert added["paper_size"] == "a4"
    assert added["width_mm"] == pytest.approx(297.0, abs=1.0)
    assert added["height_mm"] == pytest.approx(210.0, abs=1.0)
    assert added["active_sheet"] == "Sheet2"
    assert all(check["passed"] for check in added["verification"]["checks"])


def test_a_sheet_can_be_added_without_stealing_focus(call, drawing):
    added = call(
        "sw_drawing_sheet_add", {"name": "Sheet2", "paper_size": "a3", "activate": False}
    )["result"]

    assert added["sheets_after"] == 2
    assert added["active_sheet"] == "Sheet1", "activate=false must put the old sheet back"
    assert all(check["passed"] for check in added["verification"]["checks"])


def test_a_duplicate_sheet_name_is_refused(call, drawing):
    payload = call("sw_drawing_sheet_add", {"name": "Sheet1"}, expect_ok=False)

    assert payload["error"]["code"] == "SHEET_NAME_TAKEN"


def test_a_custom_sheet_without_a_size_never_reaches_solidworks(call, drawing):
    payload = call(
        "sw_drawing_sheet_add", {"name": "Sheet2", "paper_size": "custom"}, expect_ok=False
    )
    assert payload["error"]["category"] == "validation"


def test_a_new_sheet_is_listed_with_the_others(call, drawing):
    call("sw_drawing_sheet_add", {"name": "Sheet2", "paper_size": "a4"})
    listed = call("sw_drawing_list")["result"]

    assert listed["sheet_count"] == 2
    assert listed["active_sheet"] == "Sheet2"
    assert {sheet["name"] for sheet in listed["sheets"]} == {"Sheet1", "Sheet2"}


# --- DRW-004: importing model items -----------------------------------------------


def test_model_dimensions_are_imported_and_reported(call, drawing, dimensioned_model):
    call("sw_drawing_view_add", {"view_type": "standard_3", "model_path": dimensioned_model})
    imported = call("sw_drawing_annotate_model", {"kinds": ["dimensions"]})["result"]

    assert imported["imported"] > 0, "a dimensioned part must yield dimensions"
    assert imported["annotations_after"] > imported["annotations_before"]
    assert all(item["type"] == "dimension" for item in imported["annotations"])
    assert all(check["passed"] for check in imported["verification"]["checks"])


def test_even_a_part_with_no_sketch_dimensions_yields_its_feature_ones(call, drawing, model_file):
    """A part built through the API is never truly undimensioned.

    The block's sketch was drawn without dimensions, but the extrude carries its own
    depth, and that is importable. Asserting zero here was wrong, and the tool reporting
    two is correct.
    """
    call("sw_drawing_view_add", {"view_type": "standard_3", "model_path": model_file})
    imported = call("sw_drawing_annotate_model", {"kinds": ["dimensions"]})["result"]

    assert imported["imported"] > 0
    # An unsaved drawing cannot be snapshotted, so the checkpoint layer warns; what must
    # be absent is the "nothing to import" warning, since something was imported.
    assert not any("marked for drawings" in w for w in imported["warnings"])
    assert all(check["passed"] for check in imported["verification"]["checks"])


def test_importing_into_an_empty_drawing_imports_nothing_and_says_so(call, drawing):
    """The path that must never be dressed up as success: no views, so nothing to fill."""
    imported = call("sw_drawing_annotate_model", {})["result"]

    assert imported["imported"] == 0
    assert imported["kinds"] == ["dimensions"]
    assert any("marked for drawings" in w for w in imported["warnings"])
    assert all(check["passed"] for check in imported["verification"]["checks"])


# --- DRW-005: notes and centre marks ----------------------------------------------


def test_a_note_lands_on_the_sheet_with_its_text(call, drawing):
    added = call("sw_drawing_note_add", {"text": "FINISH ALL OVER", "at": [50, 30]})["result"]

    assert added["annotation"] == "note"
    assert added["text"] == "FINISH ALL OVER"
    assert added["name"]
    assert added["annotations_before"] == 0
    assert added["annotations_after"] == 1
    assert added["position_mm"][0] == pytest.approx(50.0, abs=1.0)
    assert added["position_mm"][1] == pytest.approx(30.0, abs=1.0)
    assert all(check["passed"] for check in added["verification"]["checks"])


def test_a_note_without_text_is_refused_by_the_schema(call, drawing):
    payload = call("sw_drawing_note_add", {"annotation": "note"}, expect_ok=False)
    assert payload["error"]["category"] == "validation"


def test_a_centre_mark_with_nothing_selected_is_refused(call, drawing, model_file):
    call("sw_drawing_view_add", {"view_type": "model", "model_path": model_file})
    call("sw_selection_set", {"refs": [], "clear_first": True})
    payload = call(
        "sw_drawing_note_add", {"annotation": "center_mark"}, expect_ok=False
    )

    assert payload["error"]["code"] == "NOTHING_SELECTED"


def test_notes_accumulate_and_are_all_counted(call, drawing):
    for index in range(3):
        call("sw_drawing_note_add", {"text": f"NOTE {index}", "at": [40 + index * 30, 30]})

    reviewed = call("sw_drawing_review", {"require_views": 0})["result"]
    assert reviewed["note_count"] == 3
    assert reviewed["annotation_count"] == 3


# --- DRW-006: the bill of materials -----------------------------------------------


def test_a_bom_lists_the_part_it_draws(call, drawing, model_file):
    call("sw_drawing_view_add", {"view_type": "model", "model_path": model_file})
    table = call("sw_drawing_table_add", {"bom_type": "parts_only"})["result"]

    assert table["row_count"] >= 2, "a header row and at least one part"
    assert table["column_count"] >= 3
    assert table["tables_after"] > table["tables_before"]
    assert "PART NUMBER" in [title.upper() for title in table["column_titles"]]
    # The evidence that matters: the part's own name, read out of a cell.
    flattened = [cell.lower() for row in table["rows"] for cell in row]
    assert any("swmcp_drw_model" in cell for cell in flattened), flattened
    assert all(check["passed"] for check in table["verification"]["checks"])


def test_a_bom_needs_a_view_to_anchor_to(call, drawing):
    payload = call("sw_drawing_table_add", {}, expect_ok=False)
    assert payload["error"]["code"] == "NO_VIEW_FOR_TABLE"


def test_the_table_is_counted_by_the_review(call, drawing, model_file):
    call("sw_drawing_view_add", {"view_type": "model", "model_path": model_file})
    call("sw_drawing_table_add", {})
    reviewed = call("sw_drawing_review", {})["result"]

    assert reviewed["table_count"] == 1


# --- DRW-008 and DRW-010: reviewing without overclaiming --------------------------


def test_the_review_counts_what_is_on_the_drawing(call, drawing, model_file):
    call("sw_drawing_view_add", {"view_type": "standard_3", "model_path": model_file})
    call("sw_drawing_note_add", {"text": "DO NOT SCALE"})
    reviewed = call("sw_drawing_review", {})["result"]

    assert reviewed["sheet_count"] == 1
    assert reviewed["view_count"] == 3
    assert reviewed["note_count"] == 1
    assert reviewed["dangling_count"] == 0
    assert reviewed["passed"] is True
    assert reviewed["findings"] == []


def test_an_empty_sheet_fails_the_minimum_view_count(call, drawing):
    reviewed = call("sw_drawing_review", {"require_views": 1})["result"]

    assert reviewed["passed"] is False
    assert any("view(s), fewer than" in f["detail"] for f in reviewed["findings"])
    assert all(f["read_from"] for f in reviewed["findings"]), "each finding names its source"


def test_a_missing_dimension_minimum_is_reported(call, drawing, model_file):
    call("sw_drawing_view_add", {"view_type": "standard_3", "model_path": model_file})
    reviewed = call("sw_drawing_review", {"require_dimensions": 4})["result"]

    assert reviewed["passed"] is False
    assert any("dimension(s), fewer than" in f["detail"] for f in reviewed["findings"])


def test_a_sheet_with_no_format_is_a_warning_not_a_block(call, drawing, model_file):
    """The drawing this server creates has no title block, and that is said plainly."""
    call("sw_drawing_view_add", {"view_type": "model", "model_path": model_file})
    reviewed = call("sw_drawing_review", {"require_sheet_format": True})["result"]

    formats = [f for f in reviewed["findings"] if "sheet format" in f["detail"]]
    assert formats and formats[0]["severity"] == "warn"
    assert reviewed["passed"] is True, "a missing title block must not block on its own"


def test_the_review_never_claims_to_replace_a_human(call, drawing, model_file):
    """DRW-010. Passing its own counts is not the same as the drawing being right."""
    call("sw_drawing_view_add", {"view_type": "standard_3", "model_path": model_file})
    reviewed = call("sw_drawing_review", {})["result"]

    assert reviewed["passed"] is True
    assert reviewed["visual_review_required"] is True
    assert any("a person still has to look at it" in w for w in reviewed["warnings"])
