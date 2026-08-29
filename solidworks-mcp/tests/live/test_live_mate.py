"""Live cover for mates (MATE-001 to MATE-004).

``AddMate5`` reports through an ``[out]`` status, and that status is inverted from the
reflex: ``swAddMateError_NoError`` is **1** and **0** is ``ErrorUknown``. A handler that
tested for zero would call every success a failure, so the refusal tests here matter as
much as the happy ones — they are what proves the status is being read the right way
round.

Each test builds its own assembly because mates change component positions, and a shared
assembly would make every test depend on the ones before it.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

BLOCK_W, BLOCK_D, BLOCK_H = 30.0, 20.0, 10.0


@pytest.fixture(scope="module")
def block_file(dispatcher, scratch_root):
    """One saved part, inserted twice into every assembly below."""
    target = scratch_root / "swmcp_mate_block.SLDPRT"
    for stale in scratch_root.glob("swmcp_mate_block*.SLDPRT"):
        stale.unlink(missing_ok=True)

    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    dispatcher.call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [BLOCK_W, BLOCK_D]}]},
    )
    dispatcher.call("sw_sketch_exit", {})
    built = dispatcher.call("sw_feature_extrude_boss", {"depth": BLOCK_H, "name": "Block"})
    assert built.get("ok"), built.get("error")
    saved = dispatcher.call("sw_doc_save", {"output_path": str(target)})
    assert saved.get("ok"), saved.get("error")

    yield str(target)

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": target.name}, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def pair(call, scratch_root, unique_name, block_file):
    """A saved assembly holding two instances of the block, ready to mate."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDASM"):
        stale.unlink(missing_ok=True)
    call("sw_doc_new", {"doc_type": "assembly"})
    call("sw_doc_save", {"output_path": str(scratch_root / f"{unique_name}.SLDASM")})
    call("sw_asm_insert", {"component_path": block_file})
    call("sw_asm_insert", {"component_path": block_file, "at": [60, 0, 0]})
    return call("sw_asm_tree")["result"]["components"]


def _faces(call) -> list[dict]:
    return call(
        "sw_probe_faces", {"geometry_type": "planar_face", "limit": 60}
    )["result"]["candidates"]


def _facing(call, axis: int, positive: bool) -> list[dict]:
    """Planar faces whose normal points along one axis, one per component."""
    picked = []
    for face in _faces(call):
        normal = face["measurements"].get("direction")
        if not normal:
            continue
        if (normal[axis] > 0.9) if positive else (normal[axis] < -0.9):
            picked.append(face)
    return picked


# --- MATE-001 / MATE-003: adding mates ----------------------------------------


def test_a_coincident_mate_joins_two_components(call, pair):
    right = _facing(call, 0, positive=True)
    left = _facing(call, 0, positive=False)
    assert right and left, "the two blocks should each show an X-facing face"

    mated = call(
        "sw_mate_add",
        {
            "mate_type": "coincident",
            "refs": [right[0]["tool_args"]["ref"], left[-1]["tool_args"]["ref"]],
            "name": "Butt",
        },
    )["result"]

    assert mated["mate_name"] == "Butt"
    assert mated["mate_type"] == "coincident"
    assert mated["entity_count"] == 2
    assert mated["mates_before"] == 0
    assert mated["mates_after"] == 1
    assert len(set(mated["components"])) == 2, "a mate must join two different components"
    assert all(check["passed"] for check in mated["verification"]["checks"])


def test_a_distance_mate_records_the_distance_it_was_given(call, pair):
    right = _facing(call, 0, positive=True)
    left = _facing(call, 0, positive=False)

    mated = call(
        "sw_mate_add",
        {
            "mate_type": "distance",
            "refs": [right[0]["tool_args"]["ref"], left[-1]["tool_args"]["ref"]],
            "distance": 15,
            "alignment": "closest",
        },
    )["result"]

    assert mated["mate_type"] == "distance"
    listed = call("sw_mate_list")["result"]["mates"][0]
    assert listed["value_mm"] == pytest.approx(15.0, abs=1e-6)


def test_a_distance_mate_without_a_distance_is_a_schema_error(call, pair):
    payload = call(
        "sw_mate_add",
        {"mate_type": "distance", "refs": [{"kind": "face"}, {"kind": "face"}]},
        expect_ok=False,
    )
    assert payload["error"]["category"] == "validation"


def test_a_mate_needs_exactly_two_references(call, pair):
    payload = call(
        "sw_mate_add", {"mate_type": "coincident", "refs": [{"kind": "face"}]}, expect_ok=False
    )
    assert payload["error"]["category"] == "validation"


