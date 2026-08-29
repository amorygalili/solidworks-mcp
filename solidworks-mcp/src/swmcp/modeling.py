"""Shared modelling helpers: bodies, mass properties, and before/after evidence.

Every feature operation needs the same two things — a way to see the bodies without an
``IPartDoc`` cast, and a consistent snapshot to compare before and after. Both live
here so each handler's verification block is built the same way.
"""

from __future__ import annotations

from typing import Any

from swmcp.com import swconst
from swmcp.com.marshal import (
    call_with_outparams,
    get_com_member,
    normalize_sequence,
    out_bstr,
    out_long,
    try_com_member,
)
from swmcp.units import area_from_m2, from_meters

#: A cubic-metre value converted to the cube of a display unit.
_VOLUME_UNIT = "mm"


def configuration_names(doc: Any) -> list[str]:
    """Every configuration in the document, in the order SOLIDWORKS reports them.

    Shared rather than reimplemented per handler: the parameter, constraint, and export
    domains all need it, and two copies of "how do I list configurations" is how the
    three of them would drift apart.
    """
    return [
        str(name)
        for name in normalize_sequence(
            try_com_member(doc, "GetConfigurationNames", default=None)
        )
    ]


def volume_to_display(volume_m3: float | None, unit: str = _VOLUME_UNIT) -> float | None:
    """Convert m³ to the cube of ``unit`` using the one conversion table."""
    if volume_m3 is None:
        return None
    linear = from_meters(1.0, unit)
    return float(volume_m3) * linear * linear * linear


def bodies(doc: Any) -> list[Any]:
    """Every distinct solid body, found by walking the features that own faces.

    ``IPartDoc.GetBodies2`` would be the direct route, but reaching ``IPartDoc`` from a
    late-bound ``IModelDoc2`` needs an interface cast that pywin32 will not do without
    a generated proxy. Walking faces back to their bodies needs no cast and works the
    same in a part or an assembly component.
    """
    found: list[Any] = []
    seen: set[str] = set()
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        for face in normalize_sequence(try_com_member(feature, "GetFaces", default=None)):
            body = try_com_member(face, "GetBody", default=None)
            if body is None:
                continue
            key = str(try_com_member(body, "Name", default=id(body)))
            if key not in seen:
                seen.add(key)
                found.append(body)
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return found


def document_mass_properties(doc: Any) -> dict[str, Any]:
    """Mass properties that respect the document's material.

    ``IModelDocExtension::GetMassProperties(Accuracy, out Status)`` returns thirteen
    doubles — ``[cx, cy, cz, volume, area, mass, Ixx, Iyy, Izz, Ixy, Izx, Iyz,
    accuracy]`` — and, unlike :func:`body_mass_properties`, it uses the density of the
    material actually assigned to the part. Where no material is set, SOLIDWORKS uses a
    density of 1.0 and the mass equals the volume; that is SOLIDWORKS' own convention
    and is reported as it stands rather than hidden.
    """
    status = out_long(0)
    try:
        raw, _ = call_with_outparams(
            doc.Extension.GetMassProperties, 2, status, outparams=[status]
        )
    except Exception:  # pragma: no cover - COM refusal is reported as "unavailable"
        return {}
    values = [float(v) for v in normalize_sequence(raw)]
    if len(values) < 6:
        return {}
    volume = values[3]
    mass = values[5]
    return {
        "center_of_mass_m": values[0:3],
        "volume_m3": volume,
        "surface_area_m2": values[4],
        "mass_kg": mass,
        "density_kg_m3": (mass / volume) if volume else None,
    }


def document_material(doc: Any, configuration: str = "") -> tuple[str | None, str | None]:
    """The part's material name and library, or ``(None, None)`` when none is set.

    ``GetMaterialPropertyName2(ConfigName, out Database)`` is the only reliable reader:
    ``IPartDoc::MaterialIdName`` comes back non-empty even for a part with no material,
    so a review that tested it reported "material assigned" for every document. One
    function so sw_material_get and the review checks cannot drift apart.
    """
    database = out_bstr("")
    try:
        name, outs = call_with_outparams(
            doc.GetMaterialPropertyName2, configuration, database, outparams=[database]
        )
    except Exception:  # pragma: no cover - a COM refusal reads as "no material"
        return None, None
    text = str(name or "")
    found = outs[0] if outs else None
    return (text or None), (str(found) if found else None)


