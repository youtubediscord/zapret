from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from presets.ui.common.user_presets_page import UserPresetsPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    completed = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self) -> None:
        self.start = Mock()
        self.deleteLater = Mock()


class _Runtime:
    def __init__(self, *, running: bool = False) -> None:
        self._running = bool(running)

    def is_running(self) -> bool:
        return self._running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        worker.start()
        return 0, worker


class _ActivationWorker(_Worker):
    activated = _Signal()


class UserPresetWriteSerializationTests(unittest.TestCase):
    def test_preset_write_queue_lives_in_queued_worker_state(self) -> None:
        import inspect
        from ui.queued_worker_state import QueuedWorkerState

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        module_source = inspect.getsource(
            __import__("presets.ui.common.user_presets_page", fromlist=[""])
        )
        init_source = inspect.getsource(UserPresetsPageBase.__init__)
        queue_source = inspect.getsource(UserPresetsPageBase._queue_preset_write_action)
        pop_source = inspect.getsource(UserPresetsPageBase._pop_next_preset_write_action)
        has_pending_source = inspect.getsource(UserPresetsPageBase._has_pending_preset_write_action)
        schedule_source = inspect.getsource(UserPresetsPageBase._schedule_preset_write_action_start)
        cleanup_source = inspect.getsource(UserPresetsPageBase._stop_action_workers_for_cleanup)

        self.assertIsInstance(UserPresetsPageBase._preset_write_state_obj(page), QueuedWorkerState)
        self.assertIn("from ui.queued_worker_state import QueuedWorkerState", module_source)
        self.assertIn("_preset_write_state = QueuedWorkerState", init_source)
        self.assertIn("_preset_write_state_obj()", queue_source)
        self.assertIn("state.pop_next()", pop_source)
        self.assertIn("_preset_write_state_obj().has_pending()", has_pending_source)
        self.assertIn("state.start_scheduled", schedule_source)
        self.assertIn("_preset_write_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_preset_write_actions: list", init_source)

    def test_activation_finish_uses_shared_write_queue_without_legacy_scheduler(self) -> None:
        import inspect

        finished_source = inspect.getsource(UserPresetsPageBase._on_preset_activate_worker_finished)

        self.assertIn("_start_next_preset_write_action()", finished_source)
        self.assertNotIn("_schedule_pending_preset_activation_start", finished_source)
        self.assertFalse(hasattr(UserPresetsPageBase, "_schedule_pending_preset_activation_start"))

    def test_storage_action_waits_while_item_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_runtime = _Runtime(running=True)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._pending_preset_storage_actions = []
        page._preset_storage_action_request_id = 0
        page.create_preset_storage_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_storage_action(
            page,
            "rating",
            name="Preset.txt",
            display_name="Preset",
            rating=7,
        )

        page.create_preset_storage_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_preset_write_actions,
            [
                {
                    "kind": "storage",
                    "action": "rating",
                    "name": "Preset.txt",
                    "display_name": "Preset",
                    "rating": 7,
                    "direction": 0,
                    "cached_metadata": None,
                    "source_kind": "",
                    "source_id": "",
                    "destination_kind": "",
                    "destination_id": "",
                    "destination_folder_key": "",
                    "file_name": "",
                    "file_path": "",
                }
            ],
        )

    def test_storage_action_waits_while_folder_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_folder_action_runtime = _Runtime(running=True)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._pending_preset_storage_actions = []
        page._preset_storage_action_request_id = 0
        page.create_preset_storage_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_storage_action(
            page,
            "rating",
            name="Preset.txt",
            display_name="Preset",
            rating=7,
        )

        page.create_preset_storage_action_worker.assert_not_called()
        self.assertEqual(page._pending_preset_write_actions[0]["kind"], "storage")
        self.assertEqual(page._pending_preset_storage_actions[0]["action"], "rating")

    def test_folder_action_waits_while_storage_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_storage_action_runtime = _Runtime(running=True)
        page._preset_folder_action_runtime = _Runtime(running=False)
        page._preset_folder_action_pending = []
        page._preset_folder_action_request_id = 0
        page.create_preset_folder_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_folder_action(
            page,
            "set_collapsed",
            folder_key="games",
            collapsed=True,
        )

        page.create_preset_folder_action_worker.assert_not_called()
        self.assertEqual(
            page._preset_folder_action_pending,
            [
                {
                    "action": "set_collapsed",
                    "folder_key": "games",
                    "name": "",
                    "direction": 0,
                    "collapsed": True,
                    "context_extra": {},
                }
            ],
        )

    def test_folder_action_result_ignored_when_new_folder_action_is_pending(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_folder_action_request_id = 5
        page._preset_folder_action_pending = [
            {
                "action": "rename",
                "folder_key": "games",
                "name": "Games",
                "direction": 0,
                "collapsed": False,
                "context_extra": {},
            }
        ]
        page._runtime_service = Mock()
        page._show_folder_menu_with_state = Mock()
        page._refresh_presets_view_from_cache = Mock()

        UserPresetsPageBase._on_preset_folder_action_finished(
            page,
            5,
            "rename",
            True,
            {"folder_state": {"folders": {}, "items": {}}},
        )

        page._runtime_service.update_cached_folder_state.assert_not_called()
        page._show_folder_menu_with_state.assert_not_called()
        page._refresh_presets_view_from_cache.assert_not_called()

    def test_folder_collapse_result_updates_visible_rows_without_full_refresh(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_folder_action_request_id = 6
        page._preset_folder_action_pending = []
        page._runtime_service = Mock()
        page._presets_model = Mock()
        page._presets_model.set_folder_collapsed.return_value = True
        page._update_presets_view_height = Mock()
        page._schedule_layout_resync = Mock()
        page._refresh_presets_view_from_cache = Mock(
            side_effect=AssertionError("folder collapse must not refresh the whole preset list")
        )

        UserPresetsPageBase._on_preset_folder_action_finished(
            page,
            6,
            "set_collapsed",
            True,
            {"folder_key": "games", "collapsed": True, "folder_state": {"folders": {}, "items": {}}},
        )

        page._runtime_service.update_cached_folder_state.assert_called_once_with({"folders": {}, "items": {}})
        page._presets_model.set_folder_collapsed.assert_called_once_with("games", True)
        page._update_presets_view_height.assert_called_once_with()
        page._schedule_layout_resync.assert_called_once_with()
        page._refresh_presets_view_from_cache.assert_not_called()

    def test_storage_action_waits_while_next_write_start_is_scheduled(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_write_action_start_scheduled = True
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._pending_preset_storage_actions = []
        page._preset_storage_action_request_id = 0
        page.create_preset_storage_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_storage_action(
            page,
            "rating",
            name="Preset.txt",
            display_name="Preset",
            rating=7,
        )

        page.create_preset_storage_action_worker.assert_not_called()
        self.assertEqual(page._pending_preset_write_actions[0]["kind"], "storage")
        self.assertEqual(page._pending_preset_storage_actions[0]["action"], "rating")

    def test_item_action_waits_while_storage_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=True)
        page._pending_preset_write_actions = []
        page._preset_item_action_pending = []
        page._preset_item_action_request_id = 0
        page.create_preset_item_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_item_action(
            page,
            "delete",
            file_name="Preset.txt",
            display_name="Preset",
        )

        page.create_preset_item_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_preset_write_actions,
            [
                {
                    "kind": "item",
                    "action": "delete",
                    "name": "",
                    "display_name": "Preset",
                    "rating": 0,
                    "direction": 0,
                    "cached_metadata": None,
                    "source_kind": "",
                    "source_id": "",
                    "destination_kind": "",
                    "destination_id": "",
                    "destination_folder_key": "",
                    "file_name": "Preset.txt",
                    "file_path": "",
                }
            ],
        )

    def test_activation_waits_while_item_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_runtime = _Runtime(running=True)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._preset_activate_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._pending_preset_activation = None
        page._restore_preset_activation_marker_file_name = ""
        page._preset_activate_request_id = 0
        page._runtime_service = Mock()
        page.create_preset_activate_worker = Mock(return_value=_ActivationWorker())

        UserPresetsPageBase._request_preset_activation(page, "Next.txt", "Next")

        page.create_preset_activate_worker.assert_not_called()
        page._runtime_service.apply_active_preset_marker_for_file.assert_not_called()
        self.assertEqual(
            page._pending_preset_write_actions,
            [
                {
                    "kind": "activate",
                    "action": "",
                    "name": "",
                    "display_name": "Next",
                    "rating": 0,
                    "direction": 0,
                    "cached_metadata": None,
                    "source_kind": "",
                    "source_id": "",
                    "destination_kind": "",
                    "destination_id": "",
                    "destination_folder_key": "",
                    "file_name": "Next.txt",
                    "file_path": "",
                }
            ],
        )

        page._preset_item_action_runtime._running = False
        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_item_action_worker_finished(page, SimpleNamespace(_request_id=0))

        page.create_preset_activate_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_activate_worker.assert_called_once_with(
            1,
            file_name="Next.txt",
            display_name="Next",
        )
        page._runtime_service.apply_active_preset_marker_for_file.assert_called_once_with("Next.txt")

    def test_stale_item_action_worker_finished_does_not_start_pending_write(self) -> None:
        old_worker = object()
        current_worker = object()
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_runtime_worker = current_worker
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._preset_folder_action_runtime = _Runtime(running=False)
        page._preset_folder_action_pending = []
        page._preset_write_action_start_scheduled = False
        page._preset_folder_action_start_scheduled = False
        page._cleanup_in_progress = False
        page._pending_preset_write_actions = [
            {
                "kind": "activate",
                "file_name": "Next.txt",
                "display_name": "Next",
            }
        ]
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_item_action_worker_finished(page, old_worker)

        self.assertIs(page._preset_item_action_runtime_worker, current_worker)
        self.assertEqual(len(callbacks), 0)
        self.assertEqual(page._pending_preset_write_actions[0]["file_name"], "Next.txt")

    def test_cleared_item_action_worker_finished_does_not_start_pending_write(self) -> None:
        old_worker = object()
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_runtime_worker = None
        page._pending_preset_write_actions = [
            {
                "kind": "activate",
                "file_name": "Next.txt",
                "display_name": "Next",
            }
        ]
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_item_action_worker_finished(page, old_worker)

        self.assertIsNone(page._preset_item_action_runtime_worker)
        self.assertEqual(callbacks, [])
        self.assertEqual(page._pending_preset_write_actions[0]["file_name"], "Next.txt")

    def test_scheduled_activation_uses_latest_request_before_worker_starts(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._preset_activate_request_id = 0
        page._pending_preset_activation = None
        page._pending_preset_write_actions = []
        page._restore_preset_activation_marker_file_name = ""
        page._runtime_service = Mock()
        page.create_preset_activate_worker = Mock(return_value=_ActivationWorker())
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._schedule_preset_write_action_start(
                page,
                {
                    "kind": "activate",
                    "file_name": "Old.txt",
                    "display_name": "Old",
                },
            )
            UserPresetsPageBase._request_preset_activation(page, "Latest.txt", "Latest")

        page.create_preset_activate_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_activate_worker.assert_called_once_with(
            1,
            file_name="Latest.txt",
            display_name="Latest",
        )
        page._runtime_service.apply_active_preset_marker_for_file.assert_called_once_with("Latest.txt")
        self.assertEqual(page._pending_preset_write_actions, [])
        self.assertIsNone(page._pending_preset_activation)

    def test_pending_activation_queue_keeps_only_latest_preset_click(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=True)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._pending_preset_activation = None
        page.create_preset_activate_worker = Mock(return_value=_ActivationWorker())

        UserPresetsPageBase._request_preset_activation(page, "Old.txt", "Old")
        UserPresetsPageBase._request_preset_activation(page, "Latest.txt", "Latest")

        page.create_preset_activate_worker.assert_not_called()
        self.assertEqual(
            [
                (operation["kind"], operation["file_name"], operation["display_name"])
                for operation in page._pending_preset_write_actions
            ],
            [("activate", "Latest.txt", "Latest")],
        )
        self.assertEqual(page._pending_preset_activation, ("Latest.txt", "Latest"))

    def test_edit_action_waits_while_activation_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=True)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._preset_edit_action_pending = []
        page._preset_edit_action_request_id = 0
        page.create_preset_edit_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_edit_action(
            page,
            "rename",
            current_name="Old.txt",
            new_name="New.txt",
        )

        page.create_preset_edit_action_worker.assert_not_called()
        self.assertEqual(page._pending_preset_write_actions[0]["kind"], "edit")

        page._preset_activate_runtime._running = False
        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_activate_worker_finished(page, SimpleNamespace(_request_id=0))

        page.create_preset_edit_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_edit_action_worker.assert_called_once_with(
            1,
            action="rename",
            name="",
            current_name="Old.txt",
            new_name="New.txt",
            from_current=False,
        )

    def test_bulk_action_waits_while_edit_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=True)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._preset_bulk_action_pending = []
        page._preset_bulk_action_request_id = 0
        page._preset_bulk_action_kind = ""
        page.create_preset_bulk_action_worker = Mock(return_value=_Worker())

        self.assertTrue(
            UserPresetsPageBase._request_preset_bulk_action(
                page,
                "import",
                file_path="C:/Temp/Preset.txt",
            )
        )

        page.create_preset_bulk_action_worker.assert_not_called()
        self.assertEqual(page._pending_preset_write_actions[0]["kind"], "bulk")

        page._preset_edit_action_runtime._running = False
        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_edit_action_worker_finished(page, SimpleNamespace(_request_id=0))

        page.create_preset_bulk_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_bulk_action_worker.assert_called_once_with(
            1,
            action="import",
            file_path="C:/Temp/Preset.txt",
        )

    def test_folder_action_restarts_later_after_storage_worker_finished(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._preset_folder_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._preset_folder_action_pending = [
            {
                "action": "set_collapsed",
                "folder_key": "games",
                "name": "",
                "direction": 0,
                "collapsed": True,
                "context_extra": {},
            }
        ]
        page._preset_folder_action_request_id = 0
        page.create_preset_folder_action_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_storage_action_worker_finished(page, SimpleNamespace(_request_id=0))

        page.create_preset_folder_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_folder_action_worker.assert_called_once_with(
            1,
            action="set_collapsed",
            folder_key="games",
            name="",
            direction=0,
            collapsed=True,
            context_extra={},
        )

    def test_storage_action_restarts_later_after_folder_worker_finished(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._preset_folder_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = [
            {
                "kind": "storage",
                "action": "rating",
                "name": "Default.txt",
                "display_name": "Default",
                "rating": 5,
                "direction": 0,
                "cached_metadata": None,
                "source_kind": "",
                "source_id": "",
                "destination_kind": "",
                "destination_id": "",
                "destination_folder_key": "",
                "file_name": "",
                "file_path": "",
            }
        ]
        page._pending_preset_storage_actions = [
            {
                "action": "rating",
                "name": "Default.txt",
                "display_name": "Default",
                "rating": 5,
                "direction": 0,
                "cached_metadata": None,
                "source_kind": "",
                "source_id": "",
                "destination_kind": "",
                "destination_id": "",
                "destination_folder_key": "",
            }
        ]
        page._preset_folder_action_pending = []
        page._preset_storage_action_request_id = 0
        page.create_preset_storage_action_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_folder_action_worker_finished(page, SimpleNamespace(_request_id=0))

        page.create_preset_storage_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_storage_action_worker.assert_called_once_with(
            1,
            action="rating",
            name="Default.txt",
            display_name="Default",
            rating=5,
            direction=0,
            cached_metadata=None,
            source_kind="",
            source_id="",
            destination_kind="",
            destination_id="",
            destination_folder_key="",
        )

    def test_write_action_errors_ignored_when_next_write_is_pending(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_edit_action_request_id = 2
        page._preset_bulk_action_request_id = 3
        page._preset_item_action_request_id = 4
        page._pending_preset_write_actions = [{"kind": "activate", "file_name": "Next.txt"}]
        page._pending_preset_storage_actions = []
        page._preset_item_action_pending = []
        page._preset_bulk_action_pending = []
        page._preset_edit_action_pending = []
        page._pending_preset_activation = None
        page._preset_folder_action_pending = []
        page._config = Mock(tr_prefix="page.user_presets")
        page._ui_language = "ru"
        page.window = Mock(return_value=None)

        with (
            patch("presets.ui.common.user_presets_page.InfoBar.error") as error,
            patch("presets.ui.common.user_presets_page.log") as log_mock,
        ):
            UserPresetsPageBase._on_preset_edit_action_failed(page, 2, "rename", "old edit", {})
            UserPresetsPageBase._on_preset_bulk_action_failed(page, 3, "import", "old bulk", {})
            UserPresetsPageBase._on_preset_item_action_failed(page, 4, "delete", "old item")

        error.assert_not_called()
        log_mock.assert_not_called()

    def test_write_action_results_ignored_when_next_write_is_pending(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_edit_action_request_id = 2
        page._preset_bulk_action_request_id = 3
        page._preset_storage_action_request_id = 4
        page._preset_item_action_request_id = 5
        page._pending_preset_write_actions = [{"kind": "activate", "file_name": "Next.txt"}]
        page._pending_preset_storage_actions = []
        page._preset_item_action_pending = []
        page._preset_bulk_action_pending = []
        page._preset_edit_action_pending = []
        page._pending_preset_activation = None
        page._preset_folder_action_pending = []
        page._runtime_service = Mock()
        page._config = Mock(tr_prefix="page.user_presets")
        page._ui_language = "ru"
        page.window = Mock(return_value=None)
        page._refresh_presets_view_from_cache = Mock()
        page._update_cached_preset_rating = Mock()
        page._apply_preset_move_locally = Mock(return_value=False)

        edit_result = SimpleNamespace(
            ok=True,
            structure_changed=True,
            preset_file_name="Renamed.txt",
            preset_display_name="Renamed",
            log_message="old edit",
            log_level="INFO",
        )
        bulk_result = SimpleNamespace(
            ok=True,
            structure_changed=True,
            actual_file_name="Imported.txt",
            actual_name="Imported",
            infobar_level="success",
            infobar_title="Imported",
            infobar_content="Done",
            log_message="old bulk",
            log_level="INFO",
        )
        item_result = SimpleNamespace(
            ok=True,
            structure_changed=True,
            error_code="",
            preset_file_name="Copy.txt",
            preset_display_name="Copy",
            infobar_level="success",
            infobar_title="Copied",
            infobar_content="Done",
            log_message="old item",
            log_level="INFO",
        )

        with (
            patch("presets.ui.common.user_presets_page.InfoBar.success") as success,
            patch("presets.ui.common.user_presets_page.InfoBar.warning") as warning,
            patch("presets.ui.common.user_presets_page.InfoBar.error") as error,
            patch("presets.ui.common.user_presets_page.log") as log_mock,
        ):
            UserPresetsPageBase._on_preset_edit_action_finished(
                page,
                2,
                "rename",
                edit_result,
                {"current_name": "Old.txt", "new_name": "Renamed.txt"},
            )
            UserPresetsPageBase._on_preset_bulk_action_finished(page, 3, "import", bulk_result, {})
            UserPresetsPageBase._on_preset_storage_action_finished(
                page,
                4,
                "rating",
                True,
                {"name": "Old.txt", "rating": 9, "folder_state": {"folders": {}, "items": {}}},
            )
            UserPresetsPageBase._on_preset_item_action_finished(
                page,
                5,
                "duplicate",
                item_result,
                {"file_name": "Old.txt"},
            )

        log_mock.assert_not_called()
        success.assert_not_called()
        warning.assert_not_called()
        error.assert_not_called()
        page._runtime_service.add_created_preset_locally.assert_not_called()
        page._runtime_service.rename_preset_locally.assert_not_called()
        page._runtime_service.mark_presets_structure_changed.assert_not_called()
        page._runtime_service.update_cached_folder_state.assert_not_called()
        page._refresh_presets_view_from_cache.assert_not_called()
        page._update_cached_preset_rating.assert_not_called()
        page._apply_preset_move_locally.assert_not_called()

    def test_rating_result_updates_single_visible_row_without_full_refresh(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_storage_action_request_id = 4
        page._pending_preset_write_actions = []
        page._pending_preset_storage_actions = []
        page._preset_item_action_pending = []
        page._preset_bulk_action_pending = []
        page._preset_edit_action_pending = []
        page._pending_preset_activation = None
        page._preset_folder_action_pending = []
        page._runtime_service = Mock()
        page._runtime_service.cached_presets_metadata.return_value = {
            "Preset.txt": {"name": "Preset", "rating": 1}
        }
        page._presets_model = Mock()
        page._presets_model.update_preset_row.return_value = True
        page._refresh_presets_view_from_cache = Mock(
            side_effect=AssertionError("rating must not refresh the whole preset list")
        )
        page._update_presets_view_height = Mock()
        page._schedule_layout_resync = Mock()

        with patch("presets.ui.common.user_presets_page.log") as log_mock:
            UserPresetsPageBase._on_preset_storage_action_finished(
                page,
                4,
                "rating",
                True,
                {"name": "Preset.txt", "rating": 7, "folder_state": {"folders": {}, "items": {}}},
            )

        page._presets_model.update_preset_row.assert_called_once_with("Preset.txt", rating=7)
        page._refresh_presets_view_from_cache.assert_not_called()
        page._update_presets_view_height.assert_not_called()
        page._schedule_layout_resync.assert_not_called()
        log_mock.assert_not_called()

    def test_move_step_result_updates_visible_row_without_full_refresh_when_context_is_known(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_storage_action_request_id = 4
        page._pending_preset_write_actions = []
        page._pending_preset_storage_actions = []
        page._preset_item_action_pending = []
        page._preset_bulk_action_pending = []
        page._preset_edit_action_pending = []
        page._pending_preset_activation = None
        page._preset_folder_action_pending = []
        page._runtime_service = Mock()
        page._apply_preset_move_locally = Mock(return_value=True)
        page._refresh_presets_view_from_cache = Mock(
            side_effect=AssertionError("move_step must not refresh the whole preset list")
        )

        UserPresetsPageBase._on_preset_storage_action_finished(
            page,
            4,
            "move_step",
            True,
            {
                "name": "Preset.txt",
                "destination_kind": "preset_after",
                "destination_id": "Other.txt",
                "destination_folder_key": "common",
                "folder_state": {"folders": {}, "items": {}},
            },
        )

        page._apply_preset_move_locally.assert_called_once_with(
            "Preset.txt",
            "preset_after",
            "Other.txt",
            "common",
        )
        page._refresh_presets_view_from_cache.assert_not_called()

    def test_legacy_pending_edit_action_restarts_later_after_worker_finished(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._preset_edit_action_pending = [
            {
                "action": "rename",
                "name": "Old.txt",
                "current_name": "Old.txt",
                "new_name": "New.txt",
                "from_current": False,
            }
        ]
        page._preset_edit_action_request_id = 0
        page.create_preset_edit_action_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_edit_action_worker_finished(page, SimpleNamespace(_request_id=0))

        page.create_preset_edit_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_edit_action_worker.assert_called_once_with(
            1,
            action="rename",
            name="Old.txt",
            current_name="Old.txt",
            new_name="New.txt",
            from_current=False,
        )

    def test_legacy_pending_bulk_action_restarts_later_after_worker_finished(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._preset_bulk_action_pending = [{"action": "import", "file_path": "C:/Temp/Preset.txt"}]
        page._preset_bulk_action_request_id = 0
        page._preset_bulk_action_kind = ""
        page._bulk_reset_running = False
        page.create_preset_bulk_action_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_bulk_action_worker_finished(page, SimpleNamespace(_request_id=0))

        page.create_preset_bulk_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_bulk_action_worker.assert_called_once_with(
            1,
            action="import",
            file_path="C:/Temp/Preset.txt",
        )

    def test_cleanup_clears_pending_write_actions(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._pending_preset_activation = ("Preset.txt", "Preset")
        page._restore_preset_activation_marker_file_name = "Old.txt"
        page._pending_preset_write_actions = [{"kind": "item", "action": "delete"}]
        page._pending_preset_storage_actions = [{"action": "rating"}]
        page._preset_item_action_pending = [{"action": "delete"}]
        page._preset_folder_action_pending = []
        page._preset_open_folder_pending = True
        page._preset_bulk_action_kind = "reset_all"
        page._bulk_reset_running = True
        for attr in (
            "_preset_activate_request_id",
            "_preset_item_action_request_id",
            "_preset_bulk_action_request_id",
            "_preset_edit_action_request_id",
            "_preset_storage_action_request_id",
            "_preset_folder_action_request_id",
            "_preset_open_folder_request_id",
            "_preset_link_action_request_id",
        ):
            setattr(page, attr, 0)

        UserPresetsPageBase._stop_action_workers_for_cleanup(page)

        self.assertEqual(page._pending_preset_write_actions, [])
        self.assertEqual(page._pending_preset_storage_actions, [])
        self.assertEqual(page._preset_item_action_pending, [])


if __name__ == "__main__":
    unittest.main()
