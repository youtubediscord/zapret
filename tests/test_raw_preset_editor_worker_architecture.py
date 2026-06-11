from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class RawPresetEditorWorkerArchitectureTests(unittest.TestCase):
    def test_raw_preset_editor_starts_workers_through_runtime(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        request_methods = (
            PresetRawEditorPage._request_raw_preset_text,
            PresetRawEditorPage._start_raw_preset_save_worker,
            PresetRawEditorPage._start_preset_activation_worker,
            PresetRawEditorPage._request_raw_preset_action,
            PresetRawEditorPage._start_raw_preset_action_worker,
        )
        page_source = inspect.getsource(PresetRawEditorPage)

        for method in request_methods:
            source = inspect.getsource(method)
            if method is PresetRawEditorPage._request_raw_preset_action:
                source += inspect.getsource(PresetRawEditorPage._start_raw_preset_action_worker)
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

        self.assertNotIn("get_selected_raw_preset_name", init_source)
        self.assertNotIn("get_selected_raw_preset_file_name", init_source)
        self.assertNotIn("_get_selected_raw_preset_name_fn", page_source)
        self.assertNotIn("_get_selected_raw_preset_file_name_fn", page_source)
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
        self.assertNotIn("get_selected_raw_preset_name", kwargs)
        self.assertNotIn("get_selected_raw_preset_file_name", kwargs)
        self.assertNotIn("presets_feature", kwargs)

    def test_raw_preset_load_queue_uses_shared_latest_worker_state(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_load_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(PresetRawEditorPage.__init__)
        request_source = inspect.getsource(PresetRawEditorPage._request_raw_preset_text)
        finished_source = inspect.getsource(PresetRawEditorPage._on_raw_preset_worker_finished)
        scheduled_source = inspect.getsource(PresetRawEditorPage._run_scheduled_raw_preset_load_start)
        cleanup_source = inspect.getsource(PresetRawEditorPage.cleanup)

        self.assertTrue(hasattr(PresetRawEditorPage, "_raw_load_state_obj"))
        self.assertIsInstance(page._raw_load_state_obj(), LatestValueWorkerState)
        self.assertIn("_raw_load_state = LatestValueWorkerState", init_source)
        self.assertIn("_raw_load_state_obj()", request_source)
        self.assertIn("_raw_load_state_obj()", finished_source)
        self.assertIn("_raw_load_state_obj()", scheduled_source)
        self.assertIn("_raw_load_state_obj().reset()", cleanup_source)
        self.assertIn("_raw_load_runtime_request_id", request_source)
        self.assertNotIn("_raw_load_runtime_worker", init_source)
        self.assertNotIn("_raw_load_runtime_worker", request_source)
        self.assertNotIn("_raw_load_runtime_worker", finished_source)
        self.assertNotIn("_raw_load_runtime_worker", cleanup_source)
        self.assertNotIn("self._raw_load_pending = False", init_source)
        self.assertNotIn("self._raw_load_start_scheduled = False", init_source)

    def test_raw_preset_actions_menu_dispatches_after_popup_closes(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        source = inspect.getsource(PresetRawEditorPage._open_menu)

        self.assertIn("exec_popup_menu", source)
        self.assertIn("capture_action=True", source)
        self.assertIn("action_map", source)
        self.assertNotIn("menu.exec(", source)
        self.assertNotIn("triggered.connect", source)

    def test_raw_preset_save_queue_uses_shared_latest_worker_state(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_save_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(PresetRawEditorPage.__init__)
        request_source = inspect.getsource(PresetRawEditorPage._request_raw_preset_save)
        finished_source = inspect.getsource(PresetRawEditorPage._on_raw_preset_save_worker_finished)
        scheduled_source = inspect.getsource(PresetRawEditorPage._run_scheduled_raw_preset_save_worker_start)
        cleanup_source = inspect.getsource(PresetRawEditorPage.cleanup)

        self.assertTrue(hasattr(PresetRawEditorPage, "_raw_preset_save_state_obj"))
        self.assertIsInstance(page._raw_preset_save_state_obj(), LatestValueWorkerState)
        self.assertIn("_raw_preset_save_state = LatestValueWorkerState", init_source)
        self.assertIn("_raw_preset_save_state_obj()", request_source)
        self.assertIn("_raw_preset_save_state_obj()", finished_source)
        self.assertIn("_raw_preset_save_state_obj()", scheduled_source)
        self.assertIn("_raw_preset_save_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_raw_preset_save", init_source)
        self.assertNotIn("self._raw_preset_save_start_scheduled = False", init_source)

    def test_raw_preset_activation_queue_uses_shared_latest_worker_state(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_activate_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(PresetRawEditorPage.__init__)
        request_source = inspect.getsource(PresetRawEditorPage._request_preset_activation)
        finished_source = inspect.getsource(PresetRawEditorPage._on_preset_activation_worker_finished)
        scheduled_source = inspect.getsource(PresetRawEditorPage._run_scheduled_preset_activation_worker_start)
        cleanup_source = inspect.getsource(PresetRawEditorPage.cleanup)

        self.assertTrue(hasattr(PresetRawEditorPage, "_raw_preset_activation_state_obj"))
        self.assertIsInstance(page._raw_preset_activation_state_obj(), LatestValueWorkerState)
        self.assertIn("_raw_preset_activation_state = LatestValueWorkerState", init_source)
        self.assertIn("_raw_preset_activation_state_obj()", request_source)
        self.assertIn("_raw_preset_activation_state_obj()", finished_source)
        self.assertIn("_raw_preset_activation_state_obj()", scheduled_source)
        self.assertIn("_raw_preset_activation_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_raw_preset_activation", init_source)
        self.assertNotIn("self._raw_preset_activation_start_scheduled = False", init_source)


if __name__ == "__main__":
    unittest.main()
