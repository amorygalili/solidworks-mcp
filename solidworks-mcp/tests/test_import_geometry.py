"""Import logic that needs no SOLIDWORKS: format mapping, schema guards, diagnostics."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swmcp.handlers.exchange import _geometry_summary, _run_import_diagnostics
from swmcp.schemas.exchange import (
    IMPORT_BY_EXTENSION,
    MESH_IMPORT_FORMATS,
    ImportArgs,
    ImportResult,
    import_format_for_extension,
)

# --- format mapping -------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (r"C:\parts\bracket.step", "step"),
        (r"C:\parts\bracket.STP", "step"),
        (r"C:\parts\bracket.igs", "iges"),
        (r"C:\parts\bracket.iges", "iges"),
        (r"C:\parts\bracket.x_t", "parasolid"),
        (r"C:\parts\bracket.x_b", "parasolid"),
        (r"C:\parts\bracket.sat", "acis"),
        (r"C:\parts\bracket.stl", "stl"),
    ],
)
def test_the_extension_selects_the_format(path, expected):
    assert import_format_for_extension(path) == expected


def test_an_unknown_extension_maps_to_nothing():
    """So the handler can refuse it by name rather than letting LoadFile4 guess."""
    assert import_format_for_extension(r"C:\parts\bracket.obj") is None
    assert import_format_for_extension(r"C:\parts\bracket.sldprt") is None


def test_only_stl_uses_the_mesh_preferences():
    """The knit and unit options belong to the neutral formats, not to a mesh."""
    assert set(MESH_IMPORT_FORMATS) == {"stl"}
    assert set(IMPORT_BY_EXTENSION.values()) == {"step", "iges", "parasolid", "acis", "stl"}


# --- schema guards ---------------------------------------------------------------


def test_a_format_that_contradicts_the_extension_is_refused():
    """Importing a .stl "as STEP" would silently produce something unexpected."""
    with pytest.raises(ValidationError, match="disagrees"):
        ImportArgs(input_path=r"C:\parts\bracket.stl", format="step")


def test_a_format_may_be_given_for_an_unknown_extension():
    """The override exists for a file whose extension says nothing useful."""
    args = ImportArgs(input_path=r"C:\parts\bracket.dat", format="step")
    assert args.format == "step"


def test_a_matching_format_is_accepted():
    assert ImportArgs(input_path=r"C:\parts\bracket.stp", format="step").format == "step"


def test_an_empty_path_is_refused():
    with pytest.raises(ValidationError):
        ImportArgs(input_path="")


def test_a_mesh_defaults_to_a_solid_not_to_a_picture():
    """SOLIDWORKS defaults to graphics, which yields no body and nothing measurable."""
    assert ImportArgs(input_path=r"C:\parts\bracket.stl").mesh_body_type == "solid"


def test_the_neutral_defaults_knit_and_read_the_files_own_units():
    args = ImportArgs(input_path=r"C:\parts\bracket.step")
    assert args.knit == "form_solids"
    assert args.neutral_units == "file"
    assert args.mesh_unit is None


def test_an_unknown_mesh_body_type_is_rejected():
    with pytest.raises(ValidationError):
        ImportArgs(input_path=r"C:\parts\bracket.stl", mesh_body_type="mesh")


def test_diagnostics_are_off_unless_asked_for():
    """Running a repair pass nobody asked for would change geometry silently."""
    args = ImportArgs(input_path=r"C:\parts\bracket.step")
    assert args.run_diagnostics is False
    assert args.remove_bad_faces is False, "deleting faces must never be a default"


# --- geometry summary -------------------------------------------------------------


class FakeDoc:
    """Only what ``model_snapshot`` reaches: a feature walk that yields nothing."""

    def FirstFeature(self):  # noqa: N802
        return None

    def GetFeatureCount(self):  # noqa: N802
        return 0


def test_an_empty_document_summarises_as_no_geometry(monkeypatch):
    from swmcp.handlers import exchange

    monkeypatch.setattr(
        exchange,
        "model_snapshot",
        lambda _doc: {
            "body_count": 0,
            "solid_body_count": 0,
            "sheet_body_count": 0,
            "volume_mm3": 0.0,
            "surface_area_mm2": 0.0,
            "face_count": 0,
            "edge_count": 0,
        },
    )
    found = _geometry_summary(FakeDoc())

    assert found["body_count"] == 0
    assert found["volume_mm3"] is None, "no solids means no volume, not a volume of zero"


def test_a_sheet_only_import_reports_no_volume(monkeypatch):
    """Six unknitted STEP faces are surfaces; a volume for them would be invented."""
    from swmcp.handlers import exchange

    monkeypatch.setattr(
        exchange,
        "model_snapshot",
        lambda _doc: {
            "body_count": 6,
            "solid_body_count": 0,
            "sheet_body_count": 6,
            "volume_mm3": 0.0,
            "surface_area_mm2": 5200.0,
            "face_count": 6,
            "edge_count": 24,
        },
    )
    found = _geometry_summary(FakeDoc())

    assert found["sheet_body_count"] == 6
    assert found["volume_mm3"] is None
    assert found["surface_area_mm2"] == 5200.0


# --- diagnostics are reported by what changed ---------------------------------------


class FakeDiagnosisDoc:
    """``ImportDiagnosis`` returns 1 whether or not it had anything to do."""

    def __init__(self, returns=1):
        self._returns = returns
        self.called_with = None

    def ImportDiagnosis(self, close_gaps, remove_faces, fix_faces, options):  # noqa: N802
        self.called_with = (close_gaps, remove_faces, fix_faces, options)
        return self._returns


def _snapshots(monkeypatch, sequence):
    from swmcp.handlers import exchange

    remaining = list(sequence)
    monkeypatch.setattr(exchange, "model_snapshot", lambda _doc: remaining.pop(0))


_HEALTHY = {
    "body_count": 1,
    "solid_body_count": 1,
    "sheet_body_count": 0,
    "volume_mm3": 24000.0,
    "surface_area_mm2": 5200.0,
    "face_count": 6,
    "edge_count": 12,
}


def test_diagnostics_on_healthy_geometry_report_no_change(monkeypatch):
    """The bug this prevents: claiming a repair because the call returned 1."""
    _snapshots(monkeypatch, [dict(_HEALTHY), dict(_HEALTHY)])
    doc = FakeDiagnosisDoc(returns=1)

    report = _run_import_diagnostics(doc, ImportArgs(input_path=r"C:\p.step"))

    assert report["returned"] == 1
    assert report["changed_the_model"] is False
    assert report["faces_before"] == report["faces_after"] == 6


def test_diagnostics_that_change_the_model_say_so(monkeypatch):
    repaired = dict(_HEALTHY, face_count=5, volume_mm3=23990.0)
    _snapshots(monkeypatch, [dict(_HEALTHY), repaired])

    report = _run_import_diagnostics(
        FakeDiagnosisDoc(), ImportArgs(input_path=r"C:\p.step", remove_bad_faces=True)
    )

    assert report["changed_the_model"] is True
    assert (report["faces_before"], report["faces_after"]) == (6, 5)
    assert report["volume_mm3_after"] == 23990.0


def test_diagnostics_pass_the_options_they_were_given(monkeypatch):
    _snapshots(monkeypatch, [dict(_HEALTHY), dict(_HEALTHY)])
    doc = FakeDiagnosisDoc()

    _run_import_diagnostics(
        doc,
        ImportArgs(
            input_path=r"C:\p.step", close_gaps=False, fix_faces=True, remove_bad_faces=True
        ),
    )

    close_gaps, remove_faces, fix_faces, _options = doc.called_with
    assert (close_gaps, remove_faces, fix_faces) == (False, True, True)


# --- result contract -----------------------------------------------------------------


def test_a_result_without_geometry_is_representable():
    """A graphics-only import is a real outcome, not an error."""
    result = ImportResult(
        document={"title": "mesh.SLDPRT"},
        format="stl",
        source_path=r"C:\p.stl",
        geometry_found=False,
        body_count=0,
        solid_body_count=0,
        sheet_body_count=0,
    )
    assert result.volume_mm3 is None
    assert result.diagnostics is None
