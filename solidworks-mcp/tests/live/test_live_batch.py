"""Live cover for batch export (IO-004).

The headless tests prove the plan, the routing, and the accounting against stubs. What
only a real session can prove is that the stubs stand for something: that a plan of six
outputs across two real documents produces six real files, that the manifest's hashes
match the bytes on disk, and that a document the batch opened is closed again.

Files go into a subdirectory of the scratch root rather than the root itself, because
the autouse cleanup in ``conftest.py`` sweeps exported files out of the root after every
test — which would delete a module-scoped fixture's outputs after the first one ran.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.live]

PLATE_X, PLATE_Y, PLATE_Z = 60.0, 40.0, 6.0


@pytest.fixture
def out_dir(scratch_root, unique_name):
    """A per-test output directory, emptied before use so a re-run starts clean."""
    directory = scratch_root / "batch_out" / unique_name
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.iterdir():
        try:
            stale.unlink()
        except OSError:
            # Still locked by SOLIDWORKS from an interrupted run; the assertions name
            # the files they expect rather than assuming the directory is empty.
            continue
    return directory


def _make_plate(call, target: Path, *, name: str = "Plate") -> Path:
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(target)})
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_X, PLATE_Y]}]},
    )
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": PLATE_Z, "name": name})
    call("sw_doc_save", {"output_path": str(target), "overwrite": "allow", "confirm": True})
    return target


@pytest.fixture
def plate(call, scratch_root, unique_name):
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    return _make_plate(call, scratch_root / f"{unique_name}.SLDPRT")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_batch_writes_every_file_and_the_manifest_hashes_match_the_bytes(
    call, plate, out_dir
):
    """IO-004: hashes are the point. A manifest nobody can check is documentation."""
    result = call(
        "sw_batch_export",
        {
            "items": [{"source_path": str(plate), "formats": ["step", "stl", "3mf"]}],
            "output_dir": str(out_dir),
        },
    )["result"]

    assert result["totals"] == {"planned": 3, "written": 3, "failed": 0, "skipped": 0}
    for entry in result["entries"]:
        written = Path(entry["saved_path"])
        assert written.is_file(), entry
        assert entry["signature_verified"] is True, entry["signature_detail"]
        assert entry["sha256"] == _digest(written), "the manifest hash is of these bytes"
        assert entry["size_bytes"] == written.stat().st_size

    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["totals"] == result["totals"]
    assert [e["sha256"] for e in manifest["entries"]] == [
        e["sha256"] for e in result["entries"]
    ]
    assert result["artifacts"][0]["sha256"] == _digest(Path(result["manifest_path"]))


def test_the_written_files_are_named_after_the_document(call, plate, out_dir, unique_name):
    """And the manifest names them as they are on disk, not as they were asked for.

    SOLIDWORKS writes an STL as ``.STL`` however the path was spelled. Windows resolves
    both, so this is invisible until the directory is listed — or until the manifest is
    read somewhere that is not Windows.
    """
    result = call(
        "sw_batch_export",
        {
            "items": [{"source_path": str(plate), "formats": ["step", "stl"]}],
            "output_dir": str(out_dir),
        },
    )["result"]

    on_disk = {p.name for p in out_dir.glob("*.st*")}
    assert on_disk == {f"{unique_name}.step", f"{unique_name}.STL"}, (
        "SOLIDWORKS uppercases the STL extension; if this ever changes, the warning "
        "below has become dead code"
    )
    assert {Path(e["saved_path"]).name for e in result["entries"]} == on_disk
    stl = next(e for e in result["entries"] if e["format"] == "stl")
    assert Path(stl["requested_path"]).name == f"{unique_name}.stl"
    assert any("rather than" in w for w in stl["warnings"])


def test_a_name_overrides_the_document_stem(call, plate, out_dir):
    result = call(
        "sw_batch_export",
        {
            "items": [
                {"source_path": str(plate), "formats": ["step"], "name": "supplier_pack"}
            ],
            "output_dir": str(out_dir),
        },
    )["result"]
    assert Path(result["entries"][0]["saved_path"]).name == "supplier_pack.step"


def test_each_configuration_is_exported_to_its_own_file(call, plate, out_dir):
    """IO-004 asks for configurations by name, and they must not land on one another."""
    depth = next(
        entry["name"]
        for entry in call("sw_dimension_list")["result"]["dimensions"]
        if "Plate" in entry["name"]
    )
    default = call("sw_config_list")["result"]["active"]
    call("sw_config_create", {"name": "Thick", "activate": True})
    thickened = call(
        "sw_dimension_set",
        {"name": depth, "value": PLATE_Z * 3, "configuration_scope": "this"},
    )["result"]
    assert thickened["after_mm"] == pytest.approx(PLATE_Z * 3, rel=1e-6)
    call("sw_config_activate", {"name": default})
    call("sw_doc_save", {"output_path": str(plate), "overwrite": "allow", "confirm": True})

    result = call(
        "sw_batch_export",
        {
            "items": [
                {
                    "source_path": str(plate),
                    "formats": ["step"],
                    "configurations": [default, "Thick"],
                }
            ],
            "output_dir": str(out_dir),
        },
    )["result"]

    assert result["totals"]["written"] == 2
    written = {Path(e["saved_path"]).name: e for e in result["entries"]}
    assert set(written) == {
        f"{Path(plate).stem}__{default}.step",
        f"{Path(plate).stem}__Thick.step",
    }
    assert len({e["sha256"] for e in result["entries"]}) == 2, (
        "one configuration is three times the thickness of the other, so two files "
        "with the same hash would mean the configuration argument did nothing"
    )


def test_a_document_the_batch_opened_is_closed_again(call, plate, out_dir, dispatcher):
    """The batch opens read-only and lets go, so a long run does not fill the session."""
    call("sw_doc_close", {"document": {"title": Path(plate).name}, "save_first": "discard",
                          "confirm": True})
    before = {d["title"] for d in call("sw_doc_list")["result"]["documents"]}

    result = call(
        "sw_batch_export",
        {
            "items": [{"source_path": str(plate), "formats": ["step"]}],
            "output_dir": str(out_dir),
        },
    )["result"]

    after = {d["title"] for d in call("sw_doc_list")["result"]["documents"]}
    assert result["documents_opened"], "the fixture part was closed, so it had to be opened"
    assert result["documents_closed"] == result["documents_opened"]
    assert after == before, "the batch left the session exactly as it found it"


def test_a_document_already_open_is_left_open(call, plate, out_dir):
    before = {d["title"] for d in call("sw_doc_list")["result"]["documents"]}
    assert Path(plate).name in before

    result = call(
        "sw_batch_export",
        {
            "items": [{"source_path": str(plate), "formats": ["step"]}],
            "output_dir": str(out_dir),
        },
    )["result"]

    assert result["documents_opened"] == [] and result["documents_closed"] == []
    after = {d["title"] for d in call("sw_doc_list")["result"]["documents"]}
    assert Path(plate).name in after


def test_a_drawing_and_a_model_export_side_by_side(call, plate, out_dir, unique_name):
    """The routing that only a mixed batch exercises: one plan, two exporters."""
    call("sw_drawing_new", {"paper_size": "a", "model_path": str(plate)})
    drawing = out_dir / f"{unique_name}.SLDDRW"
    call("sw_doc_save", {"output_path": str(drawing), "overwrite": "allow", "confirm": True})
    call(
        "sw_drawing_view_add",
        {"orientation": "front", "at": [100, 150], "model_path": str(plate)},
    )
    call("sw_doc_save", {"output_path": str(drawing), "overwrite": "allow", "confirm": True})

    result = call(
        "sw_batch_export",
        {
            "items": [
                {"source_path": str(plate), "formats": ["step"]},
                {"source_path": str(drawing), "formats": ["pdf"]},
            ],
            "output_dir": str(out_dir),
        },
    )["result"]

    assert result["totals"] == {"planned": 2, "written": 2, "failed": 0, "skipped": 0}
    by_format = {e["format"]: e for e in result["entries"]}
    assert by_format["step"]["document_type"] == "part"
    assert by_format["pdf"]["document_type"] == "drawing"
    assert Path(by_format["pdf"]["saved_path"]).read_bytes()[:4] == b"%PDF"
    assert any("a person" in w.lower() for w in by_format["pdf"]["warnings"]), (
        "DRW-010 travels with the file into the batch"
    )


def test_a_neutral_format_asked_of_a_drawing_fails_only_that_output(
    call, plate, out_dir, unique_name
):
    call("sw_drawing_new", {"paper_size": "a", "model_path": str(plate)})
    drawing = out_dir / f"{unique_name}.SLDDRW"
    call("sw_doc_save", {"output_path": str(drawing), "overwrite": "allow", "confirm": True})

    result = call(
        "sw_batch_export",
        {
            "items": [{"source_path": str(drawing), "formats": ["pdf", "step"]}],
            "output_dir": str(out_dir),
        },
    )["result"]

    assert result["totals"] == {"planned": 2, "written": 1, "failed": 1, "skipped": 0}
    failed = next(e for e in result["entries"] if e["status"] == "failed")
    assert failed["format"] == "step"
    assert failed["error"]["code"] == "WRONG_FORMAT_FOR_DOCUMENT"
    assert Path(result["manifest_path"]).is_file(), "the manifest survives a failed output"


def test_a_second_run_versions_both_the_files_and_the_manifest(call, plate, out_dir):
    """SAFE-008 across a whole delivery: nothing a supplier already has is replaced."""
    request = {
        "items": [{"source_path": str(plate), "formats": ["step"]}],
        "output_dir": str(out_dir),
    }
    first = call("sw_batch_export", request)["result"]
    second = call("sw_batch_export", request)["result"]

    assert Path(first["entries"][0]["saved_path"]).is_file()
    assert second["entries"][0]["overwrite_action"] == "versioned"
    assert "_v002" in Path(second["entries"][0]["saved_path"]).name
    assert first["manifest_path"] != second["manifest_path"]
    assert Path(first["manifest_path"]).is_file()


def test_an_output_directory_outside_the_allowed_roots_is_refused(call, plate):
    payload = call(
        "sw_batch_export",
        {
            "items": [{"source_path": str(plate), "formats": ["step"]}],
            "output_dir": r"C:\Windows\Temp\swmcp_batch",
        },
        expect_ok=False,
    )
    assert payload["ok"] is False
    assert payload["error"]["code"] == "PATH_NOT_ALLOWED"


def test_a_manifest_outside_the_allowed_roots_is_refused(call, plate, out_dir):
    """The nested-path guard, live: manifest_path is checked like any other output."""
    payload = call(
        "sw_batch_export",
        {
            "items": [{"source_path": str(plate), "formats": ["step"]}],
            "output_dir": str(out_dir),
            "manifest_path": r"C:\Windows\Temp\swmcp_manifest.json",
        },
        expect_ok=False,
    )
    assert payload["ok"] is False
    assert payload["error"]["code"] == "PATH_NOT_ALLOWED"
    assert payload["error"]["context"]["field"] == "manifest_path"
    assert not list(out_dir.glob("*.step")), "refused before anything was written"


def test_a_missing_source_fails_its_own_outputs_and_not_the_batch(call, plate, out_dir):
    result = call(
        "sw_batch_export",
        {
            "items": [
                {"source_path": str(out_dir / "no_such_part.SLDPRT"), "formats": ["step"]},
                {"source_path": str(plate), "formats": ["step"]},
            ],
            "output_dir": str(out_dir),
        },
    )["result"]

    assert result["totals"] == {"planned": 2, "written": 1, "failed": 1, "skipped": 0}
    assert result["entries"][0]["error"]["code"] == "FILE_NOT_FOUND"
    assert result["entries"][1]["status"] == "written"


def test_stopping_at_the_first_failure_marks_the_rest_skipped(call, plate, out_dir):
    """'skipped' is a statement that nothing was learned, not that anything went wrong."""
    result = call(
        "sw_batch_export",
        {
            "items": [
                {"source_path": str(out_dir / "no_such_part.SLDPRT"), "formats": ["step"]},
                {"source_path": str(plate), "formats": ["step", "stl"]},
            ],
            "output_dir": str(out_dir),
            "continue_on_error": False,
        },
    )["result"]

    assert result["stopped_early"] is True
    assert [e["status"] for e in result["entries"]] == ["failed", "skipped", "skipped"]
    assert result["totals"] == {"planned": 3, "written": 0, "failed": 1, "skipped": 2}
    assert json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))[
        "stopped_early"
    ] is True
