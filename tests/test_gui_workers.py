"""Worker lifecycle tests. Every test name contains `thread` so `pytest -k thread` selects them."""
import gc
import threading
import time
import weakref

import pytest
from PySide6.QtCore import QObject, QThreadPool

from wflash.core.errors import CancelledError, GitLabError
from wflash.gui import workers
from wflash.gui.workers import WorkerRegistry

pytestmark = pytest.mark.gui


class Receiver(QObject):
    """Main-thread QObject whose bound methods are the slots (never lambdas)."""

    def __init__(self):
        super().__init__()
        self.succeeded, self.failed, self.finished = [], [], []
        self.progress, self.steps = [], []
        self.slot_threads = set()
        self.registry_saw_running = []
        self.registry = None

    def on_succeeded(self, key, result):
        self.slot_threads.add(threading.get_ident())
        self.succeeded.append((key, result))

    def on_failed(self, key, exc):
        self.slot_threads.add(threading.get_ident())
        self.failed.append((key, exc))

    def on_finished(self, key):
        self.slot_threads.add(threading.get_ident())
        self.registry_saw_running.append(self.registry.is_running(key))
        self.finished.append(key)

    def on_progress(self, percent, message):
        self.slot_threads.add(threading.get_ident())
        self.progress.append((percent, message))

    def on_step(self, text):
        self.steps.append(text)


@pytest.fixture
def env(qtbot):
    pool = QThreadPool()
    registry = WorkerRegistry(pool)
    receiver = Receiver()
    receiver.registry = registry
    yield registry, receiver
    registry.cancel_all()
    assert registry.wait_idle(5.0)


def start(registry, receiver, fn, name="t"):
    return registry.start(
        name,
        fn,
        on_succeeded=receiver.on_succeeded,
        on_failed=receiver.on_failed,
        on_finished=receiver.on_finished,
        on_progress=receiver.on_progress,
        on_step=receiver.on_step,
    )


def test_thread_success_delivers_result_on_gui_thread(env, qtbot):
    registry, rx = env
    worker_threads = []

    def fn(ctx):
        worker_threads.append(threading.get_ident())
        ctx.step("S1")
        ctx.progress(50, "half")
        return 42

    key = start(registry, rx, fn, "ok")
    assert key.startswith("ok-")
    qtbot.waitUntil(lambda: rx.finished == [key], timeout=3000)
    assert rx.succeeded == [(key, 42)]
    assert rx.steps == ["S1"] and rx.progress == [(50, "half")]
    assert rx.slot_threads == {threading.get_ident()}
    assert worker_threads and worker_threads[0] != threading.get_ident()


def test_thread_failure_and_wflash_error_are_emitted(env, qtbot):
    registry, rx = env

    def boom(ctx):
        raise ValueError("nope")

    def gitlab(ctx):
        raise GitLabError("401", hint="token")

    k1 = start(registry, rx, boom, "boom")
    k2 = start(registry, rx, gitlab, "gl")
    qtbot.waitUntil(lambda: len(rx.finished) == 2, timeout=3000)
    errors = dict(rx.failed)
    assert isinstance(errors[k1], ValueError)
    assert isinstance(errors[k2], GitLabError) and errors[k2].hint == "token"
    assert rx.succeeded == []


def test_thread_cancel_inside_blocking_call(env, qtbot):
    registry, rx = env
    started = threading.Event()

    def fn(ctx):
        started.set()
        while not ctx.cancel.wait(0.01):
            pass
        ctx.cancel.raise_if_cancelled()

    key = start(registry, rx, fn, "cancel")
    assert started.wait(2)
    registry.cancel(key)
    qtbot.waitUntil(lambda: rx.finished == [key], timeout=3000)
    assert isinstance(rx.failed[0][1], CancelledError)


def test_thread_progress_callback_honours_cancel(env, qtbot):
    registry, rx = env
    reported = []

    def fn(ctx):
        ctx.cancel.cancel()
        try:
            ctx.progress(10, "after cancel")
        except CancelledError:
            reported.append("raised")
            raise
        return "not reached"

    start(registry, rx, fn, "progress-cancel")
    qtbot.waitUntil(lambda: len(rx.finished) == 1, timeout=3000)
    assert reported == ["raised"]
    assert isinstance(rx.failed[0][1], CancelledError)
    assert rx.succeeded == []


