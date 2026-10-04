"""Flash sequence: connect → validate entries → set paths → download → reset, with rollback."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from wflash.core.cancel import CancelToken
from wflash.core.debug_bundle import DebugContext
from wflash.core.errors import FlashError, MappingError, WFlashError
from wflash.core.file_matcher import MappingRow
from wflash.core.logging_setup import get_logger
from wflash.core.winidea_adapter import ProgressCallback, WinIDEAAdapter

log = get_logger("flash")

ROLLBACK_FAILED_HINT = (
    "ROLLBACK FAILED \u2014 the winIDEA workspace may still point to the new files; "
    "check the download/symbol file list in winIDEA before flashing again. "
)


class Step(str, Enum):
    CONNECT = "Connecting to winIDEA"
    VALIDATE = "Checking workspace entries"
    SET_PATHS = "Updating file paths"
    DOWNLOAD = "Downloading to external flash"
    RESET = "Resetting target"
    ROLLBACK = "Restoring previous paths"
    DONE = "Done"


@dataclass
class FlashRequest:
    instance_id: str
    mapping: list[MappingRow]
    reset: bool = True
    run: bool = False
    timeout_s: int = 600


class FlashWorkflow:
    def __init__(
        self,
        adapter: WinIDEAAdapter,
        ctx: DebugContext,
        on_step: Callable[[Step], None] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self.adapter = adapter
        self.ctx = ctx
        self._on_step = on_step or (lambda step: None)
        self._on_progress = on_progress or (lambda percent, message: None)
        self._rollback_failed = False

    def run(self, req: FlashRequest, cancel: CancelToken) -> None:
        missing = [row.target for row in req.mapping if not row.ok]
        if missing:
            raise MappingError(
                f"No file selected for: {', '.join(missing)}",
                hint="Choose a file for every red row in the mapping table.",
            )
        gone = [row.selected.name for row in req.mapping if row.selected is None or not row.selected.is_file()]
        if gone:
            raise MappingError(
                f"Selected file no longer exists: {', '.join(gone)}",
                hint="The artifact cache may have been cleared or pruned. Download the artifact again.",
            )
        self.ctx.mapping = [row.to_dict() for row in req.mapping]
        self._rollback_failed = False
        try:
            self._step(Step.CONNECT)
            self.adapter.connect(req.instance_id)
            try:
                self.ctx.adapter_info = dict(self.adapter.get_info())
                log.info("winIDEA: %s", self.ctx.adapter_info)
                self._run_connected(req, cancel)
            finally:
                self._disconnect()
        except WFlashError as exc:
            self._mark_rollback_failed(exc)
            raise
        except Exception as exc:
            self.ctx.add_error(exc)
            wrapped = FlashError(f"{type(exc).__name__}: {exc}")
            self._mark_rollback_failed(wrapped)
            raise wrapped from exc
        self._step(Step.DONE)

    def _run_connected(self, req: FlashRequest, cancel: CancelToken) -> None:
        self._step(Step.VALIDATE)
        current = self._read_current("before")
        self._check_targets(req.mapping, current)
        old = {(row.kind, row.target): current[row.kind][row.target] for row in req.mapping}
        written: list[tuple[str, str, str]] = []
        cancel.raise_if_cancelled()
        try:
            self._step(Step.SET_PATHS)
            for row in req.mapping:
                # Recorded before the call: a set that raises may still have been applied.
                written.append((row.kind, row.target, old[(row.kind, row.target)]))
                self._set_path(row.kind, row.target, str(row.selected.resolve()))
            self._read_current("after_set")
            cancel.raise_if_cancelled()
            self._step(Step.DOWNLOAD)
            self.adapter.download(self._on_progress, cancel, req.timeout_s)
        except BaseException:
            self._rollback(written)
            raise
        if req.reset:
            self._step(Step.RESET)
            self.adapter.reset(run=req.run)

    def _read_current(self, label: str) -> dict[str, dict[str, str]]:
        programs = self.adapter.read_programs()
        applications = self.adapter.read_applications()
        self.ctx.snapshot(label, programs, applications)
        return {
            "program": {e.name: e.path for e in programs},
            "application": {e.name: e.path for e in applications},
        }

    def _check_targets(self, mapping: list[MappingRow], current: dict[str, dict[str, str]]) -> None:
        missing = [f"{row.kind} '{row.target}'" for row in mapping if row.target not in current[row.kind]]
        if missing:
            raise MappingError(
                "Entries not found in the winIDEA workspace: " + ", ".join(missing),
                hint=(
                    f"Workspace programs: {sorted(current['program'])}; "
                    f"applications: {sorted(current['application'])}. Update the profile to use these names."
                ),
            )

    def _set_path(self, kind: str, target: str, path: str) -> None:
        log.info("Set %s '%s' -> %s", kind, target, path)
        if kind == "program":
            self.adapter.set_program_path(target, path)
        else:
            self.adapter.set_symbol_path(target, path)

    def _rollback(self, written: list[tuple[str, str, str]]) -> None:
        try:
            self._step(Step.ROLLBACK)
        except Exception:
            log.warning("Step callback failed for ROLLBACK; continuing with restore", exc_info=True)
        restored_all = True
        for kind, target, old in written:
            try:
                self._set_path(kind, target, old)
            except Exception as exc:
                restored_all = False
                self._rollback_failed = True
                log.error("Rollback failed for %s '%s'; it may still point to the new file: %s", kind, target, exc)
                self.ctx.add_error(exc)
        if not restored_all:
            return
        try:
            self._read_current("after_rollback")
        except Exception as exc:
            log.error("Snapshot after rollback failed: %s", exc)
            self.ctx.add_error(exc)

    def _mark_rollback_failed(self, exc: WFlashError) -> None:
        if self._rollback_failed:
            exc.rollback_failed = True
            if not exc.hint.startswith(ROLLBACK_FAILED_HINT):
                exc.hint = ROLLBACK_FAILED_HINT + exc.hint

    def _disconnect(self) -> None:
        try:
            self.adapter.disconnect()
        except Exception:
            log.warning("Disconnect from winIDEA failed", exc_info=True)

    def _step(self, step: Step) -> None:
        log.info("== %s ==", step.value)
        self._on_step(step)
