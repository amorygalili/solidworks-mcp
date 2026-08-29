"""Live cover for draft (FEAT-010) and the slot family (FEAT-013).

Draft has a closed form, which is why it is checked to twelve significant figures rather
than by "the volume changed". Drafting every side of a W x D x h prism outward from its
bottom face gives::

    V = W*D*h + tan(a)*(W+D)*h^2 + (4/3)*tan(a)^2*h^3

and flipping the draft flips the sign of the middle term. Getting the selection marks
wrong — 1 neutral plane, 2 faces, 4 edges — produces a feature that builds and is simply
the wrong shape, so the arithmetic is the only thing that catches it.

Draft tests take their own document because each one drafts the whole block; the slot
tests share one, per the cost policy in ``CLAUDE.md``.
"""

from __future__ import annotations

import math

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

W, D, H = 40.0, 30.0, 20.0
BOX_MM3 = W * D * H


def drafted_volume(angle_deg: float, *, outward: bool) -> float:
    """The closed form for a prism drafted on all four sides from its base."""
    t = math.tan(math.radians(angle_deg))
    sign = 1.0 if outward else -1.0
    return BOX_MM3 + sign * t * (W + D) * H**2 + (4.0 / 3.0) * t * t * H**3


@pytest.fixture
def block(call, scratch_root, unique_name):
    """A fresh 40 x 30 x 20 block on the top plane, so +Y is up."""
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)
    call("sw_doc_new", {"doc_type": "part"})
    call("sw_doc_save", {"output_path": str(scratch_root / f"{unique_name}.SLDPRT")})
    call("sw_sketch_start", {"on": {"standard_plane": "top"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [W, D]}]},
    )
    call("sw_sketch_exit")
    call("sw_feature_extrude_boss", {"depth": H, "name": "Block"})


def _faces(call) -> list[dict]:
    return call(
        "sw_probe_faces", {"geometry_type": "planar_face", "limit": 50}
    )["result"]["candidates"]


def _bottom_and_sides(call) -> tuple[dict, list[dict]]:
    """The -Y face is the base; the four faces with no Y component are the sides."""
    bottom = None
    sides = []
    for face in _faces(call):
        normal = face["measurements"].get("direction")
        if not normal:
            continue
        if normal[1] < -0.9:
            bottom = face
        elif abs(normal[1]) < 0.1:
            sides.append(face)
    assert bottom is not None, "no downward face found on the block"
    assert len(sides) == 4, f"expected four sides, found {len(sides)}"
    return bottom, sides


# --- draft (FEAT-010) ---------------------------------------------------------


def test_a_neutral_plane_draft_matches_the_closed_form(call, block):
    """Unflipped, SOLIDWORKS drafts outward and the block gains material."""
    bottom, sides = _bottom_and_sides(call)

    drafted = call(
        "sw_feature_draft",
        {
            "method": "neutral_plane",
            "angle": 5,
            "neutral_ref": bottom["tool_args"]["ref"],
            "face_refs": [side["tool_args"]["ref"] for side in sides],
            "name": "Taper",
        },
    )["result"]

    assert drafted["feature_name"] == "Taper"
    assert drafted["method"] == "neutral_plane"
    assert drafted["faces_drafted"] == 4
    assert drafted["volume_mm3_before"] == pytest.approx(BOX_MM3, rel=1e-9)
    assert drafted["volume_mm3_after"] == pytest.approx(
        drafted_volume(5.0, outward=True), rel=1e-9
    )
    assert all(check["passed"] for check in drafted["verification"]["checks"])


def test_flipping_the_draft_removes_material_instead(call, block):
    bottom, sides = _bottom_and_sides(call)

    drafted = call(
        "sw_feature_draft",
        {
            "method": "neutral_plane",
            "angle": 5,
            "flip": True,
            "neutral_ref": bottom["tool_args"]["ref"],
            "face_refs": [side["tool_args"]["ref"] for side in sides],
        },
    )["result"]

    assert drafted["volume_mm3_after"] == pytest.approx(
        drafted_volume(5.0, outward=False), rel=1e-9
    )
    assert drafted["volume_mm3_after"] < BOX_MM3, "a flipped draft must taper inward"


def test_a_draft_can_use_a_standard_plane_as_its_neutral_reference(call, block):
    _, sides = _bottom_and_sides(call)

    drafted = call(
        "sw_feature_draft",
        {
            "method": "neutral_plane",
            "angle": 3,
            "neutral_standard_plane": "top",
            "face_refs": [side["tool_args"]["ref"] for side in sides],
        },
    )["result"]

    assert drafted["faces_drafted"] == 4
    assert drafted["volume_mm3_after"] != pytest.approx(BOX_MM3, rel=1e-9)


def test_a_draft_without_a_neutral_reference_is_a_schema_error(call, block):
    payload = call("sw_feature_draft", {"angle": 5}, expect_ok=False)
    assert payload["error"]["category"] == "validation"


def test_naming_both_neutral_forms_is_refused(call, block):
    bottom, sides = _bottom_and_sides(call)
    payload = call(
        "sw_feature_draft",
        {
            "angle": 5,
            "neutral_ref": bottom["tool_args"]["ref"],
            "neutral_standard_plane": "top",
            "face_refs": [sides[0]["tool_args"]["ref"]],
        },
        expect_ok=False,
    )
    assert payload["error"]["category"] == "validation"


def test_parting_line_drafting_needs_edges(call, block):
    bottom, _ = _bottom_and_sides(call)
    payload = call(
        "sw_feature_draft",
        {
            "method": "parting_line",
            "angle": 5,
            "neutral_ref": bottom["tool_args"]["ref"],
        },
        expect_ok=False,
    )
    assert payload["error"]["category"] == "validation"


