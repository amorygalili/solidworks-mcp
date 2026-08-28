"""A number in an equation means whatever the document's units say it means.

Equations are the one surface in this server that is text rather than an API call, and
SOLIDWORKS evaluates that text in document units. On the stock part template here that
is inches, so ``"Width" = 120`` sets 120 inches while every other path in this codebase
speaks metres. Measured on SOLIDWORKS 2026 SP3.0:

===============  ==========================  =========================
expression       result on a 100x4 mm plate  meaning
===============  ==========================  =========================
``120``          1219200 mm3                 120 inches
``120mm``        48000 mm3                   120 millimetres
``120 mm``       rejected by SOLIDWORKS      the space is not allowed
===============  ==========================  =========================

The server cannot rewrite the caller's expression — it is an arbitrary formula, not a
length field — so it reports the document's unit and warns when a bare number appears.
"""

from __future__ import annotations

import pytest

from swmcp.handlers.parameter import _has_unitless_quantity, _unit_warnings


@pytest.mark.parametrize(
    "expression",
    ["120", "120.5", '"Width" + 10', '"A" - 3', "2 + 3"],
)
def test_a_bare_number_is_flagged(expression):
    assert _has_unitless_quantity(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "120mm",
        '"Width" + 10mm',
        '"Thickness" * 1.5',
        '1.5 * "Thickness"',
        '"A" / 2',
        '"A" ^ 2',
        '"Width"',
        "",
    ],
)
def test_an_expression_that_needs_no_unit_is_left_alone(expression):
    """A multiplier is a ratio; warning about it would train the reader to ignore this."""
    assert not _has_unitless_quantity(expression)


def test_the_warning_names_the_unit_and_the_expressions():
    warnings = _unit_warnings(["120", '"Thickness" * 1.5', '"Width" + 10'], "inches")

    assert len(warnings) == 1
    assert "inches" in warnings[0]
    assert "'120'" in warnings[0]
    assert "1.5" not in warnings[0], "the ratio is not a unit problem"


def test_no_warning_when_every_expression_says_what_it_means():
    assert _unit_warnings(["120mm", '"Thickness" * 1.5'], "inches") == []


def test_both_equation_results_report_the_document_unit():
    """A caller cannot interpret an equation list without knowing this."""
    from swmcp.schemas.parameter import EquationListResult, EquationSetResult

    for model in (EquationListResult, EquationSetResult):
        assert "document_length_unit" in model.model_fields


def test_a_global_variable_cannot_be_scoped_to_one_configuration():
    """SOLIDWORKS requires global variables to apply to every configuration.

    From IEquationMgr::Add3: "When adding global variable assignments and component
    equations, WhichConfigurations must be set to swAllConfiguration." Refusing this in
    the schema turns a -1 from deep inside COM into a readable rejection.
    """
    import pytest
    from pydantic import ValidationError

    from swmcp.schemas.parameter import EquationSpec

    with pytest.raises(ValidationError, match="every configuration"):
        EquationSpec(
            name="Width",
            expression="120mm",
            global_variable=True,
            configuration_scope="this",
        )


def test_specifying_configurations_means_naming_them():
    import pytest
    from pydantic import ValidationError

    from swmcp.schemas.parameter import EquationSpec

    with pytest.raises(ValidationError, match="at least one configuration"):
        EquationSpec(name="D1@Sketch1", expression="120mm", configuration_scope="specify")

    allowed = EquationSpec(
        name="D1@Sketch1",
        expression="120mm",
        configuration_scope="specify",
        configurations=["Default", "Large"],
    )
    assert allowed.configurations == ["Default", "Large"]


def test_a_dimension_equation_may_be_scoped():
    """The capability exists again; it was removed once on a false premise."""
    from swmcp.schemas.parameter import EquationSpec

    spec = EquationSpec(name="D1@Sketch1", expression="120mm", configuration_scope="this")

    assert spec.configuration_scope == "this"
    assert spec.global_variable is False
