from __future__ import annotations

import inspect
import unittest
from unittest.mock import Mock


class RawPresetEditorDependencyBoundaryTests(unittest.TestCase):
    def test_raw_preset_editor_receives_actions_instead_of_presets_feature(self) -> None:
        import presets.raw_preset_editor_workflow as raw_workflow
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage
        from ui.navigation_pages import PageName
        from ui.page_deps.presets import build_preset_raw_editor_page_kwargs

        page_init_source = inspect.getsource(PresetRawEditorPage.__init__)
        page_source = inspect.getsource(PresetRawEditorPage)
        deps_source = inspect.getsource(build_preset_raw_editor_page_kwargs)
        workflow_source = inspect.getsource(raw_workflow)

        self.assertFalse(hasattr(raw_workflow, "RawPresetEditorController"))
        self.assertNotIn("RawPresetEditorController", page_source)
        self.assertNotIn("presets_feature", page_init_source)
        self.assertNotIn("self._presets", page_source)

        page_dependency_keys = {
            "create_raw_preset_load_worker",
            "create_raw_preset_save_worker",
            "create_raw_preset_activate_worker",
            "create_raw_preset_action_worker",
            "get_selected_raw_preset_name",
            "get_selected_raw_preset_file_name",
        }
        for key in page_dependency_keys:
            self.assertIn(key, page_init_source)
            self.assertIn(key, deps_source)

        workflow_method_names = {
            "save_preset_source_by_file_name",
            "get_preset_source_path_by_file_name",
            "get_preset_manifest_by_file_name",
            "open_preset_source_file",
            "rename_preset_by_file_name",
            "duplicate_preset_by_file_name",
            "export_preset_plain_text",
            "reset_preset_to_builtin_by_file_name",
            "delete_preset_by_file_name",
            "get_selected_source_preset_manifest",
            "get_selected_source_preset_file_name",
            "activate_preset_file",
            "publish_preset_content_changed",
        }
        for method_name in workflow_method_names:
            self.assertIn(method_name, workflow_source)

        presets = Mock()
        kwargs = build_preset_raw_editor_page_kwargs(
            page_name=PageName.ZAPRET2_PRESET_RAW_EDITOR,
            presets_feature=presets,
            runtime_feature=Mock(),
            show_page=Mock(),
            ui_state_store=Mock(),
        )

        for key in page_dependency_keys:
            self.assertIs(kwargs[key], getattr(presets, key))
        self.assertNotIn("presets_feature", kwargs)

    def test_raw_preset_editor_receives_runtime_actions_instead_of_runtime_feature(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage
        from ui.navigation_pages import PageName
        from ui.page_deps.presets import build_preset_raw_editor_page_kwargs

        page_init_source = inspect.getsource(PresetRawEditorPage.__init__)
        page_source = inspect.getsource(PresetRawEditorPage)

        self.assertIn("runtime_actions", page_init_source)
        self.assertNotIn("runtime_feature", page_init_source)
        self.assertNotIn("self._runtime_feature", page_source)
        self.assertIn("self._runtime_actions", page_source)

        presets = Mock()
        runtime = Mock()
        kwargs = build_preset_raw_editor_page_kwargs(
            page_name=PageName.ZAPRET2_PRESET_RAW_EDITOR,
            presets_feature=presets,
            runtime_feature=runtime,
            show_page=Mock(),
            ui_state_store=Mock(),
        )

        self.assertIn("runtime_actions", kwargs)
        self.assertNotIn("runtime_feature", kwargs)
        actions = kwargs["runtime_actions"]
        self.assertIs(actions.start, runtime.start)
        self.assertIs(actions.stop, runtime.stop)
        self.assertIs(actions.is_available, runtime.is_available)


if __name__ == "__main__":
    unittest.main()
