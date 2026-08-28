"""Live cover for the remaining tools no other suite exercises.

Sketch editing, the ray probe, undo, the session tools, and the low-level invoke
escape hatch. Together with ``test_live_features.py`` this closes the gap where a tool
was published, documented, and never once run against SOLIDWORKS.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


@pytest.fixture
def part(call, scratch_root, unique_name):
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    return target


def _rectangle(call, corner=(0, 0), opposite=(100, 60)) -> list[str]:
    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": list(corner), "opposite": list(opposite)}]},
    )["result"]
    return [entry["sketch_local_id"] for entry in added["created"]]


def _lengths(call) -> list[float]:
    listed = call("sw_sketch_list", {"include_geometry": True})["result"]
    active = [entry for entry in listed["sketches"] if entry["is_active"]]
    assert active, "the open sketch should be reported as active"
    return sorted(round(seg["length_m"], 9) for seg in active[0]["segments"])


# --- sketch editing -----------------------------------------------------------


def test_construction_geometry_can_be_toggled_both_ways(call, part):
    """SK-004."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    ids = _rectangle(call)

    made = call("sw_sketch_set_construction", {"segment_ids": ids[:2], "construction": True})[
        "result"
    ]
    assert made["changed"] == ids[:2]
    assert made["missing"] == []
    assert made["verification"]["after"]["construction_count"] == 2
    assert all(check["passed"] for check in made["verification"]["checks"])

    undone = call("sw_sketch_set_construction", {"segment_ids": ids[:2], "construction": False})[
        "result"
    ]
    assert undone["changed"] == ids[:2]
    assert undone["verification"]["after"]["construction_count"] == 0


def test_an_unknown_segment_id_is_reported_not_ignored(call, part):
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    ids = _rectangle(call)

    outcome = call("sw_sketch_set_construction", {"segment_ids": [ids[0], "99:99"]})["result"]
    assert outcome["changed"] == [ids[0]]
    assert outcome["missing"] == ["99:99"]
    assert any(not check["passed"] for check in outcome["verification"]["checks"]), (
        "an id that resolved to nothing must show up as a failed check"
    )


def test_moving_a_sketch_moves_it_without_resizing_it(call, part):
    """SK-007: the move branch of sw_sketch_modify."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    ids = _rectangle(call)
    before = _lengths(call)

    moved = call(
        "sw_sketch_modify",
        {"operation": "move", "segment_ids": ids, "delta": [10, 5], "confirm": True},
    )["result"]

    assert moved["operation"] == "move"
    assert moved["affected"] == 4
    assert _lengths(call) == before, "a move must not change any length"


def test_scaling_a_sketch_scales_every_length(call, part):
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    ids = _rectangle(call)
    before = _lengths(call)

    scaled = call(
        "sw_sketch_modify",
        {
            "operation": "scale",
            "segment_ids": ids,
            "factor": 2.0,
            "about": [0, 0],
            "confirm": True,
        },
    )["result"]

    assert scaled["affected"] == 4
    after = _lengths(call)
    assert after == pytest.approx([value * 2 for value in before], rel=1e-9)


def test_sketch_modify_requires_the_argument_its_operation_needs(call, part):
    """A scale with no factor is a schema-level refusal, not a COM failure."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    ids = _rectangle(call)

    refused = call(
        "sw_sketch_modify",
        {"operation": "scale", "segment_ids": ids, "about": [0, 0], "confirm": True},
        expect_ok=False,
    )
    assert refused["error"]["code"] == "MISSING_ARGUMENT"


