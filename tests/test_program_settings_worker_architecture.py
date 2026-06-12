from __future__ import annotations

import inspect
import unittest

from app.feature_facades.program_settings import ProgramSettingsFeature
import program_settings.workers as program_settings_workers


class ProgramSettingsWorkerArchitectureTests(unittest.TestCase):
    def test_load_worker_receives_feature_action_callable(self) -> None:
        feature_source = inspect.getsource(ProgramSettingsFeature)
        worker_source = inspect.getsource(program_settings_workers.ProgramSettingsLoadWorker)
        worker_init_signature = inspect.signature(program_settings_workers.ProgramSettingsLoadWorker.__init__)

        self.assertNotIn("program_settings_feature=self", feature_source)
        self.assertNotIn("self._program_settings", worker_source)
        self.assertIn("load_program_settings_snapshot=self.load_program_settings_snapshot", feature_source)
        self.assertIn("load_program_settings_snapshot", worker_init_signature.parameters)
        self.assertNotIn("program_settings_commands.load_program_settings_snapshot", worker_source)
        self.assertNotIn("import program_settings.public", worker_source)

    def test_admin_check_worker_receives_feature_action_callable(self) -> None:
        feature_source = inspect.getsource(ProgramSettingsFeature)
        worker_source = inspect.getsource(program_settings_workers.ProgramSettingsAdminCheckWorker)
        worker_init_signature = inspect.signature(program_settings_workers.ProgramSettingsAdminCheckWorker.__init__)

        self.assertNotIn("program_settings_feature=self", feature_source)
        self.assertNotIn("self._program_settings", worker_source)
        self.assertIn("is_user_admin=self.is_user_admin", feature_source)
        self.assertIn("is_user_admin", worker_init_signature.parameters)
        self.assertNotIn("program_settings_commands.is_user_admin", worker_source)
        self.assertNotIn("import program_settings.public", worker_source)

    def test_defender_and_max_do_not_use_system_status_load_worker(self) -> None:
        feature_source = inspect.getsource(ProgramSettingsFeature)

        self.assertFalse(hasattr(program_settings_workers, "ProgramSettingsSystemStatusLoadWorker"))
        self.assertNotIn("refresh_program_settings_system_status", feature_source)
        self.assertNotIn("create_program_settings_system_status_load_worker", feature_source)

    def test_save_worker_receives_feature_action_callable(self) -> None:
        feature_source = inspect.getsource(ProgramSettingsFeature)
        worker_source = inspect.getsource(program_settings_workers.ProgramSettingsSaveWorker)
        worker_init_signature = inspect.signature(program_settings_workers.ProgramSettingsSaveWorker.__init__)

        self.assertIn("save_action=self._program_settings_save_action(action)", feature_source)
        self.assertIn("save_action", worker_init_signature.parameters)
        self.assertNotIn("import program_settings.commands", worker_source)
        self.assertNotIn("program_settings_commands.set_auto_dpi_enabled", worker_source)

    def test_auto_dpi_save_action_accepts_worker_status_callback(self) -> None:
        from unittest.mock import patch

        from program_settings.commands import set_auto_dpi_enabled

        with patch("settings.store.set_dpi_autostart") as save_autostart:
            result = set_auto_dpi_enabled(False, status_callback=lambda _message: None)

        save_autostart.assert_called_once_with(False)
        self.assertFalse(result.enabled)
        self.assertIn("отключ", result.message)

    def test_feature_does_not_expose_direct_program_setting_setters(self) -> None:
        for method_name in (
            "set_auto_dpi_enabled",
            "set_tray_close_mode",
            "set_defender_disabled",
            "set_max_block_enabled",
        ):
            self.assertFalse(hasattr(ProgramSettingsFeature, method_name), method_name)


if __name__ == "__main__":
    unittest.main()
