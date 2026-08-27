"""Shared sketch helpers: segment identity, creation, and solver state.

Segment identity is the piece everything else depends on. ``ISketchSegment.GetID``
returns a two-integer pair that is stable for the life of the sketch, so it makes a
good handle to hand back to a caller: relations, dimensions, and deletes all address
segments by it rather than by relying on selection order.
"""

from __future__ import annotations

from typing import Any

from swmcp.com import swconst
from swmcp.com.marshal import normalize_sequence, null_dispatch, try_com_member
from swmcp.errors import SwMcpError, make_error

#: swConstrainedStatus_e -> a readable state.
_STATUS_NAMES = {
    "swUnknownConstraint": "unknown",
    "swUnderConstrained": "under_defined",
    "swFullyConstrained": "fully_defined",
    "swOverConstrained": "over_defined",
    "swNoSolution": "no_solution",
    "swInvalidSolution": "invalid_solution",
    "swAutosolveOff": "autosolve_off",
}

#: Our relation names -> the SOLIDWORKS ``SketchAddConstraints`` tokens.
RELATION_TOKENS = {
    "horizontal": "sgHORIZONTAL",
    "vertical": "sgVERTICAL",
    "coincident": "sgCOINCIDENT",
    "collinear": "sgCOLINEAR",
    "parallel": "sgPARALLEL",
    "perpendicular": "sgPERPENDICULAR",
    "tangent": "sgTANGENT",
    "equal": "sgSAME",
    "concentric": "sgCONCENTRIC",
    "midpoint": "sgATMIDDLE",
    "symmetric": "sgSYMMETRIC",
    "fix": "sgFIXED",
    "merge": "sgMERGEPOINTS",
}

#: How many entities each relation needs selected.
RELATION_ARITY = {
    "horizontal": (1, 2),
    "vertical": (1, 2),
    "coincident": (2, 2),
    "collinear": (2, 2),
    "parallel": (2, 2),
    "perpendicular": (2, 2),
    "tangent": (2, 2),
    "equal": (2, 2),
    "concentric": (2, 2),
    "midpoint": (2, 2),
    "symmetric": (3, 3),
    "fix": (1, 1),
    "merge": (2, 2),
}


def segment_id(segment: Any) -> str:
    """``ISketchSegment.GetID`` is a pair of ints; render it as a stable string."""
    raw = normalize_sequence(try_com_member(segment, "GetID", default=None))
    if len(raw) >= 2:
        return f"{int(raw[0])}:{int(raw[1])}"
    return str(raw[0]) if raw else "unknown"


def active_sketch(doc: Any) -> Any | None:
    manager = try_com_member(doc, "SketchManager", default=None)
    if manager is None:
        return None
    return try_com_member(manager, "ActiveSketch", default=None)


def require_active_sketch(doc: Any) -> Any:
    sketch = active_sketch(doc)
    if sketch is None:
        raise SwMcpError(
            make_error(
                "NO_ACTIVE_SKETCH",
                "validation",
                "No sketch is open for editing.",
                remediation=[
                    "Start a sketch first, or name an existing one to edit.",
                ],
            )
        )
    return sketch


def find_sketch(doc: Any, name: str) -> Any | None:
    """Locate a sketch feature by name and return its ``ISketch``."""
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        if str(try_com_member(feature, "Name", default="")) == name:
            return try_com_member(feature, "GetSpecificFeature2", default=None)
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return None


def sketch_segments(sketch: Any) -> list[Any]:
    found = normalize_sequence(try_com_member(sketch, "GetSketchSegments", default=None))
    return [segment for segment in found if segment is not None]


def segments_by_id(sketch: Any) -> dict[str, Any]:
    return {segment_id(segment): segment for segment in sketch_segments(sketch)}


def describe_segment(segment: Any) -> dict[str, Any]:
    raw_type = try_com_member(segment, "GetType", default=None)
    type_name = (
        swconst.name_of("swSketchSegments_e", raw_type) if isinstance(raw_type, int) else None
    )
    return {
        "sketch_local_id": segment_id(segment),
        "type": (type_name or "unknown").replace("swSketch", "").lower(),
        "construction": bool(try_com_member(segment, "ConstructionGeometry", default=False)),
        "length_m": try_com_member(segment, "GetLength", default=None),
    }


def _relations(sketch: Any, filter_name: str) -> list[dict[str, Any]]:
    manager = try_com_member(sketch, "RelationManager", default=None)
    if manager is None:
        return []
    code = swconst.value("swSketchRelationFilterType_e", filter_name)
    found = normalize_sequence(try_com_member(manager, "GetRelations", code, default=None))
    described = []
    for relation in found:
        if relation is None:
            continue
        described.append(
            {
                "name": str(try_com_member(relation, "GetName", default="") or ""),
                "entity_count": try_com_member(relation, "GetEntitiesCount", default=None),
            }
        )
    return described


def sketch_state(sketch: Any) -> dict[str, Any]:
    """CON-005 evidence: the solver's verdict plus what is wrong with it."""
    raw = try_com_member(sketch, "GetConstrainedStatus", default=None)
    name = swconst.name_of("swConstrainedStatus_e", raw) if isinstance(raw, int) else None
    status = _STATUS_NAMES.get(name or "", "unknown")

    return {
        "status": status,
        "status_code": int(raw) if isinstance(raw, int) else -1,
        "fully_defined": status == "fully_defined",
        "over_defined": status == "over_defined",
        "relation_count": len(_relations(sketch, "swAll")),
        "dangling_relations": _relations(sketch, "swDangling"),
        "over_defining_relations": _relations(sketch, "swOverDefining"),
    }


def under_defined_count(sketch: Any) -> int:
    """How many segments are not yet fully defined."""
    count = 0
    for segment in sketch_segments(sketch):
        raw = try_com_member(segment, "GetConstrainedStatus", default=None)
        name = swconst.name_of("swConstrainedStatus_e", raw) if isinstance(raw, int) else None
        if _STATUS_NAMES.get(name or "") != "fully_defined":
            count += 1
    return count


def select_segments(doc: Any, segments: list[Any], *, mark: int = 0) -> int:
    """Select a list of segments, returning how many selections actually took.

    ``Select2`` carries a selection mark, which several feature APIs use to tell one
    input from another; ``Select4`` does not, so it is only the fallback.
    """
    try_com_member(doc, "ClearSelection2", True, default=None)
    selected = 0
    for segment in segments:
        if try_com_member(segment, "Select2", True, mark, default=False):
            selected += 1
            continue
        if try_com_member(segment, "Select4", True, null_dispatch(), default=False):
            selected += 1
    return selected
