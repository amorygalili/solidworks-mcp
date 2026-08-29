"""Live cover for the review block: REV-001, REV-002, REV-004, REV-005, REV-007.

These tools mostly compose facts the server already gathers, so the interesting tests
are the ones where a review must reach the *unwelcome* answer: a policy that fails, a
hole count that does not match, a check the caller turned off. A reviewer that only
ever passes is worthless, so every rule here is exercised in both directions.

The plate is 100 x 60 x 8 mm with four Ø8 holes and one Ø20 bore, which makes both the
volume and the hole audit arithmetic rather than opinion.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

PLATE_X, PLATE_Y, PLATE_Z = 100.0, 60.0, 8.0
SMALL_D, SMALL_R = 8.0, 4.0
BORE_D, BORE_R = 20.0, 10.0
SMALL_HOLES = 4

PLATE_MM3 = (
    PLATE_X * PLATE_Y * PLATE_Z
    - SMALL_HOLES * math.pi * SMALL_R**2 * PLATE_Z
    - math.pi * BORE_R**2 * PLATE_Z
)


@pytest.fixture(scope="module")
def plate(dispatcher, scratch_root):
    """One drilled plate for the whole module; every test only reads it."""
    target = scratch_root / "swmcp_review.SLDPRT"
    for stale in scratch_root.glob("swmcp_review*"):
        stale.unlink(missing_ok=True)

    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    dispatcher.call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_X, PLATE_Y]}]},
    )
    dispatcher.call("sw_sketch_exit", {})
    built = dispatcher.call("sw_feature_extrude_boss", {"depth": PLATE_Z, "name": "Plate"})
    assert built.get("ok"), built.get("error")

    dispatcher.call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    dispatcher.call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "circle", "center": [c[0], c[1]], "radius": SMALL_R}
                for c in ((20, 20), (80, 20), (20, 40), (80, 40))
            ]
            + [{"type": "circle", "center": [50, 30], "radius": BORE_R}]
        },
    )
    dispatcher.call("sw_sketch_exit", {})
    cut = dispatcher.call(
        "sw_feature_extrude_cut",
        {"end_condition": "through_all", "reverse": True, "name": "Holes"},
    )
    assert cut.get("ok"), cut.get("error")
    dispatcher.call("sw_doc_save", {"output_path": str(target)})

    yield target.name

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": target.name}, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def call(call, plate):
    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        args = dict(arguments or {})
        args.setdefault("document", {"title": plate})
        return call(name, args, expect_ok=expect_ok)

    return _call


# --- REV-001: inspection -------------------------------------------------------


def test_inspection_gathers_every_section_at_once(call):
    found = call("sw_review_inspect")["result"]

    assert found["document"]
    for section in ("features", "sketches", "bodies", "configurations", "mass"):
        assert section in found["sections"], f"{section} is missing from the inspection"

    assert found["sections"]["bodies"]["count"] == 1
    assert found["sections"]["mass"]["volume_m3"] * 1e9 == pytest.approx(PLATE_MM3, rel=1e-6)
    assert found["truncated"] == []


def test_inspection_can_be_narrowed_to_one_section(call):
    found = call("sw_review_inspect", {"sections": ["bodies"]})["result"]

    assert set(found["sections"]) == {"bodies"}


def test_inspection_says_when_it_truncated(call):
    """A silently shortened list would make a review look complete when it is not."""
    found = call("sw_review_inspect", {"sections": ["features"], "max_items": 2})["result"]

    assert found["sections"]["features"]["count"] == 2
    assert "features" in found["truncated"]
    assert any("max_items" in w for w in found["warnings"])


# --- REV-002 / REV-007: validation against caller policy ------------------------


def test_a_healthy_part_passes_the_default_policy(call):
    result = call("sw_review_validate")["result"]

    assert result["outcome"] == "pass"
    assert result["blocked"] == 0
    assert result["passed"] > 0
    for finding in result["findings"]:
        assert finding["source"], "every finding must say what it read"


def test_a_policy_the_part_cannot_meet_blocks(call):
    """The test that matters: a reviewer that only ever passes is worthless."""
    result = call(
        "sw_review_validate", {"policy": {"min_volume_mm3": 10_000_000}}
    )["result"]

    assert result["outcome"] == "block"
    assert result["blocked"] >= 1
    failing = [f for f in result["findings"] if f["name"] == "volume_at_least"]
    assert failing and failing[0]["outcome"] == "block"
    assert "mm³" in failing[0]["detail"]


def test_the_caller_can_downgrade_a_rule_to_a_warning(call):
    """REV-007: the severity is the caller's call, not the server's."""
    blocking = call("sw_review_validate", {"policy": {"min_volume_mm3": 10_000_000}})["result"]
    assert blocking["outcome"] == "block"

    warned = call(
        "sw_review_validate",
        {"policy": {"min_volume_mm3": 10_000_000, "severity": {"volume_at_least": "warn"}}},
    )["result"]

    assert warned["outcome"] == "warn"
    assert warned["blocked"] == 0
    assert warned["warned"] >= 1


def test_the_caller_can_turn_a_rule_off_entirely(call):
    result = call(
        "sw_review_validate",
        {
            "policy": {
                "require_no_feature_errors": False,
                "require_bodies_min": None,
                "forbid_zero_volume": False,
                "forbid_dangling_relations": False,
            }
        },
    )["result"]

    assert result["findings"] == []
    assert result["outcome"] == "pass"
    assert any("checked nothing" in w for w in result["warnings"]), (
        "a review that checked nothing must say so rather than report a clean pass"
    )


def test_requiring_a_material_fails_when_none_is_assigned(call):
    result = call("sw_review_validate", {"policy": {"require_material": True}})["result"]

    material = next(f for f in result["findings"] if f["name"] == "material_assigned")
    assert material["outcome"] == "block"
    assert "not set" in material["detail"]


def test_requiring_fully_defined_sketches_warns_by_default(call):
    """The plate's sketches are under-defined, and that is a warning, not a blocker."""
    result = call(
        "sw_review_validate", {"policy": {"require_fully_defined_sketches": True}}
    )["result"]

    finding = next(f for f in result["findings"] if f["name"] == "sketches_fully_defined")
    assert finding["outcome"] in {"pass", "warn"}
    if finding["outcome"] == "warn":
        assert result["outcome"] == "warn"


