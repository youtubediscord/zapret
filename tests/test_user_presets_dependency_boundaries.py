from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class UserPresetsDependencyBoundaryTests(unittest.TestCase):
    def test_user_presets_page_receives_link_worker_factory_without_open_url_callable(self) -> None:
        from app.page_names import PageName
        from presets.ui.common.user_presets_page import UserPresetsPageBase
        from ui.page_deps.presets import build_user_presets_page_kwargs

        init_source = inspect.getsource(UserPresetsPageBase.__init__)
        page_source = inspect.getsource(UserPresetsPageBase)
        runtime_source = inspect.getsource(UserPresetsPageBase._build_page_runtime)

        self.assertNotIn("open_url", init_source)
        self.assertNotIn("self._open_url", page_source)
        self.assertNotIn("external_actions_feature", init_source)
        self.assertNotIn("self._external_actions", page_source)
        self.assertNotIn("open_url=self._open_url", runtime_source)
        self.assertNotIn(
            "open_url=self._open_url",
            inspect.getsource(UserPresetsPageBase.create_preset_link_action_worker),
        )

        external_actions = Mock()
        presets = Mock()
        kwargs = build_user_presets_page_kwargs(
            page_name=PageName.ZAPRET2_USER_PRESETS,
            presets_feature=presets,
            external_actions_feature=external_actions,
            open_preset_raw_editor=Mock(),
            ui_state_store=Mock(),
        )

        self.assertNotIn("open_url", kwargs)
        self.assertNotIn("external_actions_feature", kwargs)
        parent = object()
        kwargs["create_preset_link_action_worker"](7, action="info", parent=parent)
        presets.create_preset_link_action_worker.assert_called_once_with(
            7,
            open_url=external_actions.open_url,
            action="info",
            parent=parent,
        )

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
        self.assertNotIn("delete_preset_item_meta", init_source)
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
        self.assertTrue(callable(kwargs["create_preset_link_action_worker"]))
        self.assertNotIn("open_url", kwargs)
        self.assertIs(
            kwargs["create_preset_folder_action_worker"],
            presets.create_preset_folder_action_worker,
        )
        self.assertIs(
            kwargs["create_preset_storage_action_worker"],
            presets.create_preset_storage_action_worker,
        )
        self.assertIs(kwargs["load_preset_folder_state"], presets.load_preset_folder_state)
        self.assertNotIn("delete_preset_item_meta", kwargs)

    def test_user_presets_page_uses_worker_runtime_instead_of_manual_worker_fields(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        init_source = inspect.getsource(UserPresetsPageBase.__init__)
        page_source = inspect.getsource(UserPresetsPageBase)
        request_sources = (
            inspect.getsource(UserPresetsPageBase._start_preset_open_folder_worker),
            inspect.getsource(UserPresetsPageBase._request_preset_edit_action)
            + inspect.getsource(UserPresetsPageBase._start_preset_edit_action_worker),
            inspect.getsource(UserPresetsPageBase._start_preset_bulk_action_worker),
            inspect.getsource(UserPresetsPageBase._request_preset_folder_action),
            inspect.getsource(UserPresetsPageBase._request_preset_storage_action)
            + inspect.getsource(UserPresetsPageBase._start_preset_storage_action_worker),
            inspect.getsource(UserPresetsPageBase._request_preset_activation)
            + inspect.getsource(UserPresetsPageBase._start_preset_activation_worker),
            inspect.getsource(UserPresetsPageBase._request_preset_item_action)
            + inspect.getsource(UserPresetsPageBase._start_preset_item_action_worker),
            inspect.getsource(UserPresetsPageBase._request_preset_link_action),
        )

        self.assertIn("OneShotWorkerRuntime", init_source)
        for attr in (
            "_preset_activate_runtime",
            "_preset_item_action_runtime",
            "_preset_bulk_action_runtime",
            "_preset_edit_action_runtime",
            "_preset_storage_action_runtime",
            "_preset_folder_action_runtime",
            "_preset_open_folder_runtime",
            "_preset_link_action_runtime",
        ):
            self.assertIn(attr, init_source)

        for source in request_sources:
            self.assertIn("start_qthread_worker", source)
            self.assertNotIn("worker.start()", source)

        for attr in (
            "_preset_activate_worker =",
            "_preset_item_action_worker =",
            "_preset_bulk_action_worker =",
            "_preset_edit_action_worker =",
            "_preset_storage_action_worker =",
            "_preset_folder_action_worker =",
            "_preset_open_folder_worker =",
            "_preset_link_action_worker =",
        ):
            self.assertNotIn(attr, page_source)

    def test_user_presets_link_actions_queue_while_worker_runs(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_link_action_runtime = _Runtime()
        page._preset_link_action_pending = []
        page.create_preset_link_action_worker = Mock()

        UserPresetsPageBase._request_preset_link_action(page, "info")
        UserPresetsPageBase._request_preset_link_action(page, "new_configs")

        self.assertEqual(page._preset_link_action_pending, ["info", "new_configs"])
        page.create_preset_link_action_worker.assert_not_called()

    def test_duplicate_user_presets_link_action_is_queued_once(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_link_action_runtime = _Runtime()
        page._preset_link_action_start_scheduled = False
        page._preset_link_action_pending = []
        page.create_preset_link_action_worker = Mock()

        UserPresetsPageBase._request_preset_link_action(page, "info")
        UserPresetsPageBase._request_preset_link_action(page, "info")

        self.assertEqual(page._preset_link_action_pending, ["info"])
        page.create_preset_link_action_worker.assert_not_called()

    def test_user_presets_link_action_waits_while_restart_is_scheduled(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_link_action_start_scheduled = True
        page._preset_link_action_pending = []
        page._preset_link_action_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        UserPresetsPageBase._request_preset_link_action(page, "info")

        page._preset_link_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(page._preset_link_action_pending, ["info"])

    def test_user_presets_link_worker_finished_starts_next_queued_action(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

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

            def isRunning(self) -> bool:
                return False

        worker = _Worker()
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._cleanup_in_progress = False
        page._preset_link_action_runtime = OneShotWorkerRuntime()
        page._preset_link_action_request_id = 0
        page._preset_link_action_pending = ["info", "new_configs"]
        page.create_preset_link_action_worker = Mock(return_value=worker)

        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_link_action_worker_finished(page, object())

        page.create_preset_link_action_worker.assert_not_called()
        worker.start.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_link_action_worker.assert_called_once_with(1, action="info")
        worker.start.assert_called_once()
        self.assertEqual(page._preset_link_action_pending, ["new_configs"])

    def test_stale_user_presets_link_worker_finished_does_not_start_pending_action(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        current_worker = object()
        old_worker = object()
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._cleanup_in_progress = False
        page._preset_link_action_runtime_worker = current_worker
        page._preset_link_action_pending = ["info"]
        page._schedule_preset_link_action_start = Mock(
            side_effect=AssertionError("stale link worker must not start pending action")
        )

        UserPresetsPageBase._on_preset_link_action_worker_finished(page, old_worker)

        self.assertEqual(page._preset_link_action_pending, ["info"])
        self.assertIs(page._preset_link_action_runtime_worker, current_worker)

    def test_user_presets_link_scheduled_start_queues_next_action(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._cleanup_in_progress = False
        page._preset_link_action_start_scheduled = False
        page._preset_link_action_pending = []
        page._request_preset_link_action = Mock()
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._schedule_preset_link_action_start(page, "info")
            UserPresetsPageBase._schedule_preset_link_action_start(page, "new_configs")

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(page._preset_link_action_pending, ["new_configs"])
        page._request_preset_link_action.assert_not_called()

        callbacks[0]()

        page._request_preset_link_action.assert_called_once_with("info")
        self.assertEqual(page._preset_link_action_pending, ["new_configs"])

    def test_user_presets_open_folder_pending_restarts_later_after_worker_finished(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._cleanup_in_progress = False
        page._preset_open_folder_pending = True
        page._start_preset_open_folder_worker = Mock()
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_open_folder_worker_finished(page, object())

        page._start_preset_open_folder_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._start_preset_open_folder_worker.assert_called_once_with()

    def test_stale_user_presets_open_folder_worker_finish_does_not_restart_pending_open(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        current_worker = object()
        old_worker = object()
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._cleanup_in_progress = False
        page._preset_open_folder_pending = True
        page._preset_open_folder_runtime_worker = current_worker
        page._schedule_preset_open_folder_worker_start = Mock(
            side_effect=AssertionError("stale open-folder worker must not restart pending open")
        )

        UserPresetsPageBase._on_preset_open_folder_worker_finished(page, old_worker)

        self.assertTrue(page._preset_open_folder_pending)
        self.assertIs(page._preset_open_folder_runtime_worker, current_worker)

    def test_user_presets_open_folder_waits_while_restart_is_scheduled(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_open_folder_start_scheduled = True
        page._preset_open_folder_pending = False
        page._worker_runtime_is_running = Mock(return_value=False)
        page._start_preset_open_folder_worker = Mock()

        UserPresetsPageBase._request_preset_open_folder_action(page)

        page._start_preset_open_folder_worker.assert_not_called()
        self.assertTrue(page._preset_open_folder_pending)

    def test_user_presets_folder_action_pending_restarts_later_after_worker_finished(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._cleanup_in_progress = False
        page._preset_folder_action_pending = [
            {
                "action": "move",
                "folder_key": "favorites",
                "name": "Preset.txt",
                "direction": 1,
                "collapsed": False,
                "context_extra": {"source": "menu"},
            }
        ]
        page._request_preset_folder_action = Mock()
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_folder_action_worker_finished(page, object())

        page._request_preset_folder_action.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._request_preset_folder_action.assert_called_once_with(
            "move",
            folder_key="favorites",
            name="Preset.txt",
            direction=1,
            collapsed=False,
            context_extra={"source": "menu"},
        )

    def test_user_presets_folder_scheduled_start_queues_next_action(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        first = {
            "action": "move",
            "folder_key": "favorites",
            "name": "First.txt",
            "direction": 1,
            "collapsed": False,
            "context_extra": {"source": "menu"},
        }
        second = {
            "action": "toggle",
            "folder_key": "favorites",
            "name": "",
            "direction": 0,
            "collapsed": True,
            "context_extra": {"source": "toolbar"},
        }
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._cleanup_in_progress = False
        page._preset_folder_action_start_scheduled = False
        page._preset_folder_action_pending = []
        page._request_preset_folder_action = Mock()
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._schedule_preset_folder_action_start(page, first)
            UserPresetsPageBase._schedule_preset_folder_action_start(page, second)

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(page._preset_folder_action_pending, [second])
        page._request_preset_folder_action.assert_not_called()

        callbacks[0]()

        page._request_preset_folder_action.assert_called_once_with(
            "move",
            folder_key="favorites",
            name="First.txt",
            direction=1,
            collapsed=False,
            context_extra={"source": "menu"},
        )
        self.assertEqual(page._preset_folder_action_pending, [second])

    def test_user_presets_folder_action_waits_while_restart_is_scheduled(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_folder_action_start_scheduled = True
        page._preset_folder_action_pending = []
        page._preset_folder_action_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        UserPresetsPageBase._request_preset_folder_action(
            page,
            "move",
            folder_key="favorites",
            name="Preset.txt",
            direction=1,
            collapsed=False,
            context_extra={"source": "menu"},
        )

        page._preset_folder_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(
            page._preset_folder_action_pending,
            [
                {
                    "action": "move",
                    "folder_key": "favorites",
                    "name": "Preset.txt",
                    "direction": 1,
                    "collapsed": False,
                    "context_extra": {"source": "menu"},
                }
            ],
        )

    def test_duplicate_user_presets_folder_action_is_queued_once(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_folder_action_start_scheduled = True
        page._preset_folder_action_pending = []
        page._preset_folder_action_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        for _ in range(2):
            UserPresetsPageBase._request_preset_folder_action(
                page,
                "move",
                folder_key="favorites",
                name="Preset.txt",
                direction=1,
                collapsed=False,
                context_extra={"source": "menu"},
            )

        page._preset_folder_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(
            page._preset_folder_action_pending,
            [
                {
                    "action": "move",
                    "folder_key": "favorites",
                    "name": "Preset.txt",
                    "direction": 1,
                    "collapsed": False,
                    "context_extra": {"source": "menu"},
                }
            ],
        )

    def test_user_presets_folder_set_collapsed_keeps_latest_pending_state(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_folder_action_start_scheduled = True
        page._preset_folder_action_pending = []
        page._preset_folder_action_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        UserPresetsPageBase._request_preset_folder_action(
            page,
            "set_collapsed",
            folder_key="games",
            collapsed=True,
        )
        UserPresetsPageBase._request_preset_folder_action(
            page,
            "set_collapsed",
            folder_key="games",
            collapsed=False,
        )

        page._preset_folder_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(
            page._preset_folder_action_pending,
            [
                {
                    "action": "set_collapsed",
                    "folder_key": "games",
                    "name": "",
                    "direction": 0,
                    "collapsed": False,
                    "context_extra": {},
                }
            ],
        )

    def test_user_presets_folder_toggle_fallback_keeps_order(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_folder_action_start_scheduled = True
        page._preset_folder_action_pending = []
        page._preset_folder_action_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        UserPresetsPageBase._request_preset_folder_action(page, "toggle_collapsed", folder_key="games")
        UserPresetsPageBase._request_preset_folder_action(page, "toggle_collapsed", folder_key="games")

        page._preset_folder_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(len(page._preset_folder_action_pending), 2)
        self.assertEqual(
            [item["action"] for item in page._preset_folder_action_pending],
            ["toggle_collapsed", "toggle_collapsed"],
        )

    def test_user_presets_folder_click_requests_explicit_collapsed_state(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        class _Index:
            def __init__(self, folder_key: str, collapsed: bool):
                self._folder_key = folder_key
                self._collapsed = collapsed

            def isValid(self) -> bool:
                return True

            def data(self, role):
                if role == _Model.FolderKeyRole:
                    return self._folder_key
                if role == _Model.CollapsedRole:
                    return self._collapsed
                return None

        class _Model:
            FolderKeyRole = 1
            CollapsedRole = 2

            def rowCount(self) -> int:
                return 1

            def index(self, row: int, column: int):
                return _Index("games", True)

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._presets_model = _Model()
        page._request_preset_folder_action = Mock()

        UserPresetsPageBase._on_toggle_folder(page, "games")

        page._request_preset_folder_action.assert_called_once_with(
            "set_collapsed",
            folder_key="games",
            collapsed=False,
        )

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
