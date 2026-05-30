from __future__ import annotations

import inspect
import unittest
from unittest.mock import Mock


class RawPresetEditorWorkerArchitectureTests(unittest.TestCase):
    def test_raw_preset_editor_starts_workers_through_runtime(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        request_methods = (
            PresetRawEditorPage._request_raw_preset_text,
            PresetRawEditorPage._start_raw_preset_save_worker,
            PresetRawEditorPage._request_preset_activation,
            PresetRawEditorPage._request_raw_preset_action,
        )
        page_source = inspect.getsource(PresetRawEditorPage)

        for method in request_methods:
            source = inspect.getsource(method)
            self.assertIn("start_qthread_worker", source)
            self.assertNotIn("worker.start()", source)

        for old_field in (
            "_raw_load_worker",
            "_raw_save_worker",
            "_raw_activate_worker",
            "_raw_action_worker",
        ):
            self.assertNotIn(old_field, page_source)

    def test_raw_preset_editor_receives_worker_factories_instead_of_controller(self) -> None:
        from app.feature_facades.presets import PresetsFeature
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage
        from ui.navigation_pages import PageName
        from ui.page_deps.presets import build_preset_raw_editor_page_kwargs

        init_source = inspect.getsource(PresetRawEditorPage.__init__)
        page_source = inspect.getsource(PresetRawEditorPage)
        deps_source = inspect.getsource(build_preset_raw_editor_page_kwargs)
        feature_source = inspect.getsource(PresetsFeature)
        worker_factories = (
            "create_raw_preset_load_worker",
            "create_raw_preset_save_worker",
            "create_raw_preset_activate_worker",
            "create_raw_preset_action_worker",
        )

        for factory_name in worker_factories:
            self.assertIn(factory_name, init_source)
            self.assertIn(factory_name, deps_source)
            self.assertIn(factory_name, feature_source)
            self.assertIn(f"_{factory_name}_fn", page_source)

        self.assertIn("get_selected_raw_preset_name", init_source)
        self.assertIn("get_selected_raw_preset_file_name", init_source)
        self.assertNotIn("RawPresetEditorController", page_source)
        self.assertNotIn("_controller", page_source)
        self.assertNotIn("save_preset_source_by_file_name", init_source)
        self.assertNotIn("get_preset_source_path_by_file_name", init_source)
        self.assertNotIn("open_preset_source_file", init_source)

        presets_feature = Mock()
        kwargs = build_preset_raw_editor_page_kwargs(
            page_name=PageName.ZAPRET2_PRESET_RAW_EDITOR,
            presets_feature=presets_feature,
            runtime_feature=Mock(),
            show_page=Mock(),
            ui_state_store=Mock(),
        )

        for factory_name in worker_factories:
            self.assertIs(kwargs[factory_name], getattr(presets_feature, factory_name))
        self.assertIs(kwargs["get_selected_raw_preset_name"], presets_feature.get_selected_raw_preset_name)
        self.assertIs(kwargs["get_selected_raw_preset_file_name"], presets_feature.get_selected_raw_preset_file_name)
        self.assertNotIn("presets_feature", kwargs)


if __name__ == "__main__":
    unittest.main()
