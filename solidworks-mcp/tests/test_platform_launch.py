"""Starting a 3DEXPERIENCE-managed SOLIDWORKS (SYS-001).

COM activation resolves the ProgID's ``LocalServer32`` to ``sldworks.exe``, and a
3DEXPERIENCE-managed build refuses to start that way: the user gets a modal dialog
saying SOLIDWORKS must be launched from the Platform, and the caller gets
``CO_E_SERVER_EXEC_FAILURE`` naming neither cause nor cure. Worse than the failure is
the dialog — a modal dialog blocks every subsequent COM call, which reads exactly like
a hung session.

These tests run against fake directory trees, so they exercise the discovery rules on
any machine rather than only on a managed install.
"""

from __future__ import annotations

import pytest

from swmcp.com import install as install_mod
from swmcp.com.install import (
    PLATFORM_LAUNCHER,
    InstallInfo,
    find_platform_launcher,
    find_platform_shortcut,
)


def _managed_tree(root):
    """An install laid out the way a 3DEXPERIENCE release is."""
    release = root / "Dassault Systemes" / "SOLIDWORKS 3DEXPERIENCE R2026x"
    sw = release / "SOLIDWORKS"
    sw.mkdir(parents=True)
    (sw / "sldworks.exe").write_text("", encoding="utf-8")
    launcher = release / "win_b64" / "code" / "bin" / PLATFORM_LAUNCHER
    launcher.parent.mkdir(parents=True)
    launcher.write_text("", encoding="utf-8")
    return sw, launcher


# --- detecting a managed install ------------------------------------------------


def test_the_platform_launcher_is_found_beside_the_install(tmp_path):
    sw, launcher = _managed_tree(tmp_path)
    assert find_platform_launcher(str(sw)) == str(launcher)


def test_a_differently_named_architecture_directory_is_still_found(tmp_path):
    """The arch directory is the part most likely to change between releases."""
    release = tmp_path / "SOLIDWORKS 3DEXPERIENCE R2027x"
    sw = release / "SOLIDWORKS"
    sw.mkdir(parents=True)
    launcher = release / "win_arm64" / "code" / "bin" / PLATFORM_LAUNCHER
    launcher.parent.mkdir(parents=True)
    launcher.write_text("", encoding="utf-8")

    assert find_platform_launcher(str(sw)) == str(launcher)


def test_a_classic_install_reports_no_launcher(tmp_path):
    """A non-Platform SOLIDWORKS must keep starting by COM activation."""
    sw = tmp_path / "SOLIDWORKS" / "SOLIDWORKS"
    sw.mkdir(parents=True)
    (sw / "sldworks.exe").write_text("", encoding="utf-8")

    assert find_platform_launcher(str(sw)) is None
    assert find_platform_launcher(None) is None


# --- what the install then says about itself ------------------------------------


def test_launch_mode_never_claims_the_server_can_start_a_managed_install():
    """A Platform launch needs a human, so both managed cases report the same mode.

    Distinguishing "shortcut found" from "no shortcut" here would imply the first can
    be automated. It cannot: the shortcut raises a 3DEXPERIENCE login window and waits.
    """
    classic = InstallInfo(found=True, executable="x.exe")
    assert classic.platform_managed is False
    assert classic.launch_mode == "com_activation"

    managed = InstallInfo(found=True, platform_launcher="CATSTART.exe", platform_shortcut="a.lnk")
    assert managed.platform_managed is True
    assert managed.launch_mode == "platform_manual"

    stranded = InstallInfo(found=True, platform_launcher="CATSTART.exe")
    assert stranded.launch_mode == "platform_manual"


# --- finding the shortcut -------------------------------------------------------


@pytest.fixture
def shortcut_tree(tmp_path, monkeypatch):
    """Two CATSTART shortcuts and one unrelated one, with resolution stubbed.

    Resolving a .lnk needs WScript.Shell, so the resolver is replaced rather than the
    shortcut files being made real — the rule under test is the matching, not COM.
    """
    desktop = tmp_path / "Public" / "Desktop"
    desktop.mkdir(parents=True)
    links = {
        desktop / "SOLIDWORKS Design.lnk": (r"C:\DS\win_b64\code\bin\CATSTART.exe", "-run ..."),
        desktop / "SOLIDWORKS Visualize.lnk": (r"C:\DS\win_b64\code\bin\CATSTART.exe", "-run ..."),
        desktop / "Notepad.lnk": (r"C:\Windows\notepad.exe", ""),
    }
    for link in links:
        link.write_text("", encoding="utf-8")

    monkeypatch.setattr(install_mod, "_shortcut_roots", lambda: (desktop,))
    monkeypatch.setattr(
        install_mod, "_shortcut_target", lambda path: links.get(path, (None, None))
    )
    return desktop


