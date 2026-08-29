"""Live cover for the first P2 vertical: assemblies (ASM-001, ASM-002, ASM-003).

An assembly needs a part on disk to insert, so the module builds one 30 x 20 x 10 mm
block and reuses it — the same shared-document economy the rest of the live suite uses,
extended to a shared *component file*.

The state calls are the interesting ones. ``FixComponent`` and ``UnfixComponent`` are
void, ``SetVisibility`` is void, and ``SetSuppression2`` returns a status that is 2 both
when it suppresses and when it resolves — so none of them can be believed, and every
check below re-reads the component instead.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

BLOCK_W, BLOCK_D, BLOCK_H = 30.0, 20.0, 10.0


@pytest.fixture(scope="module")
def block_file(dispatcher, scratch_root):
    """One saved part, used as the component every test inserts."""
    target = scratch_root / "swmcp_asm_block.SLDPRT"
    for stale in scratch_root.glob("swmcp_asm_block*.SLDPRT"):
        stale.unlink(missing_ok=True)

    # The new part is the active document, so these run against it without targeting.
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
def assembly(call, scratch_root, unique_name, block_file):
    """A fresh, saved assembly per test — component state is what these tests mutate."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDASM"):
        stale.unlink(missing_ok=True)
    call("sw_doc_new", {"doc_type": "assembly"})
    call("sw_doc_save", {"output_path": str(scratch_root / f"{unique_name}.SLDASM")})
    return block_file


# --- ASM-001: insert ----------------------------------------------------------


def test_inserting_a_component_puts_it_in_the_tree(call, assembly):
    inserted = call("sw_asm_insert", {"component_path": assembly})["result"]

    assert inserted["components_before"] == 0
    assert inserted["components_after"] == 1
    assert inserted["component_name"].startswith("swmcp_asm_block")
    assert inserted["configuration"] == "Default"
    assert all(check["passed"] for check in inserted["verification"]["checks"])


def test_the_first_component_is_fixed_by_solidworks_and_says_so(call, assembly):
    """SOLIDWORKS fixes the first component itself; reporting it as requested would lie."""
    inserted = call("sw_asm_insert", {"component_path": assembly, "fixed": False})["result"]

    assert inserted["fixed"] is True
    assert any("first component" in warning for warning in inserted["warnings"]), (
        "an unrequested fixed state must be explained, not silently reported"
    )


def test_a_second_component_lands_where_it_was_asked_to(call, assembly):
    call("sw_asm_insert", {"component_path": assembly})
    second = call(
        "sw_asm_insert", {"component_path": assembly, "at": [60, 0, 0], "fixed": True}
    )["result"]

    assert second["components_before"] == 1
    assert second["components_after"] == 2
    assert second["position_mm"] == pytest.approx([60.0, 0.0, 0.0])
    assert second["fixed"] is True
    assert second["warnings"] == [], "a requested fixed state needs no explanation"


def test_inserting_a_file_that_is_not_there_is_refused(call, assembly):
    payload = call(
        "sw_asm_insert", {"component_path": r"C:\nope\missing.SLDPRT"}, expect_ok=False
    )
    assert payload["error"]["code"] == "COMPONENT_FILE_MISSING"


# --- ASM-002: the tree --------------------------------------------------------


def test_the_tree_reports_every_state_the_requirement_asks_for(call, assembly):
    call("sw_asm_insert", {"component_path": assembly})
    call("sw_asm_insert", {"component_path": assembly, "at": [60, 0, 0]})

    tree = call("sw_asm_tree")["result"]

    assert tree["component_count"] == 2
    entry = tree["components"][0]
    for field in (
        "name", "path", "depth", "configuration", "suppression", "suppressed",
        "lightweight", "visible", "fixed", "virtual", "envelope", "reference_ok",
    ):
        assert field in entry, f"the tree does not report {field}"
    assert entry["reference_ok"] is True
    assert tree["broken_references"] == []


def test_the_tree_counts_instances_of_the_same_file(call, assembly):
    """Quantity is per referenced file, which is what a BOM needs."""
    call("sw_asm_insert", {"component_path": assembly})
    call("sw_asm_insert", {"component_path": assembly, "at": [60, 0, 0]})
    call("sw_asm_insert", {"component_path": assembly, "at": [120, 0, 0]})

    tree = call("sw_asm_tree")["result"]

    assert tree["component_count"] == 3
    assert list(tree["quantities"].values()) == [3], "three instances of one file"


def test_an_empty_assembly_reports_an_empty_tree(call, assembly):
    tree = call("sw_asm_tree")["result"]
    assert tree["component_count"] == 0
    assert tree["components"] == []
    assert tree["quantities"] == {}


# --- ASM-003: component state -------------------------------------------------


