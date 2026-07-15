"""Общая runtime-логика кнопок Defender/MAX."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer

from presets.ui.control.control_page_runtime_shared import (
    run_confirmation_dialog,
    show_action_result_plan,
)
from ui.latest_value_worker_state import LatestValueWorkerState

if TYPE_CHECKING:
    from ui.one_shot_worker_runtime import OneShotWorkerRuntime


class ControlPageWindowsFeatureMixin:
    """Общие обработчики служебных Windows-функций на страницах управления."""

    def _show_windows_feature_action_result(self, plan, toggle=None) -> None:
        from qfluentwidgets import InfoBar

        show_action_result_plan(
            plan,
            parent_widget=self.window(),
            set_status=self._set_status,
            info_bar_cls=InfoBar,
            toggle=toggle,
        )

    def _confirm_windows_feature_action(self, dialog_plan, toggle=None) -> bool:
        from qfluentwidgets import MessageBox

        return run_confirmation_dialog(
            dialog_plan,
            message_box_cls=MessageBox,
            parent_widget=self.window(),
            toggle=toggle,
        )

    def _on_defender_toggled(self, disable: bool) -> None:
        self._request_defender_admin_check(bool(disable))

    def create_program_settings_admin_check_worker(self, request_id: int):
        return self._create_program_settings_admin_check_worker(
            request_id,
            parent=self,
        )

    def _ensure_defender_admin_check_runtime(self) -> OneShotWorkerRuntime:
        runtime = self.__dict__.get("_defender_admin_check_runtime")
        if runtime is None:
            from ui.one_shot_worker_runtime import OneShotWorkerRuntime

            runtime = OneShotWorkerRuntime()
            self._defender_admin_check_runtime = runtime
        self._defender_admin_check_state_obj()
        return runtime

    def _request_defender_admin_check(self, disable: bool) -> None:
        self._ensure_defender_admin_check_runtime()
        self._defender_admin_check_state_obj().request_or_start(
            bool(disable),
            self._start_defender_admin_check_worker,
        )

    def _start_defender_admin_check_worker(self, disable: bool) -> None:
        runtime = self._ensure_defender_admin_check_runtime()
        runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_program_settings_admin_check_worker(request_id),
            on_loaded=lambda request_id, is_admin: self._on_defender_admin_check_finished(
                request_id,
                is_admin,
                disable=bool(disable),
            ),
            on_failed=lambda request_id, error: self._on_defender_admin_check_failed(
                request_id,
                error,
                disable=bool(disable),
            ),
            on_finished=self._on_defender_admin_check_worker_finished,
        )

    def _on_defender_admin_check_finished(self, request_id: int, is_admin: bool, *, disable: bool) -> None:
        runtime = self._ensure_defender_admin_check_runtime()
        if not runtime.is_current(request_id, cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False))):
            return
        if self._defender_admin_check_state_obj().has_pending():
            return
        self._continue_defender_toggle(bool(disable), is_admin=bool(is_admin))

    def _on_defender_admin_check_failed(self, request_id: int, _error: str, *, disable: bool) -> None:
        runtime = self._ensure_defender_admin_check_runtime()
        if not runtime.is_current(request_id, cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False))):
            return
        if self._defender_admin_check_state_obj().has_pending():
            return
        self._continue_defender_toggle(bool(disable), is_admin=False)

    def _on_defender_admin_check_worker_finished(self, _worker) -> None:
        self._defender_admin_check_state_obj().schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=self._single_shot_defender_admin_check_start,
            run_scheduled=self._run_scheduled_defender_admin_check_worker_start,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        )

    def _schedule_defender_admin_check_worker_start(self, disable: bool) -> None:
        if bool(getattr(self, "_cleanup_in_progress", False)):
            return
        state = self._defender_admin_check_state_obj()
        state.pending = bool(disable)
        state.schedule_start(
            self._single_shot_defender_admin_check_start,
            self._run_scheduled_defender_admin_check_worker_start,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        )

    def _single_shot_defender_admin_check_start(self, delay_ms: int, callback) -> None:
        try:
            QTimer.singleShot(delay_ms, callback)
        except Exception:
            callback()

    def _run_scheduled_defender_admin_check_worker_start(self) -> None:
        pending = self._defender_admin_check_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False))
        )
        if pending is None:
            return
        self._start_defender_admin_check_worker(bool(pending))

    def _continue_defender_toggle(self, disable: bool, *, is_admin: bool) -> None:
        from qfluentwidgets import InfoBar
        import presets.ui.control.control_runtime as control_runtime

        start_plan = control_runtime.build_defender_toggle_start_plan(
            disable=disable,
            language=self._ui_language,
            is_admin=bool(is_admin),
        )
        if start_plan.blocked:
            InfoBar.error(
                title=start_plan.blocked_title,
                content=start_plan.blocked_content,
                parent=self.window(),
            )
            if start_plan.blocked_revert_checked is not None:
                self._set_toggle_checked(self.defender_toggle, start_plan.blocked_revert_checked)
            return

        for dialog_plan in start_plan.confirmations:
            if not self._confirm_windows_feature_action(dialog_plan, self.defender_toggle):
                self._sync_program_settings()
                return

        if start_plan.start_status:
            self._set_status(start_plan.start_status)

        self._request_program_settings_save("defender_disabled", bool(disable))

    def _stop_defender_admin_check_worker(self) -> None:
        self._defender_admin_check_state_obj().reset()
        runtime = self.__dict__.get("_defender_admin_check_runtime")
        if runtime is not None:
            runtime.stop(blocking=False, warning_prefix="Defender admin check worker")
            runtime.cancel()

    def _defender_admin_check_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_defender_admin_check_state")
        runtime = self.__dict__.get("_defender_admin_check_runtime")
        if state is None:
            pending = self.__dict__.pop("_defender_admin_check_pending", None)
            start_scheduled = bool(self.__dict__.pop("_defender_admin_check_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_defender_admin_check_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _defender_admin_check_pending(self):
        return self._defender_admin_check_state_obj().pending

    @_defender_admin_check_pending.setter
    def _defender_admin_check_pending(self, value) -> None:
        self._defender_admin_check_state_obj().pending = value

    @property
    def _defender_admin_check_start_scheduled(self) -> bool:
        return bool(self._defender_admin_check_state_obj().start_scheduled)

    @_defender_admin_check_start_scheduled.setter
    def _defender_admin_check_start_scheduled(self, value: bool) -> None:
        self._defender_admin_check_state_obj().start_scheduled = bool(value)

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False

    def _on_max_blocker_toggled(self, enable: bool) -> None:
        import presets.ui.control.control_runtime as control_runtime

        start_plan = control_runtime.build_max_block_toggle_start_plan(
            enable=enable,
            language=self._ui_language,
        )
        for dialog_plan in start_plan.confirmations:
            if not self._confirm_windows_feature_action(dialog_plan, self.max_block_toggle):
                self._sync_program_settings()
                return

        if start_plan.start_status:
            self._set_status(start_plan.start_status)

        self._request_program_settings_save("max_block", bool(enable))

    def _on_state_media_block_toggled(self, enable: bool) -> None:
        import presets.ui.control.control_runtime as control_runtime

        start_plan = control_runtime.build_state_media_block_toggle_start_plan(
            enable=enable,
            language=self._ui_language,
        )
        toggle = getattr(self, "state_media_block_toggle", None)
        for dialog_plan in start_plan.confirmations:
            if not self._confirm_windows_feature_action(dialog_plan, toggle):
                self._sync_program_settings()
                return

        if start_plan.start_status:
            self._set_status(start_plan.start_status)

        self._request_program_settings_save("state_media_block", bool(enable))

    def _on_internet_cleanup_clicked(self) -> None:
        import presets.ui.control.control_runtime as control_runtime

        start_plan = control_runtime.build_internet_cleanup_start_plan(language=self._ui_language)
        for dialog_plan in start_plan.confirmations:
            if not self._confirm_windows_feature_action(dialog_plan):
                return

        if start_plan.start_status:
            self._set_status(start_plan.start_status)

        self._request_internet_cleanup()

    def _internet_cleanup_button(self):
        card = getattr(self, "internet_cleanup_card", None)
        return getattr(card, "button", None)

    def _set_internet_cleanup_enabled(self, enabled: bool) -> None:
        button = self._internet_cleanup_button()
        if button is not None:
            try:
                button.setEnabled(bool(enabled))
            except Exception:
                pass
        card = getattr(self, "internet_cleanup_card", None)
        if card is not None:
            try:
                card.setEnabled(bool(enabled))
            except Exception:
                pass

    def _ensure_internet_cleanup_runtime(self) -> OneShotWorkerRuntime:
        runtime = self.__dict__.get("_internet_cleanup_runtime")
        if runtime is None:
            from ui.one_shot_worker_runtime import OneShotWorkerRuntime

            runtime = OneShotWorkerRuntime()
            self._internet_cleanup_runtime = runtime
        return runtime

    def _request_internet_cleanup(self) -> None:
        runtime = self._ensure_internet_cleanup_runtime()
        if runtime.is_running():
            self._set_status("Сброс сети Windows уже выполняется...")
            return
        self._set_internet_cleanup_enabled(False)
        self._start_internet_cleanup_worker()

    def _start_internet_cleanup_worker(self) -> None:
        from windows_features.internet_cleanup import InternetCleanupWorker

        runtime = self._ensure_internet_cleanup_runtime()
        runtime.start_qthread_worker(
            worker_factory=lambda request_id: InternetCleanupWorker(request_id, parent=self),
            on_loaded=self._on_internet_cleanup_finished,
            on_failed=self._on_internet_cleanup_failed,
            on_finished=self._on_internet_cleanup_worker_finished,
            bind_worker=lambda worker: worker.status.connect(self._on_internet_cleanup_status),
        )

    def _on_internet_cleanup_status(self, request_id: int, message: str) -> None:
        runtime = self._ensure_internet_cleanup_runtime()
        if not runtime.is_current(request_id, cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False))):
            return
        self._set_status(str(message or ""))

    def _on_internet_cleanup_finished(self, request_id: int, result) -> None:
        runtime = self._ensure_internet_cleanup_runtime()
        if not runtime.is_current(request_id, cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False))):
            return
        self._show_windows_feature_action_result(result)

    def _on_internet_cleanup_failed(self, request_id: int, error: str) -> None:
        runtime = self._ensure_internet_cleanup_runtime()
        if not runtime.is_current(request_id, cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False))):
            return
        from windows_features.internet_cleanup import build_internet_cleanup_error_result

        self._show_windows_feature_action_result(build_internet_cleanup_error_result(str(error or "")))

    def _on_internet_cleanup_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_internet_cleanup_runtime"), worker):
            return
        self._set_internet_cleanup_enabled(True)

    def _stop_internet_cleanup_worker(self) -> None:
        runtime = self.__dict__.get("_internet_cleanup_runtime")
        if runtime is not None:
            runtime.stop(
                blocking=True,
                wait_timeout_ms=45000,
                terminate_wait_ms=1000,
                warning_prefix="Internet cleanup worker",
            )
            runtime.cancel()