def test_converting_an_edge_projects_it_into_the_sketch(call, part):
    """SK-006: geometry from the model, referenced rather than retyped."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    _rectangle(call)
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": 8, "name": "Plate"})

    top = call(
        "sw_probe_faces", {"geometry_type": "planar_face", "area_min_mm2": 100 * 60 * 0.99}
    )["result"]["candidates"][0]

    call("sw_sketch_start", {"on": {"ref": top["tool_args"]["ref"]}})
    converted = call(
        "sw_sketch_convert_entities", {"refs": [top["tool_args"]["ref"]], "inner_loops": False}
    )["result"]

    assert len(converted["created"]) == 4, "the face outline is four edges"
    assert not any("No geometry was projected" in warning for warning in converted["warnings"])
    assert all(check["passed"] for check in converted["verification"]["checks"])


def test_auto_dimension_drives_the_sketch_toward_fully_defined(call, part):
    """CON-004. It may not finish the job, but it must not go backwards."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    _rectangle(call)
    before = call("sw_sketch_diagnose")["result"]["sketch_state"]

    assert before["status"] == "under_defined", "a bare rectangle starts under-defined"

    applied = call("sw_sketch_auto_dimension", {"policy": "baseline", "confirm": True})["result"]
    after = applied["sketch_state"]

    assert not after["over_defined"], "auto-dimensioning must never over-define the sketch"
    assert after["status"] in {"fully_defined", "under_defined"}
    assert applied["dimensions_after"] >= applied["dimensions_before"]
    if applied["dimensions_after"] > applied["dimensions_before"]:
        assert applied["created"], "if it added dimensions it must say which"
        assert after["status"] == "fully_defined", (
            "adding a full baseline scheme to a rectangle should finish defining it"
        )


# --- probes -------------------------------------------------------------------


def test_a_ray_hits_the_face_it_is_aimed_at(call, part):
    """REF-005: pick a face by shooting at it."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    _rectangle(call)
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": 8, "name": "Plate"})

    hit = call(
        "sw_probe_ray",
        {"origin": [50, 30, 50], "direction": [0, 0, -1], "radius": 2},
    )["result"]

    assert hit["hit"] is True
    assert hit["reference"]["semantic"]["geometry_type"] == "planar_face"
    assert hit["tool_args"], "a hit must come back addressable"

    resolved = call("sw_ref_resolve", hit["tool_args"])["result"]
    assert resolved["status"] == "resolved"


def test_a_ray_that_hits_nothing_says_so(call, part):
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    _rectangle(call)
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": 8, "name": "Plate"})

    missed = call(
        "sw_probe_ray",
        {"origin": [-500, -500, 500], "direction": [0, 0, 1], "radius": 1},
    )["result"]

    assert missed["hit"] is False
    assert missed["warnings"], "a miss must be explained, not returned as an empty success"


# --- document lifecycle -------------------------------------------------------


def test_undo_reverts_the_last_feature(call, part):
    """DOC-007."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    _rectangle(call)
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": 8, "name": "Plate"})
    assert call("sw_body_list")["result"]["count"] == 1

    undone = call("sw_doc_undo", {"steps": 1, "confirm": True})["result"]

    assert undone["steps_requested"] == 1
    checks = {check["name"]: check for check in undone["verification"]["checks"]}
    assert checks["undo_had_an_effect"]["passed"], checks["undo_had_an_effect"]["detail"]
    assert call("sw_body_list")["result"]["count"] == 0


def test_undo_is_destructive_and_needs_confirmation(call, part):
    refused = call("sw_doc_undo", {"steps": 1}, expect_ok=False)
    assert refused["error"]["code"] == "CONFIRM_REQUIRED"


# --- session ------------------------------------------------------------------


def test_connect_attaches_without_launching_a_second_solidworks(call):
    """SYS-001: attaching to what is already running, never starting a rival session."""
    connected = call("sw_connect", {"start_if_missing": False})["result"]

    assert connected["attached"] is True
    assert connected["launched"] is False
    assert connected["prog_id"].startswith("SldWorks.Application")


def test_health_reports_the_worker_without_queueing(call):
    """SYS-005."""
    snapshot = call("sw_health", {"probe": False})["result"]

    # Not "healthy is True": a long automation session legitimately drives SOLIDWORKS
    # into a strained state, and reporting that is the feature. What must hold is that
    # the flag and the issue list agree — a health check that says healthy while
    # listing problems is the failure worth catching here.
    assert snapshot["healthy"] == (snapshot["issues"] == [])
    assert snapshot["worker"]["apartment"] == "STA"
    assert snapshot["worker"]["thread_alive"] is True
    assert snapshot["worker"]["calls"]["total"] > 0
    assert snapshot["probe"] is None, "probe=false must not touch the model"


