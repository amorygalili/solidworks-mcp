"""Live sketch, relation, and dimension behaviour (SK-*, CON-*)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


@pytest.fixture
def open_part(call, scratch_root, unique_name):
    """A saved scratch part with a sketch open on the front plane."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"

    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    try:
        yield target
    finally:
        # The autouse fixture closes the document and removes the file, in that order.
        pass


def test_a_sketch_survives_the_auto_checkpoint(call, open_part):
    """Regression: a SaveAs-Copy checkpoint used to close the sketch mid-edit."""
    started = call("sw_sketch_start", {"on": {"standard_plane": "front"}})["result"]
    assert started["sketch_name"]

    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}]},
    )["result"]
    assert added["sketch_name"] == started["sketch_name"], (
        "the sketch opened by the previous call must still be the one being edited"
    )
    assert len(added["created"]) == 4
    assert added["failed"] == []


def test_standard_planes_resolve_without_matching_english_names(call, open_part):
    """SYS-007: 'front' is resolved by tree position, not by the string 'Front Plane'."""
    for plane in ("front", "top", "right"):
        started = call("sw_sketch_start", {"on": {"standard_plane": plane}})["result"]
        assert started["plane"] == plane
        call("sw_sketch_exit")


def test_every_primitive_reports_a_stable_id(call, open_part):
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]},
                {"type": "circle", "center": [50, 30], "radius": 10},
                {"type": "centerline", "start": [0, 0], "end": [100, 60]},
                {"type": "line", "start": [10, 10], "end": [20, 20], "construction": True},
            ]
        },
    )["result"]

    assert added["failed"] == []
    ids = [entry["sketch_local_id"] for entry in added["created"]]
    assert len(ids) == len(set(ids)), "segment ids must be unique"
    assert all(":" in identifier for identifier in ids)

    by_request = {}
    for entry in added["created"]:
        by_request.setdefault(entry["requested_type"], []).append(entry)
    assert len(by_request["rect_corner"]) == 4, "a rectangle is four line segments"
    assert len(by_request["circle"]) == 1

    assert all(e["construction"] for e in by_request["centerline"]), "a centerline is construction"
    assert all(e["construction"] for e in by_request["line"]), "construction=true was honoured"
    assert not any(e["construction"] for e in by_request["rect_corner"])


def test_units_are_accepted_in_every_documented_form(call, open_part):
    """SYS-006 end to end: the same rectangle three ways."""
    for entities in (
        [{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}],
        [{"type": "rect_corner", "corner": ["0mm", "0mm"], "opposite": ["10cm", "60mm"]}],
        [
            {
                "type": "rect_corner",
                "corner": [{"value": 0, "unit": "mm"}, 0],
                "opposite": [{"value": 100, "unit": "mm"}, 60],
            }
        ],
    ):
        call("sw_sketch_start", {"on": {"standard_plane": "front"}})
        added = call("sw_sketch_add_geometry", {"entities": entities})["result"]
        assert added["failed"] == []
        lengths = sorted(round(e["length_m"], 6) for e in added["created"])
        assert lengths == [0.06, 0.06, 0.1, 0.1], "all three forms must produce 100 x 60 mm"
        call("sw_sketch_exit")


def test_relations_reduce_the_under_defined_count(call, open_part):
    """CON-005: progress toward fully defined is measured, not assumed."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}]},
    )["result"]
    ids = [e["sketch_local_id"] for e in added["created"]]

    applied = call(
        "sw_sketch_add_relations",
        {"relations": [{"type": "horizontal", "segment_ids": [ids[0]]}]},
    )["result"]

    assert applied["applied"] == 1
    assert applied["failed"] == []
    assert "sketch_state" in applied, "CON-005 evidence must be in the result schema"
    assert not applied["sketch_state"]["over_defined"]
    assert applied["sketch_state"]["dangling_relations"] == []

    verification = applied["verification"]
    assert verification["read_back"] is True
    assert verification["after"]["relation_count"] >= verification["before"]["relation_count"]


def test_a_bad_relation_does_not_lose_the_rest_of_the_batch(call, open_part):
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}]},
    )["result"]
    ids = [e["sketch_local_id"] for e in added["created"]]

    outcome = call(
        "sw_sketch_add_relations",
        {
            "relations": [
                {"type": "horizontal", "segment_ids": [ids[0]]},
                {"type": "parallel", "segment_ids": ["99:99"]},
                {"type": "vertical", "segment_ids": [ids[1]]},
            ]
        },
    )["result"]

    assert outcome["applied"] == 2, "the two valid relations must still apply"
    assert len(outcome["failed"]) == 1
    assert "unknown ids" in outcome["failed"][0]["reason"]


def test_preflight_reports_the_plan_without_changing_anything(call, open_part):
    """SAFE-007."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}]},
    )["result"]
    ids = [e["sketch_local_id"] for e in added["created"]]

    before = call("sw_sketch_diagnose")["result"]["sketch_state"]["relation_count"]
    planned = call(
        "sw_sketch_add_relations",
        {"relations": [{"type": "horizontal", "segment_ids": [ids[0]]}], "preflight": True},
    )["result"]

    assert planned["applied"] == 0
    assert any("Preflight" in w for w in planned["warnings"])
    after = call("sw_sketch_diagnose")["result"]["sketch_state"]["relation_count"]
    assert after == before, "preflight must not change the model"


