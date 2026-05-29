"""Общая runtime-логика кнопок Defender/MAX."""

from __future__ import annotations

from qfluentwidgets import InfoBar, MessageBox

from presets.ui.control.control_page_runtime_shared import (
    run_confirmation_dialog,
    show_action_result_plan,
)
import presets.ui.control.control_runtime as control_runtime
from ui.one_shot_worker_runtime import OneShotWorkerRuntime


class ControlPageWindowsFeatureMixin:
    """Общие обработчики служебных Windows-функций на страницах управления."""

    def _show_windows_feature_action_result(self, plan, toggle=None) -> None:
        show_action_result_plan(
            plan,
            parent_widget=self.window(),
            set_status=self._set_status,
            info_bar_cls=InfoBar,
            toggle=toggle,
        )

    def _confirm_windows_feature_action(self, dialog_plan, toggle=None) -> bool:
        return run_confirmation_dialog(
            dialog_plan,
            message_box_cls=MessageBox,
            parent_widget=self.window(),
            toggle=toggle,
        )

    def _on_defender_toggled(self, disable: bool) -> None:
        self._request_defender_admin_check(bool(disable))

    def create_program_settings_admin_check_worker(self, request_id: int):
        return self._program_settings.create_program_settings_admin_check_worker(
            request_id,
            parent=self,
        )

    def _ensure_defender_admin_check_runtime(self) -> OneShotWorkerRuntime:
        runtime = self.__dict__.get("_defender_admin_check_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._defender_admin_check_runtime = runtime
            self._defender_admin_check_pending = None
        return runtime

    def _request_defender_admin_check(self, disable: bool) -> None:
        runtime = self._ensure_defender_admin_check_runtime()
        if runtime.is_running():
            self._defender_admin_check_pending = bool(disable)
            return
        self._defender_admin_check_pending = None
        self._start_defender_admin_check_worker(bool(disable))

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
        self._continue_defender_toggle(bool(disable), is_admin=bool(is_admin))

    def _on_defender_admin_check_failed(self, request_id: int, _error: str, *, disable: bool) -> None:
        runtime = self._ensure_defender_admin_check_runtime()
        if not runtime.is_current(request_id, cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False))):
            return
        self._continue_defender_toggle(bool(disable), is_admin=False)

    def _on_defender_admin_check_worker_finished(self, _worker) -> None:
        pending = self.__dict__.get("_defender_admin_check_pending")
        self._defender_admin_check_pending = None
        if pending is not None and not bool(getattr(self, "_cleanup_in_progress", False)):
            self._start_defender_admin_check_worker(bool(pending))

    def _continue_defender_toggle(self, disable: bool, *, is_admin: bool) -> None:
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
        self._defender_admin_check_pending = None
        runtime = self.__dict__.get("_defender_admin_check_runtime")
        if runtime is not None:
            runtime.stop(blocking=True, warning_prefix="Defender admin check worker")
            runtime.cancel()

    def _on_max_blocker_toggled(self, enable: bool) -> None:
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