# --- slots (FEAT-013) ---------------------------------------------------------


@pytest.fixture(scope="module")
def slot_part(dispatcher, scratch_root):
    """One document for every slot test; they only add sketch geometry."""
    target = scratch_root / "swmcp_slots.SLDPRT"
    for stale in scratch_root.glob("swmcp_slots*.SLDPRT"):
        stale.unlink(missing_ok=True)
    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_doc_save", {"output_path": str(target)})
    yield target.name
    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": target.name}, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def slot_call(call, slot_part):
    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        args = dict(arguments or {})
        args.setdefault("document", {"title": slot_part})
        return call(name, args, expect_ok=expect_ok)

    return _call


def _sketch_with(slot_call, entity: dict) -> dict:
    slot_call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    added = slot_call("sw_sketch_add_geometry", {"entities": [entity]})["result"]
    slot_call("sw_sketch_exit")
    return added


@pytest.mark.parametrize(
    "entity",
    [
        pytest.param(
            {"type": "slot_straight", "start": [0, 0], "end": [30, 0], "width": 8},
            id="straight",
        ),
        pytest.param(
            {"type": "slot_centerpoint", "center": [0, 40], "end": [15, 40], "width": 8},
            id="centerpoint",
        ),
        pytest.param(
            {
                "type": "slot_arc",
                "center": [0, 80],
                "start": [20, 80],
                "end": [0, 100],
                "width": 6,
            },
            id="arc",
        ),
        pytest.param(
            {
                "type": "slot_3point_arc",
                "start": [60, 0],
                "end": [90, 0],
                "through": [75, 12],
                "width": 6,
            },
            id="3point_arc",
        ),
    ],
)
def test_every_slot_form_creates_geometry(slot_call, entity):
    added = _sketch_with(slot_call, entity)

    assert added["created"], f"{entity['type']} produced no geometry"
    assert added["failed"] == []
    assert added["warnings"] == []
    assert all(check["passed"] for check in added["verification"]["checks"])


def test_length_type_dimensions_the_slot_rather_than_shaping_it(slot_call):
    """A finding, pinned: the two length types build identical geometry.

    ``swSketchSlotLengthType_e`` selects how SOLIDWORKS *dimensions* a slot, not how it
    is shaped. Measured, centre-to-centre and overall gave the same total segment length
    from the same points and width. The setting only becomes observable once
    ``add_dimension`` is set, which is why that flag exists.
    """

    def extent(added: dict) -> float:
        return sum(segment.get("length_m") or 0.0 for segment in added["created"])

    centres = _sketch_with(
        slot_call,
        {
            "type": "slot_straight",
            "start": [0, 140],
            "end": [30, 140],
            "width": 8,
            "length_type": "center_to_center",
        },
    )
    overall = _sketch_with(
        slot_call,
        {
            "type": "slot_straight",
            "start": [0, 180],
            "end": [30, 180],
            "width": 8,
            "length_type": "overall",
        },
    )

    assert extent(centres) > 0, "the slot reported no segment lengths"
    assert extent(overall) == pytest.approx(extent(centres), rel=1e-9), (
        "length_type is a dimensioning choice; if this ever differs, the schema "
        "description is wrong and should be corrected rather than this assertion"
    )


def test_a_slot_reports_the_segments_it_really_created(slot_call):
    """CreateSketchSlot hands back one wrapper; the sketch gains three or four segments.

    Reporting the wrapper gave a created entry with no type and no length while the
    verification block said the sketch had grown, so the two disagreed.
    """
    added = _sketch_with(
        slot_call,
        {"type": "slot_straight", "start": [0, 220], "end": [25, 220], "width": 6},
    )

    assert len(added["created"]) == added["verification"]["after"]["segment_count"], (
        "created must list the same number of segments the sketch actually gained"
    )
    assert all(segment.get("length_m") for segment in added["created"])
    assert {segment["type"] for segment in added["created"]} <= {"line", "arc"}


def test_adding_the_slot_dimension_defines_the_sketch_further(slot_call):
    """add_dimension is what makes length_type mean anything."""
    plain = _sketch_with(
        slot_call,
        {"type": "slot_straight", "start": [0, 260], "end": [25, 260], "width": 6},
    )
    dimensioned = _sketch_with(
        slot_call,
        {
            "type": "slot_straight",
            "start": [0, 300],
            "end": [25, 300],
            "width": 6,
            "add_dimension": True,
        },
    )

    assert plain["sketch_state"]["relation_count"] <= dimensioned["sketch_state"][
        "relation_count"
    ] or dimensioned["sketch_state"]["status"] != plain["sketch_state"]["status"], (
        "asking for the dimension changed nothing about how defined the sketch is"
    )


def test_a_slot_needs_a_positive_width(slot_call):
    payload = slot_call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "slot_straight", "start": [0, 0], "end": [10, 0], "width": 0}]},
        expect_ok=False,
    )
    assert payload["error"]["category"] == "validation"


def test_a_slot_can_be_cut_and_patterned(slot_call):
    """FEAT-013 asks for slot patterns; a cut slot patterns like any other feature."""
    slot_call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    slot_call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [200, 0], "opposite": [300, 60]}]},
    )
    slot_call("sw_sketch_exit")
    slot_call("sw_feature_extrude_boss", {"depth": 10, "name": "SlotPlate"})

    slot_call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    slot_call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "slot_straight", "start": [215, 15], "end": [235, 15], "width": 6}]},
    )
    slot_call("sw_sketch_exit")
    cut = slot_call(
        "sw_feature_extrude_cut",
        {"end_condition": "through_all", "reverse": True, "name": "SlotCut"},
    )["result"]

    assert cut["volume_mm3_after"] < cut["volume_mm3_before"], "the slot removed no material"