def test_thread_finished_slot_sees_worker_released_but_still_referenced(env, qtbot):
    registry, rx = env
    gate = threading.Event()
    key = start(registry, rx, lambda ctx: gate.wait(2), "order")
    assert registry.is_running(key) and registry.has_running("order")
    gate.set()
    qtbot.waitUntil(lambda: rx.finished == [key], timeout=3000)
    assert rx.registry_saw_running == [False]  # button states computed in the slot are accurate
    assert registry.running_keys() == []
    assert rx.succeeded == [(key, True)]


def test_thread_registry_rejects_lambda_and_plain_function_slots(env):
    registry, rx = env

    def plain(key, result):
        pass

    with pytest.raises(TypeError, match="rule 8"):
        registry.start("bad", lambda ctx: None, on_succeeded=lambda k, r: None, on_failed=rx.on_failed)
    with pytest.raises(TypeError, match="rule 8"):
        registry.start("bad", lambda ctx: None, on_succeeded=plain, on_failed=rx.on_failed)
    assert registry.running_keys() == []


def test_thread_registry_refuses_start_from_pool_thread(env, qtbot):
    registry, rx = env
    errors = []

    def nested(ctx):
        try:
            registry.start("nested", lambda c: None, on_succeeded=rx.on_succeeded, on_failed=rx.on_failed)
        except RuntimeError as exc:
            errors.append(str(exc))

    start(registry, rx, nested, "outer")
    qtbot.waitUntil(lambda: len(rx.finished) == 1, timeout=3000)
    assert errors and "GUI thread" in errors[0]


def test_thread_signals_outlive_dropped_caller_reference(env, qtbot):
    registry, rx = env
    release = threading.Event()

    def fn(ctx):
        release.wait(2)
        ctx.progress(100, "late")
        return "late result"

    key = start(registry, rx, fn, "late")
    worker = registry.worker(key)
    signals = worker.signals
    del worker, signals  # the caller keeps nothing; the registry must
    release.set()
    qtbot.waitUntil(lambda: rx.finished == [key], timeout=3000)
    assert rx.succeeded == [(key, "late result")]


def test_thread_wait_idle_pumps_events_and_is_bounded(env):
    registry, rx = env
    gate = threading.Event()

    def slow(ctx):
        gate.wait(5)
        return "slow"

    key = start(registry, rx, slow, "slow")
    t0 = time.monotonic()
    assert registry.wait_idle(0.3) is False
    assert 0.25 <= time.monotonic() - t0 < 2.0
    gate.set()
    assert registry.wait_idle(5.0) is True
    # finished was delivered by wait_idle's own event pumping, not by qtbot
    assert rx.finished == [key]


def test_thread_abandon_parks_running_worker(env):
    registry, rx = env
    gate = threading.Event()
    key = start(registry, rx, lambda ctx: gate.wait(5), "stuck")
    before = len(workers._ABANDONED)
    assert registry.abandon_running() == [key]
    assert len(workers._ABANDONED) == before + 1
    assert registry.running_keys() == []
    gate.set()
    assert workers._ABANDONED[-1].done.wait(5)


def test_thread_many_workers_back_to_back(env, qtbot):
    registry, rx = env
    keys = [start(registry, rx, lambda ctx, i=i: i, f"n{i}") for i in range(50)]
    qtbot.waitUntil(lambda: len(rx.finished) == 50, timeout=10000)
    assert sorted(r for _, r in rx.succeeded) == list(range(50))
    assert set(rx.finished) == set(keys)
    assert registry.running_keys() == []


def test_thread_just_finished_worker_stays_referenced_until_a_later_event(env, qtbot):
    registry, rx = env
    first = start(registry, rx, lambda ctx: 1, "first")
    qtbot.waitUntil(lambda: rx.finished == [first], timeout=3000)
    assert [w.key for w in registry._retired] == [first]  # its owner slot may still be queued
    second = start(registry, rx, lambda ctx: 2, "second")
    qtbot.waitUntil(lambda: rx.finished == [first, second], timeout=3000)
    assert [w.key for w in registry._retired] == [second]


def test_thread_pool_retains_finished_runnables(env):
    registry, rx = env
    refs = []
    for i in range(20):
        key = start(registry, rx, lambda ctx, i=i: i, f"keep{i}")
        refs.append(weakref.ref(registry.worker(key)))
        assert registry.wait_idle(5.0)
    registry._retired.clear()  # drop the registry's own references too
    gc.collect()
    alive = sum(1 for r in refs if r() is not None)
    assert alive == 20, (
        f"only {alive}/20 finished Workers alive: a PySide upgrade changed QThreadPool runnable "
        "retention; the deallocation race (CLAUDE.md rule 6) must be revisited, see "
        "docs/walkthrough.md Phase 1.12"
    )
