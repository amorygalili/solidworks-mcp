"""Assembly components (ASM-001, ASM-002, ASM-003).

Placement here is by position only, and that is a limitation with a cause worth
recording. ``AddComponent5`` takes an X/Y/Z and no orientation, and the documented way
to set a full transform — build a ``MathTransform`` with ``IMathUtility::CreateTransform``
and hand it to ``IComponent2::SetTransformAndSolve2`` — cannot be reached on this build:
``CreateTransform`` answers "Member not found" through IDispatch for every argument form
tried, raw or cast, and ``ICreateTransform`` is bound as a write-only property.
``IAssemblyDoc::TranslateComponent`` is not an alternative either; it takes no arguments
and starts the interactive move tool. So rotation is left to mates rather than faked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import normalize_sequence, null_dispatch, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error
from swmcp.schemas.assembly import (
    AsmComponentSetArgs,
    AsmComponentSetResult,
    AsmInsertArgs,
    AsmInsertResult,
    AsmTreeArgs,
    AsmTreeResult,
)
from swmcp.units import from_meters

_SUPPRESSION_STATES = {
    "suppressed": "swComponentSuppressed",
    "lightweight": "swComponentLightweight",
    "resolved": "swComponentResolved",
    "fully_resolved": "swComponentFullyResolved",
}

_STATE_NAMES = {
    swconst.value("swComponentSuppressionState_e", member): name
    for name, member in _SUPPRESSION_STATES.items()
}


def _components(doc: Any, *, top_level_only: bool = False) -> list[Any]:
    return [
        component
        for component in normalize_sequence(
            try_com_member(doc, "GetComponents", top_level_only, default=None)
        )
        if component is not None
    ]


def _find_component(doc: Any, name: str) -> Any | None:
    for component in _components(doc):
        if str(try_com_member(component, "Name2", default="") or "") == name:
            return component
    return None


def _state_name(component: Any) -> str:
    raw = try_com_member(component, "GetSuppression2", default=None)
    return _STATE_NAMES.get(raw, f"unknown({raw})")


def _is_visible(component: Any) -> bool:
    """``IComponent2::Visible`` is ``swComponentVisibilityState_e``, not a bool.

    Hidden is 0 and visible is 1 here, so truthiness happens to work — but it is
    compared explicitly anyway, because ``IFeature::Visible`` uses a different enum
    where 1 means *hidden* and ``bool()`` silently reports everything as visible.
    """
    return int(try_com_member(component, "Visible", default=1) or 0) == 1


def _describe(component: Any, depth: int) -> dict[str, Any]:
    path = str(try_com_member(component, "GetPathName", default="") or "")
    return {
        "name": str(try_com_member(component, "Name2", default="") or ""),
        "path": path,
        "depth": depth,
        "configuration": str(
            try_com_member(component, "ReferencedConfiguration", default="") or ""
        ),
        "suppression": _state_name(component),
        "suppressed": bool(try_com_member(component, "IsSuppressed", default=False)),
        "lightweight": _state_name(component) == "lightweight",
        "visible": _is_visible(component),
        "fixed": bool(try_com_member(component, "IsFixed", default=False)),
        "virtual": bool(try_com_member(component, "IsVirtual", default=False)),
        "envelope": bool(try_com_member(component, "IsEnvelope", default=False)),
        # A virtual component lives inside the assembly and has no file of its own, so
        # its missing path is not a broken reference.
        "reference_ok": bool(
            try_com_member(component, "IsVirtual", default=False) or (path and Path(path).exists())
        ),
    }


@op(
    name="sw_asm_insert",
    tier="core",
    domains=("assembly",),
    tags=("assembly", "component", "insert"),
    summary=(
        "Insert a part or subassembly into the open assembly at a position, with an "
        "optional configuration and fixed state, verified by finding it in the tree."
    ),
    safety=ModelMutation(destructive=False),
    partially_satisfies=("ASM-001",),
    precondition="assembly",
    idempotent=False,
    timeout_s=300.0,
)
def asm_insert(ctx: OpContext, args: AsmInsertArgs) -> AsmInsertResult:
    doc = ctx.require_doc()
    source = Path(args.component_path)
    if not source.is_file():
        raise SwMcpError(
            make_error(
                "COMPONENT_FILE_MISSING",
                "validation",
                f"There is no file at {args.component_path!r}.",
                remediation=["Save the part or subassembly before inserting it."],
            )
        )

    before = _components(doc)
    before_names = {str(try_com_member(c, "Name2", default="") or "") for c in before}

    use_configuration = args.configuration is not None
    component = try_com_member(
        doc,
        "AddComponent5",
        str(source),
        swconst.value(
            "swAddComponentConfigOptions_e", "swAddComponentConfigOptions_CurrentSelectedConfig"
        ),
        "",
        use_configuration,
        args.configuration or "",
        float(args.at[0]),
        float(args.at[1]),
        float(args.at[2]),
        default=None,
    )

    after = _components(doc)
    fresh = [
        c
        for c in after
        if str(try_com_member(c, "Name2", default="") or "") not in before_names
    ]
    if component is None or not fresh:
        raise SwMcpError(
            make_error(
                "COMPONENT_NOT_INSERTED",
                "solidworks",
                f"SOLIDWORKS did not add {source.name!r} to the assembly.",
                context={"component_path": str(source), "components": len(after)},
                remediation=[
                    "The file must be a part or assembly SOLIDWORKS can open.",
                    "An assembly cannot contain itself, directly or through a subassembly.",
                ],
            )
        )

    inserted = fresh[-1]
    name = str(try_com_member(inserted, "Name2", default="") or "")

    if args.fixed and not bool(try_com_member(inserted, "IsFixed", default=False)):
        try_com_member(doc, "ClearSelection2", True, default=None)
        try_com_member(inserted, "Select4", True, null_dispatch(), False, default=False)
        try_com_member(doc, "FixComponent", default=None)
        try_com_member(doc, "ClearSelection2", True, default=None)

    fixed = bool(try_com_member(inserted, "IsFixed", default=False))
    return AsmInsertResult(
        component_name=name,
        component_path=str(source),
        configuration=str(try_com_member(inserted, "ReferencedConfiguration", default="") or ""),
        fixed=fixed,
        position_mm=[round(from_meters(float(v)), 9) for v in args.at],
        components_before=len(before),
        components_after=len(after),
        verification=Verification(
            read_back=True,
            before={"component_count": len(before)},
            after={"component_count": len(after), "component": name},
            checks=[
                Check(
                    name="component_in_tree",
                    passed=_find_component(doc, name) is not None,
                    detail=f"{name} is listed in the assembly",
                ),
                Check(
                    name="fixed_state_applied",
                    passed=(fixed if args.fixed else True),
                    detail=f"fixed={fixed}",
                ),
            ],
        ),
        warnings=(
            [
                "SOLIDWORKS fixes the first component of an assembly automatically, so "
                "this one is fixed even though fixed=false was requested."
            ]
            if fixed and not args.fixed
            else []
        ),
    )


@op(
    name="sw_asm_tree",
    tier="core",
    domains=("assembly",),
    tags=("assembly", "tree", "components", "inspect"),
    summary=(
        "List the assembly's components with path, configuration, quantity, suppression, "
        "lightweight, hidden, fixed, envelope, virtual, and broken-reference state."
    ),
    safety=ReadSafety(),
    satisfies=("ASM-002",),
    precondition="assembly",
    idempotent=True,
    timeout_s=300.0,
)
def asm_tree(ctx: OpContext, args: AsmTreeArgs) -> AsmTreeResult:
    doc = ctx.require_doc()
    described: list[dict[str, Any]] = []
    quantities: dict[str, int] = {}
    broken: list[str] = []

    def walk(components: list[Any], depth: int) -> None:
        if depth > args.max_depth:
            return
        for component in components:
            entry = _describe(component, depth)
            described.append(entry)
            if entry["path"]:
                quantities[entry["path"]] = quantities.get(entry["path"], 0) + 1
            if not entry["reference_ok"] and entry["path"] not in broken:
                broken.append(entry["path"])
            if not args.top_level_only:
                children = [
                    child
                    for child in normalize_sequence(
                        try_com_member(component, "GetChildren", default=None)
                    )
                    if child is not None
                ]
                walk(children, depth + 1)

    walk(_components(doc, top_level_only=True), 0)

    return AsmTreeResult(
        component_count=len(described),
        components=described,
        quantities=quantities,
        broken_references=broken,
        warnings=(
            [f"{len(broken)} referenced file(s) are not where the assembly expects them."]
            if broken
            else []
        ),
    )


@op(
    name="sw_asm_component_set",
    tier="core",
    domains=("assembly",),
    tags=("assembly", "component", "suppress", "fix", "visibility", "configuration"),
    summary=(
        "Change one component's suppression, fixed state, visibility, or referenced "
        "configuration, reading each back rather than trusting the call."
    ),
    safety=ModelMutation(destructive=False),
    satisfies=("ASM-003",),
    precondition="assembly",
    idempotent=True,
    timeout_s=300.0,
)
def asm_component_set(ctx: OpContext, args: AsmComponentSetArgs) -> AsmComponentSetResult:
    doc = ctx.require_doc()
    component = _find_component(doc, args.component_name)
    if component is None:
        raise SwMcpError(
            make_error(
                "COMPONENT_NOT_FOUND",
                "validation",
                f"This assembly has no component named {args.component_name!r}.",
                remediation=["Use sw_asm_tree to see the instance names, e.g. 'bracket-1'."],
            )
        )

    before = _describe(component, 0)
    changed: list[str] = []

    if args.suppression is not None:
        try_com_member(
            component,
            "SetSuppression2",
            swconst.value(
                "swComponentSuppressionState_e", _SUPPRESSION_STATES[args.suppression]
            ),
            default=None,
        )
        changed.append("suppression")

    # A suppressed component cannot be re-found by name, so re-resolve the handle.
    component = _find_component(doc, args.component_name) or component

    if args.configuration is not None:
        try_com_member(component, "ReferencedConfiguration", default=None)
        component.ReferencedConfiguration = args.configuration
        changed.append("configuration")

    if args.visible is not None:
        # SetVisibility(State, Config_opt, Config_names). The third argument is only
        # read for swSpecifyConfiguration, but the type library declares three and the
        # arity check enforces it — pywin32 accepted the short call and hid the mistake.
        try_com_member(
            component,
            "SetVisibility",
            swconst.value(
                "swComponentVisibilityState_e",
                "swComponentVisible" if args.visible else "swComponentHidden",
            ),
            swconst.value("swInConfigurationOpts_e", "swThisConfiguration"),
            null_dispatch(),
            default=None,
        )
        changed.append("visible")

    if args.fixed is not None:
        try_com_member(doc, "ClearSelection2", True, default=None)
        try_com_member(component, "Select4", True, null_dispatch(), False, default=False)
        try_com_member(doc, "FixComponent" if args.fixed else "UnfixComponent", default=None)
        try_com_member(doc, "ClearSelection2", True, default=None)
        changed.append("fixed")

    component = _find_component(doc, args.component_name) or component
    after = _describe(component, 0)

    checks = [
        Check(
            name="component_still_addressable",
            passed=bool(after["name"]),
            detail=after["name"] or "the component vanished",
        )
    ]
    if args.suppression is not None:
        checks.append(
            Check(
                name="suppression_applied",
                passed=after["suppression"] == args.suppression,
                detail=f"{before['suppression']} -> {after['suppression']}",
            )
        )
    if args.fixed is not None:
        checks.append(
            Check(
                name="fixed_applied",
                passed=after["fixed"] == args.fixed,
                detail=f"{before['fixed']} -> {after['fixed']}",
            )
        )
    if args.visible is not None:
        checks.append(
            Check(
                name="visibility_applied",
                # A suppressed component reports as hidden whatever was asked, so this
                # only holds while the component is resolved.
                passed=after["visible"] == args.visible or after["suppressed"],
                detail=f"{before['visible']} -> {after['visible']}",
            )
        )
    if args.configuration is not None:
        checks.append(
            Check(
                name="configuration_applied",
                passed=after["configuration"] == args.configuration,
                detail=f"{before['configuration']} -> {after['configuration']}",
            )
        )

    warnings: list[str] = []
    if args.suppression is not None and after["suppression"] != args.suppression:
        # SOLIDWORKS declines some transitions rather than failing: asking for
        # 'lightweight' was observed to leave a component fully resolved. The state is
        # reported as it really is, and the disagreement is said out loud, because a
        # caller that asked for lightweight and got resolved needs to know.
        warnings.append(
            f"Asked for suppression {args.suppression!r} but the component reports "
            f"{after['suppression']!r}. SOLIDWORKS declines some transitions — notably "
            f"lightweight for a component whose document is already open in the session."
        )

    return AsmComponentSetResult(
        component_name=after["name"],
        suppression=after["suppression"],
        fixed=after["fixed"],
        visible=after["visible"],
        configuration=after["configuration"],
        changed=changed,
        warnings=warnings,
        verification=Verification(read_back=True, before=before, after=after, checks=checks),
    )
