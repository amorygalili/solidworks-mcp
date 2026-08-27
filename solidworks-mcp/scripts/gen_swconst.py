"""Generate the SOLIDWORKS constant table from the locally registered type library.

Hand-copied ``sw*_e`` values are a classic source of quiet wrongness: they drift
between releases and nobody notices until a decoded error names the wrong condition.
This reads the real ``swconst.tlb`` instead.

    uv run python scripts/gen_swconst.py            # write the table
    uv run python scripts/gen_swconst.py --check    # fail if it is stale

The output is JSON rather than generated Python because the library defines ~980
enums; :mod:`swmcp.com.swconst` builds the ones actually used, lazily.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "src" / "swmcp" / "generated" / "swconst.json"

SWCONST_TYPELIB_IID = "{4687F359-55D0-4CD3-B6CF-2EB42C11F989}"
SLDWORKS_TYPELIB_IID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
# Newest first: SOLIDWORKS majors run (year - 2000) + 8, so 34 is the 2026 release.
CANDIDATE_MAJORS = list(range(40, 19, -1))


def load_typelib(iid_text: str):
    import pythoncom
    import pywintypes

    iid = pywintypes.IID(iid_text)
    errors = []
    for major in CANDIDATE_MAJORS:
        try:
            typelib = pythoncom.LoadRegTypeLib(iid, major, 0, 0)
        except Exception as exc:
            errors.append(f"{major}: {exc}")
            continue
        return typelib, major
    raise SystemExit(
        f"could not load type library {iid_text}; is SOLIDWORKS installed?\n"
        + "\n".join(errors[:3])
    )


def extract_enums(typelib) -> dict[str, dict[str, int]]:
    import pythoncom

    enums: dict[str, dict[str, int]] = {}
    for index in range(typelib.GetTypeInfoCount()):
        if typelib.GetTypeInfoType(index) != pythoncom.TKIND_ENUM:
            continue
        name = typelib.GetDocumentation(index)[0]
        info = typelib.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        members: dict[str, int] = {}
        for position in range(attributes.cVars):
            descriptor = info.GetVarDesc(position)
            member_name = info.GetNames(descriptor[0])[0]
            value = descriptor[1]
            if isinstance(value, int):
                members[member_name] = value
        if members:
            enums[name] = dict(sorted(members.items()))
    return dict(sorted(enums.items()))


def build() -> str:
    typelib, major = load_typelib(SWCONST_TYPELIB_IID)
    enums = extract_enums(typelib)
    payload = {
        "generated_from": "swconst.tlb",
        "typelib_iid": SWCONST_TYPELIB_IID,
        "typelib_major": major,
        "enum_count": len(enums),
        "enums": enums,
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
            print(f"{OUTPUT} is stale; run scripts/gen_swconst.py to regenerate")
            return 1
        print(f"{OUTPUT.name} is current")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generated, encoding="utf-8")
    payload = json.loads(generated)
    print(
        f"wrote {OUTPUT.relative_to(REPO_ROOT)}: "
        f"{payload['enum_count']} enums from swconst.tlb major {payload['typelib_major']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
