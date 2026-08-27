"""SYS-003/004/005: apartment affinity, serialization, retry scope, and diagnostics.

The COM calls are fakes, so all of this runs with no SOLIDWORKS.
"""

from __future__ import annotations

import threading
import time
from dataclasses import replace

import pytest

from swmcp.com.worker import StaWorker
from swmcp.config import SwmcpConfig
from swmcp.errors import SwMcpError
from tests.fakes.com import FakeComError

BASE = SwmcpConfig(retry_attempts=3, retry_initial_s=0.001, retry_max_s=0.004, call_timeout_s=5.0)


class FakeSession:
    def __init__(self):
        self.created_on = threading.get_ident()


@pytest.fixture
def worker():
    made = StaWorker(
        BASE,
        session_factory=FakeSession,
        com_init=lambda: None,
        com_uninit=lambda: None,
        pump=lambda: None,
    )
    made.start()
    yield made
    made.stop()


# --- apartment affinity and serialization -------------------------------------


def test_all_com_calls_share_one_sta_thread(worker):
    """The whole point: a proxy cached on one thread must never be used from another."""
    idents = [worker.call(lambda _s: threading.get_ident(), label=f"op{i}") for i in range(20)]
    assert len(set(idents)) == 1
    assert idents[0] != threading.get_ident(), "COM must not run on the calling thread"
    assert idents[0] == worker.thread_ident


def test_the_session_is_created_on_the_worker_thread(worker):
    session = worker.call(lambda s: s, label="session")
    assert session.created_on == worker.thread_ident


def test_jobs_run_one_at_a_time_in_order(worker):
    order: list[int] = []
    overlapping = threading.Event()
    running = threading.Lock()

    def body(index):
        def run(_session):
            if not running.acquire(blocking=False):
                overlapping.set()
            time.sleep(0.001)
            order.append(index)
            running.release()
            return index

        return run

    futures = [worker.submit(body(i), label=f"job{i}") for i in range(50)]
    results = [f.result(timeout=10) for f in futures]

    assert not overlapping.is_set(), "COM calls must never overlap"
    assert results == list(range(50))
    assert order == list(range(50)), "the queue must be FIFO"


def test_a_failing_job_does_not_kill_the_worker(worker):
    with pytest.raises(ValueError):
        worker.call(lambda _s: (_ for _ in ()).throw(ValueError("boom")), label="bad")
    assert worker.call(lambda _s: "still alive", label="good") == "still alive"


# --- retry policy -------------------------------------------------------------


class Flaky:
    def __init__(self, failures: int, hresult: int = 0x8001010A):
        self.remaining = failures
        self.attempts = 0
        self.hresult = hresult

    def __call__(self, _session):
        self.attempts += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise FakeComError(self.hresult, "SOLIDWORKS is busy")
        return "done"


def test_a_busy_read_is_retried_with_backoff(worker):
    flaky = Flaky(failures=2)
    assert worker.call(flaky, label="read", kind="read") == "done"
    assert flaky.attempts == 3


def test_a_mutation_is_attempted_exactly_once(worker):
    """A retried extrude leaves a second body behind. At-most-once is the safe default."""
    flaky = Flaky(failures=1)
    with pytest.raises(FakeComError):
        worker.call(flaky, label="mutate", kind="mutation")
    assert flaky.attempts == 1, "non-idempotent work must never be silently repeated"


def test_a_non_retryable_read_fails_immediately(worker):
    flaky = Flaky(failures=5, hresult=0x80070057)  # E_INVALIDARG
    with pytest.raises(FakeComError):
        worker.call(flaky, label="read", kind="read")
    assert flaky.attempts == 1


def test_retries_are_bounded(worker):
    flaky = Flaky(failures=99)
    with pytest.raises(FakeComError):
        worker.call(flaky, label="read", kind="read")
    assert flaky.attempts == BASE.retry_attempts


def test_a_disconnected_read_reattaches_once():
    sessions: list[FakeSession] = []

    def factory():
        session = FakeSession()
        sessions.append(session)
        return session

    made = StaWorker(
        BASE, session_factory=factory, com_init=lambda: None, com_uninit=lambda: None, pump=lambda: None
    ).start()
    try:
        state = {"first": True}

        def body(_session):
            if state["first"]:
                state["first"] = False
                raise FakeComError(0x800706BA, "RPC server unavailable")
            return "reconnected"

        assert made.call(body, label="read", kind="read") == "reconnected"
        assert len(sessions) == 2, "a dead session must be replaced, not reused"
        assert made.health_snapshot()["calls"]["reattaches"] == 1
    finally:
        made.stop()


