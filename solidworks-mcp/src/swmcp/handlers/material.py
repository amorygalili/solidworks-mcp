"""Part materials (FEAT-020).

``IPartDoc::SetMaterialPropertyName2`` is declared ``void``. It reports nothing at all
— not success, not failure — so the only way to know a material was applied is to read
it back, which is what this does. Assigning a material is also the one operation whose
effect is invisible in the geometry: nothing moves, and the only observable change is
the density, so the density before and after is the evidence.
"""

from __future__ import annotations

from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, ReadSafety
from swmcp.com.marshal import call_with_outparams, out_bstr, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error
from swmcp.modeling import bodies, document_mass_properties
from swmcp.schemas.material import (
    MaterialGetArgs,
    MaterialGetResult,
    MaterialSetArgs,
    MaterialSetResult,
)


def _active_configuration(doc: Any) -> str:
    manager = try_com_member(doc, "ConfigurationManager", default=None)
    active = try_com_member(manager, "ActiveConfiguration", default=None)
    return str(try_com_member(active, "Name", default="") or "Default")


def _read_material(doc: Any, configuration: str) -> tuple[str | None, str | None]:
    """``GetMaterialPropertyName2(ConfigName, out Database)`` -> (name, database).

    The database is an ``[out]`` parameter, which pywin32 binds either by mutating the
    VARIANT or by appending it to the return value; ``call_with_outparams`` covers both
    so this reads the same either way.
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


def _body_materials(doc: Any) -> list[dict[str, Any]]:
    return [
        {
            "name": str(try_com_member(body, "Name", default="") or ""),
            "material": str(try_com_member(body, "GetMaterialUserName2", default="") or ""),
        }
        for body in bodies(doc)
    ]


@op(
    name="sw_material_set",
    tier="core",
    domains=("material", "feature"),
    tags=("material", "density", "mass"),
    summary=(
        "Assign a material to the part and prove it took by reading the material back "
        "and reporting the density and mass it now has."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("FEAT-020",),
    precondition="part",
    idempotent=True,
    timeout_s=180.0,
)
def material_set(ctx: OpContext, args: MaterialSetArgs) -> MaterialSetResult:
    doc = ctx.require_doc()
    configuration = args.configuration or _active_configuration(doc)

    before_name, _ = _read_material(doc, configuration)
    before_mass = document_mass_properties(doc)

    try_com_member(
        doc, "SetMaterialPropertyName2", configuration, args.database, args.name, default=None
    )

    after_name, after_database = _read_material(doc, configuration)
    after_mass = document_mass_properties(doc)
    wanted = args.name or None

    if after_name != wanted:
        raise SwMcpError(
            make_error(
                "MATERIAL_NOT_APPLIED",
                "solidworks",
                f"SOLIDWORKS did not apply {args.name!r}; the part reports "
                f"{after_name!r} instead.",
                context={
                    "requested": args.name,
                    "database": args.database,
                    "configuration": configuration,
                    "reported": after_name,
                },
                remediation=[
                    "The name must match the library exactly, including case and "
                    "spacing, e.g. '6061 Alloy' rather than '6061'.",
                    "Check the database name; the stock library is 'SOLIDWORKS Materials'.",
                ],
            )
        )

    density = after_mass.get("density_kg_m3")
    return MaterialSetResult(
        material=after_name or "",
        database=after_database or args.database,
        configuration=configuration,
        density_kg_m3=density,
        mass_kg=after_mass.get("mass_kg"),
        volume_m3=after_mass.get("volume_m3"),
        verification=Verification(
            read_back=True,
            before={
                "material": before_name,
                "density_kg_m3": before_mass.get("density_kg_m3"),
                "mass_kg": before_mass.get("mass_kg"),
            },
            after={
                "material": after_name,
                "density_kg_m3": density,
                "mass_kg": after_mass.get("mass_kg"),
            },
            checks=[
                Check(
                    name="material_reads_back",
                    passed=after_name == wanted,
                    detail=f"{before_name!r} -> {after_name!r}",
                ),
                Check(
                    name="density_is_reported",
                    # Deliberately not asserting a particular number. The library owns
                    # each material's density, and clearing a material does not reset it
                    # to 1.0 - SOLIDWORKS keeps its own default, measured at 1000 kg/m3
                    # here. The name reading back is the proof the material applied; the
                    # density is reported as evidence rather than asserted against a
                    # figure this code would only be guessing at.
                    passed=density is not None and density > 0.0,
                    detail=(
                        f"{before_mass.get('density_kg_m3')} -> {density} kg/m3"
                        if density is not None
                        else "SOLIDWORKS returned no document mass properties"
                    ),
                ),
            ],
        ),
    )


@op(
    name="sw_material_get",
    tier="core",
    domains=("material", "feature"),
    tags=("material", "density", "mass", "inspect"),
    summary=(
        "Read the part's material, the density SOLIDWORKS is actually using, and the "
        "mass that follows from it, plus any per-body material overrides."
    ),
    safety=ReadSafety(),
    partially_satisfies=("FEAT-020",),
    precondition="part",
    idempotent=True,
    timeout_s=120.0,
)
def material_get(ctx: OpContext, args: MaterialGetArgs) -> MaterialGetResult:
    doc = ctx.require_doc()
    configuration = args.configuration or _active_configuration(doc)
    name, database = _read_material(doc, configuration)
    mass = document_mass_properties(doc)

    density = mass.get("density_kg_m3")
    warnings = []
    if name is None:
        warnings.append(
            f"No material is assigned, so the mass follows SOLIDWORKS' default density "
            f"of {density:.6g} kg/m3 rather than a material."
            if density is not None
            else "No material is assigned and SOLIDWORKS returned no density."
        )

    return MaterialGetResult(
        material=name,
        database=database,
        configuration=configuration,
        density_kg_m3=density,
        mass_kg=mass.get("mass_kg"),
        volume_m3=mass.get("volume_m3"),
        bodies=_body_materials(doc),
        warnings=warnings,
    )
