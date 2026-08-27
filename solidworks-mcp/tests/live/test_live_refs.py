"""Live entity references (REF-002..007).


The centrepiece is the ambiguity test: two identical holes must produce two distinct

candidates, and a reference that cannot tell them apart must return both rather than

picking one.

"""


from __future__ import annotations

import copy
import json

import pytest

pytestmark = pytest.mark.live


@pytest.fixture

def box_part(call, scratch_root, unique_name, dispatcher):

    """A 50 x 30 x 8 mm box, saved so it can be closed and reopened."""

    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):

        stale.unlink(missing_ok=True)

    target = scratch_root / f"{unique_name}.SLDPRT"


    call("sw_doc_new", {"doc_type": "part"})


    def build(session):

        doc = session.active_doc()

        plane = session.find_standard_plane(doc, "front")

        plane.Select2(False, 0)

        sketch = doc.SketchManager

        sketch.InsertSketch(True)

        sketch.CreateCornerRectangle(0, 0, 0, 0.050, 0.030, 0)

        sketch.InsertSketch(True)

        doc.FeatureManager.FeatureExtrusion3(

            True, False, False, 0, 0, 0.008, 0.01, False, False, False, False,

            0, 0, False, False, False, False, True, True, True, 0, 0, False,

        )

        doc.ClearSelection2(True)


    dispatcher.worker.call(build, label="build_box", kind="mutation", timeout_s=180)

    call("sw_doc_save", {"output_path": str(target)})

    try:

        yield target

    finally:

        # The autouse fixture closes the document and removes the file, in that order.

        pass


def test_a_probe_finds_every_face_of_the_box(call, box_part):

    result = call("sw_probe_faces", {})["result"]

    assert result["examined"] == 6, "a box has six faces"

    assert result["matched"] == 6


    labels = [c["label"] for c in result["candidates"]]

    assert all("planar face" in label for label in labels)


def test_a_captured_reference_carries_every_addressing_mode(call, box_part):

    """REF-002/003/004 together: opaque, semantic, and human forms in one object."""

    largest = call("sw_probe_faces", {"geometry_type": "planar_face"})["result"]["candidates"][0]

    reference = largest["reference"]


    assert reference["persistent"]["data_b64"], "REF-003: a persistent reference"

    assert reference["persistent"]["scheme"] == "GetPersistReference3"


    semantic = reference["semantic"]

    assert semantic["geometry_type"] == "planar_face"

    assert semantic["signature"], "REF-004: a geometry signature"

    assert semantic["feature_ancestry"], "REF-004: feature ancestry"

    assert semantic["feature_type_names"] == ["Extrusion"], "locale-invariant type token"

    assert semantic["measurements"]["area_m2"] > 0

    assert len(semantic["measurements"]["point_m"]) == 3


    assert reference["label"], "a human-readable description"

    assert "ref" in largest["tool_args"], "paste-ready arguments"


def test_the_largest_face_is_reported_first(call, box_part):

    candidates = call("sw_probe_faces", {"geometry_type": "planar_face"})["result"]["candidates"]

    areas = [c["measurements"]["area_m2"] for c in candidates]

    assert areas == sorted(areas, reverse=True)

    # The 50 x 30 mm face is the largest on a 50 x 30 x 8 box.

    assert areas[0] == pytest.approx(0.050 * 0.030, rel=1e-6)


def test_filters_narrow_a_probe_to_one_face(call, box_part):

    """The practical answer to ambiguity: filter before you act."""

    result = call(

        "sw_probe_faces",

        {"geometry_type": "planar_face", "area_min_mm2": 1400, "area_max_mm2": 1600},

    )["result"]

    assert result["matched"] == 2, "the two 50x30 faces, front and back"


    with_normal = call(

        "sw_probe_faces",

        {

            "geometry_type": "planar_face",

            "area_min_mm2": 1400,

            "area_max_mm2": 1600,

            "normal": [0, 0, 1],

            "normal_within_deg": 1.0,

        },

    )["result"]

    assert with_normal["matched"] == 2, "front and back share an axis, so both still match"


def test_a_reference_survives_close_and_reopen(call, box_part):

    """REF-003 and REF-007: serialize, reopen the document, resolve exactly."""

    candidate = call("sw_probe_faces", {"geometry_type": "planar_face"})["result"]["candidates"][0]

    stored = json.loads(json.dumps(candidate["tool_args"]["ref"]))


    call("sw_doc_close", {"save_first": "discard", "confirm": True})

    call("sw_doc_open", {"path": str(box_part)})


    resolved = call("sw_ref_resolve", {"ref": stored})["result"]

    assert resolved["via"] == "persistent", "the persistent reference should still be exact"

    assert resolved["refreshed"]["semantic"]["measurements"]["area_m2"] == pytest.approx(

        stored["semantic"]["measurements"]["area_m2"], rel=1e-9

    )


