"""Turn a live COM entity into an :class:`EntityRef` (REF-002/003/004).

Capture never fails the caller. If a persistent reference cannot be taken, or a
surface refuses to describe itself, the missing part becomes a warning on the
reference rather than an exception — a partially-addressable entity is still more
useful than none.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

from swmcp.com import swconst
from swmcp.com.marshal import get_com_member, normalize_bytes, normalize_sequence, try_com_member
from swmcp.refs.model import (
    DocumentRef,
    EntityRef,
    PersistentRef,
    RefMeasurements,
    SelectHint,
    SemanticRef,
)
from swmcp.refs.signature import geometry_signature
from swmcp.units import area_from_m2, from_meters

#: swSelectType_e value -> our entity kind.
_SELECT_TYPE_KIND = {
    "swSelEDGES": "edge",
    "swSelFACES": "face",
    "swSelVERTICES": "vertex",
    "swSelDATUMPLANES": "plane",
    "swSelDATUMAXES": "axis",
    "swSelDATUMPOINTS": "point",
    "swSelSKETCHES": "sketch",
    "swSelSKETCHSEGS": "sketch_segment",
    "swSelSOLIDBODIES": "body",
    "swSelSURFACEBODIES": "body",
    "swSelCOMPONENTS": "component",
    "swSelCOORDSYS": "coordinate_system",
}

#: swSurfaceTypes_e member -> a readable geometry type.
_SURFACE_TYPE = {
    "PLANE_TYPE": "planar_face",
    "CYLINDER_TYPE": "cylindrical_face",
    "CONE_TYPE": "conical_face",
    "SPHERE_TYPE": "spherical_face",
    "TORUS_TYPE": "toroidal_face",
    "BSURF_TYPE": "bspline_face",
    "BLEND_TYPE": "blend_face",
    "OFFSET_TYPE": "offset_face",
    "EXTRU_TYPE": "extruded_face",
    "SREV_TYPE": "revolved_face",
}

_SELECT_TYPE_NAME = {
    "face": "FACE",
    "edge": "EDGE",
    "vertex": "VERTEX",
    "plane": "PLANE",
    "axis": "AXIS",
    "point": "DATUMPOINT",
    "body": "SOLIDBODY",
    "component": "COMPONENT",
    "coordinate_system": "COORDSYS",
    "sketch": "SKETCH",
}


def _kind_from_entity(entity: Any) -> str:
    raw = try_com_member(entity, "GetType", default=None)
    if not isinstance(raw, int):
        return "unknown"
    name = swconst.name_of("swSelectType_e", raw)
    return _SELECT_TYPE_KIND.get(name or "", "unknown")


def _surface_geometry(face: Any) -> tuple[str, RefMeasurements, list[str]]:
    """Describe a face: type, a point on it, its direction, radius, area, and box."""
    warnings: list[str] = []
    measurements = RefMeasurements()

    surface = try_com_member(face, "GetSurface", default=None)
    identity = try_com_member(surface, "Identity", default=None) if surface is not None else None
    name = swconst.name_of("swSurfaceTypes_e", identity) if isinstance(identity, int) else None
    geometry_type = _SURFACE_TYPE.get(name or "", "face")

    area = try_com_member(face, "GetArea", default=None)
    if isinstance(area, (int, float)):
        measurements.area_m2 = float(area)

    box = normalize_sequence(try_com_member(face, "GetBox", default=None))
    if len(box) == 6:
        measurements.bbox_m = [float(v) for v in box]
        measurements.point_m = [
            (float(box[0]) + float(box[3])) / 2.0,
            (float(box[1]) + float(box[4])) / 2.0,
            (float(box[2]) + float(box[5])) / 2.0,
        ]

    if surface is not None and geometry_type == "planar_face":
        params = normalize_sequence(try_com_member(surface, "PlaneParams", default=None))
        if len(params) >= 6:
            measurements.direction = [float(v) for v in params[0:3]]
            # The plane's root point is exact; the bbox centre is only approximate.
            measurements.point_m = measurements.point_m or [float(v) for v in params[3:6]]
    elif surface is not None and geometry_type == "cylindrical_face":
        params = normalize_sequence(try_com_member(surface, "CylinderParams", default=None))
        if len(params) >= 7:
            measurements.direction = [float(v) for v in params[3:6]]
            measurements.radius_m = float(params[6])
        else:
            warnings.append("cylinder parameters were unavailable; radius is unknown")
    elif surface is not None and geometry_type == "conical_face":
        params = normalize_sequence(try_com_member(surface, "ConeParams", default=None))
        if len(params) >= 7:
            measurements.direction = [float(v) for v in params[3:6]]
            measurements.radius_m = float(params[6])

    return geometry_type, measurements, warnings


def _edge_geometry(edge: Any) -> tuple[str, RefMeasurements, list[str]]:
    measurements = RefMeasurements()
    warnings: list[str] = []

    params = normalize_sequence(try_com_member(edge, "GetCurveParams2", default=None))
    if len(params) >= 6:
        start = [float(v) for v in params[0:3]]
        end = [float(v) for v in params[3:6]]
        measurements.point_m = [(a + b) / 2.0 for a, b in zip(start, end, strict=True)]
        delta = [b - a for a, b in zip(start, end, strict=True)]
        length = sum(d * d for d in delta) ** 0.5
        if length > 0:
            measurements.direction = [d / length for d in delta]
        measurements.length_m = length
    else:
        warnings.append("edge curve parameters were unavailable")

    curve = try_com_member(edge, "GetCurve", default=None)
    identity = try_com_member(curve, "Identity", default=None) if curve is not None else None
    name = swconst.name_of("swCurveTypes_e", identity) if isinstance(identity, int) else None
    geometry_type = {"LINE_TYPE": "line_edge", "CIRCLE_TYPE": "circular_edge"}.get(
        name or "", "edge"
    )

    if geometry_type == "circular_edge" and curve is not None:
        circle = normalize_sequence(try_com_member(curve, "CircleParams", default=None))
        if len(circle) >= 7:
            measurements.point_m = [float(v) for v in circle[0:3]]
            measurements.direction = [float(v) for v in circle[3:6]]
            measurements.radius_m = float(circle[6])

    box = normalize_sequence(try_com_member(edge, "GetBox", default=None))
    if len(box) == 6:
        measurements.bbox_m = [float(v) for v in box]

    return geometry_type, measurements, warnings


def _vertex_geometry(vertex: Any) -> tuple[str, RefMeasurements, list[str]]:
    measurements = RefMeasurements()
    point = normalize_sequence(try_com_member(vertex, "GetPoint", default=None))
    if len(point) >= 3:
        measurements.point_m = [float(v) for v in point[0:3]]
    return "vertex", measurements, []


def _feature_ancestry(entity: Any) -> tuple[list[str], list[str], str | None]:
    """Walk up from an entity to its owning features, outermost last."""
    names: list[str] = []
    type_names: list[str] = []
    body_name = None

    body = try_com_member(entity, "GetBody", default=None)
    if body is not None:
        body_name = try_com_member(body, "Name", default=None)
        body_name = str(body_name) if body_name else None

    feature = try_com_member(entity, "GetFeature", default=None)
    guard = 0
    while feature is not None and guard < 20:
        guard += 1
        name = try_com_member(feature, "Name", default=None)
        type_name = try_com_member(feature, "GetTypeName2", default=None)
        if name:
            names.insert(0, str(name))
        if type_name:
            type_names.insert(0, str(type_name))
        feature = try_com_member(feature, "GetOwnerFeature", default=None)

    return names, type_names, body_name


def _component_path(entity: Any) -> list[str]:
    component = try_com_member(entity, "GetComponent", default=None)
    if component is None:
        return []
    name = try_com_member(component, "Name2", default=None) or try_com_member(
        component, "Name", default=None
    )
    return str(name).split("/") if name else []


def _persistent(
    doc: Any, entity: Any, revision: str | None
) -> tuple[PersistentRef | None, list[str]]:
    try:
        raw = doc.Extension.GetPersistReference3(entity)
    except Exception as exc:
        return None, [f"persistent reference unavailable: {exc}"]
    blob = normalize_bytes(raw)
    if not blob:
        return None, ["persistent reference unavailable: SOLIDWORKS returned no data"]
    return (
        PersistentRef(
            data_b64=base64.b64encode(blob).decode("ascii"),
            captured_revision=revision,
        ),
        [],
    )


def _label(
    kind: str, geometry_type: str, measurements: RefMeasurements, ancestry: list[str]
) -> str:
    parts = [geometry_type.replace("_", " ")]
    if measurements.radius_m:
        parts.append(f"Ø{from_meters(measurements.radius_m, 'mm') * 2:.2f} mm")
    if measurements.area_m2:
        parts.append(f"area {area_from_m2(measurements.area_m2, 'mm'):.1f} mm²")
    if measurements.length_m:
        parts.append(f"length {from_meters(measurements.length_m, 'mm'):.2f} mm")
    if measurements.point_m:
        coordinates = ", ".join(f"{from_meters(v, 'mm'):.1f}" for v in measurements.point_m)
        parts.append(f"at ({coordinates}) mm")
    described = ", ".join(parts)
    if ancestry:
        described += f" — on {ancestry[-1]}"
    return f"{kind}: {described}" if kind not in described else described


def capture(session: Any, doc: Any, entity: Any, *, revision: str | None = None) -> EntityRef:
    """Build a full :class:`EntityRef` for one live entity."""
    kind = _kind_from_entity(entity)

    if kind == "face":
        geometry_type, measurements, warnings = _surface_geometry(entity)
    elif kind == "edge":
        geometry_type, measurements, warnings = _edge_geometry(entity)
    elif kind == "vertex":
        geometry_type, measurements, warnings = _vertex_geometry(entity)
    else:
        geometry_type, measurements, warnings = kind, RefMeasurements(), []

    ancestry, type_names, body_name = _feature_ancestry(entity)
    persistent, persist_warnings = _persistent(doc, entity, revision)

    semantic = SemanticRef(
        component_path=_component_path(entity),
        feature_ancestry=ancestry,
        feature_type_names=type_names,
        geometry_type=geometry_type,
        body_name=body_name,
        measurements=measurements,
    )
    semantic.signature = geometry_signature(geometry_type, measurements)

    document = DocumentRef(
        path=getattr(session.describe(doc), "path", None),
        title=getattr(session.describe(doc), "title", None),
        configuration=getattr(session.describe(doc), "configuration", None),
    )

    hint = SelectHint(sw_select_type=_SELECT_TYPE_NAME.get(kind))
    if measurements.point_m and measurements.direction:
        offset = 0.002
        hint.ray_origin_m = [
            p + d * offset
            for p, d in zip(measurements.point_m, measurements.direction, strict=True)
        ]
        hint.ray_direction = [-d for d in measurements.direction]

    return EntityRef(
        kind=kind,
        label=_label(kind, geometry_type, measurements, ancestry),
        document=document,
        persistent=persistent,
        semantic=semantic,
        select_hint=hint,
        captured_at=datetime.now(UTC).isoformat(),
        warnings=[*warnings, *persist_warnings],
    )


def faces_of(owner: Any) -> list[Any]:
    """Faces of a feature or a body, tolerating the property/method duality."""
    found = normalize_sequence(get_com_member(owner, "GetFaces", default=None))
    return [face for face in found if face is not None]


def edges_of(owner: Any) -> list[Any]:
    """Edges of a feature or a body."""
    found = normalize_sequence(get_com_member(owner, "GetEdges", default=None))
    return [edge for edge in found if edge is not None]
