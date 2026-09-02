"""Where a batch of sketch entities comes from, and how much is said back about it.

Two costs, both measured on a real session rather than guessed at. A 240-segment
gear profile arrived as ~33 KB of argument and came back as ~64 KB of response
restating what had just been sent — and because the caller had to print the profile
into the request in the first place, it paid for the geometry twice.

Neither change may cost addressability: relations, dimensions and deletes all address
segments by the handle in ``created``, so compacting an entry must keep it.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from swmcp.handlers.sketch import load_entities
from swmcp.schemas.sketch import (
    CREATED_DETAIL_LIMIT,
    SketchAddGeometryArgs,
    SketchCreateArgs,
    compact_created,
)

LINE = {"type": "line", "start": [0, 0], "end": [10, 0]}


def entry(index: int, *, deviation: float | None = None) -> dict:
    made = {
        "index": index,
        "requested_type": "line",
        "sketch_local_id": f"line:0:{index}",
        "type": "line",
        "construction": False,
        "length_m": 0.01,
    }
    if deviation is not None:
        made["deviation_mm"] = deviation
    return made


# --- detail --------------------------------------------------------------------


def test_a_small_batch_keeps_full_detail():
    created = [entry(i) for i in range(5)]
    shown, compacted = compact_created(created, "auto")
    assert shown == created
    assert compacted is False


def test_a_large_batch_compacts_under_auto():
    created = [entry(i) for i in range(CREATED_DETAIL_LIMIT + 1)]
    shown, compacted = compact_created(created, "auto")
    assert compacted is True
    assert len(shown) == len(created), "entries are trimmed, never dropped"
    assert set(shown[0]) == {"index", "requested_type", "sketch_local_id", "type"}


def test_compacting_keeps_every_handle():
    """The handle is what relations, dimensions and deletes address."""
    created = [entry(i) for i in range(CREATED_DETAIL_LIMIT + 20)]
    shown, _ = compact_created(created, "compact")
    assert [s["sketch_local_id"] for s in shown] == [c["sketch_local_id"] for c in created]


def test_full_is_honoured_however_large():
    created = [entry(i) for i in range(CREATED_DETAIL_LIMIT + 50)]
    shown, compacted = compact_created(created, "full")
    assert shown == created
    assert compacted is False


def test_entities_that_moved_keep_their_detail():
    """A deviation is the one thing in an entry a caller has to see."""
    created = [entry(i) for i in range(CREATED_DETAIL_LIMIT + 1)]
    created[7] = entry(7, deviation=0.9)
    shown, _ = compact_created(created, "compact")
    assert shown[7]["deviation_mm"] == 0.9
    assert "length_m" in shown[7]
    assert "length_m" not in shown[8]


# --- where the entities come from ----------------------------------------------


def test_inline_entities_are_returned_as_given():
    args = SketchAddGeometryArgs(entities=[LINE])
    assert len(load_entities(args)) == 1


def test_neither_source_is_refused():
    with pytest.raises(ValidationError):
        SketchAddGeometryArgs()


def test_both_sources_are_refused():
    """Two sources of truth for the same batch is exactly the bug to avoid."""
    with pytest.raises(ValidationError):
        SketchAddGeometryArgs(entities=[LINE], entities_file="p.json")


def test_sketch_create_takes_the_same_pair(tmp_path):
    with pytest.raises(ValidationError):
        SketchCreateArgs(on={"standard_plane": "front"})
    ok = SketchCreateArgs(on={"standard_plane": "front"}, entities_file=str(tmp_path / "p.json"))
    assert ok.entities == []


def test_a_bare_array_file_loads(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps([LINE, LINE]), encoding="utf-8")
    loaded = load_entities(SketchAddGeometryArgs(entities_file=str(path)))
    assert len(loaded) == 2
    assert loaded[0].type == "line"


def test_an_object_with_an_entities_key_loads(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"entities": [LINE], "note": "ignored"}), encoding="utf-8")
    assert len(load_entities(SketchAddGeometryArgs(entities_file=str(path)))) == 1


def test_a_missing_file_names_itself(tmp_path):
    from swmcp.errors import SwMcpError

    args = SketchAddGeometryArgs(entities_file=str(tmp_path / "nope.json"))
    with pytest.raises(SwMcpError) as caught:
        load_entities(args)
    assert caught.value.envelope.code == "ENTITIES_FILE_NOT_FOUND"


def test_malformed_json_is_a_validation_error_not_a_crash(tmp_path):
    from swmcp.errors import SwMcpError

    path = tmp_path / "profile.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SwMcpError) as caught:
        load_entities(SketchAddGeometryArgs(entities_file=str(path)))
    assert caught.value.envelope.code == "ENTITIES_FILE_UNREADABLE"


def test_an_empty_file_is_refused(tmp_path):
    from swmcp.errors import SwMcpError

    path = tmp_path / "profile.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(SwMcpError) as caught:
        load_entities(SketchAddGeometryArgs(entities_file=str(path)))
    assert caught.value.envelope.code == "ENTITIES_FILE_EMPTY"


def test_the_file_route_enforces_the_same_batch_limit(tmp_path):
    from swmcp.errors import SwMcpError

    path = tmp_path / "profile.json"
    path.write_text(json.dumps([LINE] * 501), encoding="utf-8")
    with pytest.raises(SwMcpError) as caught:
        load_entities(SketchAddGeometryArgs(entities_file=str(path)))
    assert caught.value.envelope.code == "ENTITIES_FILE_TOO_LARGE"


def test_the_file_route_validates_the_same_shapes(tmp_path):
    """A file must not smuggle in geometry the inline route would have refused."""
    from swmcp.errors import SwMcpError

    path = tmp_path / "profile.json"
    path.write_text(json.dumps([{"type": "line", "start": [0, 0]}]), encoding="utf-8")
    with pytest.raises(SwMcpError) as caught:
        load_entities(SketchAddGeometryArgs(entities_file=str(path)))
    assert caught.value.envelope.code == "ENTITIES_FILE_INVALID"
    assert caught.value.envelope.context["errors"], "the reason must survive to the wire"
