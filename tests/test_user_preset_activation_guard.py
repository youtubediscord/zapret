from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.feature_facades.presets import PresetsFeature
from presets.ui.common.user_presets_page import UserPresetsPageBase
from presets.ui.common.preset_subpage_base import PresetRawEditorPage


class _Runtime:
    def __init__(self, *, running: bool) -> None:
        self._running = bool(running)

    def is_running(self) -> bool:
        return self._running


class UserPresetActivationGuardTests(unittest.TestCase):
    def test_clicking_active_preset_does_not_start_activation_worker(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._runtime_service = Mock()
        page._runtime_service.active_preset_file_name.return_value = "Default.txt"
        page._runtime_service.apply_active_preset_marker_for_file = Mock()
        page._resolve_display_name = Mock()
        page._request_preset_activation = Mock()

        self.assertTrue(UserPresetsPageBase._on_activate_preset(page, "Default.txt"))

        page._runtime_service.apply_active_preset_marker_for_file.assert_not_called()
        page._resolve_display_name.assert_not_called()
        page._request_preset_activation.assert_not_called()

    def test_clicking_preset_while_activation_runs_does_not_repaint_marker_immediately(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=True)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._pending_preset_activation = None
        page._runtime_service = Mock()
        page._runtime_service.active_preset_file_name.return_value = "Before.txt"
        page._runtime_service.apply_active_preset_marker_for_file = Mock()
        page._restore_preset_activation_marker_file_name = "Before.txt"
        page._resolve_display_name = Mock(return_value="Next")

        self.assertTrue(UserPresetsPageBase._on_activate_preset(page, "Next.txt"))

        page._runtime_service.apply_active_preset_marker_for_file.assert_not_called()
        self.assertEqual(page._pending_preset_activation, ("Next.txt", "Next"))

    def test_activation_failure_restores_previous_marker_without_settings_read(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_request_id = 7
        page._pending_preset_activation = None
        page._restore_preset_activation_marker_file_name = "Before.txt"
        page._runtime_service = Mock()
        page._runtime_service.apply_active_preset_marker = Mock(
            side_effect=AssertionError("failure restore must not read selected preset in GUI")
        )
        page._runtime_service.apply_active_preset_marker_for_file = Mock()
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)
        page.window = Mock(return_value=None)

        with patch("presets.ui.common.user_presets_page.InfoBar.error"):
            UserPresetsPageBase._on_preset_activation_failed(page, 7, "bad")

        page._runtime_service.apply_active_preset_marker.assert_not_called()
        page._runtime_service.apply_active_preset_marker_for_file.assert_called_once_with("Before.txt")

    def test_activation_error_restores_previous_marker_without_settings_read(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_request_id = 8
        page._pending_preset_activation = None
        page._restore_preset_activation_marker_file_name = "Before.txt"
        page._runtime_service = Mock()
        page._runtime_service.apply_active_preset_marker = Mock(
            side_effect=AssertionError("error restore must not read selected preset in GUI")
        )
        page._runtime_service.apply_active_preset_marker_for_file = Mock()
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)
        page.window = Mock(return_value=None)
        result = SimpleNamespace(
            ok=False,
            log_message="Ошибка активации",
            log_level="ERROR",
            infobar_level="error",
            infobar_title="Ошибка",
            infobar_content="Не удалось",
            activated_file_name=None,
        )

        with patch("presets.ui.common.user_presets_page.InfoBar.error"):
            UserPresetsPageBase._on_preset_activation_finished(page, 8, result)

        page._runtime_service.apply_active_preset_marker.assert_not_called()
        page._runtime_service.apply_active_preset_marker_for_file.assert_called_once_with("Before.txt")

    def test_activation_success_does_not_repaint_already_started_marker(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_request_id = 9
        page._pending_preset_activation = None
        page._runtime_service = Mock()
        page._runtime_service.apply_active_preset_marker_for_file = Mock(
            side_effect=AssertionError("success must not repaint marker already set when worker started")
        )
        result = SimpleNamespace(
            ok=True,
            log_message="Активирован",
            log_level="SUCCESS",
            activated_file_name="Next.txt",
        )

        UserPresetsPageBase._on_preset_activation_finished(page, 9, result)

        page._runtime_service.apply_active_preset_marker_for_file.assert_not_called()

    def test_clicking_active_raw_preset_without_changes_does_not_start_activation_worker(self) -> None:
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._run_after_raw_preset_save = Mock(return_value=True)
        page._preset_file_name = "Default.txt"
        page._preset_name = "Default"
        page._is_current_selected_file = Mock(return_value=True)
        page._set_footer = Mock()
        page._request_preset_activation = Mock()
        page._show_error = Mock()

        PresetRawEditorPage._activate_preset(page)

        page._set_footer.assert_not_called()
        page._request_preset_activation.assert_not_called()
        page._show_error.assert_not_called()

    def test_feature_worker_skips_duplicate_selected_preset_activation(self) -> None:
        feature = PresetsFeature()

        with (
            patch.object(PresetsFeature, "get_selected_source_preset_file_name", return_value="Default.txt"),
            patch.object(PresetsFeature, "activate_preset_file") as activate_preset_file,
        ):
            worker = feature.create_preset_activate_worker(
                1,
                launch_method="zapret2_mode",
                file_name="default.TXT",
                display_name="Default",
                activate_error_level="error",
                activate_error_mode="friendly",
            )
            result = worker._activate_preset(file_name="default.TXT", display_name="Default")

        activate_preset_file.assert_not_called()
        self.assertTrue(result.ok)
        self.assertEqual(result.activated_file_name, "Default.txt")

    def test_feature_worker_still_activates_when_duplicate_guard_cannot_read_selection(self) -> None:
        feature = PresetsFeature()

        with (
            patch.object(PresetsFeature, "get_selected_source_preset_file_name", side_effect=RuntimeError("settings busy")),
            patch.object(PresetsFeature, "activate_preset_file") as activate_preset_file,
        ):
            worker = feature.create_preset_activate_worker(
                1,
                launch_method="zapret2_mode",
                file_name="Other.txt",
                display_name="Other",
                activate_error_level="error",
                activate_error_mode="friendly",
            )
            result = worker._activate_preset(file_name="Other.txt", display_name="Other")

        activate_preset_file.assert_called_once_with("zapret2_mode", "Other.txt")
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
