"""Live cover for neutral-format import (IO-001).

Every case here round-trips a 40 x 30 x 20 mm block, so the answer is arithmetic rather
than opinion: 24 000 mm³ of volume and 5200 mm² of surface area. The block is built and
exported once for the module; each test imports one of those files and measures what
arrived.

Two behaviours are worth stating, because both were found by probing and neither is
guessable from the type library:

* ``LoadFile4`` returns a document and leaves its ``Errors`` out-parameter at 0 whether
  or not anything useful happened, and on failure it leaves the *previously* active
  document active. A tool that read ``ActiveDoc`` afterwards would report the caller's
  own model as the import result, so ``test_a_file_that_is_not_geometry_is_refused``
  drives exactly that path with a file that is not a STEP file.
* An STL imported with SOLIDWORKS' own default arrives as a *graphics* body: zero solid
  bodies, no volume, nothing addressable. That is a real outcome rather than an error,
  and it is reported as one.

Restoring the import preferences afterwards is the shared ``_Preferences`` machinery the
export tools already use and is covered there; this module does not re-prove it, because
reading a user preference back needs the advanced tier and the live suite runs on core.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

BLOCK_X, BLOCK_Y, BLOCK_Z = 40.0, 30.0, 20.0
BLOCK_MM3 = BLOCK_X * BLOCK_Y * BLOCK_Z
BLOCK_MM2 = 2 * (BLOCK_X * BLOCK_Y + BLOCK_X * BLOCK_Z + BLOCK_Y * BLOCK_Z)

#: One export per format, each under its own stem so two imports can never collide on a
#: document title.
EXPORTS = {
    "step": "swmcp_import_step.step",
    "iges": "swmcp_import_iges.igs",
    "parasolid_text": "swmcp_import_xt.x_t",
    "parasolid_binary": "swmcp_import_xb.x_b",
    "sat": "swmcp_import_sat.sat",
    "stl": "swmcp_import_stl.stl",
}

#: ACIS has no header this server knows how to check, and `sw_export` says so rather
#: than claiming a verification it did not perform. Every other export here is checked
#: against its own signature before the file is trusted as an import fixture.
UNVERIFIABLE_EXPORTS = {"sat"}


@pytest.fixture(scope="module")
def exported(dispatcher, scratch_root):
    """A 40 x 30 x 20 block written out in every format this release reads back.

    The files live in a subdirectory rather than in the scratch root itself: the suite's
    autouse cleanup sweeps ``swmcp_*.step`` and friends from the root after *every* test,
    which deleted this module's fixtures out from under it after the first one ran.
    """
    fixtures = scratch_root / "import_fixtures"
    if fixtures.exists():
        for stale in fixtures.iterdir():
            stale.unlink(missing_ok=True)
    fixtures.mkdir(parents=True, exist_ok=True)

    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    assert made.get("ok"), made.get("error")
    title = made["result"]["document"]["title"]

    dispatcher.call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    dispatcher.call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [BLOCK_X, BLOCK_Y]}]},
    )
    dispatcher.call("sw_sketch_exit", {})
    built = dispatcher.call("sw_feature_extrude_boss", {"depth": BLOCK_Z, "name": "Block"})
    assert built.get("ok"), built.get("error")

    paths = {}
    for fmt, name in EXPORTS.items():
        target = fixtures / name
        written = dispatcher.call("sw_export", {"output_path": str(target), "overwrite": "allow"})
        assert written.get("ok"), f"{fmt}: {written.get('error')}"
        assert written["result"]["size_bytes"] > 0, f"the {fmt} export is empty"
        if fmt not in UNVERIFIABLE_EXPORTS:
            assert written["result"]["signature_verified"], (
                f"the {fmt} export did not verify, so importing it would prove nothing: "
                f"{written['result']['signature_detail']}"
            )
        paths[fmt] = written["result"]["saved_path"]

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": title}, "save_first": "discard", "confirm": True},
    )

    yield paths

    for stale in fixtures.iterdir():
        try:
            stale.unlink()
        except OSError:
            continue


def _imported(call, exported, fmt, **arguments):
    payload = call("sw_import", {"input_path": exported[fmt], **arguments})
    return payload["result"]


# --- the solid formats round-trip the volume ------------------------------------


@pytest.mark.parametrize(
    ("fmt", "tolerance"),
    [
        ("step", 1e-9),
        # IGES came back 8e-6 mm³ heavy on a 24 000 mm³ block: its curve representation
        # is not bit-exact, so it gets a relative tolerance rather than an equality.
        ("iges", 1e-6),
        ("parasolid_text", 1e-9),
        ("parasolid_binary", 1e-9),
        ("sat", 1e-9),
    ],
)
def test_a_neutral_solid_arrives_with_its_volume_intact(call, exported, fmt, tolerance):
    found = _imported(call, exported, fmt)

    assert found["geometry_found"] is True
    assert found["solid_body_count"] == 1
    assert found["sheet_body_count"] == 0
    assert found["volume_mm3"] == pytest.approx(BLOCK_MM3, rel=tolerance)
    assert found["surface_area_mm2"] == pytest.approx(BLOCK_MM2, rel=tolerance)
    assert found["face_count"] == 6, "a box has six faces however it was translated"


def test_the_import_opens_a_new_document_and_names_it(call, exported):
    found = _imported(call, exported, "step")

    assert found["document"]["doc_type"] == "part"
    assert found["document"]["title"]
    assert found["format"] == "step"


def test_the_source_file_is_reported_as_evidence(call, exported):
    """The file that was read is hashed, so a later run can tell it apart."""
    found = _imported(call, exported, "step")

    (artifact,) = found["artifacts"]
    assert artifact["path"] == exported["step"]
    assert artifact["exists"] is True
    assert artifact["size_bytes"] > 0
    assert artifact["sha256"]


# --- knitting is the caller's choice, and changes what arrives -------------------


def test_declining_to_knit_yields_surfaces_and_no_volume(call, exported):
    """Six faces that were never sewn are six sheet bodies, and enclose nothing.

    This is also the live guard on the sheet-body measurement fix: before it, each of
    these surfaces reported its *area* as a volume.
    """
    found = _imported(call, exported, "step", knit="do_not_knit")

    assert found["solid_body_count"] == 0
    assert found["sheet_body_count"] == 6
    assert found["volume_mm3"] is None, "a surface encloses no volume"
    assert found["surface_area_mm2"] == pytest.approx(BLOCK_MM2, rel=1e-6)
    assert any("encloses no volume" in w for w in found["warnings"])


# --- a mesh is not a solid unless you ask for one --------------------------------


def test_an_stl_as_graphics_produces_nothing_measurable(call, exported):
    """SOLIDWORKS' own default, reported as the empty result it is."""
    found = _imported(call, exported, "stl", mesh_body_type="graphics")

    assert found["geometry_found"] is False
    assert found["body_count"] == 0
    assert found["volume_mm3"] is None
    assert any("graphics" in w for w in found["warnings"]), (
        "an import that produced no geometry must say why, not just return ok"
    )


