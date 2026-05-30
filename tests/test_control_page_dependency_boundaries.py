from __future__ import annotations

import inspect
import unittest
from unittest.mock import Mock


class ControlPageDependencyBoundaryTests(unittest.TestCase):
    def test_control_pages_receive_worker_factories_instead_of_broad_features(self) -> None:
        from app.page_names import PageName
        from presets.ui.control import control_page_shared
        from presets.ui.control.windows_features import runtime as windows_features_runtime
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage
        from ui.page_deps.presets import build_control_page_kwargs

        for page_cls in (Zapret1ModeControlPage, Zapret2ModeControlPage):
            init_source = inspect.getsource(page_cls.__init__)
            page_source = inspect.getsource(page_cls)

            self.assertNotIn("presets_feature", init_source)
            self.assertNotIn("profile_feature", init_source)
            self.assertNotIn("program_settings_feature", init_source)
            self.assertNotIn("external_actions_feature", init_source)
            self.assertNotIn("self._presets =", page_source)
            self.assertNotIn("self._presets.", page_source)
            self.assertNotIn("self._profile =", page_source)
            self.assertNotIn("self._profile.", page_source)
            self.assertNotIn("self._program_settings =", page_source)
            self.assertNotIn("self._program_settings.", page_source)
            self.assertNotIn("self._external_actions =", page_source)
            self.assertNotIn("self._external_actions.", page_source)
            self.assertIn("get_selected_source_preset_display", init_source)
            self.assertIn("get_enabled_profile_count_snapshot", init_source)
            self.assertIn("create_additional_settings_load_worker", init_source)
            self.assertIn("set_wssize_enabled", init_source)
            self.assertIn("set_debug_log_enabled", init_source)
            self.assertIn("create_program_settings_save_worker", init_source)
            self.assertIn("create_program_settings_load_worker", init_source)
            self.assertIn("create_program_settings_admin_check_worker", init_source)
            self.assertIn("create_external_open_url_worker", init_source)

        shared_source = inspect.getsource(control_page_shared.ControlPageActionMixin)
        windows_source = inspect.getsource(windows_features_runtime.ControlPageWindowsFeatureMixin)

        self.assertNotIn("self._program_settings.", shared_source)
        self.assertNotIn("self._external_actions.", shared_source)
        self.assertNotIn("self._program_settings.", windows_source)

        program_settings = Mock()
        external_actions = Mock()
        presets = Mock()
        profile = Mock()
        kwargs = build_control_page_kwargs(
            page_name=PageName.ZAPRET2_MODE_CONTROL,
            presets_feature=presets,
            profile_feature=profile,
            runtime_feature=Mock(),
            program_settings_feature=program_settings,
            external_actions_feature=external_actions,
            set_status=Mock(),
            request_exit=Mock(),
            open_connection_test=Mock(),
            open_folder=Mock(),
            show_page=Mock(),
            ui_state_store=Mock(),
        )

        self.assertIs(kwargs["get_selected_source_preset_display"], presets.get_selected_source_preset_display)
        self.assertIs(kwargs["get_enabled_profile_count_snapshot"], profile.get_enabled_profile_count_snapshot)
        self.assertIs(
            kwargs["create_additional_settings_load_worker"],
            profile.create_additional_settings_load_worker,
        )
        self.assertIs(kwargs["set_wssize_enabled"], profile.set_wssize_enabled)
        self.assertIs(kwargs["set_debug_log_enabled"], profile.set_debug_log_enabled)
        self.assertIs(kwargs["create_external_open_url_worker"], external_actions.create_open_url_worker)
        self.assertIs(
            kwargs["create_program_settings_save_worker"],
            program_settings.create_program_settings_save_worker,
        )
        self.assertIs(
            kwargs["create_program_settings_load_worker"],
            program_settings.create_program_settings_load_worker,
        )
        self.assertIs(
            kwargs["create_program_settings_admin_check_worker"],
            program_settings.create_program_settings_admin_check_worker,
        )
        self.assertIs(
            kwargs["attach_program_settings_runtime"],
            program_settings.attach_program_settings_runtime,
        )
        self.assertIs(
            kwargs["publish_program_settings_snapshot"],
            program_settings.publish_program_settings_snapshot,
        )
        self.assertIs(
            kwargs["remember_hide_to_tray_on_minimize_close"],
            program_settings.remember_hide_to_tray_on_minimize_close,
        )
        self.assertNotIn("presets_feature", kwargs)
        self.assertNotIn("profile_feature", kwargs)
        self.assertNotIn("program_settings_feature", kwargs)
        self.assertNotIn("external_actions_feature", kwargs)


if __name__ == "__main__":
    unittest.main()
