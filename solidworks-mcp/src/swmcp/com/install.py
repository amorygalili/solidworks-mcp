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
from typing import Any

from swmcp.com.progid import BASE_PROGID, PROBE_MAJORS, progid_for_major

_LOCAL_SERVER = re.compile(r'^"?(?P<path>[^"]+?\.exe)"?', re.IGNORECASE)
_TEMPLATE_ROOT = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "SolidWorks"

#: The 3DEXPERIENCE Platform launcher. Its presence beside the install is what makes an
#: install *managed*: such a build refuses to start from sldworks.exe, and therefore
#: refuses to start from COM activation too, which resolves the ProgID's LocalServer32
#: to exactly that executable.
PLATFORM_LAUNCHER = "CATSTART.exe"

def _shortcut_roots() -> tuple[Path, ...]:
    """Where Windows keeps shortcuts.

    Read from the environment rather than spelled out, so a redirected profile or a
    system drive that is not C: still resolves.
    """
    roots = [
        Path(os.environ.get("PUBLIC", "")) / "Desktop",
        Path.home() / "Desktop",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    return tuple(root for root in roots if root.parts and root.is_dir())


@dataclass(frozen=True, slots=True)
class InstallInfo:
    found: bool
    executable: str | None = None
    install_root: str | None = None
    clsid: str | None = None
    registered_progids: tuple[str, ...] = ()
    template_dirs: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)
    #: The Platform launcher, when this install is 3DEXPERIENCE-managed.
    platform_launcher: str | None = None
    #: A Platform-created shortcut that starts SOLIDWORKS the way it demands.
    platform_shortcut: str | None = None

    @property
    def platform_managed(self) -> bool:
        """Whether COM activation will be refused for this install."""
        return self.platform_launcher is not None

    @property
    def launch_mode(self) -> str:
        """How this install has to be started.

        ``platform_manual`` is not a variant of "the server starts it" — it means the
        server *cannot*. A Platform launch requires an interactive 3DEXPERIENCE
        sign-in, so a human has to do it and ``start_if_missing`` is refused.
        """
        return "platform_manual" if self.platform_managed else "com_activation"


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

    # Being Platform-managed is not a *fault*, so it does not belong in notes — that
    # field means something is wrong with the installation, and a permanent entry there
    # makes every health check report an unhealthy machine. It is reported structurally
    # instead, through launch_mode and platform_shortcut.
    launcher = find_platform_launcher(install_root)
    shortcut = find_platform_shortcut(launcher)

    return InstallInfo(
        found=bool(executable),
        executable=executable,
        install_root=install_root,
        clsid=clsid,
        registered_progids=registered_progids(),
        template_dirs=_template_dirs(),
        notes=notes,
        platform_launcher=launcher,
        platform_shortcut=shortcut,
    )


def find_platform_launcher(install_root: str | None) -> str | None:
    """``CATSTART.exe`` for a 3DEXPERIENCE-managed install, or ``None``.

    ``install_root`` is the directory holding ``sldworks.exe``; the launcher lives in a
    sibling platform tree — ``../win_b64/code/bin/CATSTART.exe`` on this release. The
    architecture directory is globbed rather than named, because it is the part most
    likely to differ between releases.
    """
    if not install_root:
        return None
    parent = Path(install_root).parent
    direct = parent / "win_b64" / "code" / "bin" / PLATFORM_LAUNCHER
    if direct.is_file():
        return str(direct)
    for candidate in sorted(parent.glob(f"*/code/bin/{PLATFORM_LAUNCHER}")):
        if candidate.is_file():
            return str(candidate)
    return None


def _shortcut_target(path: Path) -> tuple[str | None, str | None]:
    """Resolve a ``.lnk`` to its target and arguments, or ``(None, None)``."""
    try:
        import win32com.client
    except ImportError:  # pragma: no cover - non-Windows
        return None, None
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        link = shell.CreateShortCut(str(path))
        return str(link.TargetPath or ""), str(link.Arguments or "")
    except Exception:
        return None, None