def test_dimensions_are_created_and_readable_by_name(call, open_part):
    """CON-002 and CON-003."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}]},
    )["result"]
    ids = [e["sketch_local_id"] for e in added["created"]]

    created = call(
        "sw_sketch_add_dimensions",
        {
            "dimensions": [
                {
                    "type": "distance",
                    "segment_ids": [ids[0]],
                    "value": 100,
                    "place_at": [0.05, -0.02, 0],
                }
            ]
        },
    )["result"]

    assert created["failed"] == []
    assert len(created["created"]) == 1
    name = created["created"][0]["name"]
    assert name

    call("sw_sketch_exit")
    listed = call("sw_dimension_list")["result"]
    assert listed["unit"] == "mm"
    match = next(d for d in listed["dimensions"] if d["name"] == name)
    assert match["value_mm"] == pytest.approx(100.0, abs=1e-6)
    assert match["driving"] is True, "a dimension created this way drives the geometry"


def test_setting_a_dimension_reports_before_and_after(call, open_part):
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}]},
    )["result"]
    ids = [e["sketch_local_id"] for e in added["created"]]
    created = call(
        "sw_sketch_add_dimensions",
        {
            "dimensions": [
                {
                    "type": "distance",
                    "segment_ids": [ids[0]],
                    "value": 100,
                    "place_at": [0.05, -0.02, 0],
                }
            ]
        },
    )["result"]
    name = created["created"][0]["name"]
    call("sw_sketch_exit")

    changed = call("sw_dimension_set", {"name": name, "value": 80})["result"]
    assert changed["before_mm"] == pytest.approx(100.0, abs=1e-6)
    assert changed["after_mm"] == pytest.approx(80.0, abs=1e-6)
    assert changed["requested_mm"] == pytest.approx(80.0, abs=1e-6)
    assert changed["rebuild_errors"] == []
    assert all(check["passed"] for check in changed["verification"]["checks"])


def test_setting_a_dimension_accepts_other_units(call, open_part):
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}]},
    )["result"]
    ids = [e["sketch_local_id"] for e in added["created"]]
    created = call(
        "sw_sketch_add_dimensions",
        {
            "dimensions": [
                {
                    "type": "distance",
                    "segment_ids": [ids[0]],
                    "value": 100,
                    "place_at": [0.05, -0.02, 0],
                }
            ]
        },
    )["result"]
    name = created["created"][0]["name"]
    call("sw_sketch_exit")

    changed = call("sw_dimension_set", {"name": name, "value": "2in"})["result"]
    assert changed["after_mm"] == pytest.approx(50.8, abs=1e-6)


def test_an_unknown_dimension_lists_what_does_exist(call, open_part):
    refused = call("sw_dimension_set", {"name": "NotADimension", "value": 10}, expect_ok=False)
    assert refused["error"]["code"] == "DIMENSION_NOT_FOUND"
    assert "known_dimensions" in refused["error"]["context"]


def test_sketch_listing_reports_state_and_construction(call, open_part):
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]},
                {"type": "centerline", "start": [0, 0], "end": [100, 60]},
            ]
        },
    )
    call("sw_sketch_exit")

    listed = call("sw_sketch_list", {"include_geometry": True})["result"]
    assert listed["active_sketch"] is None, "nothing should be open for editing"
    sketch = listed["sketches"][0]
    assert sketch["segment_count"] == 5
    assert sketch["construction_count"] == 1
    assert sketch["state"]["status"] in {"under_defined", "fully_defined"}
    assert len(sketch["segments"]) == 5


def test_deleting_sketch_geometry_needs_confirmation(call, open_part):
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}]},
    )["result"]
    ids = [e["sketch_local_id"] for e in added["created"]]

    refused = call("sw_sketch_delete", {"segment_ids": [ids[0]]}, expect_ok=False)
    assert refused["error"]["code"] == "CONFIRM_REQUIRED"

    deleted = call("sw_sketch_delete", {"segment_ids": [ids[0]], "confirm": True})["result"]
    assert deleted["deleted"] == [ids[0]]
    assert deleted["verification"]["after"]["segment_count"] == 3
