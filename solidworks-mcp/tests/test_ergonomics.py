"""The shorthands and predicates, checked where they can be checked without SOLIDWORKS.

Each of these exists because driving the server through a real modelling job made the
same friction show up repeatedly: an EntityRef demanded for the part's own centreline,
edges nameable only one captured reference at a time, a delete that quietly left the
sketch it consumed behind, and three calls for every profile.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.com import swconst
from swmcp.handlers.feature import _STANDARD_AXIS_PLANES, STANDARD_AXIS_PREFIX
from swmcp.refs.model import EntityRef, RefMeasurements, SemanticRef
from swmcp.refs.probes import ProbeFilters, _matches
from swmcp.schemas.feature import ChamferArgs, FilletArgs, PatternArgs
from swmcp.schemas.sketch import SketchCreateArgs

REF = {"kind": "edge", "document": {"path": r"C:\cad\part.SLDPRT"}}


# --- pattern axis shorthand ---------------------------------------------------


def test_every_model_axis_is_two_standard_planes():
    """Front is XY, Top is XZ, Right is YZ, so each pair meets on one axis."""
    assert _STANDARD_AXIS_PLANES == {
        "x": ("front", "top"),
        "y": ("front", "right"),
        "z": ("top", "right"),
    }


def test_the_axis_planes_are_named_the_way_sketch_start_names_them():
    """A different spelling here would resolve a different plane, or none."""
    for pair in _STANDARD_AXIS_PLANES.values():
        for plane in pair:
            assert plane in {"front", "top", "right"}


def test_a_pattern_can_name_the_axis_without_an_entity_reference():
    args = PatternArgs(type="circular", feature_names=["Cut1"], count=4, standard_axis="y")
    assert args.standard_axis == "y"
    assert args.direction_ref is None


def test_a_pattern_refuses_two_directions():
    """Naming both would leave the handler quietly preferring one."""
    with pytest.raises(ValidationError, match="not both"):
        PatternArgs(
            type="circular",
            feature_names=["Cut1"],
            count=4,
            standard_axis="y",
            direction_ref=REF,
        )


def test_an_unknown_axis_is_refused_by_the_schema():
    with pytest.raises(ValidationError):
        PatternArgs(type="circular", feature_names=["Cut1"], count=4, standard_axis="w")


def test_axes_this_server_makes_are_named_so_they_can_be_found_again():
    """Without a stable name every pattern about Y would add another axis."""
    assert STANDARD_AXIS_PREFIX
    assert all(
        f"{STANDARD_AXIS_PREFIX}{axis}" != STANDARD_AXIS_PREFIX
        for axis in _STANDARD_AXIS_PLANES
    )


# --- delete_children ----------------------------------------------------------


def test_the_delete_options_are_independent_bits():
    """They are flags, not modes - which is why sending one alone orphaned a sketch."""
    absorbed = swconst.value("swDeleteSelectionOptions_e", "swDelete_Absorbed")
    children = swconst.value("swDeleteSelectionOptions_e", "swDelete_Children")
    assert absorbed == 2
    assert children == 1
    assert absorbed | children == 3
    assert absorbed & children == 0


# --- edge predicates ----------------------------------------------------------


def edge(length_m: float, geometry_type: str = "line") -> EntityRef:
    return EntityRef(
        kind="edge",
        semantic=SemanticRef(
            geometry_type=geometry_type,
            measurements=RefMeasurements(length_m=length_m),
        ),
    )


def test_an_edge_longer_than_the_bound_matches():
    assert _matches(edge(0.005), ProbeFilters(length_min_m=0.002))


def test_an_edge_shorter_than_the_bound_does_not():
    """The guard that matters: a fillet bigger than its edge is how the feature fails."""
    assert not _matches(edge(0.001), ProbeFilters(length_min_m=0.002))


def test_an_upper_bound_excludes_the_long_ones():
    assert not _matches(edge(0.05), ProbeFilters(length_max_m=0.01))
    assert _matches(edge(0.005), ProbeFilters(length_max_m=0.01))


def test_an_entity_with_no_length_cannot_satisfy_a_length_bound():
    """Silently passing something unmeasured would put it in the selection."""
    faceless = EntityRef(kind="face", semantic=SemanticRef(measurements=RefMeasurements()))
    assert not _matches(faceless, ProbeFilters(length_min_m=0.002))


def test_length_bounds_do_not_disturb_the_other_filters():
    assert _matches(edge(0.005), ProbeFilters())
    assert not _matches(edge(0.005, "circle"), ProbeFilters(geometry_type="line"))


@pytest.mark.parametrize("model", [FilletArgs, ChamferArgs])
def test_an_edge_feature_takes_references_or_a_predicate(model):
    size = {"radius": 2} if model is FilletArgs else {"distance": 2}
    by_ref = model(refs=[REF], **size)
    assert by_ref.edges is None

    by_query = model(edges={"body_name": "Body1", "min_length": 2}, **size)
    assert by_query.refs == []
    assert by_query.edges.min_length == pytest.approx(0.002)


@pytest.mark.parametrize("model", [FilletArgs, ChamferArgs])
def test_an_edge_feature_refuses_both_ways_at_once(model):
    size = {"radius": 2} if model is FilletArgs else {"distance": 2}
    with pytest.raises(ValidationError, match="exactly one of refs or edges"):
        model(refs=[REF], edges={"body_name": "Body1"}, **size)


@pytest.mark.parametrize("model", [FilletArgs, ChamferArgs])
def test_an_edge_feature_refuses_neither(model):
    size = {"radius": 2} if model is FilletArgs else {"distance": 2}
    with pytest.raises(ValidationError, match="exactly one of refs or edges"):
        model(**size)


@pytest.mark.parametrize("model", [FilletArgs, ChamferArgs])
def test_the_predicate_cannot_ask_for_more_edges_than_the_feature_accepts(model):
    """refs caps at 200, so a predicate that could return 2000 would truncate silently."""
    size = {"radius": 2} if model is FilletArgs else {"distance": 2}
    assert model.model_fields["refs"].metadata
    with pytest.raises(ValidationError):
        model(edges={"limit": 2000}, **size)


# --- the composite sketch -----------------------------------------------------


def test_a_composed_sketch_defaults_to_closing_itself():
    args = SketchCreateArgs(
        on={"standard_plane": "front"},
        entities=[{"type": "circle", "center": [0, 0], "radius": 10}],
    )
    assert args.exit_sketch is True
    assert args.rebuild is True
    assert args.auto_relations is True


def test_a_composed_sketch_can_be_left_open_for_more_work():
    args = SketchCreateArgs(
        on={"standard_plane": "front"},
        entities=[{"type": "circle", "center": [0, 0], "radius": 10}],
        exit_sketch=False,
    )
    assert args.exit_sketch is False


def test_a_composed_sketch_carries_the_inference_switch():
    args = SketchCreateArgs(
        on={"standard_plane": "front"},
        entities=[{"type": "line", "start": [0, 0], "end": [10, 0]}],
        auto_relations=False,
    )
    assert args.auto_relations is False


def test_a_composed_sketch_needs_somewhere_to_draw():
    with pytest.raises(ValidationError):
        SketchCreateArgs(entities=[{"type": "circle", "center": [0, 0], "radius": 10}])
