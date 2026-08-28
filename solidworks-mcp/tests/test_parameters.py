"""The parameter domain's pure logic, checked without SOLIDWORKS.

Equation text parsing and cycle detection are ordinary functions over strings, so they
get ordinary tests. Doing this here rather than live matters because the cases worth
covering — a self-reference, a three-step loop, an expression that reads a name nothing
defines — are exactly the ones SOLIDWORKS itself may refuse to create.
"""

from __future__ import annotations

import pytest

from swmcp.handlers.parameter import _find_cycles, _split_equation


def _equation(text: str) -> dict:
    """One entry shaped the way the reader builds it."""
    import re

    name, expression = _split_equation(text)
    return {
        "text": text,
        "name": name,
        "expression": expression,
        "reads": sorted(set(re.findall(r'"([^"]+)"', expression or ""))),
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('"Width" = 120', ("Width", "120")),
        ('"D1@Sketch1" = "Width" * 2', ("D1@Sketch1", '"Width" * 2')),
        ('  "Gap"="Width"/4  ', ("Gap", '"Width"/4')),
        ("Height = 40", ("Height", "40")),
    ],
)
def test_an_equation_splits_into_the_name_it_drives_and_the_expression(text, expected):
    assert _split_equation(text) == expected


def test_text_that_is_not_an_assignment_yields_nothing_rather_than_a_guess():
    assert _split_equation("") == (None, None)
    assert _split_equation("just a comment") == (None, None)


def test_a_straight_dependency_chain_is_not_a_cycle():
    equations = [
        _equation('"Width" = 100'),
        _equation('"Length" = "Width" * 2'),
        _equation('"Gap" = "Length" - "Width"'),
    ]
    assert _find_cycles(equations) == []


def test_a_self_reference_is_reported():
    cycles = _find_cycles([_equation('"Width" = "Width" + 1')])
    assert cycles == [["Width", "Width"]]


def test_a_two_step_loop_is_reported_once():
    cycles = _find_cycles(
        [_equation('"A" = "B" + 1'), _equation('"B" = "A" + 1')]
    )
    assert len(cycles) == 1, f"one loop, reported once, not once per entry point: {cycles}"
    assert set(cycles[0]) == {"A", "B"}


def test_a_three_step_loop_is_reported():
    cycles = _find_cycles(
        [
            _equation('"A" = "B"'),
            _equation('"B" = "C"'),
            _equation('"C" = "A"'),
        ]
    )
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B", "C"}


def test_two_independent_loops_are_both_reported():
    cycles = _find_cycles(
        [
            _equation('"A" = "B"'),
            _equation('"B" = "A"'),
            _equation('"X" = "Y"'),
            _equation('"Y" = "X"'),
        ]
    )
    assert len(cycles) == 2
    assert {frozenset(cycle) for cycle in cycles} == {frozenset({"A", "B"}), frozenset({"X", "Y"})}


def test_a_reference_to_something_undefined_is_not_a_cycle():
    """Reading a dimension the equation list does not define is normal, not a loop."""
    cycles = _find_cycles([_equation('"Width" = "D1@Sketch1" * 2')])
    assert cycles == []


def test_cycle_detection_terminates_on_a_dense_graph():
    """Every name reads every other name: the walk must not run away."""
    names = [f"V{index}" for index in range(8)]
    equations = [
        _equation(f'"{name}" = ' + " + ".join(f'"{other}"' for other in names if other != name))
        for name in names
    ]
    cycles = _find_cycles(equations)
    assert cycles, "a fully connected graph is full of cycles"
