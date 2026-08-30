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
from swmcp.errors import SwMcpError
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


def test_an_output_path_nested_in_a_list_of_items_is_still_root_checked(dispatcher, tmp_path):
    """SAFE-004 walked one level until a tool took a list of items.

    ``sw_batch_export`` is the first operation whose paths are not top-level strings:
    the only string the old walk could see was the directory. Everything each item
    named — its source document, its own destination — went past the gate unlooked at.
    """
    payload = dispatcher.call(
        "sw_batch_export",
        {
            "items": [{"formats": ["step"]}],
            "output_dir": str(tmp_path / "out"),
            "manifest_path": r"C:\somewhere\else\manifest.json",
        },
    )
    assert payload["ok"] is False
    assert payload["error"]["code"] == "PATH_NOT_ALLOWED"
    assert payload["error"]["context"]["field"] == "manifest_path"
    assert dispatcher.worker.submitted == [], "refused before COM was reached"




def test_an_output_path_inside_a_list_of_items_is_root_checked(dispatcher, tmp_path):
    """The mechanism itself: a list of sub-models is the shape the old walk could not see."""
    from pydantic import BaseModel

    class Item(BaseModel):
        output_path: str

    class Request(BaseModel):
        items: list[Item]

    dispatcher._guard_model(Request(items=[Item(output_path=str(tmp_path / "fine.step"))]))

    with pytest.raises(SwMcpError) as caught:
        dispatcher._guard_model(
            Request(items=[Item(output_path=r"C:\somewhere\else\sneaky.step")])
        )
    assert caught.value.envelope.code == "PATH_NOT_ALLOWED"


def test_an_output_path_one_model_deep_is_root_checked(dispatcher):
    from pydantic import BaseModel

    class Inner(BaseModel):
        output_path: str

    class Outer(BaseModel):
        inner: Inner

    with pytest.raises(SwMcpError) as caught:
        dispatcher._guard_model(Outer(inner=Inner(output_path=r"C:\somewhere\else\x.step")))
    assert caught.value.envelope.code == "PATH_NOT_ALLOWED"


def test_the_recursive_walk_still_reaches_the_document_target(dispatcher, tmp_path, monkeypatch):
    """The old walk special-cased args.document; the recursion has to cover it instead."""
    import swmcp.dispatch as dispatch_module
    from swmcp.schemas.exchange import ExportArgs

    seen: list[str] = []
    monkeypatch.setattr(
        dispatch_module, "prepare_document_path", lambda raw: seen.append(raw) or raw
    )
    dispatcher._guard_model(
        ExportArgs(
            output_path=str(tmp_path / "part.step"),
            document={"path": r"C:\cad\bracket.SLDPRT"},
        )
    )
    assert seen == [r"C:\cad\bracket.SLDPRT"]
