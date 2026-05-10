"""Общая runtime-логика кнопок Defender/MAX."""

from __future__ import annotations

from qfluentwidgets import InfoBar, MessageBox

from presets.ui.control.control_page_runtime_shared import (
    run_confirmation_dialog,
    show_action_result_plan,
)
from presets.ui.control.control_runtime_controller import ControlPageController
from program_settings.public import set_defender_disabled, set_max_block_enabled


class ControlPageWindowsFeatureMixin:
    """Общие обработчики служебных Windows-функций на страницах управления."""

    def _show_windows_feature_action_result(self, plan, toggle=None) -> None:
        show_action_result_plan(
            plan,
            window=self.window(),
            set_status=self._set_status,
            info_bar_cls=InfoBar,
            toggle=toggle,
        )

    def _confirm_windows_feature_action(self, dialog_plan, toggle=None) -> bool:
        return run_confirmation_dialog(
            dialog_plan,
            message_box_cls=MessageBox,
            window=self.window(),
            toggle=toggle,
        )

    def _on_defender_toggled(self, disable: bool) -> None:
        start_plan = ControlPageController.build_defender_toggle_start_plan(
            disable=disable,
            language=self._ui_language,
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

        try:
            for dialog_plan in start_plan.confirmations:
                if not self._confirm_windows_feature_action(dialog_plan, self.defender_toggle):
                    return

            if start_plan.start_status:
                self._set_status(start_plan.start_status)

            result_plan = set_defender_disabled(
                disable=disable,
                status_callback=self._set_status,
            )
            self._show_windows_feature_action_result(result_plan, self.defender_toggle)
        finally:
            self._sync_program_settings()

    def _on_max_blocker_toggled(self, enable: bool) -> None:
        start_plan = ControlPageController.build_max_block_toggle_start_plan(
            enable=enable,
            language=self._ui_language,
        )
        try:
            for dialog_plan in start_plan.confirmations:
                if not self._confirm_windows_feature_action(dialog_plan, self.max_block_toggle):
                    return

            if start_plan.start_status:
                self._set_status(start_plan.start_status)

            result_plan = set_max_block_enabled(
                enable=enable,
                status_callback=self._set_status,
            )
            self._show_windows_feature_action_result(result_plan, self.max_block_toggle)
        finally:
            self._sync_program_settings()