def document_density(doc: Any) -> float | None:
    """The density SOLIDWORKS is actually using, derived from mass over volume."""
    return document_mass_properties(doc).get("density_kg_m3")


def _body_type_label(name: str) -> str:
    """``swSheetBody`` → ``sheetbody``, the form this codebase has always reported."""
    return name.replace("sw", "", 1).lower()


_SOLID_BODY_NAME = _body_type_label("swSolidBody")
_SHEET_BODY_NAME = _body_type_label("swSheetBody")


def body_type_name(body: Any) -> str:
    """The body's ``swBodyType_e`` as a bare word: ``solidbody``, ``sheetbody``, …

    One place decides this, because the meaning of a body's mass-property array depends
    on it — see :func:`body_mass_properties`.
    """
    code = try_com_member(body, "GetType", default=None)
    name = swconst.name_of("swBodyType_e", code) if isinstance(code, int) else None
    return _body_type_label(name) if name else "unknown"


def body_mass_properties(body: Any, density: float = 1.0) -> dict[str, Any]:
    """``IBody2.GetMassProperties`` returns [cx, cy, cz, volume, area, mass, ...].

    The ``density`` argument is not a hint: index 5 is documented as
    ``Mass(Volume*density)``, computed from the number *passed in*, so this call knows
    nothing about the material on the part. Passing ``0.0`` — as this did until the
    material tools were built — makes SOLIDWORKS fall back to 1.0 and yields a "mass"
    numerically equal to the volume, identical for a steel part and an aluminium one.
    Callers that want the real figure pass :func:`document_density`, or read
    :func:`document_mass_properties` directly.

    That layout is the *solid* one, and it is the only one documented. A **sheet** body
    has no volume, and SOLIDWORKS quietly reuses the same slots for its two-dimensional
    analogues: slot 3 carries the area and slot 4 the perimeter. Reading the solid layout
    off a surface therefore reports its area as a volume — a 40 x 30 mm planar surface
    came back as 1 200 000 mm³ of material that does not exist, and its 140 mm perimeter
    as 140 000 mm² of area. Measured against a 60 x 20 rectangle (the same area as the
    40 x 30, a different perimeter) and a circle of radius 20, both exact.

    Only the solid and sheet layouts are verified, so any other body type reports no
    figures at all rather than a number whose meaning is a guess.
    """
    kind = body_type_name(body)
    raw = normalize_sequence(
        try_com_member(body, "GetMassProperties", float(density), default=None)
    )
    if len(raw) < 6:
        return {
            "body_type": kind,
            "measurement_note": "GetMassProperties returned fewer than six values.",
        }

    values = [float(v) for v in raw]
    common = {"center_of_mass_m": values[0:3], "body_type": kind}

    if kind == _SOLID_BODY_NAME:
        return {
            **common,
            "volume_m3": values[3],
            "surface_area_m2": values[4],
            "mass_kg": values[5],
            "density_kg_m3": float(density),
        }
    if kind == _SHEET_BODY_NAME:
        return {
            **common,
            "volume_m3": None,
            "surface_area_m2": values[3],
            "perimeter_m": values[4],
            "mass_kg": None,
            "density_kg_m3": None,
            "measurement_note": (
                "A sheet body encloses no volume. SOLIDWORKS reuses the volume slot for "
                "the area and the area slot for the perimeter, so no volume or mass is "
                "reported for it."
            ),
        }
    return {
        **common,
        "volume_m3": None,
        "surface_area_m2": None,
        "mass_kg": None,
        "density_kg_m3": None,
        "measurement_note": (
            f"Only the solid and sheet mass-property layouts are verified; a {kind} body "
            "reports its raw slots rather than figures with guessed meanings."
        ),
        "raw_mass_properties": values,
    }


