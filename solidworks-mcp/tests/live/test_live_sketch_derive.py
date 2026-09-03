"""Where a sketch's axes point, and copying a sketch onto another plane (SK-001/003/004).

Both come from the same modelling session. A line drawn ``(0,0)->(0,-20)`` on Top runs
along model **+Z**, and nothing in the sketch result said so - it had to be guessed and
then confirmed after the fact from a swept body's bounding box. And a bevel gear's two
loft sections are one profile and the same profile scaled by 0.717, which is
geometrically a single input; with no way to say that, both were generated and
transmitted in full, 160 entities each, at 101s and 114s.

The frame numbers here are pinned offline in ``tests/test_sketch_frame.py`` against the
arrays measured from this build. These tests check the same readings arrive through the
real pipeline, and that a derived sketch is geometrically what it claims to be.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def shared_part(dispatcher, scratch_root):
    """One document for the whole module. See the cost policy in CLAUDE.md."""
    target = scratch_root / "swmcp_sketch_derive.SLDPRT"
    for stale in scratch_root.glob("swmcp_sketch_derive*.SLDPRT"):
        stale.unlink(missing_ok=True)

    # Named explicitly rather than relying on swDefaultTemplatePart. That preference is
    # empty on this machine and stays empty: measured from a freshly started process as
    # well as from a long-lived one, so it is not the process-age effect once suspected.
    # It is Tools > Options > System Options > Default Templates, which is a different
    # setting from the File Locations directory list.
    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    if not made.get("ok") and made["error"]["code"] == "TEMPLATE_NOT_FOUND":
        fallback = Path("C:/ProgramData/SolidWorks/SOLIDWORKS 2026/templates/Part.PRTDOT")
        if not fallback.is_file():
            pytest.skip(f"no default part template and none at {fallback}")
        made = dispatcher.call(
            "sw_doc_new", {"doc_type": "part", "template_path": str(fallback)}
        )
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_doc_save", {"output_path": str(target)})
    title = target.name
    yield title

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": title}, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def call(call, shared_part):
    """Every call in this module is addressed at the shared document, never 'active'."""

    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        args = dict(arguments or {})
        args.setdefault("document", {"title": shared_part})
        return call(name, args, expect_ok=expect_ok)

    return _call


def _sketch(call, entities, plane="front", **extra):
    on = {"standard_plane": plane} if isinstance(plane, str) else plane
    return call(
        "sw_sketch_create",
        {"on": on, "auto_relations": False, "entities": entities, **extra},
    )["result"]


# --- the frame -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("plane", "expected"),
    [
        ("front", "sketch +X -> model +X, sketch +Y -> model +Y, normal -> model +Z"),
        ("top", "sketch +X -> model +X, sketch +Y -> model -Z, normal -> model +Y"),
        ("right", "sketch +X -> model -Z, sketch +Y -> model +Y, normal -> model +X"),
    ],
)
def test_a_sketch_says_where_its_own_axes_point(call, plane, expected):
    """The reading that used to require building a body to discover."""
    result = _sketch(call, [{"type": "line", "start": [0, 0], "end": [0, -20]}], plane=plane)

    frame = result["frame"]
    assert frame is not None, "a sketch on a standard plane must report a frame"
    assert frame["maps"] == expected
    assert frame["origin_mm"] == [0, 0, 0]
    assert frame["scale"] == pytest.approx(1.0)


def test_an_offset_plane_reports_where_its_origin_actually_sits(call):
    """The translation is stored negated, so reading it raw puts the sketch on the
    wrong side of the model. Confirmed here against the plane's own offset."""
    plane = call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "front", "distance": 25},
    )["result"]

    result = _sketch(
        call,
        [{"type": "line", "start": [0, 0], "end": [10, 0]}],
        plane={"plane_name": plane["plane_name"]},
    )
    frame = result["frame"]
    assert frame["origin_mm"] == pytest.approx([0, 0, 25], abs=1e-6)
    assert frame["normal"] == pytest.approx([0, 0, 1], abs=1e-9)


def test_the_frame_comes_back_from_diagnose_too(call):
    """Whatever answers 'what is wrong with this sketch' should answer 'where is it'."""
    made = _sketch(call, [{"type": "circle", "center": [0, 0], "radius": 8}], plane="top")
    found = call("sw_sketch_diagnose", {"sketch_name": made["sketch_name"]})["result"]
    assert found["frame"]["maps"] == made["frame"]["maps"]


# --- deriving --------------------------------------------------------------------


def test_a_plain_derive_repeats_the_source(call):
    source = _sketch(
        call,
        [
            {"type": "line", "start": [0, 0], "end": [20, 0]},
            {"type": "line", "start": [20, 0], "end": [20, 10]},
            {"type": "line", "start": [20, 10], "end": [0, 10]},
            {"type": "line", "start": [0, 10], "end": [0, 0]},
        ],
    )
    assert source["contours"]["closed_contour_count"] == 1

    derived = call(
        "sw_sketch_derive",
        {"source_sketch": source["sketch_name"], "on": {"standard_plane": "right"}},
    )["result"]

    assert derived["sketch_name"] != source["sketch_name"]
    assert derived["created_total"] == 4
    assert derived["skipped"] == []
    # The copy has to be a usable profile, not just the right number of segments.
    assert derived["contours"]["closed_contour_count"] == 1
    assert derived["contours"]["self_intersections"] == []
    assert derived["max_deviation_mm"] == pytest.approx(0.0, abs=1e-3)


