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

    def run(self, req: FlashRequest, cancel: CancelToken) -> None:
        missing = [row.target for row in req.mapping if not row.ok]
        if missing:
            raise MappingError(
                f"No file selected for: {', '.join(missing)}",
                hint="Choose a file for every red row in the mapping table.",
            )
        self.ctx.mapping = [row.to_dict() for row in req.mapping]
        try:
            self._step(Step.CONNECT)
            self.adapter.connect(req.instance_id)
            try:
                self.ctx.adapter_info = dict(self.adapter.get_info())
                log.info("winIDEA: %s", self.ctx.adapter_info)
                self._run_connected(req, cancel)
            finally:
                self._disconnect()
        except WFlashError:
            raise
        except Exception as exc:
            raise FlashError(f"{type(exc).__name__}: {exc}") from exc
        self._step(Step.DONE)

    def _run_connected(self, req: FlashRequest, cancel: CancelToken) -> None:
        self._step(Step.VALIDATE)
        current = self._read_current("before")
        self._check_targets(req.mapping, current)
        backup = [(row.kind, row.target, current[row.kind][row.target]) for row in req.mapping]
        cancel.raise_if_cancelled()
        try:
            self._step(Step.SET_PATHS)
            for row in req.mapping:
                self._set_path(row.kind, row.target, str(row.selected.resolve()))
            self._read_current("after_set")
            cancel.raise_if_cancelled()
            self._step(Step.DOWNLOAD)
            self.adapter.download(self._on_progress, cancel, req.timeout_s)
        except BaseException:
            self._rollback(backup)
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

    def _rollback(self, backup: list[tuple[str, str, str]]) -> None:
        self._step(Step.ROLLBACK)
        try:
            for kind, target, old in backup:
                self._set_path(kind, target, old)
            self._read_current("after_rollback")
        except Exception as exc:
            log.error("Rollback failed; the workspace may still point to the new files: %s", exc)
            self.ctx.add_error(exc)

    def _disconnect(self) -> None:
        try:
            self.adapter.disconnect()
        except Exception:
            log.warning("Disconnect from winIDEA failed", exc_info=True)

    def _step(self, step: Step) -> None:
        log.info("== %s ==", step.value)
        self._on_step(step)
