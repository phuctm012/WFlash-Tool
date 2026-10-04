"""Run blocking work on a QThreadPool and report back to the GUI thread through Qt signals.

Threading model (CLAUDE.md "Threading model"; the numbers below refer to its rules):

- `core/` never sees Qt. A job receives a `WorkerContext` of plain callbacks plus a
  `CancelToken`; only `WorkerSignals` turns those into Qt signals.
- Rule 1/2: `WorkerSignals` is created in `Worker.__init__`, i.e. on the main thread, and
  is owned by the `Worker`. `WorkerRegistry` keeps the `Worker` (and so its signals)
  referenced until its `finished` signal has been handled on the main thread, and until
  `run()` has passed its last statement (see `_purge_retired`).
- Rule 6: every `connect()` happens in `WorkerRegistry.start()` on the main thread,
  before the runnable is handed to the pool. Nothing in `Worker.run()` connects,
  disconnects, moves or deletes a QObject.
- Rule 8: `WorkerRegistry.start()` refuses any slot that is not a bound method of a
  QObject (a lambda or a plain function has no thread affinity, so a queued call
  cannot be made and it would silently run on the pool thread).
- Rule 3: `wait_idle()` waits with a deadline and pumps the event loop between
  attempts. Nothing here calls `QThreadPool.waitForDone()`.
- Rule 7: `WorkerContext.progress` raises `CancelledError` once cancel was requested,
  so a blocking call that reports progress is stopped from inside.
"""
from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QRunnable, QThread, QThreadPool, Signal

from wflash.core.cancel import CancelToken
from wflash.core.errors import CancelledError, WFlashError
from wflash.core.logging_setup import get_logger

log = get_logger("worker")

# Workers still running when their owner gave up waiting (window closed, wait timed out).
# Parked here for the rest of the process so their signals object is never deleted
# while run() can still emit (CLAUDE.md threading rule 1).
_ABANDONED: list["Worker"] = []


class WorkerSignals(QObject):
    """Signals of one Worker. Every signal carries the worker key first."""

    progress = Signal(object, str)  # percent (int | None), message
    step = Signal(str)
    succeeded = Signal(str, object)  # key, result
    failed = Signal(str, object)  # key, exception
    finished = Signal(str)  # key; always the last signal of a worker


@dataclass
class WorkerContext:
    cancel: CancelToken
    progress: Callable[[int | None, str], None]
    step: Callable[[str], None]


class Worker(QRunnable):
    def __init__(self, key: str, fn: Callable[[WorkerContext], Any]) -> None:
        super().__init__()
        # autoDelete=False stops Qt from deleting the C++ object under the Python wrapper
        # (with the default True the pool destroys it as soon as run() returns: a
        # use-after-free, CLAUDE.md threading rule 2).
        # Lifetime: PySide6 (verified on 6.11) keeps every started runnable referenced by
        # the QThreadPool for the pool's lifetime. That retention is what keeps
        # WorkerSignals alive (rule 1) and guarantees the last reference is never dropped
        # on a pool thread (rule 6). WorkerRegistry's references are belt-and-braces plus
        # idle tracking. Per-operation memory growth (one small Worker) is accepted; do NOT
        # add a release path. See the WorkerRegistry docstring and walkthrough Phase 1.12.
        self.setAutoDelete(False)
        self.key = key
        self._fn = fn
        self.signals = WorkerSignals()  # created on the main thread (rule 1, rule 6)
        self.cancel = CancelToken()
        self.done = threading.Event()  # set as the very last statement of run()

    def _progress(self, percent: int | None, message: str) -> None:
        self.signals.progress.emit(percent, message)
        # Rule 7: a cancel is honoured inside the blocking call that reports progress.
        self.cancel.raise_if_cancelled()

    def run(self) -> None:
        try:
            ctx = WorkerContext(cancel=self.cancel, progress=self._progress, step=self.signals.step.emit)
            log.debug("Worker %s started", self.key)
            try:
                result = self._fn(ctx)
            except CancelledError as exc:
                log.warning("%s cancelled", self.key)
                self.signals.failed.emit(self.key, exc)
            except WFlashError as exc:
                log.error("%s failed: %s%s", self.key, exc, f" (hint: {exc.hint})" if exc.hint else "")
                log.debug("%s traceback", self.key, exc_info=True)
                self.signals.failed.emit(self.key, exc)
            except Exception as exc:
                log.exception("%s crashed: %s", self.key, exc)
                self.signals.failed.emit(self.key, exc)
            else:
                log.debug("Worker %s finished", self.key)
                self.signals.succeeded.emit(self.key, result)
        finally:
            self.signals.finished.emit(self.key)
            self.done.set()


