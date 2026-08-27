"""The request pipeline's gates, proven without SOLIDWORKS.

These are the tests ``swmcp.catalog.scope.PLATFORM_REQUIREMENTS`` names as the proof
for SAFE-003, SAFE-007, and DISC-001 — requirements no single tool satisfies. The
important property of each is that the gate fires *before* the COM boundary, which is
asserted by spying on the worker: a refused request must never reach SOLIDWORKS.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from swmcp.catalog.registry import load_all_ops
from swmcp.config import SwmcpConfig
from swmcp.dispatch import Dispatcher
from swmcp.server import list_tool_descriptors, search_tools

BASE = SwmcpConfig(worker_start_timeout_s=2.0)


class SpyWorker:
    """Stands in for the STA worker and records whether COM was ever reached."""

    def __init__(self):
        self.submitted: list[str] = []

    def call(self, fn, *, label, kind="read", timeout_s=None):
        self.submitted.append(label)
        raise AssertionError(
            f"{label} reached the worker; this request should have been refused first"
        )

    def stop(self, timeout: float = 5.0) -> None:
        pass

    def health_snapshot(self) -> dict:
        return {}


@pytest.fixture
def dispatcher(tmp_path):
    load_all_ops()
    config = replace(
        BASE, allowed_roots=(tmp_path,), audit_path=tmp_path / "audit.jsonl"
    )
    made = Dispatcher(config, worker=SpyWorker())
    return made


def test_destructive_requires_confirm(dispatcher):
    """SAFE-003, and it is refused before any COM call happens."""
    payload = dispatcher.call("sw_doc_close", {"save_first": "discard"})

    assert payload["ok"] is False
    assert payload["error"]["code"] == "CONFIRM_REQUIRED"
    assert any("confirm=true" in step for step in payload["error"]["remediation"])
    assert dispatcher.worker.submitted == [], "the gate must fire before the COM boundary"


def test_output_paths_are_refused_before_the_com_boundary(dispatcher):
    """SAFE-004 in the pipeline, not just in the guard's own unit tests."""
    payload = dispatcher.call("sw_doc_save", {"output_path": r"C:\windows\system32\x.SLDPRT"})

    assert payload["ok"] is False
    assert payload["error"]["code"] == "PATH_NOT_ALLOWED"
    assert dispatcher.worker.submitted == []


def test_unknown_arguments_are_refused_before_the_com_boundary(dispatcher):
    """SAFE-001."""
    payload = dispatcher.call("sw_doc_list", {"nope": 1})

    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENTS"
    assert payload["error"]["context"]["errors"]
    assert dispatcher.worker.submitted == []


def test_an_unknown_tool_is_an_error_not_a_crash(dispatcher):
    payload = dispatcher.call("sw_not_a_tool", {})

    assert payload["ok"] is False
    assert payload["error"]["code"] == "UNKNOWN_TOOL"
    assert dispatcher.worker.submitted == []


def test_preflight_skips_mutation(dispatcher):
    """SAFE-007: every operation offering preflight declares it in its schema."""
    from swmcp.catalog.registry import OPS

    offering = [
        spec
        for spec in OPS.values()
        if "preflight" in spec.args_model.model_fields
    ]
    assert offering, "no operation offers a preflight"

    for spec in offering:
        field = spec.args_model.model_fields["preflight"]
        assert field.default is False, f"{spec.name}: preflight must be opt-in"
        assert spec.safety.kind == "model_mutation", (
            f"{spec.name}: preflight only makes sense for something that would mutate"
        )
        schema = spec.args_model.model_json_schema()
        assert "preflight" in schema["properties"]


def test_search_tools_sees_untiered_ops():
    """DISC-001: a search that can only find what you have cannot tell you what you lack."""
    load_all_ops()
    core = replace(BASE, tool_tier="core")

    registered = {tool.name for tool in list_tool_descriptors(core)}
    found = search_tools("", limit=100, config=core)

    assert found["matched"] > len(registered), "the catalog is larger than the core tier"

    hidden = [hit for hit in found["tools"] if not hit["available"]]
    assert hidden, "some operations should sit above the core tier"
    for hit in hidden:
        assert hit["tier_needed"], "an unavailable tool must say which tier it needs"
    assert "SWMCP_TOOL_TIER" in found["hint"]


def test_search_matches_by_name_domain_and_requirement_id():
    load_all_ops()
    config = replace(BASE, tool_tier="all")

    by_name = search_tools("extrude", config=config)
    assert any(hit["name"] == "sw_feature_extrude_boss" for hit in by_name["tools"])

    by_domain = search_tools("", domain="sketch", config=config)
    assert by_domain["matched"] > 0
    assert all("sketch" in hit["domains"] for hit in by_domain["tools"])

    by_requirement = search_tools("REF-006", config=config)
    assert any(hit["name"] == "sw_ref_resolve" for hit in by_requirement["tools"])


def test_search_tools_is_available_at_every_tier():
    for tier in ("core", "extended", "advanced", "debug", "all"):
        names = {tool.name for tool in list_tool_descriptors(replace(BASE, tool_tier=tier))}
        assert "sw_search_tools" in names, f"missing from the {tier} tier"


def test_tier_gating_is_monotonic():
    load_all_ops()
    sizes = [
        len(list_tool_descriptors(replace(BASE, tool_tier=tier)))
        for tier in ("core", "extended", "advanced", "debug")
    ]
    assert sizes == sorted(sizes), "a higher tier must never expose fewer tools"
    assert sizes[0] < sizes[-1]


def test_published_schemas_are_strict_and_described():
    """What an MCP client actually receives."""
    for tool in list_tool_descriptors(replace(BASE, tool_tier="all")):
        schema = tool.input_schema
        assert schema.get("type") == "object", tool.name
        assert schema.get("additionalProperties") is False, (
            f"{tool.name}: unknown properties must be refused, not ignored"
        )
        assert tool.description, tool.name
        assert tool.annotations is not None, tool.name


def test_annotations_match_the_safety_projection():
    from swmcp.catalog.projection import project
    from swmcp.catalog.registry import OPS

    for tool in list_tool_descriptors(replace(BASE, tool_tier="all")):
        spec = OPS.get(tool.name)
        if spec is None:
            continue  # the search meta-tool
        projection = project(spec.safety)
        assert tool.annotations.read_only_hint == projection.read_only, tool.name
        assert tool.annotations.destructive_hint == projection.destructive, tool.name