# --- timeouts -----------------------------------------------------------------


def test_a_timeout_reports_the_outcome_as_unknown(worker):
    release = threading.Event()

    def slow(_session):
        release.wait(5)
        return "eventually"

    try:
        with pytest.raises(SwMcpError) as caught:
            worker.call(slow, label="sw_feature_hole", kind="mutation", timeout_s=0.05)

        envelope = caught.value.envelope
        assert envelope.code == "WORKER_OUTCOME_UNKNOWN"
        assert envelope.category == "timeout"
        assert "not retried" in envelope.message
        assert any("dialog" in step for step in envelope.remediation)
        assert any("checkpoint" in step for step in envelope.remediation)
    finally:
        release.set()


def test_health_answers_while_the_worker_is_wedged(worker):
    """A health check that queues behind the wedge cannot report the wedge."""
    release = threading.Event()
    worker.submit(lambda _s: release.wait(5), label="sw_feature_hole", kind="mutation")
    try:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and worker.inflight() is None:
            time.sleep(0.01)

        snapshot = worker.health_snapshot()
        assert snapshot["inflight"]["label"] == "sw_feature_hole"
        assert snapshot["inflight"]["elapsed_s"] >= 0
        assert snapshot["thread_alive"] is True
        assert snapshot["apartment"] == "STA"
    finally:
        release.set()


def test_queue_depth_is_visible_without_joining_the_queue(worker):
    release = threading.Event()
    worker.submit(lambda _s: release.wait(5), label="blocker", kind="mutation")
    try:
        for index in range(3):
            worker.submit(lambda _s, n=index: n, label="queued")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and worker.queue_depth() < 3:
            time.sleep(0.01)
        assert worker.queue_depth() >= 3
    finally:
        release.set()


# --- lifecycle and diagnostics ------------------------------------------------


def test_the_apartment_is_initialized_once_and_torn_down():
    events: list[str] = []
    made = StaWorker(
        BASE,
        session_factory=FakeSession,
        com_init=lambda: events.append("init"),
        com_uninit=lambda: events.append("uninit"),
        pump=lambda: None,
    ).start()
    for _ in range(5):
        made.call(lambda _s: None, label="noop")
    made.stop()
    assert events == ["init", "uninit"], "CoInitializeEx must happen exactly once per thread"


def test_the_idle_loop_pumps_the_message_queue():
    """An STA that never pumps can deadlock on a marshalled callback."""
    pumps = threading.Event()
    made = StaWorker(
        BASE,
        session_factory=FakeSession,
        com_init=lambda: None,
        com_uninit=lambda: None,
        pump=pumps.set,
    ).start()
    try:
        assert pumps.wait(2.0), "the worker must pump while idle"
    finally:
        made.stop()


def test_a_failed_apartment_init_is_reported_not_hung():
    made = StaWorker(
        replace(BASE, worker_start_timeout_s=2.0),
        session_factory=FakeSession,
        com_init=lambda: (_ for _ in ()).throw(ImportError("no pywin32")),
        com_uninit=lambda: None,
        pump=lambda: None,
    )
    with pytest.raises(SwMcpError) as caught:
        made.start()
    assert caught.value.envelope.code == "WORKER_START_FAILED"


def test_stats_record_latency_and_busy_retries(worker):
    worker.call(lambda _s: None, label="sw_doc_list")
    worker.call(Flaky(failures=1), label="sw_doc_list", kind="read")
    stats = worker.health_snapshot()["calls"]
    assert stats["total"] == 2
    assert stats["busy_retries"] == 1
    assert "sw_doc_list" in stats["latency_ms"]
    assert stats["latency_ms"]["sw_doc_list"]["p50"] >= 0


@pytest.mark.asyncio_skip
def test_acall_is_available_for_the_async_server(worker):
    import asyncio

    async def main():
        return await worker.acall(lambda _s: "async ok", label="async")

    assert asyncio.run(main()) == "async ok"


def test_acall_timeout_also_reports_unknown_outcome(worker):
    import asyncio

    release = threading.Event()

    async def main():
        return await worker.acall(
            lambda _s: release.wait(5), label="slow", kind="mutation", timeout_s=0.05
        )

    try:
        with pytest.raises(SwMcpError) as caught:
            asyncio.run(main())
        assert caught.value.envelope.code == "WORKER_OUTCOME_UNKNOWN"
    finally:
        release.set()
