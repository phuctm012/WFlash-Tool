"""Flash mixin: winIDEA instance list, Flash/Cancel, step and progress display, post-flash state.

The flash runs `FlashWorkflow` (core) in one worker named "flash". The workflow already
guarantees the rollback (Approach A); this mixin only has to start it, honour Cancel, and
show the outcome — including a failed rollback, which the user must never miss.

Host contract: `self.ui`, `self.adapter`, `self.profile`, `self.ctx`, `self._workers`,
`self._closing`, `self.show_error()`, `self.statusBar()`, `self.mapping_rows()` and
`self.mapping_complete()` (MappingTableMixin), `self.gitlab_busy()` (GitlabBrowserMixin).
"""
from __future__ import annotations

import dataclasses

from wflash.core.errors import CancelledError, WinIDEAError
from wflash.core.flash_workflow import FlashRequest, FlashWorkflow, Step
from wflash.core.logging_setup import get_logger
from wflash.core.winidea_adapter import InstanceInfo, WinIDEAAdapter
from wflash.gui.workers import WorkerContext

log = get_logger("ui.flash")


def safe_list_instances(adapter: WinIDEAAdapter) -> list[InstanceInfo]:
    """No winIDEA, no running instance and no probe are normal states, never exceptions."""
    try:
        return list(adapter.list_instances())
    except Exception as exc:
        log.warning("Listing winIDEA instances failed: %s", exc, exc_info=True)
        return []


def instance_data(info: InstanceInfo) -> dict:
    """What the instance combo stores; read back with currentData(), never from the text."""
    return {"instance_id": info.instance_id, "workspace": info.workspace, "tcp_port": info.tcp_port}


