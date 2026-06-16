from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from log.log import log
from settings.mode import is_preset_launch_method, normalize_launch_method
from ui.latest_value_worker_state import LatestValueWorkerState
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
        refresh_reason: str = "",
        max_items: int = 2,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._request_id = int(request_id)
        self._method = normalize_launch_method(method, default="")
        self._profile_feature = profile_feature
        self._refresh_reason = str(refresh_reason or "").strip()
        self._max_items = max(1, int(max_items))

    def run(self) -> None:
        try:
            warm_profile_list = getattr(self._profile_feature, "warm_profile_list", None)
            if callable(warm_profile_list) and self._refresh_reason != "strategy_only":
                try:
                    warm_profile_list(self._method)
                except Exception as exc:
                    log(f"PresetProfileStrategySummaryWorker: прогрев профилей не выполнен: {exc}", "DEBUG")

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
        self._summary_state = LatestValueWorkerState(
            self._summary_runtime,
            empty_value=False,
        )

    def request_refresh(self, *, reason: str = "") -> None:
        method = normalize_launch_method(self._get_launch_method(), default="")
        if not method or not is_preset_launch_method(method):
            return

        state = self._summary_state_obj()
        if state.is_busy():
            state.pending = str(reason or "").strip() or True
            return

        self._start_worker(method, reason=str(reason or "").strip())

    def _start_worker(self, method: str, *, reason: str = "") -> None:
        self._summary_state_obj().pending = False
        self._summary_runtime.start_qthread_worker(
            worker_factory=lambda request_id: PresetProfileStrategySummaryWorker(
                request_id,
                method=method,
                profile_feature=self._profile_feature,
                refresh_reason=reason,
                parent=self,
            ),
            on_loaded=self._on_summary_loaded,
            on_failed=self._on_summary_failed,
            on_finished=self._on_worker_finished,
        )

    def _on_summary_loaded(self, request_id: int, state) -> None:
        if not self._summary_runtime.is_current(request_id):
            return
        state_obj = self._summary_state_obj()
        if state_obj.has_pending():
            return
        from presets.display_state import publish_profile_strategy_summary_in_store

        publish_profile_strategy_summary_in_store(
            state=state,
            ui_state_store=self._state_store,
        )

    def _on_summary_failed(self, request_id: int, error: str) -> None:
        if not self._summary_runtime.is_current(request_id):
            return
        state = self._summary_state_obj()
        if state.has_pending():
            return
        log(f"Preset summary refresh skipped: {error}", "DEBUG")

    def _on_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(worker):
            return
        state = self._summary_state_obj()
        if state.has_pending():
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
        state = self._summary_state_obj()
        if state.start_scheduled:
            return
        state.start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_refresh_start)

    def _run_scheduled_refresh_start(self) -> None:
        state = self._summary_state_obj()
        state.start_scheduled = False
        if not state.has_pending():
            return
        pending = state.pending
        state.pending = False
        reason = pending if isinstance(pending, str) else ""
        if reason:
            self.request_refresh(reason=reason)
        else:
            self.request_refresh()

    def _summary_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_summary_state")
        runtime = self.__dict__.get("_summary_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_pending", False))
            start_scheduled = bool(self.__dict__.pop("_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_summary_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending(self) -> bool:
        return bool(self._summary_state_obj().pending)

    @_pending.setter
    def _pending(self, value: bool) -> None:
        self._summary_state_obj().pending = bool(value)

    @property
    def _start_scheduled(self) -> bool:
        return bool(self._summary_state_obj().start_scheduled)

    @_start_scheduled.setter
    def _start_scheduled(self, value: bool) -> None:
        self._summary_state_obj().start_scheduled = bool(value)

    def cleanup(self) -> None:
        self._summary_state_obj().reset()
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
