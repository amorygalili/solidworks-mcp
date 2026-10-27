"""The library, the CLI, and the skill: three front ends over one pipeline.

Each is checked without SOLIDWORKS. The library and CLI are proven to reach the same
dispatcher the MCP server does — refused requests are refused before the COM boundary,
exactly as they are over MCP — and the skill's own examples are validated against the
catalog, because a skill whose sample call names a field that does not exist teaches
an agent to fail.
"""

from __future__ import annotations

import ast
import json
import re
import shlex
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from swmcp import OperationError, SolidWorks, VerificationFailed
from swmcp.__main__ import EXIT_UNVERIFIED, _parser, main
from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.catalog.search import method_name, resolve_op_name
from swmcp.com.worker import StaWorker
from swmcp.config import SwmcpConfig
from swmcp.dispatch import Dispatcher, Outcome
from swmcp.envelope import Check, MutationResult, Verification
from swmcp.library import _raw_arguments
from swmcp.operations import Operations
from swmcp.skill_install import (
    LAUNCHER_END,
    LAUNCHER_START,
    SKILL_SOURCE,
    SkillInstallError,
    install_skill,
)

BASE = SwmcpConfig(worker_start_timeout_s=5.0)
SKILL_MD = SKILL_SOURCE / "SKILL.md"


class SpyWorker:
    """Records whether COM was reached; any request that gets here fails the test."""

    def __init__(self):
        self.submitted: list[str] = []

    def call(self, fn, *, label, kind="read", timeout_s=None):
        self.submitted.append(label)
        raise AssertionError(f"{label} reached the worker")

    def stop(self, timeout: float = 5.0) -> None:
        pass


@pytest.fixture
def spy(tmp_path):
    load_all_ops()
    config = replace(BASE, allowed_roots=(tmp_path,), audit_path=tmp_path / "audit.jsonl")
    worker = SpyWorker()
    return SolidWorks(dispatcher=Dispatcher(config, worker=worker)), worker


@pytest.fixture
def offline(tmp_path):
    """A real STA worker with COM stubbed out, for operations that need no session."""
    config = replace(BASE, allowed_roots=(tmp_path,), audit_path=tmp_path / "audit.jsonl")
    worker = StaWorker(
        config,
        session_factory=lambda: None,
        com_init=lambda: None,
        com_uninit=lambda: None,
        pump=lambda: None,
    )
    try:
        yield SolidWorks(dispatcher=Dispatcher(config, worker=worker))
    finally:
        worker.stop()


# -- the typed surface ----------------------------------------------------------


def test_every_operation_has_exactly_one_method():
    load_all_ops()
    methods = {method_name(name): name for name in OPS}
    assert len(methods) == len(OPS), "two operations map to the same method name"
    for method, name in methods.items():
        assert callable(getattr(Operations, method, None)), f"{name} has no method {method}"
        assert resolve_op_name(method) == name


def test_no_operation_shadows_the_client_itself():
    """An op named ``close`` or ``call`` would silently replace the client's own method."""
    own = {name for name in vars(SolidWorks) if not name.startswith("_")}
    clashes = own & {method_name(name) for name in load_all_ops()}
    assert not clashes, f"operations shadow SolidWorks attributes: {sorted(clashes)}"


def test_a_keyword_operation_gets_a_trailing_underscore():
    assert method_name("sw_import") == "import_"
    assert resolve_op_name("import_") == "sw_import"
    assert resolve_op_name("import") == "sw_import"


def test_an_unknown_name_is_passed_through_for_the_dispatcher_to_refuse(spy):
    sw, worker = spy
    assert resolve_op_name("no_such_thing") == "no_such_thing"
    outcome = sw.execute("no_such_thing")
    assert outcome.error is not None and outcome.error.code == "UNKNOWN_TOOL"
    assert worker.submitted == []


def test_every_argument_form_reaches_the_dispatcher_identically():
    from swmcp.schemas.safety import PathPolicyArgs

    model = PathPolicyArgs(path="C:/x.step", intent="output")
    as_model = _raw_arguments(model, {})
    as_dict = _raw_arguments({"path": "C:/x.step", "intent": "output"}, {})
    as_kwargs = _raw_arguments(None, {"path": "C:/x.step", "intent": "output"})
    assert as_model == as_dict == as_kwargs
    # Keywords win over the positional form, so a model can be reused with one change.
    assert _raw_arguments(model, {"intent": "document_input"})["intent"] == "document_input"


def test_a_field_named_name_or_args_still_passes_as_a_keyword():
    """``call(name, args, /)`` is positional-only for exactly this reason."""
    assert _raw_arguments(None, {"name": "Boss", "args": [1]}) == {"name": "Boss", "args": [1]}


# -- calls through the pipeline -------------------------------------------------