def test_health_with_a_probe_actually_probes(call):
    probed = call("sw_health", {"probe": True})["result"]
    assert probed["probe"] is not None
    assert probed["probe"]["answered"] is True
    assert probed["probe"]["revision"]
    assert probed["probe"]["latency_ms"] >= 0


def test_capabilities_are_probed_rather_than_assumed(call):
    """DISC-005."""
    reported = call("sw_capabilities")["result"]
    capabilities = reported["capabilities"]

    assert capabilities["attach"] is True
    assert capabilities["default_templates"]["part"], "the part template must be discovered"
    assert capabilities["templates_present"]["part"] is True, "and must exist on disk"
    assert reported["evidence"]["install_root"]
    assert reported["evidence"]["registered_prog_ids"]


def test_resolve_names_reports_tokens_and_units_for_the_document(call, part):
    """SYS-007 through the tool surface rather than the session object."""
    resolved = call("sw_resolve_names")["result"]

    assert [plane["standard"] for plane in resolved["standard_planes"][:3]] == [
        "front",
        "top",
        "right",
    ]
    assert all(plane["type_name"] == "RefPlane" for plane in resolved["standard_planes"][:3])
    assert resolved["units"]["api_units"]


def test_api_search_finds_an_enum_from_the_installed_typelib(call):
    """DISC-002."""
    found = call("sw_api_search", {"query": "swEndConditions", "kind": "enum"})["result"]

    assert found["enums"], "swEndConditions_e is in every SOLIDWORKS type library"
    names = {entry["enum"] for entry in found["enums"]}
    assert "swEndConditions_e" in names
    assert found["typelib"]["typelib_major"] >= 30
    assert found["warnings"] == [], "the table must match the running release"


# --- the low-level escape hatch -----------------------------------------------


def test_api_invoke_reads_a_member_that_is_on_the_allowlist(call, part):
    """DISC-003: the escape hatch works for reads."""
    invoked = call("sw_api_invoke", {"target": "doc", "member": "GetTitle"})["result"]

    assert invoked["value"], "GetTitle must return the document title"
    assert invoked["value_type"] == "str"


def test_api_invoke_refuses_a_member_that_can_mutate(call, part):
    """The read invoker is an allowlist, not a filter you can talk past."""
    refused = call(
        "sw_api_invoke",
        {"target": "doc.Extension", "member": "SelectByID2", "args": ["Front Plane", "PLANE"]},
        expect_ok=False,
    )

    assert refused["error"]["code"] == "MEMBER_NOT_READ_ONLY"
    assert refused["error"]["context"]["member"] == "SelectByID2"


def test_api_batch_invoke_reports_each_call_separately(call, part):
    """DISC-004."""
    batch = call(
        "sw_api_batch_invoke",
        {
            "calls": [
                {"target": "doc", "member": "GetTitle"},
                {"target": "doc", "member": "GetType"},
                {"target": "doc", "member": "NotARealMember"},
            ],
            "stop_on_error": False,
        },
    )["result"]

    assert len(batch["results"]) == 3
    assert batch["results"][0]["ok"] is True
    assert batch["results"][1]["ok"] is True
    assert batch["results"][2]["ok"] is False, "one bad call must not fail the batch"
    assert batch["failed"] == 1
    assert batch["warnings"], "a partial failure must be visible at the top level"


def test_the_write_invoker_is_off_unless_it_is_switched_on(call, part):
    """DISC-003's write half is gated by an environment flag, not by politeness."""
    refused = call(
        "sw_api_invoke_write",
        {"target": "doc", "member": "EditRebuild3", "confirm": True},
        expect_ok=False,
    )

    assert refused["error"]["code"] == "LOWLEVEL_WRITE_DISABLED"
    assert any("SWMCP_ENABLE_LOWLEVEL_WRITE" in step for step in refused["error"]["remediation"])
