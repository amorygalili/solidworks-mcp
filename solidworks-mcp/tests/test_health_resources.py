"""``sw_health`` has to answer when nothing else can.

A SOLIDWORKS session driven hard for long enough accumulates private bytes and handles
it never gives back. Past a point every COM call slows and then stops returning, so the
one question a caller has — *why* — cannot be answered by asking SOLIDWORKS. The
resource figures come from WMI instead, which keeps replying while COM does not.

Measured on a real session that reached this state: 11.6 GB private, 44,662 handles,
and a 60-second read that never came back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from swmcp.com.install import (
    CRITICAL_PRIVATE_BYTES,
    STRAINED_HANDLE_COUNT,
    STRAINED_PRIVATE_BYTES,
)
from swmcp.config import SwmcpConfig
from swmcp.handlers import system as system_handlers
from swmcp.schemas.system import HealthArgs


@dataclass
class FakeInstall:
    found: bool = True
    notes: list[str] = field(default_factory=list)
    platform_launcher: str | None = None
    platform_shortcut: str | None = None

    @property
    def platform_managed(self) -> bool:
        return self.platform_launcher is not None


class FakeSession:
    #: These tests are about a *running* SOLIDWORKS whose process is strained, so the
    #: double is attached. Install notes are only reported as issues when it is not.
    attached = True

    def install(self) -> FakeInstall:
        return FakeInstall()


class FakeWorker:
    def __init__(self, inflight: dict[str, Any] | None = None) -> None:
        self._inflight = inflight

    def health_snapshot(self) -> dict[str, Any]:
        return {"thread_alive": True, "apartment": "STA", "inflight": self._inflight}


def _health(monkeypatch, resources, *, inflight=None):
    from swmcp.catalog.registry import OPS, load_all_ops
    from swmcp.context import OpContext

    load_all_ops()
    monkeypatch.setattr(system_handlers, "process_resources", lambda: resources)
    ctx = OpContext(
        session=FakeSession(),
        config=SwmcpConfig(),
        checkpoints=None,
        spec=OPS["sw_health"],
        request_id="test",
        worker=FakeWorker(inflight),
    )
    return system_handlers.health(ctx, HealthArgs(probe=False))


def _resources(*, private: int, handles: int) -> dict[str, Any]:
    strained = private >= STRAINED_PRIVATE_BYTES or handles >= STRAINED_HANDLE_COUNT
    return {
        "process_id": 1234,
        "private_bytes": private,
        "private_mb": round(private / 1024**2, 1),
        "working_set_bytes": private // 4,
        "handle_count": handles,
        "strained": strained,
        "critical": private >= CRITICAL_PRIVATE_BYTES,
        "note": "..." if strained else None,
    }


def test_a_healthy_session_reports_its_resources_without_complaint(monkeypatch):
    result = _health(monkeypatch, _resources(private=2 * 1024**3, handles=5_000))

    assert result.healthy is True
    assert result.issues == []
    assert result.process["private_mb"] == pytest.approx(2048.0)
    assert result.process["strained"] is False


def test_a_session_holding_too_much_memory_is_called_out(monkeypatch):
    """The condition that produced a 60-second read that never returned."""
    result = _health(monkeypatch, _resources(private=12 * 1024**3, handles=44_662))

    assert result.healthy is False
    assert len(result.issues) == 1
    assert "Restart SOLIDWORKS" in result.issues[0]
    assert "12288" in result.issues[0] or "MB" in result.issues[0]
    assert result.process["strained"] is True


def test_handles_alone_are_enough_to_raise_it(monkeypatch):
    """Handle exhaustion arrives before memory does on some machines."""
    result = _health(monkeypatch, _resources(private=1 * 1024**3, handles=40_000))

    assert result.healthy is False
    assert "handles" in result.issues[0]


def test_a_long_running_call_on_a_strained_process_says_which_it_probably_is(monkeypatch):
    """"Check for a modal dialog" is the wrong advice when the process is thrashing."""
    result = _health(
        monkeypatch,
        _resources(private=12 * 1024**3, handles=44_000),
        inflight={"label": "sw_doc_new", "elapsed_s": 180.0},
    )

    stalled = [issue for issue in result.issues if "sw_doc_new" in issue]
    assert stalled
    assert "paging" in stalled[0]
    assert "modal dialog" not in stalled[0]


def test_a_long_running_call_on_a_healthy_process_still_suggests_a_dialog(monkeypatch):
    result = _health(
        monkeypatch,
        _resources(private=1 * 1024**3, handles=5_000),
        inflight={"label": "sw_feature_hole", "elapsed_s": 214.0},
    )

    stalled = [issue for issue in result.issues if "sw_feature_hole" in issue]
    assert stalled
    assert "modal dialog" in stalled[0]


def test_health_still_answers_when_the_process_cannot_be_read(monkeypatch):
    """WMI can fail too; that must not take the health report down with it."""
    result = _health(monkeypatch, None)

    assert result.healthy is True
    assert result.process is None


def test_how_to_start_solidworks_is_keyed_to_the_process_not_the_attachment(monkeypatch):
    """The bug this pins: health never attaches, so `attached` is always False here.

    Keying the launch advice off ``session.attached`` made every cold health check on a
    perfectly good machine report "SOLIDWORKS is not running" — while reporting its
    memory in the same payload. Whether it is running is the WMI process read, which is
    the whole reason health can answer while COM is wedged.
    """
    shortcut = "SOLIDWORKS Design.lnk"

    class Managed(FakeSession):
        # Health does not attach, so this is False even while SOLIDWORKS runs.
        attached = False

        def install(self) -> FakeInstall:
            return FakeInstall(platform_launcher="CATSTART.exe", platform_shortcut=shortcut)

    running = _health_with(
        monkeypatch, Managed(), _resources(private=1 * 1024**3, handles=5_000)
    )
    assert running.issues == [], (
        "a running SOLIDWORKS must not be told how to start itself, however "
        "unattached the session happens to be"
    )
    assert running.healthy is True

    stopped = _health_with(monkeypatch, Managed(), None)
    assert any(shortcut in issue for issue in stopped.issues), (
        "with no process at all, naming the shortcut to run is the whole point"
    )


def test_a_classic_install_is_never_told_to_use_the_platform(monkeypatch):
    """The advice is specific to a managed install; a normal one can just be started."""
    stopped = _health_with(monkeypatch, FakeSession(), None)

    assert not any("Platform" in issue for issue in stopped.issues)


def _health_with(monkeypatch, session, resources):
    from swmcp.catalog.registry import OPS, load_all_ops
    from swmcp.context import OpContext

    load_all_ops()
    monkeypatch.setattr(system_handlers, "process_resources", lambda: resources)
    ctx = OpContext(
        session=session,
        config=SwmcpConfig(),
        checkpoints=None,
        spec=OPS["sw_health"],
        request_id="test",
        worker=FakeWorker(None),
    )
    return system_handlers.health(ctx, HealthArgs(probe=False))


def test_the_thresholds_are_stated_rather_than_buried():
    assert STRAINED_PRIVATE_BYTES == 8 * 1024**3
    assert STRAINED_HANDLE_COUNT == 30_000


def test_the_advisory_threshold_and_the_measured_wall_are_different_numbers():
    """Two readings, two claims. Collapsing them is what made a batch stop too early.

    ``strained`` says "worth watching" and is what ``sw_health`` reports. ``critical``
    says "calls will hang" and is what anything acting on the reading must use. If these
    were ever set equal, every consumer of the advisory number would silently become a
    consumer of the wall.
    """
    from swmcp.com.install import CRITICAL_PRIVATE_BYTES

    assert CRITICAL_PRIVATE_BYTES > STRAINED_PRIVATE_BYTES


def test_a_session_between_the_two_is_reported_as_strained_but_not_critical():
    resources = _resources(private=STRAINED_PRIVATE_BYTES + 1024**3, handles=1000)
    assert resources["strained"] is True
    assert resources["critical"] is False
