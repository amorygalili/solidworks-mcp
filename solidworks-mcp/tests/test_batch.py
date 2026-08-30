"""Batch export (IO-004).

The batch writes no files of its own — it drives ``sw_export`` and ``sw_drawing_export``
— so what is worth testing headless is the part that *is* new: the plan, the routing,
the naming, and the accounting. Every planned output must appear in the result exactly
once, and a run that stops halfway must still say what it never attempted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from swmcp.catalog.registry import OPS, load_all_ops
from swmcp.com.install import (
    CRITICAL_PRIVATE_BYTES,
    STRAINED_HANDLE_COUNT,
    STRAINED_PRIVATE_BYTES,
)
from swmcp.config import SwmcpConfig
from swmcp.context import OpContext
from swmcp.errors import SwMcpError, validation_error
from swmcp.handlers import batch as batch_handlers
from swmcp.schemas.batch import (
    MAX_PLANNED_OUTPUTS,
    BatchExportArgs,
    BatchExportItem,
)
from swmcp.schemas.exchange import (
    BY_EXTENSION,
    EXTENSION_FOR_FORMAT,
    ExportFormat,
    format_for_extension,
)

# --- the format table has one owner -------------------------------------------


def test_every_writable_format_has_an_extension_to_write_it_to():
    formats = set(ExportFormat.__args__)
    assert formats == set(EXTENSION_FOR_FORMAT), (
        "a format the schema offers with no extension to write it to would fail only "
        "once a batch reached it"
    )


def test_the_extension_chosen_reads_back_as_the_same_format():
    """The reverse map is derived, so it cannot name an extension the forward map rejects."""
    for fmt, extension in EXTENSION_FOR_FORMAT.items():
        assert extension in BY_EXTENSION
        assert format_for_extension(f"part{extension}") == fmt


def test_a_format_with_two_spellings_writes_the_long_one():
    assert EXTENSION_FOR_FORMAT["step"] == ".step"
    assert EXTENSION_FOR_FORMAT["iges"] == ".iges"
    assert format_for_extension("part.stp") == "step", "the short spelling still reads"


# --- the schema refuses what would collide ------------------------------------


def test_an_item_may_not_be_addressed_twice():
    with pytest.raises(ValidationError, match="both source_path and title"):
        BatchExportItem(source_path=r"C:\cad\a.SLDPRT", title="a.SLDPRT", formats=["step"])


def test_an_item_with_neither_means_the_active_document():
    assert BatchExportItem(formats=["step"]).source_path is None


def test_the_same_format_twice_is_refused_rather_than_deduplicated():
    """Two identical outputs would either collide or version each other, silently."""
    with pytest.raises(ValidationError, match="same entry twice"):
        BatchExportItem(formats=["step", "step"])


def test_the_same_configuration_twice_is_refused():
    with pytest.raises(ValidationError, match="same entry twice"):
        BatchExportItem(formats=["step"], configurations=["Default", "default"])


def test_a_name_is_a_filename_and_not_a_path():
    for bad in ["sub/part", "sub\\part", "..", "a..b/c"]:
        with pytest.raises(ValidationError):
            BatchExportItem(formats=["step"], name=bad)
    assert BatchExportItem(formats=["step"], name="bracket_rev_b").name == "bracket_rev_b"


def test_a_blank_name_is_refused_rather_than_producing_a_dotfile():
    with pytest.raises(ValidationError):
        BatchExportItem(formats=["step"], name="   ")


def test_planned_output_count_multiplies_configurations_by_formats():
    item = BatchExportItem(formats=["step", "stl"], configurations=["A", "B", "C"])
    assert item.planned_output_count() == 6
    assert BatchExportItem(formats=["step", "stl"]).planned_output_count() == 2


def _args(**overrides: Any) -> dict[str, Any]:
    return {"items": [BatchExportItem(formats=["step"])], "output_dir": "out", **overrides}


def test_a_batch_larger_than_the_cap_is_refused_before_anything_opens():
    """A request big enough to exhaust the session takes the whole session with it."""
    huge = [
        BatchExportItem(formats=["step", "stl", "iges", "3mf"], configurations=[f"c{n}" for n in range(8)])
        for _ in range(8)
    ]
    with pytest.raises(ValidationError, match=str(MAX_PLANNED_OUTPUTS)):
        BatchExportArgs(items=huge, output_dir="out")


def test_a_batch_at_the_cap_is_accepted():
    items = [BatchExportItem(formats=["step"], configurations=[f"c{n}" for n in range(25)])
             for _ in range(8)]
    assert sum(i.planned_output_count() for i in items) == MAX_PLANNED_OUTPUTS
    assert BatchExportArgs(items=items, output_dir="out")


def test_the_overwrite_policy_is_the_shared_vocabulary():
    """'replace' reads like a policy and is not one; the owner is safety/overwrite.py."""
    assert BatchExportArgs(**_args()).overwrite == "version"
    with pytest.raises(ValidationError):
        BatchExportArgs(**_args(overwrite="replace"))


# --- the plan -----------------------------------------------------------------


def test_the_plan_enumerates_every_output_before_anything_runs():
    items = [
        BatchExportItem(formats=["step", "stl"], configurations=["A", "B"]),
        BatchExportItem(formats=["iges"]),
    ]
    units = batch_handlers._plan(items)

    assert [u.index for u in units] == list(range(5))
    assert [(u.item_index, u.configuration, u.format) for u in units] == [
        (0, "A", "step"),
        (0, "A", "stl"),
        (0, "B", "step"),
        (0, "B", "stl"),
        (1, None, "iges"),
    ]


# --- naming -------------------------------------------------------------------


def test_a_configuration_becomes_part_of_the_filename():
    path = batch_handlers._output_path(Path("/out"), "bracket", "Rev B", "step")
    assert path.name == "bracket__Rev B.step"


def test_no_configuration_leaves_the_stem_alone():
    assert batch_handlers._output_path(Path("/out"), "bracket", None, "stl").name == "bracket.stl"


def test_a_configuration_name_windows_refuses_is_repaired_not_rejected():
    """'1/2 scale' and 'Rev: B' are ordinary configuration names and both are illegal."""
    assert batch_handlers._sanitize("1/2 scale") == "1_2 scale"
    assert batch_handlers._sanitize("Rev: B") == "Rev_ B"
    assert batch_handlers._sanitize("a\tb") == "a_b"


def test_a_configuration_of_nothing_usable_still_yields_a_name():
    """Illegal characters become underscores; a name that strips to nothing gets one."""
    assert batch_handlers._sanitize("///") == "___", "still a usable filename"
    assert batch_handlers._sanitize("  . ") == "configuration"
    assert batch_handlers._sanitize("") == "configuration"


@dataclass
class FakeInfo:
    title: str
    path: str | None = None
    doc_type: str = "part"


def test_a_saved_document_is_named_after_its_file():
    assert batch_handlers._document_stem(FakeInfo("bracket.SLDPRT", r"C:\cad\bracket.SLDPRT")) == "bracket"


def test_an_unsaved_document_loses_the_extension_solidworks_puts_in_its_title():
    """Using the title verbatim would produce Part1.SLDPRT.step."""
    assert batch_handlers._document_stem(FakeInfo("Part1.SLDPRT")) == "Part1"
    assert batch_handlers._document_stem(FakeInfo("Part1")) == "Part1"


# --- stopping before the session stops answering ------------------------------


def _resources(*, private: int, handles: int) -> dict[str, Any]:
    return {
        "private_bytes": private,
        "private_mb": round(private / 1024**2, 1),
        "handle_count": handles,
        "strained": private >= STRAINED_PRIVATE_BYTES or handles >= STRAINED_HANDLE_COUNT,
        "critical": private >= CRITICAL_PRIVATE_BYTES,
    }


def test_a_healthy_session_does_not_stop_the_batch():
    assert batch_handlers.strain_stop_reason(None) is None
    assert batch_handlers.strain_stop_reason(_resources(private=2 * 1024**3, handles=5000)) is None


def test_the_advisory_threshold_alone_does_not_stop_the_batch():
    """The bug this separation exists for.

    ``strained`` is 8 GiB and means "worth watching"; a session there is slower and
    entirely usable, and an eleven-minute live run completed well past it. Stopping on
    it made every batch on a well-used machine give up after a single item.
    """
    warm = _resources(private=STRAINED_PRIVATE_BYTES + 1024**3, handles=STRAINED_HANDLE_COUNT)
    assert warm["strained"] is True and warm["critical"] is False
    assert batch_handlers.strain_stop_reason(warm) is None


def test_the_measured_wall_stops_the_batch_and_says_why():
    reason = batch_handlers.strain_stop_reason(
        _resources(private=CRITICAL_PRIVATE_BYTES, handles=9000)
    )
    assert reason is not None
    assert "11264.0 MB" in reason
    assert "Restart" in reason and "manifest" in reason


def test_handles_alone_never_stop_the_batch():
    """No handle count has been observed to fail, so none is treated as a wall."""
    many = _resources(private=1024**3, handles=STRAINED_HANDLE_COUNT * 3)
    assert batch_handlers.strain_stop_reason(many) is None


# --- routing a format to the kind of document that can write it ---------------


def _target(doc_type: str, **overrides: Any) -> batch_handlers._Target:
    return batch_handlers._Target(
        item=BatchExportItem(formats=["step"]),
        doc=object(),
        doc_type=doc_type,
        stem="x",
        source="x",
        **overrides,
    )


def _unit(fmt: str, configuration: str | None = None) -> batch_handlers._Unit:
    return batch_handlers._Unit(index=0, item_index=0, configuration=configuration, format=fmt)


@pytest.mark.parametrize("fmt", ["step", "stl", "iges"])
def test_a_drawing_cannot_produce_a_neutral_format(fmt):
    error = batch_handlers._routing_error(_target("drawing"), _unit(fmt))
    assert error is not None and error.code == "WRONG_FORMAT_FOR_DOCUMENT"


@pytest.mark.parametrize("doc_type", ["part", "assembly"])
@pytest.mark.parametrize("fmt", ["pdf", "dxf", "dwg"])
def test_a_model_is_not_silently_saved_to_a_drawing_format(doc_type, fmt):
    """SOLIDWORKS would write something; it would not be the sheet the caller meant."""
    error = batch_handlers._routing_error(_target(doc_type), _unit(fmt))
    assert error is not None and error.code == "WRONG_FORMAT_FOR_DOCUMENT"
    assert "drawing" in error.message


def test_a_drawing_has_no_configurations_of_its_own():
    error = batch_handlers._routing_error(_target("drawing"), _unit("pdf", "Default"))
    assert error is not None and error.code == "CONFIGURATIONS_NEED_A_MODEL"


@pytest.mark.parametrize(
    ("doc_type", "fmt"),
    [("drawing", "pdf"), ("part", "step"), ("assembly", "stl"), ("part", "3mf")],
)
def test_a_matching_pair_is_not_refused(doc_type, fmt):
    assert batch_handlers._routing_error(_target(doc_type), _unit(fmt)) is None


# --- a failure is an envelope, not a sentence ---------------------------------


def test_a_known_failure_keeps_its_code_and_remediation():
    error = batch_handlers._error_dict(
        SwMcpError(validation_error("SHEET_NOT_FOUND", "no such sheet", remediation=["look"]))
    )
    assert error["code"] == "SHEET_NOT_FOUND"
    assert error["remediation"] == ["look"]


def test_an_unexpected_failure_still_arrives_as_an_envelope():
    error = batch_handlers._error_dict(RuntimeError("com blew up"))
    assert error["code"] == "UNEXPECTED_EXPORT_FAILURE"
    assert "RuntimeError" in error["message"]
    assert error["remediation"], "an error with no next step is not a report"


# --- driving the whole operation ----------------------------------------------


class FakeDoc:
    def __init__(self, title: str, path: str | None, doc_type: str) -> None:
        self.info = FakeInfo(title=title, path=path, doc_type=doc_type)


class FakeApp:
    def __init__(self, docs: dict[str, FakeDoc]) -> None:
        self.docs = docs
        self.closed: list[str] = []

    def GetOpenDocumentByName(self, name: str) -> FakeDoc | None:  # noqa: N802
        return self.docs.get(Path(name).name)

    def CloseDoc(self, title: str) -> None:  # noqa: N802
        self.closed.append(title)


class FakeSession:
    def __init__(self, docs: dict[str, FakeDoc], active: FakeDoc | None = None) -> None:
        self.app = FakeApp(docs)
        self._active = active

    def describe(self, doc: FakeDoc) -> FakeInfo:
        return doc.info

    def active_doc(self) -> FakeDoc | None:
        return self._active

    def resolve_doc(self, *, title: str | None = None, **_: Any) -> FakeDoc:
        for doc in self.app.docs.values():
            if doc.info.title == title:
                return doc
        raise SwMcpError(validation_error("DOCUMENT_NOT_OPEN", f"no {title!r}"))


@dataclass
class FakeExportResult:
    saved_path: str
    overwrite_action: str = "create"
    signature_verified: bool = True
    signature_detail: str = "header found"
    warnings: list[str] = field(default_factory=list)


def _ctx(session: FakeSession, tmp_path: Path) -> OpContext:
    load_all_ops()
    return OpContext(
        session=session,
        config=SwmcpConfig(allowed_roots=(tmp_path,)),
        checkpoints=None,
        spec=OPS["sw_batch_export"],
        request_id="test",
    )


@pytest.fixture
def stub_exports(monkeypatch):
    """Stand in for the two exporters, writing a real file so the hashes are real."""
    calls: list[tuple[str, str]] = []

    def fake_export(ctx, args):
        calls.append(("export", args.output_path))
        Path(args.output_path).write_bytes(b"ISO-10303-21;\n" + args.output_path.encode())
        return FakeExportResult(saved_path=args.output_path)

    def fake_drawing_export(ctx, args):
        calls.append(("drawing", args.output_path))
        Path(args.output_path).write_bytes(b"%PDF-1.7\n")
        return FakeExportResult(saved_path=args.output_path, warnings=["a person must look"])

    monkeypatch.setattr(batch_handlers, "export", fake_export)
    monkeypatch.setattr(batch_handlers, "drawing_export", fake_drawing_export)
    monkeypatch.setattr(batch_handlers, "process_resources", lambda: None)
    return calls


def test_a_batch_writes_every_output_and_a_manifest_that_names_them(tmp_path, stub_exports):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    drawing = FakeDoc("bracket.SLDDRW", str(tmp_path / "bracket.SLDDRW"), "drawing")
    session = FakeSession({"bracket.SLDPRT": part, "bracket.SLDDRW": drawing})

    result = batch_handlers.batch_export(
        _ctx(session, tmp_path),
        BatchExportArgs(
            items=[
                BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step", "stl"]),
                BatchExportItem(source_path=str(tmp_path / "bracket.SLDDRW"), formats=["pdf"]),
            ],
            output_dir=str(tmp_path / "out"),
        ),
    )

    assert result.totals == {"planned": 3, "written": 3, "failed": 0, "skipped": 0}
    assert [Path(e.saved_path).name for e in result.entries] == [
        "bracket.step",
        "bracket.stl",
        "bracket.pdf",
    ]
    assert all(e.sha256 and e.size_bytes for e in result.entries)

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["schema"] == batch_handlers.MANIFEST_SCHEMA
    assert manifest["totals"] == result.totals
    assert [entry["sha256"] for entry in manifest["entries"]] == [
        e.sha256 for e in result.entries
    ]


def test_the_manifest_is_the_artifact_and_carries_its_own_hash(tmp_path, stub_exports):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step"])],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert len(result.artifacts) == 1
    assert result.artifacts[0].path == result.manifest_path
    assert result.artifacts[0].sha256 == result.manifest_sha256
    assert Path(result.manifest_path).name == batch_handlers.DEFAULT_MANIFEST_NAME


def test_a_second_run_versions_the_manifest_rather_than_erasing_the_first(tmp_path, stub_exports):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    args = BatchExportArgs(
        items=[BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step"])],
        output_dir=str(tmp_path / "out"),
    )
    first = batch_handlers.batch_export(_ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path), args)
    second = batch_handlers.batch_export(_ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path), args)

    assert first.manifest_path != second.manifest_path
    assert Path(first.manifest_path).is_file(), "the earlier run's record survives"
    assert "_v002" in Path(second.manifest_path).name
    assert any("earlier run's record" in w for w in second.warnings)


def test_configurations_multiply_into_distinct_files(tmp_path, stub_exports):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[
                BatchExportItem(
                    source_path=str(tmp_path / "bracket.SLDPRT"),
                    formats=["step", "stl"],
                    configurations=["Default", "Rev B"],
                )
            ],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert result.totals["written"] == 4
    assert sorted(Path(e.saved_path).name for e in result.entries) == [
        "bracket__Default.step",
        "bracket__Default.stl",
        "bracket__Rev B.step",
        "bracket__Rev B.stl",
    ]
    assert {e.configuration for e in result.entries} == {"Default", "Rev B"}


def test_a_name_overrides_the_document_stem(tmp_path, stub_exports):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[
                BatchExportItem(
                    source_path=str(tmp_path / "bracket.SLDPRT"),
                    formats=["step"],
                    name="supplier_pack_01",
                )
            ],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert Path(result.entries[0].saved_path).name == "supplier_pack_01.step"


def test_a_wrong_format_fails_that_output_alone(tmp_path, stub_exports):
    """One mismatched format must not cost the other files or the manifest."""
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[
                BatchExportItem(
                    source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step", "pdf", "stl"]
                )
            ],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert result.totals == {"planned": 3, "written": 2, "failed": 1, "skipped": 0}
    failed = [e for e in result.entries if e.status == "failed"]
    assert failed[0].format == "pdf"
    assert failed[0].error["code"] == "WRONG_FORMAT_FOR_DOCUMENT"
    assert failed[0].saved_path is None
    assert Path(result.manifest_path).is_file()


def test_an_export_that_raises_is_reported_rather_than_ending_the_batch(
    tmp_path, stub_exports, monkeypatch
):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")

    def angry_export(ctx, args):
        if args.output_path.endswith(".stl"):
            raise RuntimeError("tessellation failed")
        Path(args.output_path).write_bytes(b"ISO-10303-21;")
        return FakeExportResult(saved_path=args.output_path)

    monkeypatch.setattr(batch_handlers, "export", angry_export)
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[
                BatchExportItem(
                    source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step", "stl", "iges"]
                )
            ],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert result.totals == {"planned": 3, "written": 2, "failed": 1, "skipped": 0}
    failure = next(e for e in result.entries if e.status == "failed")
    assert failure.format == "stl"
    assert "tessellation failed" in failure.error["message"]
    assert failure.requested_path is not None, "the caller still learns which file was meant"


def test_stopping_early_reports_the_rest_as_skipped_and_not_as_failed(tmp_path, stub_exports, monkeypatch):
    """'skipped' means nothing is known; calling it 'failed' would be a claim."""
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")

    def angry_export(ctx, args):
        raise RuntimeError("nope")

    monkeypatch.setattr(batch_handlers, "export", angry_export)
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[
                BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step", "stl"]),
                BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["iges"]),
            ],
            output_dir=str(tmp_path / "out"),
            continue_on_error=False,
        ),
    )
    assert result.stopped_early is True
    assert result.totals == {"planned": 3, "written": 0, "failed": 1, "skipped": 2}
    assert [e.status for e in result.entries] == ["failed", "skipped", "skipped"]
    assert any("never attempted" in w for w in result.warnings)


def test_the_wall_stops_the_batch_between_items_and_the_manifest_still_lands(
    tmp_path, stub_exports, monkeypatch
):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    monkeypatch.setattr(
        batch_handlers,
        "process_resources",
        lambda: _resources(private=CRITICAL_PRIVATE_BYTES, handles=40_000),
    )
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[
                BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step"]),
                BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["stl"]),
            ],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert result.totals == {"planned": 2, "written": 1, "failed": 0, "skipped": 1}
    assert result.stopped_early and "Restart" in result.stop_reason
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["stopped_early"] is True
    assert manifest["entries"][0]["status"] == "written"


def test_an_unopenable_document_fails_all_of_its_outputs_and_none_of_the_others(
    tmp_path, stub_exports
):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    session = FakeSession({"bracket.SLDPRT": part})
    result = batch_handlers.batch_export(
        _ctx(session, tmp_path),
        BatchExportArgs(
            items=[
                BatchExportItem(title="missing.SLDPRT", formats=["step", "stl"]),
                BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step"]),
            ],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert result.totals == {"planned": 3, "written": 1, "failed": 2, "skipped": 0}
    assert all(e.error["code"] == "DOCUMENT_NOT_OPEN" for e in result.entries[:2])
    assert result.entries[2].status == "written"


def test_an_item_with_no_document_named_and_none_active_says_so(tmp_path, stub_exports):
    result = batch_handlers.batch_export(
        _ctx(FakeSession({}, active=None), tmp_path),
        BatchExportArgs(
            items=[BatchExportItem(formats=["step"])], output_dir=str(tmp_path / "out")
        ),
    )
    assert result.entries[0].error["code"] == "NO_ACTIVE_DOCUMENT"
    assert result.entries[0].source == "active document"


def test_sheets_asked_of_a_part_are_reported_as_ignored_rather_than_dropped(
    tmp_path, stub_exports
):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[
                BatchExportItem(
                    source_path=str(tmp_path / "bracket.SLDPRT"),
                    formats=["step"],
                    sheets=["Sheet1"],
                )
            ],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert result.entries[0].status == "written"
    assert any("which has none" in w for w in result.entries[0].warnings)


def test_a_document_already_open_is_never_closed(tmp_path, stub_exports):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    session = FakeSession({"bracket.SLDPRT": part})
    result = batch_handlers.batch_export(
        _ctx(session, tmp_path),
        BatchExportArgs(
            items=[BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step"])],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert session.app.closed == []
    assert result.documents_opened == [] and result.documents_closed == []


def test_the_exporter_warnings_reach_the_entry(tmp_path, stub_exports):
    """DRW-010 travels with the file: a verified PDF is still not a correct drawing."""
    drawing = FakeDoc("bracket.SLDDRW", str(tmp_path / "bracket.SLDDRW"), "drawing")
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDDRW": drawing}), tmp_path),
        BatchExportArgs(
            items=[BatchExportItem(source_path=str(tmp_path / "bracket.SLDDRW"), formats=["pdf"])],
            output_dir=str(tmp_path / "out"),
        ),
    )
    assert "a person must look" in result.entries[0].warnings


# --- the catalog claim --------------------------------------------------------


def test_the_batch_is_a_side_effect_that_needs_no_document_of_its_own():
    spec = load_all_ops()["sw_batch_export"]
    assert spec.safety.kind == "non_model_side_effect"
    assert spec.precondition == "none", "every item addresses its own document"
    assert spec.idempotent is False


def test_the_claim_on_io_004_is_partial_and_says_what_is_missing():
    from swmcp.catalog.scope import DECLARED_PARTIAL, IN_SCOPE_REQUIREMENTS

    spec = load_all_ops()["sw_batch_export"]
    assert spec.partially_satisfies == ("IO-004",)
    assert "IO-004" in IN_SCOPE_REQUIREMENTS
    assert "PDF-only" in DECLARED_PARTIAL["IO-004"]


def test_the_manifest_records_the_name_on_disk_not_the_one_asked_for(
    tmp_path, stub_exports, monkeypatch
):
    """SOLIDWORKS writes an STL as .STL whatever case the path was given in.

    Windows resolves both spellings, so nothing fails locally and this went unnoticed
    until a live test globbed the directory. A manifest is read elsewhere, though, and
    one naming a file that is not there is worse than no manifest.
    """
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")

    def shouting_export(ctx, args):
        actual = Path(args.output_path).with_suffix(".STL")
        actual.write_bytes(b"solid x\nfacet\n")
        return FakeExportResult(saved_path=args.output_path)

    monkeypatch.setattr(batch_handlers, "export", shouting_export)
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["stl"])],
            output_dir=str(tmp_path / "out"),
        ),
    )

    entry = result.entries[0]
    assert entry.status == "written"
    assert Path(entry.saved_path).name.endswith(".STL")
    assert Path(entry.requested_path).name.endswith(".stl"), "what was asked for is kept too"
    assert any("rather than" in w for w in entry.warnings)
    assert entry.sha256 and entry.size_bytes == len(b"solid x\nfacet\n")


def test_a_file_written_under_the_name_asked_for_is_not_warned_about(tmp_path, stub_exports):
    part = FakeDoc("bracket.SLDPRT", str(tmp_path / "bracket.SLDPRT"), "part")
    result = batch_handlers.batch_export(
        _ctx(FakeSession({"bracket.SLDPRT": part}), tmp_path),
        BatchExportArgs(
            items=[BatchExportItem(source_path=str(tmp_path / "bracket.SLDPRT"), formats=["step"])],
            output_dir=str(tmp_path / "out"),
        ),
    )
    entry = result.entries[0]
    assert entry.saved_path == entry.requested_path
    assert not any("rather than" in w for w in entry.warnings)