class FlashMixin:
    def _init_flash(self) -> None:
        self._flash_key: str | None = None
        self._flash_cancel_requested = False
        self._flash_error_during_close: BaseException | None = None
        self._instances_key: str | None = None
        self.ui.progressBar_flash.setRange(0, 100)
        self.ui.progressBar_flash.setValue(0)
        self.ui.pushButton_flash.clicked.connect(self.start_flash)
        self.ui.pushButton_cancelFlash.clicked.connect(self.cancel_flash)
        self.ui.pushButton_refreshInstances.clicked.connect(self.refresh_instances)
        self.ui.comboBox_instance.currentIndexChanged.connect(self._update_flash_controls)
        self.ui.checkBox_reset.toggled.connect(self._update_flash_controls)

    # -- state ------------------------------------------------------------------------
    def flash_active(self) -> bool:
        return self._workers.is_running(self._flash_key)

    def selected_instance(self) -> dict | None:
        data = self.ui.comboBox_instance.currentData()
        return data if isinstance(data, dict) else None

    def _update_flash_controls(self, *_args) -> None:
        flashing = self.flash_active()
        can_flash = (
            not flashing
            and not self._closing
            and not self.gitlab_busy()
            and not self._workers.is_running(self._instances_key)  # the real adapter may not be thread-safe
            and self.profile is not None
            and self.mapping_complete()
            and self.selected_instance() is not None
        )
        self.ui.pushButton_flash.setEnabled(can_flash)
        self.ui.pushButton_cancelFlash.setEnabled(flashing)
        for widget in (
            self.ui.comboBox_profile,
            self.ui.pushButton_reloadProfiles,
            self.ui.pushButton_settings,
            self.ui.groupBox_gitlab,
            self.ui.tableWidget_mapping,
            self.ui.comboBox_instance,
            self.ui.pushButton_refreshInstances,
            self.ui.checkBox_reset,
            self.ui.pushButton_exportBundle,
        ):
            widget.setEnabled(not flashing)
        self.ui.checkBox_run.setEnabled(not flashing and self.ui.checkBox_reset.isChecked())

    # -- instances --------------------------------------------------------------------
    def refresh_instances(self, *_args) -> None:
        if self._workers.is_running(self._instances_key) or self.flash_active() or self._closing:
            return
        adapter = self.adapter

        def job(ctx: WorkerContext) -> list[InstanceInfo]:
            return safe_list_instances(adapter)

        self._instances_key = self._workers.start(
            "winidea-instances",
            job,
            on_succeeded=self._on_instances_loaded,
            on_failed=self._on_instances_failed,
            on_finished=self._on_instances_finished,
        )
        self._update_flash_controls()

    def _on_instances_loaded(self, _key: str, instances: list[InstanceInfo]) -> None:
        if self._closing:
            return
        combo = self.ui.comboBox_instance
        previous = self.selected_instance()
        combo.blockSignals(True)
        combo.clear()
        for info in instances:
            combo.addItem(info.label(), instance_data(info))
        if previous is not None:
            for index in range(combo.count()):
                if combo.itemData(index)["instance_id"] == previous["instance_id"]:
                    combo.setCurrentIndex(index)
        combo.blockSignals(False)
        if instances:
            log.info("Found %d winIDEA instance(s)", len(instances))
        else:
            log.warning("No running winIDEA instance found. Open winIDEA with the SAF85xx workspace and click Refresh.")
        self._update_flash_controls()

    def _on_instances_finished(self, _key: str) -> None:
        if not self._closing:
            self._update_flash_controls()  # the worker only stops counting as running now

    def _on_instances_failed(self, _key: str, exc: BaseException) -> None:
        # safe_list_instances never raises; this only catches a bug in the job itself.
        if self._closing:
            return
        log.error("Instance refresh failed: %s", exc)

    # -- flash ------------------------------------------------------------------------
    def start_flash(self, *_args) -> None:
        if (
            self.flash_active()
            or self._closing
            or self._workers.is_running(self._instances_key)
            or not self.ui.pushButton_flash.isEnabled()
        ):
            return
        instance = self.selected_instance()
        if instance is None:
            self.show_error(WinIDEAError("No winIDEA instance selected"))
            return
        request = FlashRequest(
            instance_id=instance["instance_id"],
            # Copies: the worker must not share mutable rows with the table.
            mapping=[dataclasses.replace(row) for row in self.mapping_rows()],
            reset=self.ui.checkBox_reset.isChecked(),
            run=self.ui.checkBox_reset.isChecked() and self.ui.checkBox_run.isChecked(),
            timeout_s=self.profile.timeouts.download_s,
        )
        adapter, debug_ctx = self.adapter, self.ctx

        def job(wctx: WorkerContext) -> None:
            def on_step(step: Step) -> None:
                wctx.step(step.value)

            FlashWorkflow(adapter, debug_ctx, on_step=on_step, on_progress=wctx.progress).run(request, wctx.cancel)

        self._flash_cancel_requested = False
        self.ui.label_rollbackWarning.setVisible(False)
        self.ui.label_step.setText("Starting")
        self.ui.progressBar_flash.setRange(0, 100)
        self.ui.progressBar_flash.setValue(0)
        self.ui.progressBar_flash.setFormat("%p%")
        log.info("Flash requested on %s (%d file(s))", instance["instance_id"], len(request.mapping))
        self._flash_key = self._workers.start(
            "flash",
            job,
            on_succeeded=self._on_flash_succeeded,
            on_failed=self._on_flash_failed,
            on_finished=self._on_flash_finished,
            on_progress=self._on_flash_progress,
            on_step=self._on_flash_step,
        )
        self._update_flash_controls()

    def cancel_flash(self, *_args) -> None:
        if not self.flash_active() or self._flash_cancel_requested:
            return
        # Guard first (threading rule 4), then the token the workflow checks inside download().
        self._flash_cancel_requested = True
        log.warning("Flash cancel requested; the workspace paths will be restored")
        self.ui.label_step.setText("Cancelling")
        self._workers.cancel(self._flash_key)

    def _on_flash_step(self, text: str) -> None:
        if self._closing:
            return
        if self._flash_cancel_requested and text != Step.ROLLBACK.value:
            return  # keep "Cancelling" visible until the workflow reports the rollback
        self.ui.label_step.setText(text)

    def _on_flash_progress(self, percent, message: str) -> None:
        if self._closing:
            return
        bar = self.ui.progressBar_flash
        if percent is None:
            bar.setRange(0, 0)
            bar.setFormat(message)
        else:
            bar.setRange(0, 100)
            bar.setValue(percent)
            bar.setFormat(f"%p%  {message}")

    def _on_flash_succeeded(self, _key: str, _result) -> None:
        if self._closing:
            return
        if self._flash_cancel_requested:
            log.warning("The flash completed before the cancel took effect")
        self.ui.label_step.setText(Step.DONE.value)
        self.ui.progressBar_flash.setRange(0, 100)
        self.ui.progressBar_flash.setValue(100)
        log.info("Flash completed successfully")
        self.statusBar().showMessage("Flash completed", 10000)

    def _on_flash_failed(self, _key: str, exc: BaseException) -> None:
        if self._closing:
            # No dialogs while closing; closeEvent reports a failed rollback after the wait.
            self._flash_error_during_close = exc
            return
        rollback_failed = getattr(exc, "rollback_failed", False)
        self.ctx.add_error(exc)  # the workflow has returned; nothing else writes ctx now
        self.ui.progressBar_flash.setRange(0, 100)
        if rollback_failed:
            self.ui.label_rollbackWarning.setVisible(True)
            log.critical("Rollback failed: the winIDEA workspace may still point to the new files")
        if isinstance(exc, CancelledError):
            self.ui.label_step.setText("Cancelled")
            if not rollback_failed:
                return
        else:
            self.ui.label_step.setText("Failed")
        self.show_error(exc)

    def _on_flash_finished(self, key: str) -> None:
        if key == self._flash_key:
            self._flash_key = None
        if self._closing:
            return
        self._update_flash_controls()
