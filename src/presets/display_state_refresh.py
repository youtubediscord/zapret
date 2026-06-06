from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from log.log import log
from settings.mode import is_preset_launch_method, normalize_launch_method
from ui.one_shot_worker_runtime import OneShotWorkerRuntime


class PresetProfileStrategySummaryWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        method: str,
        profile_feature,
        max_items: int = 2,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._request_id = int(request_id)
        self._method = normalize_launch_method(method, default="")
        self._profile_feature = profile_feature
        self._max_items = max(1, int(max_items))

    def run(self) -> None:
        try:
            from presets.display_state import resolve_profile_strategy_display_state

            result = resolve_profile_strategy_display_state(
                method=self._method,
                profile_feature=self._profile_feature,
                max_items=self._max_items,
            )
        except Exception as exc:
            log(f"PresetProfileStrategySummaryWorker: не удалось обновить summary profile: {exc}", "DEBUG")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


class PresetProfileStrategySummaryRefreshRuntime(QObject):
    """Запрашивает пересчёт краткого summary profile вне GUI-потока."""

    def __init__(
        self,
        *,
        profile_feature,
        state_store,
        get_launch_method: Callable[[], str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._profile_feature = profile_feature
        self._state_store = state_store
        self._get_launch_method = get_launch_method
        self._summary_runtime = OneShotWorkerRuntime()
        self._pending = False
        self._start_scheduled = False

    def request_refresh(self) -> None:
        method = normalize_launch_method(self._get_launch_method(), default="")
        if not method or not is_preset_launch_method(method):
            return

        if self._summary_runtime.is_running() or self.__dict__.get("_start_scheduled", False):
            self._pending = True
            return

        self._start_worker(method)

    def _start_worker(self, method: str) -> None:
        self._pending = False
        self._summary_runtime.start_qthread_worker(
            worker_factory=lambda request_id: PresetProfileStrategySummaryWorker(
                request_id,
                method=method,
                profile_feature=self._profile_feature,
                parent=self,
            ),
            on_loaded=self._on_summary_loaded,
            on_failed=self._on_summary_failed,
            on_finished=self._on_worker_finished,
        )

    def _on_summary_loaded(self, request_id: int, state) -> None:
        if not self._summary_runtime.is_current(request_id):
            return
        if self.__dict__.get("_pending", False):
            return
        from presets.display_state import publish_profile_strategy_summary_in_store

        publish_profile_strategy_summary_in_store(
            state=state,
            ui_state_store=self._state_store,
        )

    def _on_summary_failed(self, request_id: int, error: str) -> None:
        if not self._summary_runtime.is_current(request_id):
            return
        if self.__dict__.get("_pending", False):
            return
        log(f"Preset summary refresh skipped: {error}", "DEBUG")

    def _on_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(worker):
            return
        if self._pending:
            self._schedule_refresh_start()

    def _is_current_worker_finish(self, worker) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            summary_runtime = self.__dict__.get("_summary_runtime")
            current_worker = getattr(summary_runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        try:
            return int(request_id) == int(self._summary_runtime.request_id)
        except (TypeError, ValueError):
            return False

    def _schedule_refresh_start(self) -> None:
        if self.__dict__.get("_start_scheduled", False):
            return
        self._start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_refresh_start)

    def _run_scheduled_refresh_start(self) -> None:
        self._start_scheduled = False
        if not self._pending:
            return
        self.request_refresh()

    def cleanup(self) -> None:
        self._pending = False
        self._start_scheduled = False
        self._summary_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="preset summary refresh worker",
        )
        self._summary_runtime.cancel()


__all__ = [
    "PresetProfileStrategySummaryRefreshRuntime",
    "PresetProfileStrategySummaryWorker",
]
