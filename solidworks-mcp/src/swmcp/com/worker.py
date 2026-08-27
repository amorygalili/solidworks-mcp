"""SYS-003/004/005: one STA thread owns every COM call.

SOLIDWORKS COM is a single-threaded apartment. Both sibling Python projects only take
a lock, which serializes calls but leaves *apartment affinity* unhandled: a proxy
cached on one thread is not legally usable from another, and the resulting corruption
is intermittent and miserable to diagnose. Here a single thread calls
``CoInitializeEx(COINIT_APARTMENTTHREADED)`` once and every job is marshalled to it.

Two decisions worth stating plainly:

**Idle pumping.** An STA that never pumps its message queue can deadlock when the
server marshals a callback back to us. The idle loop pumps between jobs.

**No retry for mutations.** A retried extrude leaves a second body behind, so a
non-idempotent call is attempted exactly once. When one times out the caller is told
the outcome is *unknown* rather than being given a false failure — which is precisely
why auto-checkpointing is load-bearing. Only read-only calls retry, and only on the
HRESULTs that mean "busy, ask again".
"""

from __future__ import annotations

import asyncio
import contextlib
import queue
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any, Literal

from swmcp.com.classify import classify
from swmcp.config import SwmcpConfig, get_config
from swmcp.errors import SwMcpError, timeout_error, worker_error
from swmcp.timing import elapsed_s, seconds_to_ms

JobKind = Literal["read", "mutation"]

_SHUTDOWN = object()
_IDLE_SLICE_S = 0.05


@dataclass(slots=True)
class _Job:
    fn: Callable[[Any], Any]
    future: Future
    label: str
    kind: JobKind
    enqueued_at: float


@dataclass
class WorkerStats:
    total: int = 0
    failed: int = 0
    retry_later: int = 0
    reattaches: int = 0
    durations_s: dict[str, list[float]] = field(default_factory=dict)

    def record(self, label: str, seconds: float, *, ok: bool) -> None:
        self.total += 1
        if not ok:
            self.failed += 1
        samples = self.durations_s.setdefault(label, [])
        samples.append(seconds)
        if len(samples) > 50:
            del samples[0]

    def as_dict(self) -> dict[str, Any]:
        def percentile(values: list[float], fraction: float) -> float:
            if not values:
                return 0.0
            ordered = sorted(values)
            index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
            return seconds_to_ms(ordered[index])

        return {
            "total": self.total,
            "failed": self.failed,
            "busy_retries": self.retry_later,
            "reattaches": self.reattaches,
            "latency_ms": {
                label: {"p50": percentile(samples, 0.5), "p95": percentile(samples, 0.95)}
                for label, samples in sorted(self.durations_s.items())
            },
        }


