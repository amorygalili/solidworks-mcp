"""Vendor the offline SOLIDWORKS API documentation into ``reference/swapi-docs``.

The type library says what exists and with how many arguments; it cannot say what a
call *means*, what it returns, or what it quietly requires. That gap is where this
project's real bugs have lived, so the prose is worth keeping next to the code.

Two findings from this corpus, both of which had previously been recorded in the source
as quirks of this release, are what earned it a place here:

* ``IFeatureManager::InsertRib`` is declared ``void``. A ``None`` return is the
  signature, not a failure.
* ``IEquationMgr::SetEquationAndConfigurationOption`` "modifies only equations added
  using ``Add3``", and ``Add3`` "only works for parts having multiple configurations".
  Both -1 returns were documented behaviour, not a broken API.

Run ``uv run python scripts/fetch_api_docs.py`` to download and extract, and
``--check`` to verify what is vendored still matches the installed type library.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "reference" / "swapi-docs"
SWAPI = ROOT / "src" / "swmcp" / "generated" / "swapi.json"

RELEASE = "v3.12.1"
URL = (
    "https://github.com/pedropaulovc/offline-solidworks-api-docs/releases/download/"
    f"{RELEASE}/SolidWorks.Interop.llms.{RELEASE}.zip"
)

#: Signature line as the corpus writes it: ``**Signature**: `ret Name( a, b )```
SIGNATURE = re.compile(
    r"\*\*Signature\*\*: `(?P<returns>[\w.<>\[\] ]+?)\s+(?P<name>\w+)\((?P<args>.*?)\)`", re.S
)

#: IUnknown/IDispatch plumbing and typelib padding. Present in the type library,
#: absent from the documentation, and not API in any useful sense.
PLUMBING = re.compile(
    r"^(AddRef|Release|QueryInterface|GetIDsOfNames|GetTypeInfo|GetTypeInfoCount"
    r"|Invoke|Dummy\d+)$"
)


def interfaces() -> dict[str, dict]:
    return json.loads(SWAPI.read_text(encoding="utf-8"))["interfaces"]


def download() -> zipfile.ZipFile:
    print(f"downloading {URL}")
    with urllib.request.urlopen(URL) as response:
        payload = response.read()
    print(f"  {len(payload) / 1e6:.1f} MB")
    return zipfile.ZipFile(io.BytesIO(payload))


def extract(archive: zipfile.ZipFile) -> None:
    """Keep the interfaces this server actually calls, plus the enums and indexes.

    The whole corpus is 31.8 MB across 16,254 files. Curating it to the interfaces
    ``swapi.json`` lists keeps the reference aligned with the surface the code can reach —
    the same curation the generated API table already applies.
    """
    wanted = set(interfaces())
    if TARGET.exists():
        for path in sorted(TARGET.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
    TARGET.mkdir(parents=True, exist_ok=True)

    kept = 0
    for name in archive.namelist():
        if name.endswith("/"):
            continue
        parts = name.split("/")
        keep = (
            (parts[0] == "types" and len(parts) > 1 and parts[1] in wanted)
            or parts[0] in {"enums", "index", "docs"}
            or name == "README.md"
        )
        if not keep:
            continue
        destination = TARGET / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.read(name))
        kept += 1

    size = sum(path.stat().st_size for path in TARGET.rglob("*") if path.is_file())
    print(f"kept {kept} files, {size / 1e6:.1f} MB, under {TARGET.relative_to(ROOT)}")


def check() -> int:
    """Does the vendored prose still describe the type library that is installed?"""
    if not TARGET.exists():
        print(f"{TARGET.relative_to(ROOT)} is missing; run this script without --check")
        return 1

    mismatches: list[str] = []
    undocumented: list[str] = []
    checked = 0
    for interface, members in interfaces().items():
        if not (TARGET / "types" / interface / "_overview.md").exists():
            undocumented.append(interface)
            continue
        for member, entry in members.items():
            page = TARGET / "types" / interface / f"{member}.md"
            if not page.exists():
                if not PLUMBING.match(member):
                    undocumented.append(f"{interface}.{member}")
                continue
            found = SIGNATURE.search(page.read_text(encoding="utf-8", errors="replace"))
            if not found:
                continue
            checked += 1
            documented = [a for a in found.group("args").split(",") if a.strip()]
            if len(documented) != len(entry["params"]):
                mismatches.append(
                    f"{interface}.{member}: type library takes {len(entry['params'])} "
                    f"argument(s), the documentation describes {len(documented)}"
                )

    print(f"cross-checked {checked} member signatures against the installed type library")
    print(f"  undocumented but present in the type library: {len(undocumented)}")
    if mismatches:
        print(f"  ARITY MISMATCHES: {len(mismatches)}")
        for row in mismatches[:20]:
            print(f"    {row}")
        print("\nThe vendored documentation describes a different release than the one")
        print("installed here. Treat the type library as authoritative and re-vendor.")
        return 1
    print("  arity mismatches: 0 — the documentation matches this installation")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the vendored documentation against the installed type library.",
    )
    args = parser.parse_args()
    if args.check:
        return check()
    extract(download())
    return check()


if __name__ == "__main__":
    sys.exit(main())
