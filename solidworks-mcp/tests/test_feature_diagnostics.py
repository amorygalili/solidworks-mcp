"""What a failed edge feature and a merge-only relation batch report, without SOLIDWORKS.

Both are cases where the server had the evidence and threw it away: a fillet failure
with an empty context, and a merge verified against a relation count it can never move.
"""

from __future__ import annotations

from swmcp.com import swconst
from swmcp.handlers.constraint import _merge_detail, _points_were_merged
from swmcp.handlers.feature import _END_CONDITION, _edge_sizing
from swmcp.refs.model import EntityRef, RefMeasurements, SemanticRef


def edge(label: str, length_mm: float) -> EntityRef:
    return EntityRef(
        kind="edge",
        label=label,
        semantic=SemanticRef(measurements=RefMeasurements(length_m=length_mm / 1000.0)),
    )


# --- end conditions -----------------------------------------------------------


def test_every_end_condition_names_a_real_constant():
    for token in _END_CONDITION.values():
        assert isinstance(swconst.value("swEndConditions_e", token), int)


def test_through_all_both_is_sent_as_through_all_on_two_directions():
    """Not as swEndCondThroughAllBoth, whose name overpromises.

    Passing 9 as T1 on a single-ended cut behaves like plain through-all: measured on
    2026 (34.3.0), a 10mm bore through a 40mm cube sketched on its mid-plane removed
    half the volume it should have and stopped at the sketch plane. The constant is
    real - the behaviour is not - so the mapping says what actually goes over the wire.
    Pinned live in tests/live/test_live_spline_contours.py.
    """
    assert _END_CONDITION["through_all_both"] == "swEndCondThroughAll"
    assert swconst.value("swEndConditions_e", "swEndCondThroughAllBoth") == 9


# --- fillet sizing ------------------------------------------------------------


def test_the_edges_too_short_for_the_radius_are_named():
    """The knight's ear: one sharp edge fails the fillet and nothing said which."""
    sizing = _edge_sizing([edge("long edge", 30.0), edge("ear tip", 0.4)], 0.001)

    assert sizing["size_mm"] == 1.0
    assert sizing["shortest_edge_mm"] == 0.4
    assert [item["label"] for item in sizing["edges_shorter_than_size"]] == ["ear tip"]


def test_edges_that_fit_are_not_blamed():
    sizing = _edge_sizing([edge("a", 30.0), edge("b", 12.0)], 0.001)

    assert sizing["edges_shorter_than_size"] == []
    assert sizing["shortest_edge_mm"] == 12.0


def test_unmeasured_references_still_report_the_size_asked_for():
    """References captured without a length must not crash the failure path."""
    assert _edge_sizing([EntityRef(kind="edge", label="bare")], 0.002) == {"size_mm": 2.0}


def test_the_shortest_edges_are_listed_first_and_capped():
    sizing = _edge_sizing([edge(f"e{i}", float(i)) for i in range(20, 0, -1)], 0.030)

    labels = [item["label"] for item in sizing["edges_shorter_than_size"]]
    assert labels[:3] == ["e1", "e2", "e3"]
    assert len(labels) == 10, "a failure message should not list every edge in the body"


# --- merge verification -------------------------------------------------------


def test_fusing_loose_ends_counts_as_merged():
    before = {"loose_ends_mm": [[0.0, 0.0], [0.0, 0.0]], "open_contour_count": 1}
    after = {"loose_ends_mm": [], "open_contour_count": 0}

    assert _points_were_merged(before, after) is True
    assert "2 -> 0 loose ends" in _merge_detail(before, after)


def test_a_merge_that_changed_nothing_is_reported_as_such():
    unchanged = {"loose_ends_mm": [[0.0, 0.0], [1.0, 1.0]], "open_contour_count": 1}

    assert _points_were_merged(unchanged, unchanged) is False


def test_a_merge_on_an_already_closed_profile_is_not_a_failure():
    """Nothing to close means nothing to prove, and no grounds to claim it failed."""
    closed = {"loose_ends_mm": [], "open_contour_count": 0}

    assert _points_were_merged(closed, closed) is True


def test_topology_that_was_never_read_does_not_fail_the_check():
    assert _points_were_merged({}, {}) is True
