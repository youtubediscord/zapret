from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.feature_facades.updater import UpdaterFeature
import updater.retry_workers as retry_workers
import updater.settings_workers as settings_workers
import updater.update_page_runtime as update_page_runtime


class UpdaterSettingsWorkerArchitectureTests(unittest.TestCase):
    def test_auto_check_workers_receive_feature_action_callables(self) -> None:
        feature_source = inspect.getsource(UpdaterFeature)
        save_source = inspect.getsource(settings_workers.UpdaterAutoCheckSaveWorker)
        load_source = inspect.getsource(settings_workers.UpdaterAutoCheckLoadWorker)
        save_signature = inspect.signature(settings_workers.UpdaterAutoCheckSaveWorker.__init__)
        load_signature = inspect.signature(settings_workers.UpdaterAutoCheckLoadWorker.__init__)

        self.assertNotIn("updater_feature=self", feature_source)
        self.assertNotIn("self._updater", save_source)
        self.assertNotIn("self._updater", load_source)
        self.assertIn("set_auto_update_enabled=self.set_auto_update_enabled", feature_source)
        self.assertIn("is_auto_update_enabled=self.is_auto_update_enabled", feature_source)
        self.assertIn("set_auto_update_enabled", save_signature.parameters)
        self.assertIn("is_auto_update_enabled", load_signature.parameters)
        self.assertNotIn("updater_commands.set_auto_update_enabled", save_source)
        self.assertNotIn("updater_commands.is_auto_update_enabled", load_source)
        self.assertNotIn("import updater.commands", save_source)
        self.assertNotIn("import updater.commands", load_source)

    def test_auto_check_load_queues_while_worker_runs(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._auto_check_load_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        runtime._auto_check_load_pending = False

        update_page_runtime.UpdatePageRuntime._request_auto_check_load(runtime)

        runtime._auto_check_load_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(runtime._auto_check_load_pending)

    def test_auto_check_load_pending_restarts_after_event_loop_turn(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._auto_check_load_pending = True
        runtime._auto_check_load_start_scheduled = False
        runtime._request_auto_check_load = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(update_page_runtime, "QTimer", SimpleNamespace(singleShot=single_shot)):
            update_page_runtime.UpdatePageRuntime._on_auto_check_load_worker_finished(runtime, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        runtime._request_auto_check_load.assert_not_called()

        single_shot.call_args.args[1]()

        runtime._request_auto_check_load.assert_called_once_with()
        self.assertFalse(runtime._auto_check_load_pending)

    def test_auto_check_load_result_ignored_when_new_load_is_pending(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._auto_check_user_changed = False
        runtime._auto_check_load_pending = True
        runtime._auto_check_load_runtime = Mock()
        runtime._auto_check_load_runtime.is_current.return_value = True
        runtime._view = Mock()
        runtime._resolve_idle_view_decision = Mock()
        runtime.apply_idle_view_state = Mock()

        update_page_runtime.UpdatePageRuntime._on_auto_check_load_finished(runtime, 12, True)

        runtime._view.set_auto_check_toggle_checked.assert_not_called()
        runtime._resolve_idle_view_decision.assert_not_called()
        runtime.apply_idle_view_state.assert_not_called()

    def test_channel_open_worker_receives_feature_action_callable(self) -> None:
        feature_source = inspect.getsource(UpdaterFeature)
        worker_source = inspect.getsource(settings_workers.UpdaterChannelOpenWorker)
        worker_signature = inspect.signature(settings_workers.UpdaterChannelOpenWorker.__init__)
        runtime_source = inspect.getsource(update_page_runtime.UpdatePageRuntime)

        self.assertNotIn("updater_feature=self", feature_source)
        self.assertNotIn("self._updater", worker_source)
        self.assertIn("open_update_channel=self.open_update_channel", feature_source)
        self.assertIn("open_update_channel", worker_signature.parameters)
        self.assertIn("_update_channel_open_pending", runtime_source)
        self.assertNotIn("updater_commands.open_update_channel", worker_source)
        self.assertNotIn("import updater.commands", worker_source)

    def test_update_channel_open_queues_while_worker_runs(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._update_channel_open_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        runtime._update_channel_open_pending = ""
        runtime._update_channel_open_start_scheduled = False

        update_page_runtime.UpdatePageRuntime.request_open_update_channel(runtime, "dev")

        runtime._update_channel_open_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(runtime._update_channel_open_pending, "dev")

    def test_update_channel_open_pending_restarts_after_event_loop_turn(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._update_channel_open_pending = "dev"
        runtime._request_update_channel_open = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(update_page_runtime, "QTimer", SimpleNamespace(singleShot=single_shot)):
            update_page_runtime.UpdatePageRuntime._on_update_channel_open_worker_finished(runtime, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        runtime._request_update_channel_open.assert_not_called()

        single_shot.call_args.args[1]()

        runtime._request_update_channel_open.assert_called_once_with("dev")

    def test_update_channel_open_scheduled_start_uses_latest_pending_channel(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._update_channel_open_pending = "stable"
        runtime._update_channel_open_start_scheduled = False
        runtime._update_channel_open_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())
        runtime._request_update_channel_open = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(update_page_runtime, "QTimer", SimpleNamespace(singleShot=single_shot)):
            update_page_runtime.UpdatePageRuntime._on_update_channel_open_worker_finished(runtime, object())
            runtime._update_channel_open_pending = "dev"

        single_shot.call_args.args[1]()

        runtime._request_update_channel_open.assert_called_once_with("dev")

    def test_update_channel_open_result_ignored_when_new_channel_is_pending(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._update_channel_open_pending = "dev"
        runtime._update_channel_open_runtime = Mock()
        runtime._update_channel_open_runtime.is_current.return_value = True
        runtime._view = Mock()

        update_page_runtime.UpdatePageRuntime._on_update_channel_open_finished(
            runtime,
            8,
            SimpleNamespace(ok=False, message="old channel failed"),
        )

        runtime._view.show_update_channel_open_error.assert_not_called()

    def test_cache_invalidate_worker_receives_feature_action_callable(self) -> None:
        feature_source = inspect.getsource(UpdaterFeature)
        worker_source = inspect.getsource(settings_workers.UpdaterCacheInvalidateWorker)
        worker_signature = inspect.signature(settings_workers.UpdaterCacheInvalidateWorker.__init__)

        self.assertIn("create_cache_invalidate_worker", feature_source)
        self.assertIn("invalidate_update_cache=self.invalidate_update_cache", feature_source)
        self.assertIn("invalidate_update_cache", worker_signature.parameters)
        self.assertIn("_invalidate_update_cache", worker_source)
        self.assertNotIn("updater_commands.invalidate_cache", worker_source)
        self.assertNotIn("import updater.commands", worker_source)

    def test_retry_workers_receive_feature_action_callables(self) -> None:
        feature_source = inspect.getsource(UpdaterFeature)
        retry_source = inspect.getsource(retry_workers.UpdaterServerRetryWithoutDpiWorker)
        restart_source = inspect.getsource(retry_workers.UpdaterDpiRestartWorker)

        self.assertIn("create_server_retry_without_dpi_worker", feature_source)
        self.assertIn("retry_server_check_without_dpi=self.retry_server_check_without_dpi", feature_source)
        self.assertIn("create_dpi_restart_worker", feature_source)
        self.assertIn("restart_dpi_after_update=self.restart_dpi_after_update", feature_source)
        self.assertIn("_retry_server_check_without_dpi", retry_source)
        self.assertIn("_restart_dpi_after_update", restart_source)
        self.assertNotIn("import updater.commands", retry_source)
        self.assertNotIn("import updater.commands", restart_source)

    def test_cache_invalidate_pending_restarts_after_event_loop_turn(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._cache_invalidate_pending_context = "manual_check"
        runtime._request_update_cache_invalidate = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(update_page_runtime, "QTimer", SimpleNamespace(singleShot=single_shot)):
            update_page_runtime.UpdatePageRuntime._on_update_cache_invalidate_worker_finished(runtime, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        runtime._request_update_cache_invalidate.assert_not_called()

        single_shot.call_args.args[1]()

        runtime._request_update_cache_invalidate.assert_called_once_with("manual_check")

    def test_cache_invalidate_scheduled_start_uses_latest_pending_context(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._cache_invalidate_pending_context = "manual_check"
        runtime._cache_invalidate_start_scheduled = False
        runtime._cache_invalidate_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        runtime._request_update_cache_invalidate = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(update_page_runtime, "QTimer", SimpleNamespace(singleShot=single_shot)):
            update_page_runtime.UpdatePageRuntime._on_update_cache_invalidate_worker_finished(runtime, object())
            update_page_runtime.UpdatePageRuntime._request_update_cache_invalidate(runtime, "install_update")

        single_shot.call_args.args[1]()

        runtime._request_update_cache_invalidate.assert_called_once_with("install_update")

    def test_auto_check_save_pending_restarts_after_event_loop_turn(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._auto_check_enabled = True
        runtime._auto_check_save_pending = True
        runtime._start_auto_check_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(update_page_runtime, "QTimer", SimpleNamespace(singleShot=single_shot)):
            update_page_runtime.UpdatePageRuntime._on_auto_check_save_finished(runtime)

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        runtime._start_auto_check_save_worker.assert_not_called()

        single_shot.call_args.args[1]()

        runtime._start_auto_check_save_worker.assert_called_once_with(True)

    def test_auto_check_save_scheduled_start_uses_latest_pending_value(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._auto_check_enabled = True
        runtime._auto_check_save_pending = True
        runtime._auto_check_save_start_scheduled = False
        runtime._auto_check_save_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        runtime._start_auto_check_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(update_page_runtime, "QTimer", SimpleNamespace(singleShot=single_shot)):
            update_page_runtime.UpdatePageRuntime._on_auto_check_save_finished(runtime)
            runtime._auto_check_enabled = False
            update_page_runtime.UpdatePageRuntime._request_auto_check_save(runtime, False)

        single_shot.call_args.args[1]()

        runtime._start_auto_check_save_worker.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