def test_a_component_can_be_suppressed_and_resolved(call, assembly):
    call("sw_asm_insert", {"component_path": assembly})
    name = call("sw_asm_tree")["result"]["components"][0]["name"]

    suppressed = call(
        "sw_asm_component_set", {"component_name": name, "suppression": "suppressed"}
    )["result"]
    assert suppressed["suppression"] == "suppressed"
    assert "suppression" in suppressed["changed"]
    assert all(check["passed"] for check in suppressed["verification"]["checks"])

    resolved = call(
        "sw_asm_component_set", {"component_name": name, "suppression": "fully_resolved"}
    )["result"]
    assert resolved["suppression"] == "fully_resolved"
    assert all(check["passed"] for check in resolved["verification"]["checks"])


def test_a_declined_lightweight_request_is_reported_not_claimed(call, assembly):
    """A finding, pinned: SOLIDWORKS does not always honour a lightweight request.

    ASM-003 names lightweight explicitly, and asking for it here left the component
    fully resolved — observed with the component's own document still open in the
    session. The tool reports the state the component really has, fails its
    ``suppression_applied`` check, and warns; it does not echo back what was asked.
    Claiming the requested state would be exactly the lie this project exists to avoid.
    """
    call("sw_asm_insert", {"component_path": assembly})
    call("sw_asm_insert", {"component_path": assembly, "at": [60, 0, 0]})
    name = call("sw_asm_tree")["result"]["components"][1]["name"]

    light = call(
        "sw_asm_component_set", {"component_name": name, "suppression": "lightweight"}
    )["result"]

    assert light["suppression"] != "lightweight", (
        "if SOLIDWORKS now honours this, drop the warning and assert the state instead"
    )
    applied = next(
        c for c in light["verification"]["checks"] if c["name"] == "suppression_applied"
    )
    assert applied["passed"] is False, "a declined transition must fail its own check"
    assert any("declines some transitions" in w for w in light["warnings"])


def test_suppressing_and_resolving_do_take_effect(call, assembly):
    """The transitions that are honoured, so the test above is not the only evidence."""
    call("sw_asm_insert", {"component_path": assembly})
    call("sw_asm_insert", {"component_path": assembly, "at": [60, 0, 0]})
    name = call("sw_asm_tree")["result"]["components"][1]["name"]

    off = call("sw_asm_component_set", {"component_name": name, "suppression": "suppressed"})
    assert off["result"]["suppression"] == "suppressed"
    assert off["result"]["warnings"] == []

    on = call("sw_asm_component_set", {"component_name": name, "suppression": "fully_resolved"})
    assert on["result"]["suppression"] == "fully_resolved"
    assert on["result"]["warnings"] == []


def test_a_component_can_be_floated_and_fixed(call, assembly):
    """The first component starts fixed, so this floats it before fixing it again."""
    call("sw_asm_insert", {"component_path": assembly})
    name = call("sw_asm_tree")["result"]["components"][0]["name"]

    floated = call("sw_asm_component_set", {"component_name": name, "fixed": False})["result"]
    assert floated["fixed"] is False
    assert all(check["passed"] for check in floated["verification"]["checks"])

    refixed = call("sw_asm_component_set", {"component_name": name, "fixed": True})["result"]
    assert refixed["fixed"] is True


def test_a_component_can_be_hidden_and_shown(call, assembly):
    call("sw_asm_insert", {"component_path": assembly})
    name = call("sw_asm_tree")["result"]["components"][0]["name"]

    hidden = call("sw_asm_component_set", {"component_name": name, "visible": False})["result"]
    assert hidden["visible"] is False
    assert all(check["passed"] for check in hidden["verification"]["checks"])

    shown = call("sw_asm_component_set", {"component_name": name, "visible": True})["result"]
    assert shown["visible"] is True


def test_several_states_change_in_one_call(call, assembly):
    call("sw_asm_insert", {"component_path": assembly})
    call("sw_asm_insert", {"component_path": assembly, "at": [60, 0, 0]})
    name = call("sw_asm_tree")["result"]["components"][1]["name"]

    changed = call(
        "sw_asm_component_set",
        {"component_name": name, "fixed": True, "visible": False},
    )["result"]

    assert set(changed["changed"]) == {"fixed", "visible"}
    assert changed["fixed"] is True
    assert changed["visible"] is False
    assert all(check["passed"] for check in changed["verification"]["checks"])


def test_an_unknown_component_is_named_in_the_error(call, assembly):
    call("sw_asm_insert", {"component_path": assembly})
    payload = call(
        "sw_asm_component_set", {"component_name": "no-such-part-1", "visible": False},
        expect_ok=False,
    )
    assert payload["error"]["code"] == "COMPONENT_NOT_FOUND"
    assert any("sw_asm_tree" in step for step in payload["error"]["remediation"])


def test_assembly_tools_refuse_a_part_document(call, scratch_root, unique_name):
    """The precondition is real: these tools have nothing to do in a part."""
    call("sw_doc_new", {"doc_type": "part"})
    payload = call("sw_asm_tree", {}, expect_ok=False)
    assert not payload["ok"]