class StaWorker:
    """A dedicated STA thread with a FIFO job queue."""

    def __init__(
        self,
        config: SwmcpConfig | None = None,
        *,
        session_factory: Callable[[], Any] | None = None,
        com_init: Callable[[], None] | None = None,
        com_uninit: Callable[[], None] | None = None,
        pump: Callable[[], None] | None = None,
    ):
        self._config = config or get_config()
        self._session_factory = session_factory
        self._com_init = com_init if com_init is not None else _default_com_init
        self._com_uninit = com_uninit if com_uninit is not None else _default_com_uninit
        self._pump = pump if pump is not None else _default_pump

        self._queue: queue.Queue[Any] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="swmcp-sta", daemon=True)
        self._ready = threading.Event()
        self._start_error: BaseException | None = None
        self._session: Any = None
        self._lock = threading.Lock()
        self._inflight: tuple[str, float] | None = None
        self._thread_ident: int | None = None
        self._stats = WorkerStats()
        self._stopped = False

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> StaWorker:
        if self._thread.is_alive():
            return self
        self._thread.start()
        if not self._ready.wait(self._config.worker_start_timeout_s):
            raise SwMcpError(
                worker_error(
                    "WORKER_START_TIMEOUT",
                    "The COM worker thread did not become ready in time.",
                    remediation=["Check that pywin32 is installed and importable."],
                )
            )
        if self._start_error is not None:
            raise SwMcpError(
                worker_error(
                    "WORKER_START_FAILED",
                    f"The COM worker thread failed to initialize: {self._start_error}",
                    remediation=["Confirm pywin32 is installed for this interpreter."],
                )
            )
        return self

    def stop(self, timeout: float = 5.0) -> None:
        if not self._thread.is_alive():
            return
        self._stopped = True
        self._queue.put(_SHUTDOWN)
        self._thread.join(timeout)

    @property
    def thread_ident(self) -> int | None:
        return self._thread_ident

    def _run(self) -> None:
        self._thread_ident = threading.get_ident()
        try:
            self._com_init()
        except BaseException as exc:
            self._start_error = exc
            self._ready.set()
            return

        self._ready.set()
        try:
            while True:
                job = self._next_job()
                if job is None:
                    continue
                if job is _SHUTDOWN:
                    break
                self._execute(job)
        finally:
            self._session = None
            # Shutdown must not raise out of the thread.
            with contextlib.suppress(Exception):
                self._com_uninit()

    def _next_job(self) -> Any:
        """Block briefly, then pump, so the apartment never goes deaf."""
        try:
            return self._queue.get(timeout=_IDLE_SLICE_S)
        except queue.Empty:
            self._pump()
            return None

    def _execute(self, job: _Job) -> None:
        if not job.future.set_running_or_notify_cancel():
            return
        started = time.monotonic()
        with self._lock:
            self._inflight = (job.label, started)
        ok = True
        try:
            job.future.set_result(self._invoke(job))
        except BaseException as exc:
            ok = False
            job.future.set_exception(exc)
        finally:
            with self._lock:
                self._inflight = None
            self._stats.record(job.label, time.monotonic() - started, ok=ok)

    # -- invocation --------------------------------------------------------

    def _ensure_session(self) -> Any:
        if self._session is None and self._session_factory is not None:
            self._session = self._session_factory()
        return self._session

    def _invoke(self, job: _Job) -> Any:
        session = self._ensure_session()
        attempts = self._config.retry_attempts if job.kind == "read" else 1
        delay = self._config.retry_initial_s
        last: BaseException | None = None

        for attempt in range(1, attempts + 1):
            try:
                return job.fn(session)
            except Exception as exc:
                verdict = classify(exc)
                last = exc

                if verdict.disconnected and job.kind == "read" and attempt < attempts:
                    # The session died; one reattach is worth trying for a pure read.
                    self._session = None
                    self._stats.reattaches += 1
                    session = self._ensure_session()
                    continue

                if not (verdict.retryable and job.kind == "read" and attempt < attempts):
                    raise

                self._stats.retry_later += 1
                time.sleep(delay)
                delay = min(delay * 2.5, self._config.retry_max_s)

        raise last  # pragma: no cover - the loop always returns or raises

    # -- submission --------------------------------------------------------

    def submit(self, fn: Callable[[Any], Any], *, label: str, kind: JobKind = "read") -> Future:
        if self._stopped or not self._thread.is_alive():
            self.start()
        future: Future = Future()
        self._queue.put(
            _Job(fn=fn, future=future, label=label, kind=kind, enqueued_at=time.monotonic())
        )
        return future

    def call(
        self,
        fn: Callable[[Any], Any],
        *,
        label: str,
        kind: JobKind = "read",
        timeout_s: float | None = None,
    ) -> Any:
        """Synchronous submit-and-wait."""
        limit = timeout_s if timeout_s is not None else self._config.call_timeout_s
        future = self.submit(fn, label=label, kind=kind)
        try:
            return future.result(timeout=limit)
        except TimeoutError:
            raise SwMcpError(self._timeout_envelope(label, limit)) from None

    async def acall(
        self,
        fn: Callable[[Any], Any],
        *,
        label: str,
        kind: JobKind = "read",
        timeout_s: float | None = None,
    ) -> Any:
        """Await a job without blocking the event loop."""
        limit = timeout_s if timeout_s is not None else self._config.call_timeout_s
        future = self.submit(fn, label=label, kind=kind)
        wrapped = asyncio.wrap_future(future)
        try:
            # Shielded: cancelling the await must not pretend the COM call stopped.
            return await asyncio.wait_for(asyncio.shield(wrapped), limit)
        except TimeoutError:
            raise SwMcpError(self._timeout_envelope(label, limit)) from None

    def _timeout_envelope(self, label: str, limit: float):
        return timeout_error(
            "WORKER_OUTCOME_UNKNOWN",
            f"{label} did not complete within {limit:.0f}s. It may still be executing "
            f"inside SOLIDWORKS. It was not retried and could not be cancelled.",
            context={
                "label": label,
                "timeout_s": limit,
                "queue_depth": self.queue_depth(),
                "inflight": self.inflight(),
            },
            remediation=[
                "Check SOLIDWORKS for a modal dialog; one blocks every API call indefinitely.",
                "Call the health operation to see whether the worker is still on this call.",
                "Inspect the model and the checkpoint list BEFORE repeating a mutating call.",
            ],
        )

    # -- diagnostics -------------------------------------------------------

    def queue_depth(self) -> int:
        return self._queue.qsize()

    def inflight(self) -> dict[str, Any] | None:
        with self._lock:
            current = self._inflight
        if current is None:
            return None
        return {"label": current[0], "elapsed_s": elapsed_s(current[1])}

    def health_snapshot(self) -> dict[str, Any]:
        """State without touching COM or joining the queue.

        A health check that queues behind a wedged worker cannot report the wedge.
        This one answers even while the worker is stuck.
        """
        return {
            "thread_alive": self._thread.is_alive(),
            "apartment": "STA",
            "thread_ident": self._thread_ident,
            "queue_depth": self.queue_depth(),
            "inflight": self.inflight(),
            "session_attached": self._session is not None,
            "calls": self._stats.as_dict(),
        }


def _default_com_init() -> None:  # pragma: no cover - Windows-only
    import pythoncom

    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)


def _default_com_uninit() -> None:  # pragma: no cover - Windows-only
    import pythoncom

    pythoncom.CoUninitialize()


def _default_pump() -> None:  # pragma: no cover - Windows-only
    import pythoncom

    pythoncom.PumpWaitingMessages()
