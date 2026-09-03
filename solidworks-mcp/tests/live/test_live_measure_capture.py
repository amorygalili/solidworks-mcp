"""A box that bounds the surfaces, and a preview full of scaffolding (FEAT-019/VIEW-004).

Two readings from the same modelling session that were quietly wrong rather than
loudly broken. ``sw_measure`` reported a helical gear as 47.48mm across a 46.57mm OD -
``IBody2::GetBodyBox`` bounds the underlying surface definition, not the trimmed
material, and reads large on anything spline-shaped. And a gear preview came back with
``swmcp_axis_z`` and ``InnerConePlane`` drawn across the model.

The bounding-box numbers are pinned offline in ``tests/test_measure_bounding_box.py``
from this build's own readings. These check the same behaviour through the real
pipeline, on geometry whose true size the test knows in advance.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

#: A spline arch whose apex is specified at exactly y=10mm, closed by its own chord.
#: GetBodyBox reported 10.843455mm tall for this shape class; the material is 10.000mm.
_ARCH = [
    {"type": "spline", "points": [[0, 0], [5, 8], [10, 10], [15, 8], [20, 0]]},
    {"type": "line", "start": [20, 0], "end": [0, 0]},
]


@pytest.fixture(scope="module")
def shared_part(dispatcher, scratch_root):
    """One document, one spline body, for the whole module."""
    target = scratch_root / "swmcp_measure_capture.SLDPRT"
    for stale in scratch_root.glob("swmcp_measure_capture*.SLDPRT"):
        stale.unlink(missing_ok=True)

    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    if not made.get("ok") and made["error"]["code"] == "TEMPLATE_NOT_FOUND":
        fallback = Path("C:/ProgramData/SolidWorks/SOLIDWORKS 2026/templates/Part.PRTDOT")
        if not fallback.is_file():
            pytest.skip(f"no default part template and none at {fallback}")
        made = dispatcher.call(
            "sw_doc_new", {"doc_type": "part", "template_path": str(fallback)}
        )
    assert made.get("ok"), made.get("error")
    title = target.name
    dispatcher.call("sw_doc_save", {"output_path": str(target)})

    document = {"title": title}
    dispatcher.call("sw_sketch_create", {
        "document": document,
        "on": {"standard_plane": "front"},
        "auto_relations": False,
        "entities": _ARCH,
    })
    built = dispatcher.call("sw_feature_extrude_boss", {
        "document": document, "depth": 10, "merge_result": False,
    })
    assert built.get("ok"), built.get("error")

    yield title

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": title}, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def call(call, shared_part):
    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        args = dict(arguments or {})
        args.setdefault("document", {"title": shared_part})
        return call(name, args, expect_ok=expect_ok)

    return _call


# --- the bounding box ------------------------------------------------------------


def test_the_default_box_names_itself_as_approximate(call):
    """It was never wrong to report the cheap box; it was wrong not to say so."""
    box = call("sw_measure")["result"]["bounding_box"]
    assert box["method"] == "body_box"
    assert box["approximate"] is True


def test_the_tight_box_measures_the_material(call):
    """The spline apex is at exactly 10mm, and only one of the two readings says so."""
    fast = call("sw_measure")["result"]["bounding_box"]
    tight = call("sw_measure", {"bounding_box": "tight"})["result"]["bounding_box"]

    assert tight["method"] == "extreme_point"
    assert tight["approximate"] is False

    assert tight["size_mm"][1] == pytest.approx(10.0, abs=1e-4)
    assert fast["size_mm"][1] > tight["size_mm"][1], (
        "this shape class is exactly where GetBodyBox reads large"
    )
    # The X span is bounded by the spline's own endpoints, so both should agree there.
    assert fast["size_mm"][0] == pytest.approx(tight["size_mm"][0], abs=1e-4)


def test_the_tight_reading_reports_what_the_cheap_one_overstated(call):
    """Evidence, not a claim: two readings of the same body in the same call."""
    tight = call("sw_measure", {"bounding_box": "tight"})["result"]["bounding_box"]
    overstated = tight["fast_box_overstated_mm"]

    assert overstated[1] > 0.5, f"expected the phantom height to show up, got {overstated}"
    assert overstated[0] == pytest.approx(0.0, abs=1e-4)
    assert overstated[2] == pytest.approx(0.0, abs=1e-4)


def test_both_readings_agree_on_analytic_geometry(call, unique_name):
    """The false-positive guard. If tight moved a box that was already exact, the
    tight path would be the broken one - a cylinder r=10 is exactly 20mm across."""
    call("sw_sketch_create", {
        "on": {"standard_plane": "top"},
        "auto_relations": False,
        "entities": [{"type": "circle", "center": [100, 0], "radius": 10}],
    })
    call("sw_feature_extrude_boss", {"depth": 10, "merge_result": False, "name": unique_name})

    fast = call("sw_measure", {"scope": {"body_name": unique_name}})
    tight = call("sw_measure", {"scope": {"body_name": unique_name}, "bounding_box": "tight"})
    fast_size = fast["result"]["bounding_box"]["size_mm"]
    tight_size = tight["result"]["bounding_box"]["size_mm"]

    assert tight_size == pytest.approx(fast_size, abs=1e-4)
    assert tight_size[0] == pytest.approx(20.0, abs=1e-4)


# --- the capture ------------------------------------------------------------------


def _capture(call, scratch_root, name, **extra):
    path = scratch_root / f"{name}.png"
    path.unlink(missing_ok=True)
    result = call(
        "sw_view_capture",
        {"output_path": str(path), "overwrite": "allow", "orientation": "isometric", **extra},
    )["result"]
    return result, Path(result["saved_path"])


def test_a_capture_says_which_scaffolding_it_suppressed(call, scratch_root, unique_name):
    result, written = _capture(call, scratch_root, unique_name)
    hidden = result["details"]["reference_geometry_hidden"]

    assert "swDisplayPlanes" in hidden
    assert "swDisplayAxes" in hidden
    assert "swDisplayOrigins" in hidden
    # Sketches are content, not scaffolding, and are deliberately left alone.
    assert "swDisplaySketches" not in hidden
    assert written.is_file()


def test_asking_for_the_scaffolding_suppresses_nothing(call, scratch_root, unique_name):
    result, _ = _capture(call, scratch_root, unique_name, show_reference_geometry=True)
    assert result["details"]["reference_geometry_hidden"] == []


def test_the_users_own_view_preferences_survive_a_capture(call, scratch_root, unique_name):
    """These are application-wide settings. A capture that left the user's planes
    switched off would be a lasting change made on their behalf without asking.
    """
    def toggle(code):
        return call(
            "sw_api_invoke",
            {"target": "app", "member": "GetUserPreferenceToggle", "args": [code]},
        )["result"]["value"]

    codes = {"swDisplayPlanes": 5, "swDisplayAxes": 4, "swDisplayOrigins": 6}
    before = {name: toggle(code) for name, code in codes.items()}
    _capture(call, scratch_root, unique_name)
    after = {name: toggle(code) for name, code in codes.items()}

    assert after == before


def test_two_captures_of_the_same_view_are_byte_identical(call, scratch_root, unique_name):
    """Guards the restore from the other side.

    If a capture leaked a changed preference, the second one would render a different
    scene from the first and the hashes would diverge. Same view, same settings, same
    bytes.
    """
    _, first = _capture(call, scratch_root, f"{unique_name}_a")
    _, second = _capture(call, scratch_root, f"{unique_name}_b")

    assert (
        hashlib.sha256(first.read_bytes()).hexdigest()
        == hashlib.sha256(second.read_bytes()).hexdigest()
    )
