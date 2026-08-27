"""Discover the SOLIDWORKS installation from the registry (SYS-002).

Every path glob in the sibling projects looks under ``C:/Program Files/SOLIDWORKS Corp``,
which does not exist on this machine — 3DEXPERIENCE SOLIDWORKS 2026 installs to
``C:/Program Files/Dassault Systemes/SOLIDWORKS 3DEXPERIENCE R2026x/SOLIDWORKS``. Guessing
paths is how that breaks; the registry knows.

The registry entry stores a short (8.3) path, which is expanded here so reported paths
are the ones a human recognises.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from swmcp.com.progid import BASE_PROGID, PROBE_MAJORS, progid_for_major

_LOCAL_SERVER = re.compile(r'^"?(?P<path>[^"]+?\.exe)"?', re.IGNORECASE)
_TEMPLATE_ROOT = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "SolidWorks"


@dataclass(frozen=True, slots=True)
class InstallInfo:
    found: bool
    executable: str | None = None
    install_root: str | None = None
    clsid: str | None = None
    registered_progids: tuple[str, ...] = ()
    template_dirs: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)


def _read_registry(root: str, key: str, value: str = "") -> str | None:
    try:
        import winreg
    except ImportError:  # pragma: no cover - non-Windows
        return None
    hive = {
        "HKCR": winreg.HKEY_CLASSES_ROOT,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
    }[root]
    try:
        with winreg.OpenKey(hive, key) as handle:
            data, _kind = winreg.QueryValueEx(handle, value)
    except OSError:
        return None
    return str(data) if data is not None else None


def _expand_short_path(path: str) -> str:
    """``C:\\PROGRA~1\\...`` → the long form, so reported paths are recognisable."""
    try:
        import win32api

        return str(win32api.GetLongPathName(path))
    except Exception:
        return path


def registered_progids() -> tuple[str, ...]:
    """Which SOLIDWORKS ProgIDs actually exist in the registry."""
    found = []
    if _read_registry("HKCR", BASE_PROGID) is not None:
        found.append(BASE_PROGID)
    for major in PROBE_MAJORS:
        progid = progid_for_major(major)
        if _read_registry("HKCR", progid) is not None:
            found.append(progid)
    return tuple(found)


def _template_dirs() -> tuple[str, ...]:
    """Fallback template locations, used only if SOLIDWORKS does not report its own."""
    if not _TEMPLATE_ROOT.is_dir():
        return ()
    found = [
        str(candidate)
        for candidate in sorted(_TEMPLATE_ROOT.glob("SOLIDWORKS */templates"), reverse=True)
        if candidate.is_dir()
    ]
    return tuple(found)


def find_install() -> InstallInfo:
    """Locate SOLIDWORKS without launching it."""
    notes: list[str] = []

    clsid = _read_registry("HKCR", f"{BASE_PROGID}\\CLSID")
    if not clsid:
        return InstallInfo(
            found=False,
            registered_progids=registered_progids(),
            template_dirs=_template_dirs(),
            notes=[f"{BASE_PROGID} is not registered; SOLIDWORKS does not appear to be installed."],
        )

    server = _read_registry("HKCR", f"CLSID\\{clsid}\\LocalServer32")
    executable = None
    install_root = None
    if server:
        match = _LOCAL_SERVER.match(server.strip())
        raw = match.group("path") if match else server.strip()
        executable = _expand_short_path(raw)
        install_root = str(Path(executable).parent)
    else:
        notes.append(f"CLSID {clsid} has no LocalServer32 entry; the registration looks partial.")

    if executable and not Path(executable).is_file():
        notes.append(
            f"The registry points at {executable}, which does not exist. "
            "The installation may have been moved or removed."
        )

    return InstallInfo(
        found=bool(executable),
        executable=executable,
        install_root=install_root,
        clsid=clsid,
        registered_progids=registered_progids(),
        template_dirs=_template_dirs(),
        notes=notes,
    )


def is_running() -> bool:
    """Whether a SOLIDWORKS process exists, without attaching to it.

    Attaching is a side effect; a health report should be able to say "not running"
    without starting anything or waiting on COM.
    """
    try:
        import win32com.client
    except ImportError:  # pragma: no cover - non-Windows
        return False
    try:
        wmi = win32com.client.GetObject("winmgmts:")
        processes = wmi.ExecQuery("SELECT Name FROM Win32_Process WHERE Name='SLDWORKS.exe'")
        return len(list(processes)) > 0
    except Exception:
        return False