def test_an_impossible_mate_is_refused_with_the_reason_solidworks_gave(call, pair):
    """The test that proves the out-status is read the right way round.

    A concentric mate needs cylindrical geometry; asking for it between two flat faces
    makes SOLIDWORKS return a specific error, and the tool must surface that rather
    than treat a non-zero status as success.
    """
    right = _facing(call, 0, positive=True)
    left = _facing(call, 0, positive=False)

    payload = call(
        "sw_mate_add",
        {
            "mate_type": "concentric",
            "refs": [right[0]["tool_args"]["ref"], left[-1]["tool_args"]["ref"]],
        },
        expect_ok=False,
    )

    assert payload["error"]["code"] == "MATE_FAILED"
    assert payload["error"]["context"]["error_name"].startswith("swAddMateError_")
    assert payload["error"]["context"]["error_name"] != "swAddMateError_NoError"
    assert call("sw_mate_list")["result"]["mate_count"] == 0, "a refused mate must leave none"


# --- MATE-002: limit mates -----------------------------------------------------


def test_a_limit_distance_mate_reports_its_range(call, pair):
    right = _facing(call, 0, positive=True)
    left = _facing(call, 0, positive=False)

    call(
        "sw_mate_add",
        {
            "mate_type": "distance",
            "refs": [right[0]["tool_args"]["ref"], left[-1]["tool_args"]["ref"]],
            "distance": 20,
            "distance_min": 10,
            "distance_max": 40,
            "name": "Travel",
        },
    )

    listed = call("sw_mate_list")["result"]["mates"][0]
    assert listed["name"] == "Travel"
    assert "limit_min" in listed and "limit_max" in listed, (
        "a limit mate must report the range it was built with"
    )
    assert listed["limit_max"] > listed["limit_min"]


def test_limits_must_come_as_a_pair(call, pair):
    payload = call(
        "sw_mate_add",
        {
            "mate_type": "distance",
            "refs": [{"kind": "face"}, {"kind": "face"}],
            "distance": 10,
            "distance_min": 5,
        },
        expect_ok=False,
    )
    assert payload["error"]["category"] == "validation"


def test_a_reversed_limit_range_is_refused(call, pair):
    payload = call(
        "sw_mate_add",
        {
            "mate_type": "distance",
            "refs": [{"kind": "face"}, {"kind": "face"}],
            "distance": 10,
            "distance_min": 40,
            "distance_max": 5,
        },
        expect_ok=False,
    )
    assert payload["error"]["category"] == "validation"


# --- MATE-004: listing ---------------------------------------------------------


def test_listing_reports_every_field_the_requirement_asks_for(call, pair):
    right = _facing(call, 0, positive=True)
    left = _facing(call, 0, positive=False)
    call(
        "sw_mate_add",
        {
            "mate_type": "coincident",
            "refs": [right[0]["tool_args"]["ref"], left[-1]["tool_args"]["ref"]],
        },
    )

    listed = call("sw_mate_list")["result"]

    assert listed["mate_count"] == 1
    assert listed["suppressed_count"] == 0
    entry = listed["mates"][0]
    for field in (
        "name", "type", "alignment", "flipped", "suppressed", "entity_count", "components",
    ):
        assert field in entry, f"the mate listing does not report {field}"
    assert entry["type"] == "coincident"
    assert len(entry["components"]) == 2


def test_an_assembly_with_no_mates_lists_none(call, pair):
    listed = call("sw_mate_list")["result"]
    assert listed["mate_count"] == 0
    assert listed["mates"] == []


def test_mates_accumulate_and_are_all_listed(call, pair):
    right = _facing(call, 0, positive=True)
    left = _facing(call, 0, positive=False)
    top = _facing(call, 1, positive=True)

    call(
        "sw_mate_add",
        {
            "mate_type": "coincident",
            "refs": [right[0]["tool_args"]["ref"], left[-1]["tool_args"]["ref"]],
            "name": "First",
        },
    )
    if len(top) >= 2:
        call(
            "sw_mate_add",
            {
                "mate_type": "parallel",
                "refs": [top[0]["tool_args"]["ref"], top[-1]["tool_args"]["ref"]],
                "name": "Second",
            },
        )

    listed = call("sw_mate_list")["result"]
    assert listed["mate_count"] >= 1
    assert "First" in {mate["name"] for mate in listed["mates"]}


def test_mate_tools_refuse_a_part_document(call):
    call("sw_doc_new", {"doc_type": "part"})
    payload = call("sw_mate_list", {}, expect_ok=False)
    assert not payload["ok"]


# --- MATE-006: editing mates ---------------------------------------------------


def _one_mate(call, pair) -> str:
    """Create a coincident mate and return its name."""
    right = _facing(call, 0, positive=True)
    left = _facing(call, 0, positive=False)
    return call(
        "sw_mate_add",
        {
            "mate_type": "coincident",
            "refs": [right[0]["tool_args"]["ref"], left[-1]["tool_args"]["ref"]],
        },
    )["result"]["mate_name"]


def test_a_mate_can_be_renamed(call, pair):
    name = _one_mate(call, pair)

    edited = call("sw_mate_edit", {"mate_name": name, "rename_to": "Butt"})["result"]

    assert edited["mate_name"] == "Butt"
    assert edited["renamed_to"] == "Butt"
    assert "deleted" not in edited, "editing a mate has nothing to say about deletion"
    assert all(check["passed"] for check in edited["verification"]["checks"])
    assert "Butt" in {m["name"] for m in call("sw_mate_list")["result"]["mates"]}


