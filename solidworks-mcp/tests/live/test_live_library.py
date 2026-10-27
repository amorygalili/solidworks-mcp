"""The library and the skill's CLI against a real session.

Everything below the library is already proven live by the other modules; what these
tests add is the two claims the front ends make. First, that a script gets typed
results and a measured part out of the same pipeline. Second, that a separate CLI
process — which is how the skill runs — sees the same session state the library left
behind, since nothing the skill relies on lives in Python memory between commands.

One document for the module, built by extrusion; see the cost policy in CLAUDE.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

PLATE = (100.0, 60.0, 8.0)
FALLBACK_TEMPLATE = Path("C:/ProgramData/SolidWorks/SOLIDWORKS 2026/templates/Part.PRTDOT")


@pytest.fixture(scope="module")
def sw(dispatcher):
    """A library client borrowing the suite's dispatcher, so it shares the STA worker."""
    from swmcp import SolidWorks

    return SolidWorks(dispatcher=dispatcher)


@pytest.fixture(scope="module")
def plate(sw, scratch_root):
    from swmcp import OperationError

    target = scratch_root / "swmcp_library_plate.SLDPRT"
    target.unlink(missing_ok=True)

    # Named explicitly when the default-template preference is empty, as it is on
    # this machine; see "swDefaultTemplatePart is not File Locations" in CLAUDE.md.
    try:
        sw.doc_new(doc_type="part")
    except OperationError as exc:
        if exc.code != "TEMPLATE_NOT_FOUND":
            raise
        if not FALLBACK_TEMPLATE.is_file():
            pytest.skip(f"no default part template and none at {FALLBACK_TEMPLATE}")
        sw.doc_new(doc_type="part", template_path=str(FALLBACK_TEMPLATE))
    title = Path(sw.doc_save(output_path=str(target)).saved_path).name
    document = {"title": title}

    x, y, z = PLATE
    sw.sketch_start(document=document, on={"standard_plane": "front"})
    sw.sketch_add_geometry(
        document=document,
        entities=[{"type": "rect_corner", "corner": [0, 0], "opposite": [x, y]}],
        auto_relations=False,
    )
    sw.sketch_exit(document=document)
    sw.feature_extrude_boss(document=document, depth=z, name="LibraryPlate")
    yield title

    sw.doc_close(document=document, save_first="discard", confirm=True)


def test_a_script_builds_a_part_that_measures_right(sw, plate):
    """Verified by arithmetic known in advance, not by the calls having returned."""
    measured = sw.measure(document={"title": plate})
    x, y, z = PLATE
    assert measured.mass_properties["volume_mm3"] == pytest.approx(x * y * z, abs=1e-3)
    assert sw.last is not None and sw.last.ok


def test_the_cli_sees_what_the_library_built(plate, scratch_root):
    """The skill runs one process per command; the session is what carries state."""
    completed = subprocess.run(
        [sys.executable, "-m", "swmcp", "call", "sw_feature_list",
         json.dumps({"document": {"title": plate}}),
         "--allowed-root", str(scratch_root)],
        capture_output=True,
        timeout=110,
        check=False,
    )
    payload = json.loads(completed.stdout.decode("utf-8"))
    assert completed.returncode == 0, payload
    names = json.dumps(payload["result"])
    assert "LibraryPlate" in names