def _require_qobject_slot(slot: Callable[..., Any] | None, name: str) -> None:
    if slot is None:
        return
    owner = getattr(slot, "__self__", None)
    if not isinstance(owner, QObject):
        raise TypeError(
            f"{name} must be a bound method of a QObject living on the GUI thread, got {slot!r} "
            "(CLAUDE.md threading rule 8: never connect a lambda or plain function to a pool-thread signal)"
        )


class WorkerRegistry(QObject):
    """Main-thread owner of every running Worker of one window.

    Lifetime note: PySide6 (verified on 6.11) keeps every started runnable referenced from
    the QThreadPool wrapper for the pool's lifetime, so the pool itself is the real lifetime
    guarantee for Worker and WorkerSignals (CLAUDE.md rules 1 and 6); releasing a runnable
    would let a connected QObject be deallocated on a pool thread. The references and the
    `_retired` list kept here are belt-and-braces plus idle tracking. Memory grows by one
    small Worker per operation, which is accepted.
    """

    def __init__(self, pool: QThreadPool, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = pool
        self._running: dict[str, Worker] = {}
        self._retired: list[Worker] = []
        self._counter = itertools.count(1)

    def start(
        self,
        name: str,
        fn: Callable[[WorkerContext], Any],
        *,
        on_succeeded: Callable[[str, Any], None],
        on_failed: Callable[[str, Any], None],
        on_finished: Callable[[str], None] | None = None,
        on_progress: Callable[[Any, str], None] | None = None,
        on_step: Callable[[str], None] | None = None,
    ) -> str:
        app = QCoreApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            raise RuntimeError("WorkerRegistry.start() must be called on the GUI thread")
        for slot, slot_name in (
            (on_succeeded, "on_succeeded"),
            (on_failed, "on_failed"),
            (on_finished, "on_finished"),
            (on_progress, "on_progress"),
            (on_step, "on_step"),
        ):
            _require_qobject_slot(slot, slot_name)
        self._purge_retired()
        key = f"{name}-{next(self._counter)}"
        worker = Worker(key, fn)
        signals = worker.signals
        signals.succeeded.connect(on_succeeded)
        signals.failed.connect(on_failed)
        if on_progress is not None:
            signals.progress.connect(on_progress)
        if on_step is not None:
            signals.step.connect(on_step)
        # Connected before the owner's finished slot, so that slot already sees the worker
        # as no longer running when it recomputes button states (the registry still keeps
        # the Worker referenced in `_retired`).
        signals.finished.connect(self._on_worker_finished)
        if on_finished is not None:
            signals.finished.connect(on_finished)
        self._running[key] = worker
        self._pool.start(worker)
        return key

    def _on_worker_finished(self, key: str) -> None:
        worker = self._running.pop(key, None)
        # Workers retired earlier: their owners' finished slots were queued before this
        # event and have run. The one finishing now is kept: its owner slot is still queued.
        self._purge_retired()
        if worker is not None:
            self._retired.append(worker)

    def _purge_retired(self) -> None:
        # Drop our reference only once run() has passed its last statement; the finished
        # signal is emitted a few statements before that.
        self._retired = [w for w in self._retired if not w.done.is_set()]

    def worker(self, key: str | None) -> Worker | None:
        return self._running.get(key) if key else None

    def is_running(self, key: str | None) -> bool:
        return bool(key) and key in self._running

    def running_keys(self) -> list[str]:
        return list(self._running)

    def has_running(self, prefix: str = "") -> bool:
        return any(key.startswith(prefix) for key in self._running)

    def cancel(self, key: str | None) -> None:
        worker = self.worker(key)
        if worker is not None:
            worker.cancel.cancel()

    def cancel_all(self) -> None:
        for worker in self._running.values():
            worker.cancel.cancel()

    def wait_idle(self, timeout_s: float) -> bool:
        """Pump events until every finished signal was handled, or the deadline passes.

        Rule 3: never block the GUI loop on the pool — the workers' queued signals can only
        be delivered while this loop runs.
        """
        deadline = time.monotonic() + timeout_s
        while self._running:
            if time.monotonic() >= deadline:
                return False
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            pending = next(iter(self._running.values()), None)
            if pending is not None:
                pending.done.wait(0.01)
        return True

    def abandon_running(self) -> list[str]:
        """Park still-running workers for the rest of the process; return their keys."""
        keys = list(self._running)
        for key in keys:
            worker = self._running.pop(key)
            log.warning("Worker %s did not stop in time; abandoning it", key)
            _ABANDONED.append(worker)
        _ABANDONED.extend(self._retired)
        self._retired = []
        return keys
