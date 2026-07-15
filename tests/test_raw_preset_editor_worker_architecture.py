from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


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

    def test_clean_same_raw_preset_open_skips_redundant_load_worker(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._preset_file_name = "Default.txt"
        page._preset_name = "Default"
        page._preset_path = "C:/Zapret/Dev/presets/winws2/Default.txt"
        page._preset_origin = "user"
        page._raw_editor_text_snapshot = "--new\nloaded\n"
        page._raw_preset_content_loaded_once = True
        page._raw_preset_content_dirty = False
        page._run_after_raw_preset_save = Mock(return_value=True)
        page._load_file = Mock(side_effect=AssertionError("clean same preset must not reload"))
        page._refresh_header = Mock()

        PresetRawEditorPage.set_preset_file_name(page, "Default.txt")

        page._load_file.assert_not_called()
        page._refresh_header.assert_called_once_with()
        self.assertEqual(page._raw_editor_text_snapshot, "--new\nloaded\n")

    def test_clean_raw_editor_activation_restores_editor_after_show(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        class _Editor:
            def __init__(self) -> None:
                self.visible_calls: list[bool] = []

            def setVisible(self, value: bool) -> None:  # noqa: N802
                self.visible_calls.append(bool(value))

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        editor = _Editor()
        page.editor = editor
        page._cleanup_in_progress = False
        page._raw_preset_content_loaded_once = True
        page._raw_preset_content_dirty = False
        page._raw_editor_show_scheduled = False
        page._commit_pending_content_change = Mock()
        scheduled: list[object] = []

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: scheduled.append(callback),
        ), patch(
            "presets.ui.common.preset_subpage_base.QApplication.instance",
            return_value=None,
        ):
            PresetRawEditorPage.on_page_hidden(page)
            PresetRawEditorPage.on_page_activated(page)

        page._commit_pending_content_change.assert_called_once_with()
        self.assertEqual(editor.visible_calls, [False])
        self.assertEqual(len(scheduled), 1)

        scheduled[0]()

        self.assertEqual(editor.visible_calls, [False, True])

    def test_raw_preset_content_revision_marks_loaded_text_dirty(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._raw_preset_content_loaded_once = True
        page._raw_preset_content_dirty = False
        page._render_runtime_toggle = Mock()
        page._render_footer_status = Mock()

        PresetRawEditorPage._on_ui_state_changed(
            page,
            object(),
            frozenset({"preset_content_revision"}),
        )

        self.assertTrue(page._raw_preset_content_dirty)
        page._render_runtime_toggle.assert_not_called()
        page._render_footer_status.assert_not_called()

    def test_own_raw_preset_save_revision_keeps_loaded_text_clean(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        updated = SimpleNamespace(name="Default", file_name="Default.txt", kind="user")
        result = SimpleNamespace(
            updated=updated,
            path="C:/Zapret/Dev/presets/winws2/Default.txt",
            footer_text="Сохранено 12:00",
        )
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._raw_save_request_id = 3
        page._preset_name = "Default"
        page._preset_file_name = "Default.txt"
        page._preset_path = "C:/Zapret/Dev/presets/winws2/Default.txt"
        page._preset_origin = "user"
        page._raw_preset_content_loaded_once = True
        page._raw_preset_content_dirty = True
        page._content_publish_pending = True
        page._set_footer = Mock()
        page._render_runtime_toggle = Mock()
        page._render_footer_status = Mock()

        PresetRawEditorPage._on_raw_preset_save_finished(page, 3, "Default.txt", result, True)
        PresetRawEditorPage._on_ui_state_changed(
            page,
            object(),
            frozenset({"preset_content_revision"}),
        )

        self.assertFalse(page._raw_preset_content_dirty)
        self.assertFalse(page._ignore_next_raw_preset_content_revision)

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
