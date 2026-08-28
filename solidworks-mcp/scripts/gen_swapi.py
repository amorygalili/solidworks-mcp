"""Generate the SOLIDWORKS API member table from the locally registered type library.

The point is arity and existence. ``FeatureCircularPattern5`` takes fourteen arguments;
passing thirteen returns "Parameter not optional", which names neither the member nor
the count, and a version-suffixed member that does not exist on an older release fails
just as opaquely. Both are checkable against ``sldworks.tlb``, so they should be checked
rather than discovered in a model that quietly came out wrong.

    uv run python scripts/gen_swapi.py            # write the table
    uv run python scripts/gen_swapi.py --check    # fail if it is stale

Only the interfaces this server actually calls are captured; the library defines over a
thousand, and a table nobody reads is just a large file to keep current.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "src" / "swmcp" / "generated" / "swapi.json"

SLDWORKS_TYPELIB_IID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
CANDIDATE_MAJORS = list(range(40, 19, -1))

#: The interfaces swmcp reaches through. Keep this list and the handlers in step: a
#: member called on an interface that is not here simply is not checked.
INTERFACES = (
    "ISldWorks",
    "IModelDoc2",
    "IModelDocExtension",
    "IPartDoc",
    "IAssemblyDoc",
    "IFeatureManager",
    "ISketchManager",
    "ISelectionMgr",
    "IFeature",
    "ISketch",
    "ISketchSegment",
    "ISketchRelationManager",
    "IEntity",
    "IFace2",
    "IEdge",
    "IVertex",
    "IBody2",
    "ISurface",
    "ICurve",
    "IDimension",
    "IDisplayDimension",
    "IConfiguration",
    "IConfigurationManager",
    "IComponent2",
    "IMassProperty",
    "IEquationMgr",
    "ICustomPropertyManager",
    "IModelView",
    "IMathUtility",
)


def load_typelib(iid_text: str):
    import pythoncom
    import pywintypes

    iid = pywintypes.IID(iid_text)
    errors = []
    for major in CANDIDATE_MAJORS:
        try:
            return pythoncom.LoadRegTypeLib(iid, major, 0, 0), major
        except Exception as exc:  # any failure here just means "try the next major"
            errors.append(f"{major}: {exc}")
    raise SystemExit(
        f"could not load type library {iid_text}; is SOLIDWORKS installed?\n"
        + "\n".join(errors[:3])
    )


def _kind_of(invoke_kind: int) -> str:
    import pythoncom

    if invoke_kind == pythoncom.INVOKE_PROPERTYGET:
        return "propget"
    if invoke_kind in (pythoncom.INVOKE_PROPERTYPUT, pythoncom.INVOKE_PROPERTYPUTREF):
        return "propput"
    return "method"


def extract_members(typelib, wanted: tuple[str, ...]) -> dict[str, dict]:
    """``{interface: {member: {"params", "flags", "kind", "returns_void"}}}``."""
    import pythoncom

    remaining = set(wanted)
    interfaces: dict[str, dict] = {}

    for index in range(typelib.GetTypeInfoCount()):
        name = typelib.GetDocumentation(index)[0]
        if name not in remaining:
            continue
        info = typelib.GetTypeInfo(index)
        attributes = info.GetTypeAttr()

        members: dict[str, dict] = {}
        for position in range(attributes.cFuncs):
            descriptor = info.GetFuncDesc(position)
            names = info.GetNames(descriptor.memid)
            member = names[0]
            kind = _kind_of(descriptor.invkind)
            # Each arg descriptor is (vartype, paramflags, default). The flags matter:
            # PARAMFLAG_FOUT alone (2) means pywin32 fills the parameter in and returns
            # it, so a caller may omit it, while FIN|FOUT (3) must still be passed as a
            # by-ref VARIANT — which is what out_long() is for in swmcp.com.marshal.
            flags = [
                int(arg[1]) if len(arg) > 1 and arg[1] is not None else 1
                for arg in descriptor.args
            ]
            entry = {
                "params": list(names[1:]),
                "flags": flags[: len(names) - 1],
                "kind": kind,
                # VT_VOID means there is nothing to test when the call comes back.
                # IFeatureManager::InsertRib is declared void, and reading its None
                # return as failure once reported RIB_FAILED for a rib that had built
                # correctly, so the fact is recorded and checked by the test suite.
                "returns_void": descriptor.rettype[0] == pythoncom.VT_VOID,
            }
            # A property with both a getter and a setter appears twice; the getter is
            # the one callers read, so it wins.
            if member in members and members[member]["kind"] == "propget":
                continue
            members[member] = entry

        if members:
            interfaces[name] = dict(sorted(members.items()))
            remaining.discard(name)

    if remaining:
        raise SystemExit(
            "these interfaces are not in the type library: " + ", ".join(sorted(remaining))
        )
    return dict(sorted(interfaces.items()))


def build() -> str:
    typelib, major = load_typelib(SLDWORKS_TYPELIB_IID)
    interfaces = extract_members(typelib, INTERFACES)
    payload = {
        "generated_from": "sldworks.tlb",
        "typelib_iid": SLDWORKS_TYPELIB_IID,
        "typelib_major": major,
        "interface_count": len(interfaces),
        "member_count": sum(len(members) for members in interfaces.values()),
        "interfaces": interfaces,
    }
    return json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the table is stale")
    arguments = parser.parse_args()

    generated = build()
    if arguments.check:
        if not OUTPUT.is_file():
            print(f"{OUTPUT} is missing; run without --check to generate it")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != generated:
            print(f"{OUTPUT} is stale; run scripts/gen_swapi.py to regenerate")
            return 1
        print(f"{OUTPUT.name} is current")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generated, encoding="utf-8")
    payload = json.loads(generated)
    print(
        f"wrote {OUTPUT.relative_to(REPO_ROOT)}: {payload['member_count']} members across "
        f"{payload['interface_count']} interfaces from sldworks.tlb major "
        f"{payload['typelib_major']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
