"""A schema rejection must come back as a payload, not as an exception.

``ValidationError.errors()`` looks JSON-safe and is not. When a ``model_validator``
raises — which is how several operations express "these arguments do not go together" —
pydantic puts the original ``ValueError`` object into the entry's ``ctx``. Putting that
straight into the error envelope made the envelope unserializable, so the most ordinary
failure there is escaped the server as a ``PydanticSerializationError`` instead of
arriving as ``INVALID_ARGUMENTS``.

Every operation is checked here rather than the handful that have validators today,
because the next one to grow a validator should not be able to reintroduce this.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError, model_validator

from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.config import SwmcpConfig
from swmcp.dispatch import Dispatcher
from swmcp.errors import wire_safe_validation_errors


class Refuses(BaseModel):
    """A model whose validator raises, the way the real argument models do."""

    left: int = 0

    @model_validator(mode="after")
    def _never(self) -> Refuses:
        raise ValueError("these arguments do not go together")


class Unserializable:
    """Something pydantic would happily put in an error's ``input`` field."""

    def __repr__(self) -> str:  # pragma: no cover - only reached on failure
        raise AssertionError("the reducer must not repr the input object")


class SpyWorker:
    def call(self, fn, *, label, kind="read", timeout_s=None):
        raise AssertionError(f"{label} should have been refused before the worker")

    def stop(self, timeout: float = 5.0) -> None:
        pass


@pytest.fixture(scope="module", autouse=True)
def _catalog():
    load_all_ops()


@pytest.fixture
def dispatcher(tmp_path):
    return Dispatcher(
        SwmcpConfig(worker_start_timeout_s=2.0, allowed_roots=(tmp_path,)),
        worker=SpyWorker(),
    )


def test_a_validator_failure_survives_serialization():
    try:
        Refuses(left=1)
    except ValidationError as exc:
        reduced = wire_safe_validation_errors(exc)
    else:  # pragma: no cover - the model always refuses
        pytest.fail("the fixture model should have raised")

    json.dumps(reduced), "the whole point is that this can be serialized"
    assert reduced
    assert "do not go together" in reduced[0]["msg"]
    assert "ctx" not in reduced[0], "the raw exception object must not come along"


def test_the_reducer_describes_an_input_it_cannot_serialize():
    class Holds(BaseModel):
        value: int

    try:
        Holds(value=Unserializable())
    except ValidationError as exc:
        reduced = wire_safe_validation_errors(exc)
    else:  # pragma: no cover
        pytest.fail("an object is not an int")

    json.dumps(reduced)
    assert reduced[0]["input"] == "<Unserializable>"


def test_the_reducer_keeps_plain_values_readable():
    class Holds(BaseModel):
        value: int

    try:
        Holds(value="not a number")
    except ValidationError as exc:
        reduced = wire_safe_validation_errors(exc)
    else:  # pragma: no cover
        pytest.fail("a string is not an int")

    assert reduced[0]["loc"] == ["value"]
    assert reduced[0]["input"] == "not a number"


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        # Each of these trips a model_validator rather than a plain field constraint.
        ("sw_body_primitive", {"kind": "cylinder", "radius": 10}),
        ("sw_body_primitive", {"kind": "torus", "radius": 10, "tube_radius": 12}),
        ("sw_export", {"output_path": "C:/cad/a.step", "format": "stl"}),
        ("sw_safe_execute", {"steps": [], "confirm": True}),
    ],
)
def test_a_validator_rejection_arrives_as_a_payload(dispatcher, tool, args):
    payload = dispatcher.call(tool, args)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENTS"
    assert payload["error"]["context"]["errors"], "the reason must survive"
    json.dumps(payload), "an MCP client receives this as JSON"


def test_every_argument_model_produces_a_serializable_rejection(dispatcher):
    """Send each operation an argument it cannot possibly accept, and check the answer.

    An unknown key is refused by every model, so this reaches all of them without
    needing to know what each one wants.
    """
    problems = []
    for name in sorted(OPS):
        payload = dispatcher.call(name, {"definitely_not_a_field": object()})
        try:
            json.dumps(payload)
        except TypeError as exc:  # pragma: no cover - the bug this test exists for
            problems.append(f"{name}: {exc}")
            continue
        if payload["ok"] or payload["error"]["code"] != "INVALID_ARGUMENTS":
            problems.append(f"{name}: got {payload.get('error', {}).get('code')}")
    assert not problems, "these did not refuse an unknown field cleanly:\n" + "\n".join(problems)


def test_a_missing_confirmation_is_still_reported_as_a_policy_problem(dispatcher):
    """The reducer changed the shape of ``loc``; the confirm special case must follow."""
    payload = dispatcher.call("sw_feature_delete", {"feature_name": "Plate"})

    assert payload["error"]["code"] == "CONFIRM_REQUIRED"
    assert any("confirm=true" in step for step in payload["error"]["remediation"])