def test_a_session_free_operation_returns_its_typed_result(offline):
    from swmcp.schemas.safety import ExplainErrorResult

    result = offline.explain_error(code="PATH_NOT_ALLOWED")
    assert isinstance(result, ExplainErrorResult)
    assert result.explanations
    assert offline.last is not None and offline.last.ok


def test_the_payload_is_the_mcp_wire_shape(offline):
    payload = offline.execute("explain_error", code="PATH_NOT_ALLOWED").payload()
    assert payload["ok"] is True
    assert payload["tool"] == "sw_explain_error"
    assert payload["units"] == {"length": "mm", "angle": "deg", "mass": "kg"}
    assert set(payload) == {"ok", "tool", "request_id", "units", "duration_ms", "result"}
    json.dumps(payload)


def test_a_refused_request_raises_before_the_com_boundary(spy):
    sw, worker = spy
    with pytest.raises(OperationError) as caught:
        sw.doc_close(save_first="discard")
    assert caught.value.code == "CONFIRM_REQUIRED"
    assert caught.value.tool == "sw_doc_close"
    assert any("confirm=true" in step for step in caught.value.remediation)
    assert worker.submitted == []


def test_an_output_outside_the_roots_is_refused_by_the_library_too(spy):
    sw, worker = spy
    with pytest.raises(OperationError) as caught:
        sw.export(output_path="C:/Windows/System32/swmcp_never.step")
    assert caught.value.code == "PATH_NOT_ALLOWED"
    assert worker.submitted == []


def _failing_mutation() -> MutationResult:
    return MutationResult(
        verification=Verification(
            read_back=True,
            checks=[
                Check(name="segments_created", passed=True),
                Check(name="every_entity_created", passed=False, detail="1 of 1 failed"),
            ],
        )
    )


def _outcome_of(result) -> Outcome:
    return Outcome(tool="sw_sketch_add_geometry", request_id="r", duration_ms=1.0, result=result)


def test_strict_mode_raises_when_verification_did_not_hold(spy, monkeypatch):
    sw, _ = spy
    result = _failing_mutation()
    monkeypatch.setattr(sw.dispatcher, "execute", lambda name, raw: _outcome_of(result))

    with pytest.raises(VerificationFailed) as caught:
        sw.sketch_add_geometry(entities=[])
    assert caught.value.result is result
    assert [check.name for check in caught.value.failed_checks] == ["every_entity_created"]

    sw.strict = False
    assert sw.sketch_add_geometry(entities=[]) is result


def test_closing_a_client_leaves_a_borrowed_dispatcher_running(tmp_path):
    class CountingWorker(SpyWorker):
        stops = 0

        def stop(self, timeout: float = 5.0) -> None:
            self.stops += 1

    worker = CountingWorker()
    with SolidWorks(dispatcher=Dispatcher(BASE, worker=worker)):
        pass
    assert worker.stops == 0, "a client stopped a worker it did not create"


def test_search_from_the_library_sees_every_tier(spy):
    sw, _ = spy
    found = sw.search_tools("", limit=200)
    assert found["matched"] == len(OPS)
    assert all(tool["available"] for tool in found["tools"])


def test_describe_names_the_method():
    described = SolidWorks.describe("sw_import")
    assert described["method"] == "import_"
    assert described["input_schema"]["properties"]["input_path"]
    with pytest.raises(KeyError):
        SolidWorks.describe("no_such_thing")


def test_importing_the_package_does_not_load_the_handlers():
    """``python -m swmcp`` imports the package first; that must stay cheap."""
    code = "import sys, swmcp; assert 'swmcp.handlers' not in sys.modules, 'eager'"
    subprocess.run([sys.executable, "-c", code], check=True)


# -- the CLI --------------------------------------------------------------------