def test_a_broken_persistent_reference_heals_by_geometry(call, box_part):

    """REF-004/006: when the opaque handle dies, geometry matching takes over."""

    import base64


    candidate = call("sw_probe_faces", {"geometry_type": "planar_face"})["result"]["candidates"][0]

    damaged = copy.deepcopy(candidate["tool_args"]["ref"])

    # Valid base64 of the right length, but not a reference SOLIDWORKS can resolve.

    blob_length = len(base64.b64decode(damaged["persistent"]["data_b64"]))

    damaged["persistent"]["data_b64"] = base64.b64encode(bytes(blob_length)).decode("ascii")


    resolved = call("sw_ref_resolve", {"ref": damaged})["result"]

    assert resolved["via"] == "semantic", "it must fall back rather than fail"

    assert resolved["drift"]["persistent_status"], "the failure reason must be reported"

    assert resolved["drift"]["moved_mm"] == pytest.approx(0.0, abs=1e-6)

    assert resolved["refreshed"]["persistent"]["data_b64"], "a fresh handle to store"

    assert any("persistent reference did not resolve" in w for w in resolved["warnings"])


def test_an_unresolvable_reference_says_so(call, box_part):

    """REF-006: not found is an answer; picking something anyway is not."""

    candidate = call("sw_probe_faces", {"geometry_type": "planar_face"})["result"]["candidates"][0]

    impossible = copy.deepcopy(candidate["tool_args"]["ref"])

    impossible.pop("persistent", None)

    impossible["semantic"]["geometry_type"] = "toroidal_face"

    impossible["semantic"]["signature"] = "0" * 20


    refused = call("sw_ref_resolve", {"ref": impossible}, expect_ok=False)

    assert refused["error"]["code"] == "REF_NOT_FOUND"

    assert refused["error"]["remediation"]


def test_identical_faces_produce_an_ambiguous_reference(call, box_part):

    """REF-006, the acceptance case: two equally good matches must both be returned."""

    faces = call(

        "sw_probe_faces",

        {"geometry_type": "planar_face", "area_min_mm2": 1400, "area_max_mm2": 1600},

    )["result"]["candidates"]

    assert len(faces) == 2, "the box has two identical 50x30 faces"


    # Strip the two things that tell them apart: the opaque handle and the location.

    vague = copy.deepcopy(faces[0]["tool_args"]["ref"])

    vague.pop("persistent", None)

    vague["semantic"]["signature"] = ""

    vague["semantic"]["measurements"].pop("point_m", None)

    vague["semantic"]["measurements"].pop("bbox_m", None)


    refused = call("sw_ref_resolve", {"ref": vague}, expect_ok=False)

    assert refused["error"]["code"] == "REF_AMBIGUOUS", (

        "the resolver must refuse rather than silently pick the first face"

    )


    candidates = refused["error"]["context"]["candidates"]

    assert len(candidates) == 2

    for entry in candidates:

        assert entry["label"]

        assert "ref" in entry["tool_args"], "each candidate must be directly reusable"

        assert entry["why"], "and must explain why it matched"

    assert any("Pick one candidate" in step for step in refused["error"]["remediation"])


def test_an_ambiguous_candidate_can_be_used_verbatim(call, box_part):

    """The candidates handed back must actually resolve when passed straight through."""

    faces = call(

        "sw_probe_faces",

        {"geometry_type": "planar_face", "area_min_mm2": 1400, "area_max_mm2": 1600},

    )["result"]["candidates"]


    vague = copy.deepcopy(faces[0]["tool_args"]["ref"])

    vague.pop("persistent", None)

    vague["semantic"]["signature"] = ""

    vague["semantic"]["measurements"].pop("point_m", None)

    vague["semantic"]["measurements"].pop("bbox_m", None)


    refused = call("sw_ref_resolve", {"ref": vague}, expect_ok=False)

    chosen = refused["error"]["context"]["candidates"][0]["tool_args"]["ref"]


    resolved = call("sw_ref_resolve", {"ref": chosen})["result"]

    assert resolved["via"] == "persistent"


def test_a_reference_round_trips_through_json(call, box_part):

    """REF-007: checkpoint and resume needs nothing beyond model_dump."""

    from swmcp.refs.model import EntityRef


    candidate = call("sw_probe_faces", {})["result"]["candidates"][0]

    original = EntityRef.model_validate(candidate["reference"])

    revived = EntityRef.model_validate(json.loads(json.dumps(original.model_dump(mode="json"))))

    assert revived == original


def test_selection_round_trip(call, box_part):

    """REF-001: select from a reference, then read the selection back."""

    candidate = call("sw_probe_faces", {})["result"]["candidates"][0]


    selected = call("sw_selection_set", {"refs": [candidate["tool_args"]["ref"]]})["result"]

    assert selected["selected"] == 1

    assert selected["failed"] == []


    read_back = call("sw_selection_get")["result"]

    assert read_back["count"] == 1

    assert read_back["selections"][0]["kind"] == "face"


    captured = call("sw_ref_capture")["result"]["references"]

    assert len(captured) == 1

    assert captured[0]["reference"]["semantic"]["signature"]


    cleared = call("sw_selection_set", {"refs": [], "clear_first": True})["result"]

    assert cleared["selected"] == 0

    assert call("sw_selection_get")["result"]["count"] == 0


def test_capturing_with_nothing_selected_is_a_clear_error(call, box_part):

    call("sw_selection_set", {"refs": [], "clear_first": True})

    refused = call("sw_ref_capture", expect_ok=False)

    assert refused["error"]["code"] == "NO_SELECTION"

    assert any("probe" in step for step in refused["error"]["remediation"])