def find_platform_shortcut(launcher: str | None) -> str | None:
    """A Platform-created shortcut that launches SOLIDWORKS through ``launcher``.

    The shortcut is what gets started, never a reconstructed command line: its
    arguments carry the tenant id and 3DRegistryURL of whoever installed SOLIDWORKS.
    Those are per-account values that belong to the user, so they are read from the
    user's own shortcut at launch time rather than copied into this package.
    """
    if not launcher:
        return None
    wanted = Path(launcher).name.lower()

    matches: list[Path] = []
    for root in _shortcut_roots():
        for link in sorted(root.rglob("*.lnk")):
            target, _arguments = _shortcut_target(link)
            if target and Path(target).name.lower() == wanted:
                matches.append(link)

    if not matches:
        return None
    # A Platform install makes several CATSTART shortcuts — Design, Visualize, and so
    # on. Only the one that starts SOLIDWORKS itself is any use here.
    preferred = [m for m in matches if "solidworks" in m.stem.lower()]
    return str((preferred or matches)[0])


def is_running() -> bool:
    """Whether a SOLIDWORKS process exists, without attaching to it.

    Attaching is a side effect; a health report should be able to say "not running"
    without starting anything or waiting on COM.
    """
    return process_resources() is not None


#: A SOLIDWORKS session that has been driven hard for a long time accumulates private
#: bytes and handles it never gives back. Past roughly this much it is worth watching:
#: calls slow markedly. This is a *reporting* threshold and nothing enforces it — a
#: session at 9 GB is slower but entirely usable, and a full live suite has run to
#: completion well past it.
STRAINED_PRIVATE_BYTES = 8 * 1024**3
STRAINED_HANDLE_COUNT = 30_000

#: The measured wall, which is a different number and a different claim. At roughly
#: 11.6 GB of private bytes calls went from 3s to 15s and then stopped returning at all;
#: only a restart recovers it. Anything that *acts* on the reading rather than reporting
#: it belongs here, not above — treating the advisory number as a stop signal makes a
#: perfectly healthy session refuse to work.
#:
#: There is deliberately no critical handle count. The wall was measured in private
#: bytes; no handle figure has been observed to fail, and inventing one would be
#: dressing a guess as a measurement.
CRITICAL_PRIVATE_BYTES = 11 * 1024**3


def process_resources() -> dict[str, Any] | None:
    """What the SOLIDWORKS process is costing, or ``None`` if it is not running.

    Read through WMI rather than COM, deliberately: when a session has exhausted itself
    every COM call blocks, which is exactly when a caller most needs to be told why.
    """
    try:
        import win32com.client
    except ImportError:  # pragma: no cover - non-Windows
        return None
    try:
        wmi = win32com.client.GetObject("winmgmts:")
        rows = list(
            wmi.ExecQuery(
                "SELECT ProcessId, PrivatePageCount, HandleCount, WorkingSetSize "
                "FROM Win32_Process WHERE Name='SLDWORKS.exe'"
            )
        )
    except Exception:
        return None
    if not rows:
        return None

    row = rows[0]
    private = int(getattr(row, "PrivatePageCount", 0) or 0)
    handles = int(getattr(row, "HandleCount", 0) or 0)
    strained = private >= STRAINED_PRIVATE_BYTES or handles >= STRAINED_HANDLE_COUNT
    critical = private >= CRITICAL_PRIVATE_BYTES

    return {
        "process_id": int(getattr(row, "ProcessId", 0) or 0),
        "private_bytes": private,
        "private_mb": round(private / 1024**2, 1),
        "working_set_bytes": int(getattr(row, "WorkingSetSize", 0) or 0),
        "handle_count": handles,
        "strained": strained,
        "critical": critical,
        "note": (
            "A long automation session leaks private bytes and handles that SOLIDWORKS "
            "never returns, and past this point calls slow noticeably. The session is "
            "still usable; restarting SOLIDWORKS is what recovers the speed."
        )
        if strained and not critical
        else (
            "This session has passed the point where calls stop returning rather than "
            "failing. Restarting SOLIDWORKS is the only remedy."
        )
        if critical
        else None,
    }
