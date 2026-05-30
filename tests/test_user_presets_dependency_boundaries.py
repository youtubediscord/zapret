from __future__ import annotations

import inspect
import unittest
from unittest.mock import Mock


class UserPresetsDependencyBoundaryTests(unittest.TestCase):
    def test_user_presets_page_receives_open_url_callable_for_link_worker_factory(self) -> None:
        from app.page_names import PageName
        from presets.ui.common.user_presets_page import UserPresetsPageBase
        from ui.page_deps.presets import build_user_presets_page_kwargs

        init_source = inspect.getsource(UserPresetsPageBase.__init__)
        page_source = inspect.getsource(UserPresetsPageBase)
        runtime_source = inspect.getsource(UserPresetsPageBase._build_page_runtime)

        self.assertIn("open_url", init_source)
        self.assertNotIn("external_actions_feature", init_source)
        self.assertNotIn("self._external_actions", page_source)
        self.assertNotIn("open_url=self._open_url", runtime_source)
        self.assertIn("open_url=self._open_url", inspect.getsource(UserPresetsPageBase.create_preset_link_action_worker))

        external_actions = Mock()
        kwargs = build_user_presets_page_kwargs(
            page_name=PageName.ZAPRET2_USER_PRESETS,
            presets_feature=Mock(),
            external_actions_feature=external_actions,
            open_preset_raw_editor=Mock(),
            ui_state_store=Mock(),
        )

        self.assertIs(kwargs["open_url"], external_actions.open_url)
        self.assertNotIn("external_actions_feature", kwargs)

    def test_user_presets_page_receives_concrete_preset_actions_instead_of_feature(self) -> None:
        from app.page_names import PageName
        from presets.ui.common.user_presets_page import UserPresetsPageBase
        from presets.ui.common.user_presets_page_runtime import UserPresetsPageRuntimeConfig
        from ui.page_deps.presets import build_user_presets_page_kwargs

        init_source = inspect.getsource(UserPresetsPageBase.__init__)
        page_source = inspect.getsource(UserPresetsPageBase)
        runtime_config_source = inspect.getsource(UserPresetsPageRuntimeConfig)
        runtime_build_source = inspect.getsource(UserPresetsPageBase._build_page_runtime)

        self.assertNotIn("presets_feature", init_source)
        self.assertNotIn("self._presets_feature", page_source)
        self.assertNotIn("get_presets_feature", runtime_config_source)
        self.assertNotIn("get_presets_feature", runtime_build_source)
        self.assertIn("preset_runtime_actions", init_source)
        self.assertIn("connect_preset_signals", init_source)
        self.assertIn("create_user_presets_open_folder_worker", init_source)
        self.assertIn("create_preset_edit_action_worker", init_source)
        self.assertIn("create_preset_bulk_action_worker", init_source)
        self.assertIn("create_preset_activate_worker", init_source)
        self.assertIn("create_preset_item_action_worker", init_source)
        self.assertIn("create_preset_link_action_worker", init_source)
        self.assertIn("create_preset_folder_action_worker", init_source)
        self.assertIn("create_preset_storage_action_worker", init_source)
        self.assertIn("load_preset_folder_state", init_source)
        self.assertIn("delete_preset_item_meta", init_source)
        self.assertNotIn("from presets.folders import", page_source)

        presets = Mock()
        external_actions = Mock()
        kwargs = build_user_presets_page_kwargs(
            page_name=PageName.ZAPRET2_USER_PRESETS,
            presets_feature=presets,
            external_actions_feature=external_actions,
            open_preset_raw_editor=Mock(),
            ui_state_store=Mock(),
        )

        self.assertNotIn("presets_feature", kwargs)
        self.assertIn("preset_runtime_actions", kwargs)
        self.assertIs(kwargs["connect_preset_signals"], presets.connect_preset_signals)
        self.assertIs(
            kwargs["create_user_presets_open_folder_worker"],
            presets.create_user_presets_open_folder_worker,
        )
        self.assertIs(
            kwargs["create_preset_edit_action_worker"],
            presets.create_preset_edit_action_worker,
        )
        self.assertIs(
            kwargs["create_preset_bulk_action_worker"],
            presets.create_preset_bulk_action_worker,
        )
        self.assertIs(
            kwargs["create_preset_activate_worker"],
            presets.create_preset_activate_worker,
        )
        self.assertIs(
            kwargs["create_preset_item_action_worker"],
            presets.create_preset_item_action_worker,
        )
        self.assertIs(
            kwargs["create_preset_link_action_worker"],
            presets.create_preset_link_action_worker,
        )
        self.assertIs(
            kwargs["create_preset_folder_action_worker"],
            presets.create_preset_folder_action_worker,
        )
        self.assertIs(
            kwargs["create_preset_storage_action_worker"],
            presets.create_preset_storage_action_worker,
        )
        self.assertIs(kwargs["load_preset_folder_state"], presets.load_preset_folder_state)
        self.assertIs(kwargs["delete_preset_item_meta"], presets.delete_preset_item_meta)

    def test_user_presets_runtime_actions_do_not_expose_mutating_preset_commands(self) -> None:
        from dataclasses import fields

        from presets.ui.common.user_presets_page_runtime import UserPresetsRuntimeActions
        from ui.page_deps.presets import build_user_presets_page_kwargs
        from app.page_names import PageName

        field_names = {field.name for field in fields(UserPresetsRuntimeActions)}
        forbidden = {
            "create_preset",
            "rename_preset_by_file_name",
            "import_preset_from_file",
            "reset_all_presets_to_builtin",
            "duplicate_preset_by_file_name",
            "reset_preset_to_builtin_by_file_name",
            "delete_preset_by_file_name",
            "export_preset_plain_text",
            "activate_preset_file",
        }

        self.assertFalse(field_names & forbidden)

        presets = Mock()
        kwargs = build_user_presets_page_kwargs(
            page_name=PageName.ZAPRET2_USER_PRESETS,
            presets_feature=presets,
            external_actions_feature=Mock(),
            open_preset_raw_editor=Mock(),
            ui_state_store=Mock(),
        )
        runtime_actions = kwargs["preset_runtime_actions"]

        for name in forbidden:
            self.assertFalse(hasattr(runtime_actions, name), name)


if __name__ == "__main__":
    unittest.main()