def test_an_stl_as_a_solid_recovers_the_volume(call, exported):
    found = _imported(call, exported, "stl", mesh_body_type="solid")

    assert found["geometry_found"] is True
    assert found["solid_body_count"] == 1
    # A tessellated box is triangles, not planes: two per face.
    assert found["face_count"] == 12
    assert found["volume_mm3"] == pytest.approx(BLOCK_MM3, rel=1e-6)


def test_an_stl_as_a_surface_has_area_but_no_volume(call, exported):
    found = _imported(call, exported, "stl", mesh_body_type="surface")

    assert found["solid_body_count"] == 0
    assert found["sheet_body_count"] == 1
    assert found["volume_mm3"] is None
    assert found["surface_area_mm2"] == pytest.approx(BLOCK_MM2, rel=1e-6)


def test_the_settings_report_what_was_applied(call, exported):
    found = _imported(call, exported, "stl", mesh_body_type="surface", mesh_unit="mm")

    assert found["settings"]["mesh_body_type"] == "surface"
    assert found["settings"]["mesh_unit"] == "mm"


# --- diagnostics report what they changed, not what they returned ----------------


def test_diagnostics_on_sound_geometry_change_nothing(call, exported):
    """ImportDiagnosis returns 1 regardless, so the claim has to rest on the geometry."""
    found = _imported(call, exported, "step", run_diagnostics=True)

    diagnosis = found["diagnostics"]
    assert diagnosis["ran"] is True
    assert diagnosis["changed_the_model"] is False
    assert diagnosis["faces_before"] == diagnosis["faces_after"] == 6
    assert found["volume_mm3"] == pytest.approx(BLOCK_MM3, rel=1e-9)


def test_diagnostics_are_absent_unless_asked_for(call, exported):
    assert _imported(call, exported, "step")["diagnostics"] is None


# --- refusals --------------------------------------------------------------------


def test_a_missing_file_is_refused_by_name(call, scratch_root):
    payload = call(
        "sw_import",
        {"input_path": str(scratch_root / "swmcp_import_absent.step")},
        expect_ok=False,
    )

    assert payload["error"]["code"] == "FILE_NOT_FOUND"


def test_an_unsupported_format_is_refused_before_solidworks_sees_it(call, exported, scratch_root):
    target = scratch_root / "swmcp_import_unsupported.obj"
    target.write_text("# not imported by this release\n", encoding="utf-8")

    payload = call("sw_import", {"input_path": str(target)}, expect_ok=False)

    assert payload["error"]["code"] == "UNSUPPORTED_IMPORT_FORMAT"
    assert ".step" in str(payload["error"]["context"]["supported_extensions"])


def test_a_file_that_is_not_geometry_is_refused(call, exported, scratch_root):
    """The trap: a failed LoadFile4 leaves the previous document active.

    Reading ActiveDoc afterwards would report whatever the caller had open as a
    successful import, complete with its volume. The new document is therefore
    identified by difference, and its absence is an error.
    """
    target = scratch_root / "swmcp_import_garbage.step"
    target.write_text("this is not an ISO-10303-21 file\n", encoding="utf-8")

    payload = call("sw_import", {"input_path": str(target)}, expect_ok=False)

    assert payload["error"]["code"] == "IMPORT_PRODUCED_NO_DOCUMENT"