def _json_out(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_cli_describe(capsys):
    assert main(["describe", "doc_new"]) == 0
    described = _json_out(capsys)
    assert described["name"] == "sw_doc_new"
    assert "doc_type" in described["input_schema"]["properties"]


def test_cli_describe_an_unknown_operation_fails(capsys):
    assert main(["describe", "no_such_thing"]) == 1


def test_cli_tools_searches_every_tier(capsys):
    assert main(["tools", "extrude", "boss"]) == 0
    found = _json_out(capsys)
    assert found["tools"][0]["name"] == "sw_feature_extrude_boss"
    assert found["active_tier"] == "all"


def test_cli_call_refuses_before_com_and_exits_one(capsys):
    assert main(["call", "sw_doc_close", '{"save_first": "discard"}']) == 1
    payload = _json_out(capsys)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "CONFIRM_REQUIRED"


def test_cli_call_rejects_arguments_that_are_not_an_object(capsys):
    assert main(["call", "sw_doc_list", "[1, 2]"]) == 1
    assert _json_out(capsys)["error"]["code"] == "INVALID_ARGUMENTS"


def test_cli_call_reads_arguments_from_a_file(capsys, tmp_path):
    source = tmp_path / "args.json"
    source.write_text('{"save_first": "discard"}', encoding="utf-8")
    assert main(["call", "doc_close", f"@{source}"]) == 1
    assert _json_out(capsys)["error"]["code"] == "CONFIRM_REQUIRED"


def test_cli_call_exits_two_when_verification_did_not_hold(capsys, monkeypatch):
    result = _failing_mutation()
    monkeypatch.setattr(SolidWorks, "execute", lambda self, name, raw: _outcome_of(result))
    assert main(["call", "sw_sketch_add_geometry", '{"entities": []}']) == EXIT_UNVERIFIED
    assert _json_out(capsys)["ok"] is True


def test_cli_with_no_command_still_means_serve():
    """Every existing MCP client config runs the bare command; it must not change."""
    arguments = _parser().parse_args([])
    assert arguments.command is None


# -- the skill ------------------------------------------------------------------


def _skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def test_skill_frontmatter_is_valid():
    text = _skill_text()
    match = re.match(r"---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must open with YAML frontmatter"
    fields = dict(line.split(": ", 1) for line in match["body"].splitlines())
    assert fields["name"] == "solidworks"
    assert 0 < len(fields["description"]) <= 1024


def test_every_operation_the_skill_names_exists():
    load_all_ops()
    named = set(re.findall(r"\bsw_[a-z_]+[a-z]\b", _skill_text()))
    missing = sorted(name for name in named if name not in OPS)
    assert not missing, f"SKILL.md names operations that do not exist: {missing}"


def test_every_shell_example_in_the_skill_parses_and_validates():
    load_all_ops()
    commands = [
        line.strip()
        for line in _skill_text().splitlines()
        if line.strip().startswith("swpy -m swmcp ")
    ]
    assert commands, "the skill has no shell examples to check"
    for command in commands:
        argv = shlex.split(command)[3:]
        arguments = _parser().parse_args(argv)
        if arguments.command != "call":
            continue
        spec = OPS[resolve_op_name(arguments.operation)]
        raw = json.loads(arguments.arguments) if arguments.arguments else {}
        spec.args_model.model_validate(raw)


def _python_examples() -> list[str]:
    return re.findall(r"```python\n(.*?)```", _skill_text(), re.DOTALL)


class _Placeholder(ast.NodeTransformer):
    """Stand in a plain string for any f-string, so the call can be literal-evaluated."""

    def visit_JoinedStr(self, node):  # noqa: N802 - the ast API's name
        return ast.copy_location(ast.Constant("C:/cad/work/placeholder"), node)


def test_every_library_call_in_the_skill_validates():
    """Field names in the example are checked against the real args models."""
    load_all_ops()
    examples = _python_examples()
    assert examples, "the skill has no Python example to check"
    checked = 0
    for source in examples:
        tree = _Placeholder().visit(ast.parse(source))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sw"
            ):
                continue
            method = node.func.attr
            assert callable(getattr(Operations, method, None)), f"sw.{method} does not exist"
            spec = OPS[resolve_op_name(method)]
            spec.args_model.model_validate(
                {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
            )
            checked += 1
    assert checked >= 5


def test_install_pins_the_interpreter(tmp_path):
    target = install_skill(tmp_path / "solidworks", python="C:/py/python.exe")
    text = (target / "SKILL.md").read_text(encoding="utf-8")
    block = text[text.index(LAUNCHER_START) : text.index(LAUNCHER_END)]
    assert "`C:/py/python.exe`" in block
    assert "Not pinned yet" not in text
    assert (target / "reference" / "tools.md").is_file()


def test_install_refuses_to_overwrite_without_force(tmp_path):
    target = install_skill(tmp_path / "solidworks", python="C:/py/python.exe")
    with pytest.raises(SkillInstallError, match="--force"):
        install_skill(target, python="C:/py/python.exe")
    install_skill(target, force=True, python="D:/other/python.exe")
    assert "D:/other/python.exe" in (target / "SKILL.md").read_text(encoding="utf-8")


def test_install_never_replaces_a_directory_that_is_not_this_skill(tmp_path):
    foreign = tmp_path / "solidworks"
    foreign.mkdir()
    (foreign / "notes.txt").write_text("someone else's", encoding="utf-8")
    with pytest.raises(SkillInstallError, match="left alone"):
        install_skill(foreign, force=True, python="C:/py/python.exe")
    assert (foreign / "notes.txt").read_text(encoding="utf-8") == "someone else's"


def test_the_skill_ships_inside_the_package():
    """So an installed wheel can install its own skill, with no repository checkout."""
    assert SKILL_SOURCE.parent == Path(__import__("swmcp").__file__).parent