def test_the_shortcut_pointing_at_the_launcher_is_chosen(shortcut_tree):
    found = find_platform_shortcut(r"C:\DS\win_b64\code\bin\CATSTART.exe")
    assert found == str(shortcut_tree / "SOLIDWORKS Design.lnk")


def test_an_unrelated_shortcut_is_never_chosen(shortcut_tree):
    """Matching on the target, not the name: Notepad.lnk must not be launched."""
    found = find_platform_shortcut(r"C:\DS\win_b64\code\bin\CATSTART.exe")
    assert "Notepad" not in found


def test_no_launcher_means_no_shortcut_search(shortcut_tree):
    assert find_platform_shortcut(None) is None


def test_a_missing_shortcut_is_reported_as_none(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(install_mod, "_shortcut_roots", lambda: (empty,))
    assert find_platform_shortcut(r"C:\DS\CATSTART.exe") is None


def test_nothing_is_ever_spawned_for_a_managed_install():
    """The regression this exists to prevent: launching the shortcut anyway.

    Running it starts CATSTART and SWXDesktopLauncher, which raise a 3DEXPERIENCE login
    window and wait for a human. SOLIDWORKS never appears, the call burns its whole
    timeout, and a login prompt is left on the user's screen. Refusing is the feature.
    """
    import inspect

    from swmcp.com import session

    source = inspect.getsource(session.SwSession._launch_via_platform)
    for spawner in ("startfile", "Popen", "subprocess", "ShellExecute", "system("):
        assert spawner not in source, f"{spawner} would raise a login window and hang"

    # The user's tenant id lives in the shortcut's arguments; nothing reads them.
    assert "Arguments" not in inspect.getsource(install_mod.find_platform_shortcut)


# --- not attaching is not the same as not using a session -----------------------


def test_the_diagnostics_still_use_a_session_when_there_is_one():
    """The trap in exempting them from the dispatcher's attach.

    ``needs_session=False`` stops the dispatcher attaching on their behalf, so they
    answer when SOLIDWORKS is stopped. Taken literally it also made them answer
    *badly* when it was running: sw_capabilities reported no templates and
    ``attach: False`` on a healthy machine, because nothing had attached yet and it
    read ``session.attached`` rather than trying. They must opportunistically attach.
    """
    import inspect

    from swmcp.handlers import system as system_handlers

    for handler in (system_handlers.capabilities, system_handlers.system_info):
        source = inspect.getsource(handler)
        assert "try_attach" in source, (
            f"{handler.__name__} must try to attach, or it reports degraded answers "
            f"on a machine where SOLIDWORKS is running perfectly well"
        )

    # Health is deliberately excluded: it has to answer while a COM call is wedged, and
    # attaching could block on the very thing it is being asked to explain.
    assert "try_attach" not in inspect.getsource(system_handlers.health)


def test_try_attach_reports_failure_rather_than_raising():
    """It runs on the "SOLIDWORKS is absent" path, where failing is the normal case."""
    from swmcp.com.session import SwSession
    from swmcp.errors import SwMcpError, worker_error

    session = SwSession.__new__(SwSession)
    session._app = None

    def refuse(**_kwargs):
        raise SwMcpError(worker_error("SOLIDWORKS_NOT_RUNNING", "nothing to attach to"))

    session.ensure = refuse
    assert session.try_attach() is False


def test_try_attach_never_launches():
    """Launching is sw_connect's job, and on this install it cannot succeed anyway."""
    import inspect

    from swmcp.com.session import SwSession

    source = inspect.getsource(SwSession.try_attach)
    assert "start_if_missing" not in source


# --- the failure a caller used to get -------------------------------------------


def test_the_activation_failure_now_decodes(monkeypatch):
    """CO_E_SERVER_EXEC_FAILURE is what a managed install returns to COM activation."""
    from swmcp.decode.hresult import decode_hresult

    info = decode_hresult(0x80080005)
    assert info is not None
    assert info.code == "COM_SERVER_EXEC_FAILED"
    assert info.symbol == "CO_E_SERVER_EXEC_FAILURE"
    assert any("3DEXPERIENCE" in step for step in info.remediation)


def test_the_negative_form_decodes_to_the_same_thing():
    """pywin32 reports it as a signed int; both forms must reach the same entry."""
    from swmcp.decode.hresult import decode_hresult, normalize_hresult

    assert normalize_hresult(-2146959355) == 0x80080005
    assert decode_hresult(-2146959355).code == "COM_SERVER_EXEC_FAILED"


@pytest.mark.parametrize("shortcut", [None, r"C:\Users\Public\Desktop\SOLIDWORKS Design.lnk"])
def test_a_managed_install_refuses_to_be_started(shortcut):
    """It refuses whether or not a shortcut was found — neither can be automated."""
    from swmcp.com.session import SwSession
    from swmcp.errors import SwMcpError

    session = SwSession.__new__(SwSession)
    managed = InstallInfo(
        found=True,
        executable="sldworks.exe",
        platform_launcher="CATSTART.exe",
        platform_shortcut=shortcut,
    )

    with pytest.raises(SwMcpError) as caught:
        session._launch_via_platform(managed)

    envelope = caught.value.envelope
    assert envelope.code == "SOLIDWORKS_PLATFORM_LAUNCH_REQUIRED"
    assert "sign-in" in envelope.message
    if shortcut:
        assert any(shortcut in step for step in envelope.remediation), (
            "the refusal must name the shortcut the user should run"
        )
    assert any("sldworks.exe" in step for step in envelope.remediation)


def test_being_platform_managed_is_reported_structurally_not_as_a_fault(monkeypatch, tmp_path):
    """``notes`` means the *installation* is wrong; being managed is not.

    Filing a permanent note there made ``sw_health`` report every machine as unhealthy
    and broke a live test that reads ``notes == []`` as "nothing is wrong with this
    install". The launch requirement belongs in ``launch_mode``, which callers can
    branch on, and health composes its advice from that only while SOLIDWORKS is down.
    """
    sw, launcher = _managed_tree(tmp_path)
    executable = sw / "sldworks.exe"

    def registry(root, key, value=""):
        if key.endswith("CLSID"):
            return "{GUID}"
        if "LocalServer32" in key:
            return f'"{executable}"'
        return None

    monkeypatch.setattr(install_mod, "_read_registry", registry)
    monkeypatch.setattr(install_mod, "registered_progids", lambda: ())
    monkeypatch.setattr(install_mod, "_template_dirs", lambda: ())
    monkeypatch.setattr(install_mod, "_expand_short_path", lambda path: path)
    monkeypatch.setattr(install_mod, "find_platform_shortcut", lambda _launcher: None)

    info = install_mod.find_install()

    assert info.platform_launcher == str(launcher)
    assert info.platform_shortcut is None
    assert info.launch_mode == "platform_manual"
    assert info.notes == [], (
        "a managed install is not a broken one; notes must stay empty so a real "
        "installation fault is still visible there"
    )


# --- prompts that wedge the API -------------------------------------------------


def test_the_automation_guard_disables_both_known_wedging_prompts():
    """Two settings stop SOLIDWORKS answering, and neither announces itself as a dialog.

    swInputDimValOnCreate pops a modal Modify box for every dimension the API creates.
    swInsertViewForNewDrawing is worse, because it is not a dialog at all: it opens the
    Model View PropertyManager on every new drawing, leaving an interactive command
    waiting for a selection. The process then reports "not responding" with its memory
    flat while the next COM call blocks forever — indistinguishable from a hung session
    until someone reads the status bar.
    """
    import inspect

    from swmcp.com import swconst
    from swmcp.com.session import SwSession

    source = inspect.getsource(SwSession._configure_for_automation)
    for name in ("swInputDimValOnCreate", "swInsertViewForNewDrawing"):
        assert name in source, f"{name} is not disabled, so it will wedge the API"
        assert isinstance(swconst.value("swUserPreferenceToggle_e", name), int), (
            f"{name} must be a real swUserPreferenceToggle_e member"
        )


def test_the_wedging_prompts_are_restored_afterwards():
    """They are the user's own settings, not ours to keep."""
    import inspect

    from swmcp.com.session import SwSession

    configure = inspect.getsource(SwSession._configure_for_automation)
    assert "_preference_overrides" in configure, "the previous value must be remembered"
    restore = inspect.getsource(SwSession.restore_user_preferences)
    assert "_preference_overrides" in restore, "and put back"