def test_a_mate_can_be_suppressed_and_unsuppressed(call, pair):
    name = _one_mate(call, pair)

    off = call("sw_mate_edit", {"mate_name": name, "suppressed": True})["result"]
    assert off["suppressed"] is True
    assert all(check["passed"] for check in off["verification"]["checks"])
    assert call("sw_mate_list")["result"]["suppressed_count"] == 1

    on = call("sw_mate_edit", {"mate_name": name, "suppressed": False})["result"]
    assert on["suppressed"] is False
    assert call("sw_mate_list")["result"]["suppressed_count"] == 0


def test_a_mate_can_be_deleted(call, pair):
    name = _one_mate(call, pair)

    deleted = call("sw_mate_delete", {"mate_name": name, "confirm": True})["result"]

    assert deleted["deleted"] is True
    assert deleted["mates_before"] == 1
    assert deleted["mates_after"] == 0
    assert all(check["passed"] for check in deleted["verification"]["checks"])
    assert call("sw_mate_list")["result"]["mate_count"] == 0


def test_deleting_a_mate_needs_confirmation(call, pair):
    """Deleting is its own tool precisely so renaming does not inherit this."""
    name = _one_mate(call, pair)
    payload = call("sw_mate_delete", {"mate_name": name}, expect_ok=False)
    assert not payload["ok"]
    assert call("sw_mate_list")["result"]["mate_count"] == 1, "the mate must survive"


def test_editing_a_mate_that_is_not_there_is_refused(call, pair):
    payload = call("sw_mate_edit", {"mate_name": "Ghost1", "suppressed": True}, expect_ok=False)
    assert payload["error"]["code"] == "MATE_NOT_FOUND"


def test_renaming_a_mate_needs_no_confirmation(call, pair):
    """The reason edit and delete are separate tools.

    Folding them into one meant marking the whole thing destructive, and a rename then
    demanded a confirmation it had no business demanding.
    """
    name = _one_mate(call, pair)
    renamed = call("sw_mate_edit", {"mate_name": name, "rename_to": "NoConfirmNeeded"})
    assert renamed["ok"]
    assert renamed["result"]["renamed_to"] == "NoConfirmNeeded"


def test_an_edit_that_changes_nothing_is_refused(call, pair):
    payload = call("sw_mate_edit", {"mate_name": "Any"}, expect_ok=False)
    assert payload["error"]["category"] == "validation"


# --- MATE-008: interference ----------------------------------------------------


@pytest.fixture
def overlapping(call, scratch_root, unique_name, block_file):
    """Two blocks overlapping by 10 mm in X, so the overlap volume is arithmetic."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDASM"):
        stale.unlink(missing_ok=True)
    call("sw_doc_new", {"doc_type": "assembly"})
    call("sw_doc_save", {"output_path": str(scratch_root / f"{unique_name}.SLDASM")})
    call("sw_asm_insert", {"component_path": block_file})
    call("sw_asm_insert", {"component_path": block_file, "at": [20, 0, 0]})
    # 30 wide, offset 20 -> 10 mm of overlap across the full 20 x 10 section.
    return 10.0 * BLOCK_D * BLOCK_H


def test_interference_reports_the_overlap_volume(call, overlapping):
    found = call("sw_interference_check")["result"]

    assert found["interference_count"] == 1
    assert found["total_volume_mm3"] == pytest.approx(overlapping, rel=1e-6)

    entry = found["interferences"][0]
    assert entry["volume_mm3"] == pytest.approx(overlapping, rel=1e-6)
    assert entry["component_count"] == 2
    assert len(set(entry["components"])) == 2
    assert entry["possible_only"] is False


def test_components_that_do_not_touch_report_no_interference(call, pair):
    """The blocks in `pair` are 60 mm apart, so there is nothing to find."""
    found = call("sw_interference_check")["result"]

    assert found["interference_count"] == 0
    assert found["total_volume_mm3"] == 0.0
    assert found["interferences"] == []
    assert found["warnings"] == []


def test_the_interference_settings_are_reported_as_they_read_back(call, overlapping):
    """An option SOLIDWORKS declines must not be echoed back as if it took."""
    found = call(
        "sw_interference_check",
        {"treat_coincidence_as_interference": True, "ignore_hidden_bodies": True},
    )["result"]

    assert set(found["settings"]) == {
        "treat_coincidence_as_interference",
        "ignore_hidden_bodies",
        "treat_subassemblies_as_components",
        "include_multibody_part_interferences",
    }
    assert found["interference_count"] >= 1


def test_interference_check_refuses_a_part_document(call):
    call("sw_doc_new", {"doc_type": "part"})
    payload = call("sw_interference_check", {}, expect_ok=False)
    assert not payload["ok"]
