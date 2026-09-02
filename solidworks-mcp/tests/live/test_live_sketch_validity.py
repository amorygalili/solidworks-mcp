"""A profile can close and still be invalid (SK-*, FEAT-*).

Found while cutting an involute gear. The tooth-space profile was emitted with its
root fillets drawn as centre-point arcs whose ``direction`` named the long way round,
so each 0.76 mm fillet swept 272 degrees instead of 88. Both endpoints are identical
either way, so the sketch reported one closed contour with 0.0 mm placement deviation
and every check green — and the cut that consumed it failed with a message naming
neither the segment nor the reason. Two more attempts went into ``reverse`` and a
symmetric end condition before arc *length* gave it away.

These tests pin the readings that make that visible: the sweep an arc actually turns,
and the crossings a closed contour can still contain.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

#: The real m=2 z=20 root region: flank, fillet, root land, mirrored fillet, flank,
#: closed back on itself. Millimetres, exactly as the gear was drawn.
_FLANK_A = [18.71186, 1.75362]
_TAN_A = [18.16458, 1.70233]
_ROOT_A = [17.34059, 2.35667]
_ROOT_B = [17.22013, 3.11721]
_TAN_B = [17.80159, 3.99415]
_FLANK_B = [18.33794, 4.11449]


def _root_region(fillet_direction: str) -> list[dict]:
    """The profile with both fillets swept the named way.

    ``clockwise`` is the minor arc and the way it was meant to be drawn;
    ``counterclockwise`` is the 272 degree complement that broke the cut.
    """
    return [
        {"type": "line", "start": _FLANK_A, "end": _TAN_A},
        {
            "type": "arc_center",
            "center": [18.09367, 2.45902],
            "start": _TAN_A,
            "end": _ROOT_A,
            "direction": fillet_direction,
        },
        {
            "type": "arc_center",
            "center": [0, 0],
            "start": _ROOT_A,
            "end": _ROOT_B,
            "direction": "counterclockwise",
        },
        {
            "type": "arc_center",
            "center": [17.96798, 3.25259],
            "start": _ROOT_B,
            "end": _TAN_B,
            "direction": fillet_direction,
        },
        {"type": "line", "start": _TAN_B, "end": _FLANK_B},
        {"type": "line", "start": _FLANK_B, "end": _FLANK_A},
    ]


@pytest.fixture(scope="module")
def shared_part(dispatcher, scratch_root):
    """One document for the whole module. See the cost policy in CLAUDE.md.

    Every test here adds its own sketch and asserts only on what that sketch reports,
    so sharing a document couples them no further than the sketch counter.
    """
    target = scratch_root / "swmcp_sketch_validity.SLDPRT"
    for stale in scratch_root.glob("swmcp_sketch_validity*.SLDPRT"):
        stale.unlink(missing_ok=True)

    # Named explicitly rather than relying on swDefaultTemplatePart. That preference
    # is a machine-level UI setting (Tools > Options > Default Templates), it is
    # separate from the File Locations directory list, and it came back empty on a
    # freshly launched session here - which fails every live module that assumes it.
    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    if not made.get("ok") and made["error"]["code"] == "TEMPLATE_NOT_FOUND":
        fallback = Path("C:/ProgramData/SolidWorks/SOLIDWORKS 2026/templates/Part.PRTDOT")
        if not fallback.is_file():
            pytest.skip(f"no default part template and none at {fallback}")
        made = dispatcher.call(
            "sw_doc_new", {"doc_type": "part", "template_path": str(fallback)}
        )
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_doc_save", {"output_path": str(target)})
    title = target.name
    yield title

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": title}, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def call(call, shared_part):
    """Every call in this module is addressed at the shared document, never 'active'."""

    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        args = dict(arguments or {})
        args.setdefault("document", {"title": shared_part})
        return call(name, args, expect_ok=expect_ok)

    return _call


def _sketch(call, entities, **extra):
    return call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "auto_relations": False,
            "entities": entities,
            **extra,
        },
    )["result"]


# --- what an arc says about itself ---------------------------------------------


def test_an_arc_reports_the_sweep_it_actually_turned(call):
    """The reading that separates an arc from its complement.

    Both arcs here share a centre, a radius and both endpoints. Only the sweep
    differs, so only the sweep can tell a caller which one they got.
    """
    minor = _sketch(call, _root_region("clockwise"))
    arcs = [c for c in minor["created"] if c["type"] == "arc"]
    fillets = [a for a in arcs if a["radius_mm"] == pytest.approx(0.76, abs=1e-3)]
    assert len(fillets) == 2
    for fillet in fillets:
        assert fillet["sweep_deg"] == pytest.approx(87.66, abs=0.5)
        # The old giveaway, now stated directly: length over radius is the sweep.
        assert math.degrees(fillet["length_m"] / (fillet["radius_mm"] / 1000.0)) == (
            pytest.approx(fillet["sweep_deg"], abs=0.01)
        )

    major = _sketch(call, _root_region("counterclockwise"))
    swept = [
        c["sweep_deg"]
        for c in major["created"]
        if c["type"] == "arc" and c["radius_mm"] == pytest.approx(0.76, abs=1e-3)
    ]
    assert all(s == pytest.approx(272.34, abs=0.5) for s in swept), swept


# --- what a closed contour can still hide ---------------------------------------


def test_the_profile_as_drawn_is_clean(call):
    """False-positive guard: this exact geometry cuts, so it must report clean."""
    result = _sketch(call, _root_region("clockwise"))
    contours = result["contours"]

    assert contours["closed_contour_count"] == 1
    assert contours["self_intersections"] == []
    assert contours["major_arc_segment_ids"] == []
    assert not [w for w in result["warnings"] if "self-intersection" in w]


def test_a_closed_contour_reports_its_crossings(call):
    """The whole point: closed, exact, and geometrically impossible.

    Every reading the server had before this change is unchanged and healthy —
    one closed contour, zero deviation. Only the crossing distinguishes it.
    """
    result = _sketch(call, _root_region("counterclockwise"))
    contours = result["contours"]

    assert contours["closed_contour_count"] == 1, "the old reading is still 'closed'"
    assert contours["open_contour_count"] == 0
    assert result["max_deviation_mm"] == pytest.approx(0.0, abs=1e-3)

    assert contours["self_intersections"], "a 272 degree fillet must be caught"
    assert len(contours["major_arc_segment_ids"]) == 2
    hit = contours["self_intersections"][0]
    assert len(hit["segments"]) == 2
    assert len(hit["at_mm"]) == 2


def test_the_warning_names_the_direction_field(call):
    """A diagnosis that does not say what to change is not a diagnosis."""
    result = _sketch(call, _root_region("counterclockwise"))
    warning = " ".join(w for w in result["warnings"] if "self-intersection" in w)

    assert warning, result["warnings"]
    assert "180 degrees" in warning
    assert "direction" in warning


def test_the_cut_that_fails_points_at_the_profile(call):
    """The failure a caller actually meets, and what it now tells them.

    A ``through_all_both`` cut reaches both ways from the sketch plane, so suggesting
    ``reverse`` sends them to re-run the same failure — which is exactly what the old
    remediation did.
    """
    call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "auto_relations": False,
            "entities": [{"type": "circle", "center": [0, 0], "radius": 25}],
        },
    )
    call("sw_feature_extrude_boss", {"end_condition": "mid_plane", "depth": 10})

    bad = _sketch(call, _root_region("counterclockwise"))
    payload = call(
        "sw_feature_extrude_cut",
        {"sketch_name": bad["sketch_name"], "end_condition": "through_all_both"},
        expect_ok=False,
    )

    assert not payload["ok"], "a self-intersecting profile must not cut"
    remediation = " ".join(payload["error"]["remediation"])
    assert "reverse=true" not in remediation, "reverse cannot help a symmetric cut"
    assert "sw_sketch_diagnose" in remediation
    assert "both ways" in remediation


def test_diagnose_reaches_the_same_verdict(call):
    """The tool the remediation names has to actually answer the question."""
    bad = _sketch(call, _root_region("counterclockwise"))
    found = call("sw_sketch_diagnose", {"sketch_name": bad["sketch_name"]})["result"]

    assert found["contours"]["self_intersections"]
    assert any("self-intersection" in w for w in found["warnings"])


# --- how the batch arrives, and how much comes back ------------------------------


def test_a_profile_can_arrive_as_a_file(call, scratch_root, unique_name):
    """Anything that computes a profile has already written it to a file."""
    path = scratch_root / f"{unique_name}_profile.json"
    path.write_text(json.dumps(_root_region("clockwise")), encoding="utf-8")

    result = call(
        "sw_sketch_create",
        {
            "on": {"standard_plane": "front"},
            "auto_relations": False,
            "entities_file": str(path),
        },
    )["result"]

    assert result["created_total"] == 6
    assert result["contours"]["closed_contour_count"] == 1
    assert result["max_deviation_mm"] == pytest.approx(0.0, abs=1e-3)
    path.unlink(missing_ok=True)


def test_compacting_keeps_handles_usable(call):
    """A compacted entry must still address its segment well enough to delete it."""
    result = _sketch(call, _root_region("clockwise"), detail="compact", exit_sketch=False)

    assert result["created_compacted"] is True
    assert result["created_total"] == 6
    assert "length_m" not in result["created"][0]

    handle = result["created"][0]["sketch_local_id"]
    removed = call(
        "sw_sketch_delete",
        {"segment_ids": [handle], "confirm": True},
    )["result"]
    assert removed["deleted"] == [handle]
    call("sw_sketch_exit", {})


# --- deleting from a sketch that is not the open one -----------------------------


def test_a_closed_sketch_can_be_edited_by_name(call):
    """``sw_sketch_delete`` used to reach only the sketch open for editing.

    Everything else in this domain takes ``sketch_name``; this one did not, so
    correcting a finished sketch meant deleting the whole feature and rebuilding it.
    """
    made = _sketch(call, _root_region("clockwise"))
    name = made["sketch_name"]
    handle = made["created"][0]["sketch_local_id"]

    removed = call(
        "sw_sketch_delete",
        {"sketch_name": name, "segment_ids": [handle], "confirm": True},
    )["result"]

    assert removed["deleted"] == [handle]
    # Opened and closed again: nothing is left in edit mode behind the caller's back.
    assert call("sw_sketch_list", {})["result"]["active_sketch"] is None

    after = call("sw_sketch_diagnose", {"sketch_name": name})["result"]
    assert after["segment_count"] == 5


def test_editing_a_second_sketch_is_refused_not_forced(call):
    """Closing whichever sketch is open is not a side effect a delete should have."""
    first = _sketch(call, _root_region("clockwise"))
    still_open = _sketch(call, _root_region("clockwise"), exit_sketch=False)
    assert still_open["sketch_name"] != first["sketch_name"]

    payload = call(
        "sw_sketch_delete",
        {
            "sketch_name": first["sketch_name"],
            "segment_ids": [first["created"][0]["sketch_local_id"]],
            "confirm": True,
        },
        expect_ok=False,
    )
    assert payload["error"]["code"] == "SKETCH_ALREADY_OPEN"

    # The open sketch is untouched.
    assert call("sw_sketch_list", {})["result"]["active_sketch"] == still_open["sketch_name"]
    call("sw_sketch_exit", {})
