"""SYS-001/002/007: attach to SOLIDWORKS and address its documents.

Everything here runs *on the STA worker thread*. Nothing in this module may be called
from the event loop, because the COM proxies it holds have thread affinity.

Attach order is deliberate: probe for a running instance first and only launch when
explicitly asked, because starting SOLIDWORKS is a heavyweight, visible side effect
that the caller should have to opt into.
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from typing import Any

from swmcp.com import swconst
from swmcp.com.install import InstallInfo, find_install, is_running
from swmcp.com.marshal import try_com_member
from swmcp.com.progid import candidate_progids, describe_version, major_from_revision
from swmcp.config import SwmcpConfig, get_config
from swmcp.errors import SwMcpError, make_error, worker_error
from swmcp.safety.paths import classify_document_path, prepare_document_path
from swmcp.timing import seconds_to_ms

#: Standard planes are addressed by tree position, not by name, so a localized
#: SOLIDWORKS works without an alias table (SYS-007).
STANDARD_PLANE_ORDER = ("front", "top", "right")

_LAUNCH_MUTEX = "Local\\SwMcp.SolidWorks.Launch"
_READY_POLL_S = 0.25


@dataclass(slots=True)
class DocumentInfo:
    title: str
    path: str | None
    doc_type: str
    doc_type_code: int
    is_saved: bool
    is_dirty: bool
    configuration: str | None
    checkpointable: bool
    opened_read_only: bool = False
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "path": self.path,
            "doc_type": self.doc_type,
            "doc_type_code": self.doc_type_code,
            "is_saved": self.is_saved,
            "is_dirty": self.is_dirty,
            "configuration": self.configuration,
            "checkpointable": self.checkpointable,
            "opened_read_only": self.opened_read_only,
            "warnings": list(self.warnings),
        }


def _doc_type_name(code: int) -> str:
    mapping = {
        swconst.value("swDocumentTypes_e", "swDocPART"): "part",
        swconst.value("swDocumentTypes_e", "swDocASSEMBLY"): "assembly",
        swconst.value("swDocumentTypes_e", "swDocDRAWING"): "drawing",
    }
    return mapping.get(code, f"unknown({code})")


class _LaunchGuard:
    """A cross-process mutex so two servers cannot race SOLIDWORKS up at once."""

    def __init__(self, timeout_s: float):
        self._timeout_s = timeout_s
        self._handle = None

    def __enter__(self) -> _LaunchGuard:
        try:
            import win32event
        except ImportError:  # pragma: no cover - non-Windows
            return self
        self._handle = win32event.CreateMutex(None, False, _LAUNCH_MUTEX)
        waited = win32event.WaitForSingleObject(self._handle, int(seconds_to_ms(self._timeout_s)))
        # WAIT_ABANDONED means a previous owner crashed holding it; we now own it.
        if waited not in (0, 0x80):
            raise SwMcpError(
                worker_error(
                    "LAUNCH_LOCK_TIMEOUT",
                    "Another process is starting SOLIDWORKS and did not finish in time.",
                    remediation=["Wait for the other launch to finish, then retry."],
                )
            )
        return self

    def __exit__(self, *_exc: Any) -> None:
        if self._handle is None:
            return
        # Releasing is best-effort; the handle dies with the process anyway.
        with contextlib.suppress(Exception):
            import win32event

            win32event.ReleaseMutex(self._handle)


class SwSession:
    """A live ``ISldWorks`` handle plus document addressing."""

    def __init__(self, config: SwmcpConfig | None = None):
        self._config = config or get_config()
        self._app: Any = None
        self._attached_progid: str | None = None
        self._revision: str | None = None
        self._install: InstallInfo | None = None
        self._launched_here = False
        self._preference_overrides: dict[str, bool] = {}

    # -- attach ------------------------------------------------------------

    @property
    def attached(self) -> bool:
        return self._app is not None

    @property
    def app(self) -> Any:
        if self._app is None:
            self.ensure()
        return self._app

    def install(self) -> InstallInfo:
        if self._install is None:
            self._install = find_install()
        return self._install

    def ensure(self, *, start_if_missing: bool = False, visible: bool = True) -> Any:
        """Attach to SOLIDWORKS, optionally launching it."""
        if self._app is not None:
            return self._app

        install = self.install()
        if not install.found:
            raise SwMcpError(
                make_error(
                    "SOLIDWORKS_NOT_INSTALLED",
                    "worker",
                    "SOLIDWORKS is not registered on this machine.",
                    context={"notes": install.notes},
                    remediation=[
                        "Install SOLIDWORKS, or repair the installation to re-register COM.",
                    ],
                )
            )

        import pywintypes
        import win32com.client as com

        # The registered version-suffixed ProgID is the most specific handle available.
        suffixed = [p for p in install.registered_progids if p.count(".") > 1]
        majors = [int(p.rsplit(".", 1)[1]) for p in suffixed if p.rsplit(".", 1)[1].isdigit()]
        probe = candidate_progids(max(majors) if majors else None)

        failures: list[str] = []
        for progid in probe:
            try:
                self._app = com.GetActiveObject(progid)
                self._attached_progid = progid
                break
            except (pywintypes.com_error, AttributeError, OSError) as exc:
                failures.append(f"{progid}: {exc}")

        if self._app is None:
            if not start_if_missing:
                raise SwMcpError(
                    make_error(
                        "SOLIDWORKS_NOT_RUNNING",
                        "worker",
                        "No running SOLIDWORKS instance could be attached to.",
                        context={"tried": probe, "failures": failures[:3]},
                        remediation=[
                            "Start SOLIDWORKS, or call connect with start_if_missing=true.",
                            "COM cannot attach across elevation levels: if SOLIDWORKS runs "
                            "elevated and this process does not (or the reverse), attach fails.",
                        ],
                    )
                )
            self._launch(probe[0], visible=visible)

        self._revision = str(try_com_member(self._app, "RevisionNumber", default="") or "")
        self._configure_for_automation()
        return self._app

    def _configure_for_automation(self) -> None:
        """Turn off interactive prompts that would wedge the API.

        With ``swInputDimValOnCreate`` on — the SOLIDWORKS default — every dimension
        created through the API pops a modal Modify dialog, and a modal dialog makes
        every subsequent COM call return "server busy" indefinitely. There is no way to
        dismiss it from here, so the only workable answer is not to raise it.

        The previous value is remembered and reported in the system info, and restored
        by :meth:`restore_user_preferences`, because this is a change to the user's
        own SOLIDWORKS settings rather than to any document.
        """
        for name in ("swInputDimValOnCreate",):
            try:
                code = swconst.value("swUserPreferenceToggle_e", name)
                previous = self._app.GetUserPreferenceToggle(code)
            except Exception:
                continue
            if previous:
                self._preference_overrides[name] = bool(previous)
                with contextlib.suppress(Exception):
                    self._app.SetUserPreferenceToggle(code, False)

    def restore_user_preferences(self) -> dict[str, bool]:
        """Put back any SOLIDWORKS preference this session changed."""
        restored = {}
        for name, previous in list(self._preference_overrides.items()):
            try:
                code = swconst.value("swUserPreferenceToggle_e", name)
                self._app.SetUserPreferenceToggle(code, previous)
            except Exception:
                continue
            restored[name] = previous
            self._preference_overrides.pop(name, None)
        return restored

    def _launch(self, progid: str, *, visible: bool) -> None:
        """Start SOLIDWORKS the way this installation allows.

        COM activation resolves the ProgID to the ``LocalServer32`` executable, which is
        ``sldworks.exe``. A 3DEXPERIENCE-managed install refuses to start that way: the
        user gets a modal dialog saying SOLIDWORKS "must be launched from the
        3DEXPERIENCE Platform", and the caller gets ``CO_E_SERVER_EXEC_FAILURE`` with no
        indication of why. Such an install is started through its Platform shortcut
        instead, and then attached to once it registers itself.
        """
        import win32com.client as com

        install = self.install()
        with _LaunchGuard(self._config.com_lock_timeout_s):
            if install.platform_managed:
                self._launch_via_platform(install)
            else:
                self._app = com.Dispatch(progid)
            self._launched_here = True
            # Visibility is a nicety; a headless start is still usable. A Platform
            # launch always shows the UI, and asking it not to is not honoured.
            with contextlib.suppress(Exception):
                self._app.Visible = visible
            self._wait_until_ready()

    def _launch_via_platform(self, install: InstallInfo) -> None:
        """Refuse to start a Platform-managed install, and say what to run instead.

        An earlier version of this ran the Platform shortcut. Measured, that is not a
        launch: ``CATSTART`` and ``SWXDesktopLauncher`` start, raise a 3DEXPERIENCE
        **login** window, and wait for a human. SOLIDWORKS never appears until someone
        signs in, so an automated caller burns its entire timeout and leaves a login
        prompt on the user's screen — the same harm as starting sldworks.exe directly,
        arrived at more slowly.

        There is no unattended path here, so this refuses at once and names the
        shortcut. Failing in a second with an instruction beats failing in four minutes
        with a dialog.
        """
        raise SwMcpError(
            make_error(
                "SOLIDWORKS_PLATFORM_LAUNCH_REQUIRED",
                "worker",
                "This SOLIDWORKS is 3DEXPERIENCE-managed and cannot be started "
                "automatically: the Platform requires an interactive sign-in that no "
                "API caller can complete.",
                context={
                    "platform_launcher": install.platform_launcher,
                    "platform_shortcut": install.platform_shortcut,
                    "executable": install.executable,
                },
                remediation=[
                    (
                        f"Start SOLIDWORKS yourself from {install.platform_shortcut}, "
                        "sign in to the 3DEXPERIENCE Platform, then connect again."
                    )
                    if install.platform_shortcut
                    else (
                        "Start SOLIDWORKS from the 3DEXPERIENCE Platform, or from the "
                        "desktop shortcut it created, then connect again."
                    ),
                    "Do not start sldworks.exe directly: a managed build refuses, and "
                    "the modal dialog it raises blocks every API call until dismissed.",
                    "sw_health and sw_system_info answer while SOLIDWORKS is stopped, "
                    "so they can be used to confirm when it is back.",
                ],
            )
        )

    def try_attach(self) -> bool:
        """Attach if SOLIDWORKS is there, and report whether it worked.

        For the diagnostics. They must answer when SOLIDWORKS is *not* running, which is
        why the dispatcher no longer attaches on their behalf — but "do not require a
        session" is not the same as "do not use one". Without this they report degraded
        answers on a perfectly healthy machine, purely because nothing had attached yet:
        sw_capabilities listed no templates while SOLIDWORKS sat running behind it.

        Never launches. A failure here is the ordinary case, not an error.
        """
        if self._app is not None:
            return True
        try:
            self.ensure()
        except SwMcpError:
            return False
        return self._app is not None

    def _wait_until_ready(self, timeout_s: float = 180.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            revision = try_com_member(self._app, "RevisionNumber", default=None)
            if revision:
                self._revision = str(revision)
                return
            time.sleep(_READY_POLL_S)
        raise SwMcpError(
            worker_error(
                "SOLIDWORKS_START_TIMEOUT",
                f"SOLIDWORKS did not become ready within {timeout_s:.0f}s.",
                remediation=["Check for a licence prompt or splash dialog on the desktop."],
            )
        )

    def detach(self) -> None:
        self._app = None
        self._attached_progid = None

    # -- system information ------------------------------------------------

    def system_info(self) -> dict[str, Any]:
        """SYS-002: version, session identity, and installation evidence."""
        install = self.install()
        info: dict[str, Any] = {
            "attached": self.attached,
            "attached_prog_id": self._attached_progid,
            "launched_by_this_server": self._launched_here,
            "process_running": is_running(),
            "install": {
                "found": install.found,
                "executable": install.executable,
                "install_root": install.install_root,
                "clsid": install.clsid,
                "registered_prog_ids": list(install.registered_progids),
                "template_dirs": list(install.template_dirs),
                "notes": list(install.notes),
                "launch_mode": install.launch_mode,
                "platform_launcher": install.platform_launcher,
                "platform_shortcut": install.platform_shortcut,
            },
            "constants": swconst.table_info(),
            "preference_overrides": dict(self._preference_overrides),
        }
        info.update(describe_version(self._revision))
        if self.attached:
            info["language"] = try_com_member(self._app, "GetCurrentLanguage", default=None)
            info["executable_path"] = try_com_member(self._app, "GetExecutablePath", default=None)
            info["active_document"] = None
            active = self.active_doc()
            if active is not None:
                info["active_document"] = self.describe(active).as_dict()
        return info

    @property
    def major(self) -> int | None:
        return major_from_revision(self._revision)

    # -- documents ---------------------------------------------------------

    def active_doc(self) -> Any | None:
        if self._app is None:
            return None
        return try_com_member(self._app, "ActiveDoc", default=None)

    def open_documents(self) -> list[Any]:
        """Every document currently loaded in the session."""
        if self._app is None:
            return []
        documents: list[Any] = []
        current = try_com_member(self._app, "GetFirstDocument2", default=None)
        if current is None:
            current = try_com_member(self._app, "GetFirstDocument", default=None)
        seen = 0
        while current is not None and seen < 500:
            documents.append(current)
            seen += 1
            current = try_com_member(current, "GetNext", default=None)
        return documents

    def describe(self, doc: Any) -> DocumentInfo:
        """DOC-003: the facts a caller needs before acting on a document."""
        warnings: list[str] = []
        title = str(try_com_member(doc, "GetTitle", default="") or "")
        raw_path = try_com_member(doc, "GetPathName", default="") or ""
        path, is_local = classify_document_path(str(raw_path))
        doc_type_code = int(try_com_member(doc, "GetType", default=0) or 0)

        if path is None:
            warnings.append(
                "This document has never been saved, so it cannot be checkpointed. "
                "Save it before making risky changes."
            )
        elif not is_local:
            warnings.append(
                f"This document's path ({path}) is not a local file, so file-based "
                "checkpointing is unavailable."
            )

        saved = bool(try_com_member(doc, "GetSaveFlag", default=False))
        return DocumentInfo(
            title=title,
            path=path,
            doc_type=_doc_type_name(doc_type_code),
            doc_type_code=doc_type_code,
            is_saved=path is not None,
            is_dirty=bool(saved),
            configuration=self._active_configuration(doc),
            checkpointable=bool(path and is_local),
            opened_read_only=bool(try_com_member(doc, "IsOpenedReadOnly", default=False)),
            warnings=warnings,
        )

    @staticmethod
    def _active_configuration(doc: Any) -> str | None:
        config = try_com_member(doc, "ConfigurationManager", default=None)
        if config is None:
            return None
        active = try_com_member(config, "ActiveConfiguration", default=None)
        if active is None:
            return None
        name = try_com_member(active, "Name", default=None)
        return str(name) if name else None

    def resolve_doc(
        self,
        *,
        path: str | None = None,
        title: str | None = None,
        require_type: str | None = None,
    ) -> Any:
        """DOC-004: address a document by path or title, refusing ambiguity."""
        doc = self._find_doc(path=path, title=title)
        if require_type is not None:
            self.require_type(doc, require_type)
        return doc

    def _find_doc(self, *, path: str | None, title: str | None) -> Any:
        if path:
            normalized = prepare_document_path(path)
            found = try_com_member(self.app, "GetOpenDocumentByName", normalized, default=None)
            if found is not None:
                return found
            raise SwMcpError(
                make_error(
                    "DOCUMENT_NOT_OPEN",
                    "validation",
                    f"No open document matches {normalized!r}.",
                    context={"path": normalized},
                    remediation=[
                        "Open the document first, or address the active document instead.",
                    ],
                )
            )

        if title:
            matches = [
                d
                for d in self.open_documents()
                if str(try_com_member(d, "GetTitle", default="")) == title
            ]
            if len(matches) == 1:
                return matches[0]
            if not matches:
                available = [
                    str(try_com_member(d, "GetTitle", default=""))
                    for d in self.open_documents()
                ]
                raise SwMcpError(
                    make_error(
                        "DOCUMENT_NOT_OPEN",
                        "validation",
                        f"No open document is titled {title!r}.",
                        context={"open_titles": available},
                        remediation=["Address one of the open titles, or open the file by path."],
                    )
                )
            raise SwMcpError(
                make_error(
                    "AMBIGUOUS_DOCUMENT",
                    "validation",
                    f"{len(matches)} open documents are titled {title!r}.",
                    context={
                        "candidates": [self.describe(d).as_dict() for d in matches],
                    },
                    remediation=["Address the document by its full path instead of its title."],
                )
            )

        active = self.active_doc()
        if active is None:
            raise SwMcpError(
                make_error(
                    "NO_ACTIVE_DOCUMENT",
                    "validation",
                    "There is no active SOLIDWORKS document.",
                    remediation=[
                        "Create or open a document first, or name one explicitly by path.",
                    ],
                )
            )
        return active

    def require_type(self, doc: Any, expected: str) -> None:
        """Enforce a document-type precondition before a typed operation runs."""
        actual = _doc_type_name(int(try_com_member(doc, "GetType", default=0) or 0))
        allowed = {
            "any": {"part", "assembly", "drawing"},
            "part": {"part"},
            "assembly": {"assembly"},
            "drawing": {"drawing"},
            "part_or_assembly": {"part", "assembly"},
        }.get(expected, {"part", "assembly", "drawing"})
        if actual not in allowed:
            raise SwMcpError(
                make_error(
                    "WRONG_DOCUMENT_TYPE",
                    "validation",
                    f"This operation needs a {expected.replace('_', ' ')} document, "
                    f"but the target is a {actual}.",
                    context={"expected": expected, "actual": actual},
                    remediation=[f"Activate a {expected.replace('_', ' ')} document and retry."],
                )
            )

    # -- reference geometry naming (SYS-007) -------------------------------

    def standard_planes(self, doc: Any) -> list[dict[str, Any]]:
        """Report standard planes with both localized and invariant identity.

        ``GetTypeName2`` returns English-invariant tokens such as ``RefPlane``, and the
        first three reference planes are always front/top/right in tree order. Matching
        on the display name would break on a localized install.
        """
        feature = try_com_member(doc, "FirstFeature", default=None)
        planes: list[dict[str, Any]] = []
        guard = 0
        while feature is not None and guard < 200:
            guard += 1
            type_name = str(try_com_member(feature, "GetTypeName2", default="") or "")
            if type_name == "RefPlane":
                index = len(planes)
                planes.append(
                    {
                        "name": str(try_com_member(feature, "Name", default="") or ""),
                        "type_name": type_name,
                        "index": index,
                        "standard": STANDARD_PLANE_ORDER[index]
                        if index < len(STANDARD_PLANE_ORDER)
                        else None,
                    }
                )
            feature = try_com_member(feature, "GetNextFeature", default=None)
        return planes

    def find_standard_plane(self, doc: Any, which: str) -> Any:
        """Resolve ``front``/``top``/``right`` by tree position, not by display name."""
        wanted = which.strip().lower()
        if wanted not in STANDARD_PLANE_ORDER:
            raise SwMcpError(
                make_error(
                    "UNKNOWN_STANDARD_PLANE",
                    "validation",
                    f"{which!r} is not a standard plane.",
                    context={"supported": list(STANDARD_PLANE_ORDER)},
                )
            )
        target_index = STANDARD_PLANE_ORDER.index(wanted)

        feature = try_com_member(doc, "FirstFeature", default=None)
        seen = 0
        guard = 0
        while feature is not None and guard < 200:
            guard += 1
            if str(try_com_member(feature, "GetTypeName2", default="") or "") == "RefPlane":
                if seen == target_index:
                    return feature
                seen += 1
            feature = try_com_member(feature, "GetNextFeature", default=None)

        raise SwMcpError(
            make_error(
                "STANDARD_PLANE_NOT_FOUND",
                "reference",
                f"Could not locate the {wanted} plane in the feature tree.",
                remediation=["List the document's datum features to see what exists."],
            )
        )

    def units(self, doc: Any) -> dict[str, Any]:
        """The document's display units, reported but never used for conversion."""
        linear = try_com_member(doc, "LengthUnit", default=None)
        return {
            "document_linear_unit_code": linear,
            "document_linear_unit": (
                swconst.name_of("swLengthUnit_e", linear) if isinstance(linear, int) else None
            ),
            "api_units": "The SOLIDWORKS API is always metres and radians.",
        }