def body_summary(body: Any, density: float = 1.0) -> dict[str, Any]:
    """Everything FEAT-016 asks for about one body.

    ``density`` comes from the document so the reported mass is the model's, not
    volume-times-one. See :func:`body_mass_properties`.
    """
    properties = body_mass_properties(body, density)
    box = normalize_sequence(try_com_member(body, "GetBodyBox", default=None))
    faces = normalize_sequence(get_com_member(body, "GetFaces", default=None))
    edges = normalize_sequence(get_com_member(body, "GetEdges", default=None))

    return {
        "name": str(try_com_member(body, "Name", default="") or ""),
        # The type comes from the mass-property reader rather than a second GetType
        # call: that reader chooses its array layout from the type, so the two must
        # never be able to disagree about what this body is.
        "type": properties.get("body_type", "unknown"),
        "visible": bool(try_com_member(body, "Visible", default=True)),
        "material": str(try_com_member(body, "GetMaterialPropertyName2", "", default="") or ""),
        "face_count": len(faces),
        "edge_count": len(edges),
        "bounding_box_m": [float(v) for v in box] if len(box) == 6 else None,
        "owning_features": _owning_features(faces),
        **properties,
    }


def _owning_features(faces: list[Any]) -> list[str]:
    names: list[str] = []
    for face in faces:
        feature = try_com_member(face, "GetFeature", default=None)
        name = str(try_com_member(feature, "Name", default="") or "") if feature else ""
        if name and name not in names:
            names.append(name)
    return names


def model_snapshot(doc: Any) -> dict[str, Any]:
    """A comparable before/after picture of the model (REV-003 in spirit).

    The volume counts solid bodies only. A sheet body has none, and folding its area in
    here would make a surface operation look like it added material — see
    :func:`body_mass_properties`. The two counts are reported separately so a comparison
    can still see a surface appear or disappear.
    """
    found = bodies(doc)
    total_volume = 0.0
    total_area = 0.0
    faces = 0
    edges = 0
    solids = 0
    sheets = 0
    for body in found:
        properties = body_mass_properties(body)
        kind = properties.get("body_type")
        solids += kind == _SOLID_BODY_NAME
        sheets += kind == _SHEET_BODY_NAME
        total_volume += properties.get("volume_m3") or 0.0
        total_area += properties.get("surface_area_m2") or 0.0
        faces += len(normalize_sequence(get_com_member(body, "GetFaces", default=None)))
        edges += len(normalize_sequence(get_com_member(body, "GetEdges", default=None)))

    return {
        "body_count": len(found),
        "solid_body_count": solids,
        "sheet_body_count": sheets,
        "volume_m3": total_volume,
        "volume_mm3": volume_to_display(total_volume),
        "surface_area_m2": total_area,
        "surface_area_mm2": area_from_m2_display(total_area),
        "face_count": faces,
        "edge_count": edges,
        "feature_count": feature_count(doc),
    }


def area_from_m2_display(area_m2: float | None, unit: str = _VOLUME_UNIT) -> float | None:
    """Convert m² into the square of a display unit through the one conversion table."""
    if area_m2 is None:
        return None
    return area_from_m2(float(area_m2), unit)


def feature_count(doc: Any) -> int:
    count = 0
    feature = try_com_member(doc, "FirstFeature", default=None)
    while feature is not None and count < 5000:
        count += 1
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return count


def find_feature(doc: Any, name: str) -> Any | None:
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        if str(try_com_member(feature, "Name", default="")) == name:
            return feature
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return None


def describe_feature(feature: Any) -> dict[str, Any]:
    error_code = try_com_member(feature, "GetErrorCode2", default=0)
    return {
        "name": str(try_com_member(feature, "Name", default="") or ""),
        "type": str(try_com_member(feature, "GetTypeName2", default="") or ""),
        "suppressed": bool(try_com_member(feature, "IsSuppressed", default=False)),
        "error_code": error_code,
        "error_name": swconst.name_of("swFeatureError_e", error_code) if error_code else None,
        "created_at": str(try_com_member(feature, "DateCreated", default="") or ""),
    }


def latest_unused_sketch(doc: Any) -> str | None:
    """The most recent sketch that no feature consumes — the usual extrude profile."""
    candidates: list[str] = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        if str(try_com_member(feature, "GetTypeName2", default="")) == "ProfileFeature":
            parents = normalize_sequence(try_com_member(feature, "GetChildren", default=None))
            if not parents:
                candidates.append(str(try_com_member(feature, "Name", default="")))
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return candidates[-1] if candidates else None
