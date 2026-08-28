"""Live cover for the atomic mutate-and-validate workflow (REV-006).

The interesting cases are the failures. A sequence that works is easy; the claim worth
testing is that a sequence which goes wrong leaves the model exactly where it started,
and says so.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

PLATE_X, PLATE_Y, PLATE_Z = 100.0, 60.0, 8.0
PLATE_VOLUME = PLATE_X * PLATE_Y * PLATE_Z


@pytest.fixture
def plate(call, scratch_root, unique_name):
    """A saved part with one plate, so a checkpoint of it exists to roll back to."""
    for stale in scratch_root.glob(f"{unique_name}*"):
        stale.unlink(missing_ok=True)
    target = scratch_root / f"{unique_name}.SLDPRT"

    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_X, PLATE_Y]}]},
    )
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": PLATE_Z, "name": "Plate"})
    call("sw_doc_save", {"output_path": str(target), "overwrite": "allow", "confirm": True})
    return target


def _volume(call) -> float:
    return call("sw_measure")["result"]["mass_properties"]["volume_mm3"]


def _fillet_step(call, radius: float = 5) -> dict:
    edges = call("sw_probe_faces", {"entity_class": "edge", "geometry_type": "line_edge"})
    vertical = [
        candidate
        for candidate in edges["result"]["candidates"]
        if candidate["measurements"].get("length_m")
        and abs(candidate["measurements"]["length_m"] - PLATE_Z / 1000.0) < 1e-9
    ][:4]
    assert len(vertical) == 4
    return {
        "tool": "sw_feature_fillet",
        "args": {
            "refs": [candidate["tool_args"]["ref"] for candidate in vertical],
            "radius": radius,
            "name": "Corners",
        },
    }


def test_a_sequence_that_holds_its_invariants_is_kept(call, plate):
    outcome = call(
        "sw_safe_execute",
        {
            "steps": [_fillet_step(call)],
            "invariants": {
                "body_count": 1,
                "volume_change": "decrease",
                "require_features": ["Plate", "Corners"],
                "max_volume_mm3": PLATE_VOLUME,
            },
            "confirm": True,
        },
    )["result"]

    assert outcome["completed"] == 1
    assert outcome["invariants_held"] is True
    assert outcome["rolled_back"] is False
    assert all(entry["held"] for entry in outcome["invariants_checked"])
    assert all(check["passed"] for check in outcome["verification"]["checks"])
    assert _volume(call) < PLATE_VOLUME, "the fillet is still there"


def test_a_failing_invariant_rolls_the_whole_sequence_back(call, plate):
    """The headline behaviour: the model returns to where it started."""
    outcome = call(
        "sw_safe_execute",
        {
            "steps": [_fillet_step(call)],
            # The fillet removes material, so this cannot hold.
            "invariants": {"volume_change": "increase"},
            "confirm": True,
        },
    )["result"]

    assert outcome["completed"] == 1, "the step itself ran"
    assert outcome["invariants_held"] is False
    assert outcome["rolled_back"] is True
    assert outcome["rollback"]["restored_from"]
    assert outcome["rollback"]["pre_restore_checkpoint"], "the restore is itself reversible"
    assert any("rolled back" in warning for warning in outcome["warnings"])

    assert _volume(call) == pytest.approx(PLATE_VOLUME, rel=1e-6)
    names = [f["name"] for f in call("sw_feature_list")["result"]["features"]]
    assert "Corners" not in names, "the fillet must be gone after the rollback"


def test_a_failing_step_rolls_back_the_steps_before_it(call, plate):
    """Half-applied is the state this operation exists to prevent."""
    outcome = call(
        "sw_safe_execute",
        {
            "steps": [
                _fillet_step(call),
                {"tool": "sw_feature_shell", "args": {"thickness": 500}},
            ],
            "confirm": True,
        },
    )["result"]

    assert outcome["completed"] == 1
    assert outcome["step_results"][1]["ok"] is False
    assert outcome["step_results"][1]["error"]["code"] == "SHELL_FAILED"
    assert outcome["rolled_back"] is True

    assert _volume(call) == pytest.approx(PLATE_VOLUME, rel=1e-6), (
        "the fillet from the first step must have been undone too"
    )


def test_rollback_can_be_turned_off_to_inspect_a_partial_result(call, plate):
    outcome = call(
        "sw_safe_execute",
        {
            "steps": [_fillet_step(call)],
            "invariants": {"volume_change": "increase"},
            "rollback_on_failure": False,
            "confirm": True,
        },
    )["result"]

    assert outcome["invariants_held"] is False
    assert outcome["rolled_back"] is False
    assert any("NOT rolled back" in warning for warning in outcome["warnings"])
    assert _volume(call) < PLATE_VOLUME, "the partial result is deliberately still here"


def test_every_step_is_validated_before_any_of_them_runs(call, plate):
    """A typo in the last step must not leave the first one applied."""
    refused = call(
        "sw_safe_execute",
        {
            "steps": [
                _fillet_step(call),
                {"tool": "sw_feature_chamfer", "args": {"nonsense": 1}},
            ],
            "confirm": True,
        },
        expect_ok=False,
    )

    assert refused["error"]["code"] == "INVALID_ARGUMENTS"
    assert _volume(call) == pytest.approx(PLATE_VOLUME, rel=1e-6)
    names = [f["name"] for f in call("sw_feature_list")["result"]["features"]]
    assert "Corners" not in names, "nothing should have run at all"


def test_a_destructive_step_still_needs_its_own_confirmation(call, plate):
    refused = call(
        "sw_safe_execute",
        {
            "steps": [{"tool": "sw_feature_delete", "args": {"feature_name": "Plate"}}],
            "confirm": True,
        },
        expect_ok=False,
    )

    assert refused["error"]["code"] == "CONFIRM_REQUIRED"
    assert call("sw_body_list")["result"]["count"] == 1


def test_a_step_that_would_change_the_document_is_refused(call, plate):
    """Closing the document would make the checkpoint point at nothing."""
    refused = call(
        "sw_safe_execute",
        {
            "steps": [
                {
                    "tool": "sw_doc_close",
                    "args": {"save_first": "discard", "confirm": True},
                }
            ],
            "confirm": True,
        },
        expect_ok=False,
    )

    assert refused["error"]["code"] == "STEP_NOT_ALLOWED"
    assert "sw_doc_close" in refused["error"]["context"]["forbidden"]


def test_safe_execute_cannot_nest(call, plate):
    refused = call(
        "sw_safe_execute",
        {
            "steps": [{"tool": "sw_safe_execute", "args": {"steps": [], "confirm": True}}],
            "confirm": True,
        },
        expect_ok=False,
    )
    assert refused["error"]["code"] in {"STEP_NOT_ALLOWED", "INVALID_ARGUMENTS"}


def test_the_sequence_itself_needs_confirmation(call, plate):
    refused = call(
        "sw_safe_execute", {"steps": [_fillet_step(call)]}, expect_ok=False
    )
    assert refused["error"]["code"] == "CONFIRM_REQUIRED"


def test_a_read_only_step_is_allowed_between_mutations(call, plate):
    """Measuring mid-sequence is useful and must not be treated as a mutation."""
    outcome = call(
        "sw_safe_execute",
        {
            "steps": [
                {"tool": "sw_measure", "label": "before"},
                _fillet_step(call),
                {"tool": "sw_measure", "label": "after"},
            ],
            "invariants": {"volume_change": "decrease"},
            "confirm": True,
        },
    )["result"]

    assert outcome["completed"] == 3
    assert outcome["invariants_held"] is True
    assert [entry["label"] for entry in outcome["step_results"]] == [
        "before",
        "sw_feature_fillet",
        "after",
    ]