def test_a_derive_can_scale_onto_another_plane(call):
    """The bevel case: one section, and the same section at k."""
    source = _sketch(call, [{"type": "circle", "center": [0, 0], "radius": 10}])
    plane = call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "front", "distance": 20},
    )["result"]

    derived = call(
        "sw_sketch_derive",
        {
            "source_sketch": source["sketch_name"],
            "on": {"plane_name": plane["plane_name"]},
            "scale": 0.717,
        },
    )["result"]

    circles = [c for c in derived["created"] if c["type"] == "arc"]
    assert len(circles) == 1
    assert circles[0]["radius_mm"] == pytest.approx(7.17, abs=1e-3)
    assert derived["frame"]["origin_mm"] == pytest.approx([0, 0, 20], abs=1e-6)


def test_a_mirrored_derive_keeps_every_arc_the_same_size(call):
    """Mirroring without reversing an arc rebuilds its complement.

    Endpoints are identical either way, so nothing but the sweep can catch it - the
    same fault that made a 0.76mm fillet sweep 272 degrees instead of 88.
    """
    source = _sketch(
        call,
        [
            {"type": "line", "start": [0, 0], "end": [20, 0]},
            {
                "type": "arc_center",
                "center": [20, 5],
                "start": [20, 0],
                "end": [20, 10],
                "direction": "counterclockwise",
            },
            {"type": "line", "start": [20, 10], "end": [0, 10]},
            {"type": "line", "start": [0, 10], "end": [0, 0]},
        ],
    )
    original = next(c for c in source["created"] if c["type"] == "arc")
    assert original["sweep_deg"] == pytest.approx(180.0, abs=0.5)

    derived = call(
        "sw_sketch_derive",
        {
            "source_sketch": source["sketch_name"],
            "on": {"standard_plane": "top"},
            "mirror": "y",
        },
    )["result"]

    copied = [c for c in derived["created"] if c["type"] == "arc"]
    assert len(copied) == 1
    assert copied[0]["sweep_deg"] == pytest.approx(original["sweep_deg"], abs=0.5)
    assert copied[0]["radius_mm"] == pytest.approx(original["radius_mm"], abs=1e-3)
    assert derived["contours"]["closed_contour_count"] == 1
    assert derived["contours"]["major_arc_segment_ids"] == []


def test_a_segment_with_no_spec_is_named_rather_than_dropped(call):
    """An ellipse cannot be restated as a primitive. Silently omitting it would leave
    a derived profile that does not close, with nothing saying why."""
    source = _sketch(
        call,
        [
            {
                "type": "ellipse",
                "center": [0, 0],
                "major_axis_point": [15, 0],
                "minor_axis_point": [0, 8],
            }
        ],
    )

    payload = call(
        "sw_sketch_derive",
        {"source_sketch": source["sketch_name"], "on": {"standard_plane": "top"}},
        expect_ok=False,
    )
    assert payload["error"]["code"] == "NOTHING_TO_DERIVE"
    assert payload["error"]["context"]["skipped"], "the refusal must say what it could not do"


def test_deriving_a_sketch_that_does_not_exist_is_refused(call):
    payload = call(
        "sw_sketch_derive",
        {"source_sketch": "NoSuchSketch", "on": {"standard_plane": "top"}},
        expect_ok=False,
    )
    assert payload["error"]["code"] == "SKETCH_NOT_FOUND"


def test_a_loft_between_a_section_and_its_derived_copy(call, unique_name):
    """The motivating case, checked by arithmetic the test knew in advance.

    A frustum r=10 to r=5 over 20mm is (pi*h/3)(R^2 + Rr + r^2) = 3665.19 mm^3. A loft
    between two circles is a B-spline surface rather than an exact frustum - measured
    0.0036% under the closed form - so this compares with a relative tolerance.
    """
    big = _sketch(call, [{"type": "circle", "center": [0, 0], "radius": 10}], plane="top")
    plane = call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "top", "distance": 20},
    )["result"]
    small = call(
        "sw_sketch_derive",
        {
            "source_sketch": big["sketch_name"],
            "on": {"plane_name": plane["plane_name"]},
            "scale": 0.5,
        },
    )["result"]

    # Not measured before: at this point the document holds only sketches, and
    # sw_measure rightly refuses a document with no bodies. The loft is the only body
    # afterwards, so its own volume is the whole comparison.
    call(
        "sw_feature_loft",
        {
            "profile_sketches": [big["sketch_name"], small["sketch_name"]],
            "merge_result": False,
            "name": unique_name,
        },
    )
    volume = call(
        "sw_measure", {"scope": {"feature_name": unique_name}}
    )["result"]["mass_properties"]["volume_mm3"]

    expected = (math.pi * 20 / 3) * (10**2 + 10 * 5 + 5**2)
    assert volume == pytest.approx(expected, rel=1e-3)