# --- REV-004: hole audit --------------------------------------------------------


def test_holes_are_counted_from_the_geometry(call):
    found = call("sw_review_holes")["result"]

    diameters = {group["diameter_mm"]: group["count"] for group in found["groups"]}
    assert SMALL_D in diameters, f"no Ø{SMALL_D} group in {diameters}"
    assert diameters[SMALL_D] == SMALL_HOLES
    assert diameters[BORE_D] == 1
    assert found["hole_count"] == SMALL_HOLES + 1


def test_matching_expectations_are_reported_as_met(call):
    found = call(
        "sw_review_holes",
        {
            "expect": [
                {"diameter_mm": SMALL_D, "count": SMALL_HOLES},
                {"diameter_mm": BORE_D, "count": 1},
            ]
        },
    )["result"]

    assert found["outcome"] == "pass"
    assert len(found["matched"]) == 2
    assert found["unmatched"] == []


def test_a_wrong_expectation_is_reported_not_glossed_over(call):
    found = call(
        "sw_review_holes", {"expect": [{"diameter_mm": SMALL_D, "count": 7}]}
    )["result"]

    assert found["outcome"] == "block"
    assert len(found["unmatched"]) == 1
    miss = found["unmatched"][0]
    assert miss["expected_count"] == 7
    assert miss["found_count"] == SMALL_HOLES
    assert str(SMALL_HOLES) in miss["detail"]


def test_a_diameter_filter_narrows_the_audit(call):
    found = call("sw_review_holes", {"min_diameter_mm": 15.0})["result"]

    assert found["hole_count"] == 1
    assert [g["diameter_mm"] for g in found["groups"]] == [BORE_D]


def test_each_hole_comes_back_addressable(call):
    found = call("sw_review_holes")["result"]
    face = found["groups"][0]["faces"][0]

    assert face["tool_args"]["ref"], "a hole you cannot address is a dead end"
    assert face["axis"], "a hole audit without an axis cannot check orientation"
    assert len(face["at_mm"]) == 3


# --- REV-005: reports -----------------------------------------------------------


def test_a_report_is_written_in_both_formats(call, scratch_root):
    written = call(
        "sw_review_report", {"output_path": str(scratch_root / "swmcp_review_report.md")}
    )["result"]

    markdown = Path(written["markdown_path"])
    payload = Path(written["json_path"])
    assert markdown.exists() and payload.exists()
    assert markdown.suffix == ".md"
    assert payload.suffix == ".json"
    assert len(written["artifacts"]) == 2
    for artifact in written["artifacts"]:
        assert artifact["exists"] is True
        assert artifact["size_bytes"] > 0
        assert artifact["sha256"]


def test_the_json_report_carries_the_findings_and_the_policy(call, scratch_root):
    written = call(
        "sw_review_report",
        {
            "output_path": str(scratch_root / "swmcp_review_json.md"),
            "policy": {"min_volume_mm3": 10_000_000},
        },
    )["result"]

    payload = json.loads(Path(written["json_path"]).read_text(encoding="utf-8"))

    assert payload["outcome"] == "block"
    assert payload["policy"]["min_volume_mm3"] == 10_000_000
    assert payload["counts"]["block"] >= 1
    assert all(f["source"] for f in payload["findings"])
    assert payload["document"]


def test_the_markdown_report_is_readable_and_attributes_its_findings(call, scratch_root):
    written = call(
        "sw_review_report",
        {
            "output_path": str(scratch_root / "swmcp_review_md.md"),
            "title": "Plate review",
        },
    )["result"]

    text = Path(written["markdown_path"]).read_text(encoding="utf-8")

    assert text.startswith("# Plate review")
    assert "| Check | Outcome | Detail | Source |" in text
    assert "`non_zero_volume`" in text
    assert written["outcome"] == "pass"


def test_a_report_outside_the_allowed_roots_is_refused(call):
    payload = call(
        "sw_review_report", {"output_path": r"C:\Windows\System32\swmcp_review.md"},
        expect_ok=False,
    )
    assert not payload["ok"]
