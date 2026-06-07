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
    def _runtime_mock(self):
        return SimpleNamespace(stop=Mock(), cancel=Mock())

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

    def test_cleanup_does_not_wait_for_read_only_update_workers(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._server_worker_runtime = self._runtime_mock()
        runtime._version_worker_runtime = self._runtime_mock()
        runtime._auto_check_load_runtime = self._runtime_mock()
        runtime._update_channel_open_runtime = self._runtime_mock()
        runtime._cache_invalidate_runtime = self._runtime_mock()
        runtime._server_check_gate_runtime = self._runtime_mock()
        runtime._auto_check_save_runtime = self._runtime_mock()
        runtime._dpi_restart_runtime = self._runtime_mock()
        runtime._server_retry_without_dpi_runtime = self._runtime_mock()
        runtime._dpi_restart_after = "version_check"
        runtime._auto_check_save_pending = True
        runtime._auto_check_save_start_scheduled = True
        runtime._auto_check_load_pending = True
        runtime._auto_check_load_start_scheduled = True
        runtime._update_channel_open_pending = "dev"
        runtime._update_channel_open_start_scheduled = True
        runtime._cache_invalidate_pending_context = "manual_check"
        runtime._cache_invalidate_start_scheduled = True
        runtime._server_check_gate_pending = True
        runtime._server_check_gate_start_scheduled = True

        update_page_runtime.UpdatePageRuntime._teardown_server_worker(runtime)
        update_page_runtime.UpdatePageRuntime._teardown_version_worker(runtime)
        update_page_runtime.UpdatePageRuntime._teardown_auto_check_load_worker(runtime)
        update_page_runtime.UpdatePageRuntime._teardown_update_channel_open_worker(runtime)
        update_page_runtime.UpdatePageRuntime._teardown_cache_invalidate_worker(runtime)
        update_page_runtime.UpdatePageRuntime._teardown_server_check_gate_worker(runtime)
        update_page_runtime.UpdatePageRuntime._teardown_auto_check_save_worker(runtime)
        update_page_runtime.UpdatePageRuntime._teardown_dpi_restart_worker(runtime)
        update_page_runtime.UpdatePageRuntime._teardown_server_retry_without_dpi_worker(runtime)

        for worker_runtime, prefix in (
            (runtime._server_worker_runtime, "server_worker"),
            (runtime._version_worker_runtime, "version_worker"),
            (runtime._auto_check_load_runtime, "auto_check_load_worker"),
            (runtime._update_channel_open_runtime, "update_channel_open_worker"),
            (runtime._cache_invalidate_runtime, "cache_invalidate_worker"),
            (runtime._server_check_gate_runtime, "server_check_gate_worker"),
        ):
            worker_runtime.stop.assert_called_once_with(
                blocking=False,
                log_fn=update_page_runtime.log,
                warning_prefix=prefix,
            )
            worker_runtime.cancel.assert_called_once_with()

        runtime._auto_check_save_runtime.stop.assert_called_once_with(
            blocking=True,
            log_fn=update_page_runtime.log,
            warning_prefix="auto_check_save_worker",
        )
        runtime._dpi_restart_runtime.stop.assert_called_once_with(
            blocking=True,
            log_fn=update_page_runtime.log,
            warning_prefix="dpi_restart_worker",
        )
        runtime._server_retry_without_dpi_runtime.stop.assert_called_once_with(
            blocking=True,
            log_fn=update_page_runtime.log,
            warning_prefix="server_retry_without_dpi_worker",
        )

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

    def test_auto_check_load_queue_state_lives_in_state_object(self) -> None:
        init_source = inspect.getsource(update_page_runtime.UpdatePageRuntime.__init__)
        finished_source = inspect.getsource(update_page_runtime.UpdatePageRuntime._on_auto_check_load_worker_finished)
        state_source = inspect.getsource(update_page_runtime.UpdateLatestValueWorkerState)

        self.assertIn("_auto_check_load_state = UpdateLatestValueWorkerState", init_source)
        self.assertIn("schedule_pending_after_finish", finished_source)
        self.assertIn("def schedule_pending_after_finish", state_source)

    def test_stale_auto_check_load_finish_does_not_restart_pending_load(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._auto_check_load_runtime = SimpleNamespace(request_id=3)
        runtime._auto_check_load_pending = True
        runtime._schedule_auto_check_load_start = Mock()

        update_page_runtime.UpdatePageRuntime._on_auto_check_load_worker_finished(
            runtime,
            SimpleNamespace(_request_id=2),
        )

        runtime._schedule_auto_check_load_start.assert_not_called()

    def test_stale_auto_check_load_worker_object_finish_does_not_restart_pending_load(self) -> None:
        current_worker = object()
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._auto_check_load_runtime = SimpleNamespace(worker=current_worker)
        runtime._auto_check_load_pending = True
        runtime._schedule_auto_check_load_start = Mock()

        update_page_runtime.UpdatePageRuntime._on_auto_check_load_worker_finished(
            runtime,
            object(),
        )

        runtime._schedule_auto_check_load_start.assert_not_called()

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

    def test_auto_check_load_error_ignored_when_new_load_is_pending(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._auto_check_load_pending = True
        runtime._auto_check_load_runtime = Mock()
        runtime._auto_check_load_runtime.is_current.return_value = True

        with patch.object(update_page_runtime, "log") as log_mock:
            update_page_runtime.UpdatePageRuntime._on_auto_check_load_failed(
                runtime,
                12,
                "old load failed",
            )

        log_mock.assert_not_called()

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

    def test_update_channel_open_queue_state_lives_in_state_object(self) -> None:
        self.assertTrue(hasattr(update_page_runtime, "UpdateLatestValueWorkerState"))

        state_source = inspect.getsource(update_page_runtime.UpdateLatestValueWorkerState)
        init_source = inspect.getsource(update_page_runtime.UpdatePageRuntime.__init__)
        finished_source = inspect.getsource(update_page_runtime.UpdatePageRuntime._on_update_channel_open_worker_finished)

        self.assertIn("_update_channel_open_state = UpdateLatestValueWorkerState", init_source)
        self.assertIn("schedule_pending_after_finish", finished_source)
        self.assertIn("def schedule_pending_after_finish", state_source)

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

    def test_stale_update_channel_open_finish_does_not_restart_pending_open(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._update_channel_open_runtime = SimpleNamespace(request_id=5)
        runtime._update_channel_open_pending = "dev"
        runtime._schedule_update_channel_open_start = Mock()

        update_page_runtime.UpdatePageRuntime._on_update_channel_open_worker_finished(
            runtime,
            SimpleNamespace(_request_id=4),
        )

        runtime._schedule_update_channel_open_start.assert_not_called()

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

    def test_update_channel_open_error_ignored_when_new_channel_is_pending(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._update_channel_open_pending = "dev"
        runtime._update_channel_open_runtime = Mock()
        runtime._update_channel_open_runtime.is_current.return_value = True
        runtime._view = Mock()

        update_page_runtime.UpdatePageRuntime._on_update_channel_open_failed(
            runtime,
            8,
            "old channel failed",
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

    def test_server_full_check_gate_runs_through_worker(self) -> None:
        feature_source = inspect.getsource(UpdaterFeature)
        runtime_source = inspect.getsource(update_page_runtime.UpdatePageRuntime)
        worker_source = inspect.getsource(settings_workers.UpdaterServerFullCheckGateWorker)
        worker_signature = inspect.signature(settings_workers.UpdaterServerFullCheckGateWorker.__init__)

        self.assertIn("create_server_full_check_gate_worker", feature_source)
        self.assertIn("prepare_server_full_check=self.prepare_server_full_check", feature_source)
        self.assertIn("prepare_server_full_check", worker_signature.parameters)
        self.assertIn("_prepare_server_full_check", worker_source)
        self.assertIn("_server_check_gate_runtime", runtime_source)
        self.assertIn("create_server_full_check_gate_worker", runtime_source)
        self.assertNotIn("UpdateRateLimiter", runtime_source)

    def test_full_server_check_starts_rate_limit_gate_worker(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._check_state = SimpleNamespace(is_active=False)
        runtime._can_start_new_check = Mock(return_value=True)
        runtime._request_server_check_gate = Mock()
        runtime._continue_start_checks = Mock()

        update_page_runtime.UpdatePageRuntime.start_checks(
            runtime,
            telegram_only=False,
            skip_server_rate_limit=True,
        )

        runtime._request_server_check_gate.assert_called_once_with(skip_rate_limit=True)
        runtime._continue_start_checks.assert_not_called()

    def test_telegram_only_check_skips_rate_limit_gate_worker(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._check_state = SimpleNamespace(is_active=False)
        runtime._can_start_new_check = Mock(return_value=True)
        runtime._request_server_check_gate = Mock()
        runtime._continue_start_checks = Mock()

        update_page_runtime.UpdatePageRuntime.start_checks(runtime, telegram_only=True)

        runtime._request_server_check_gate.assert_not_called()
        runtime._continue_start_checks.assert_called_once_with(telegram_only=True, keep_existing_rows=False)

    def test_server_check_gate_result_continues_start_check(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._server_check_gate_pending = None
        runtime._server_check_gate_runtime = Mock()
        runtime._server_check_gate_runtime.is_current.return_value = True
        runtime._continue_start_checks = Mock()

        update_page_runtime.UpdatePageRuntime._on_server_check_gate_finished(
            runtime,
            11,
            SimpleNamespace(telegram_only=True, keep_existing_rows=True, message="limited"),
        )

        runtime._continue_start_checks.assert_called_once_with(
            telegram_only=True,
            keep_existing_rows=True,
        )

    def test_server_check_gate_error_ignored_when_new_gate_is_pending(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._server_check_gate_pending = True
        runtime._server_check_gate_runtime = Mock()
        runtime._server_check_gate_runtime.is_current.return_value = True
        runtime._continue_start_checks = Mock()

        with patch.object(update_page_runtime, "log") as log_mock:
            update_page_runtime.UpdatePageRuntime._on_server_check_gate_failed(
                runtime,
                11,
                "old gate failed",
            )

        log_mock.assert_not_called()
        runtime._continue_start_checks.assert_not_called()

    def test_stale_server_check_gate_finish_does_not_restart_pending_gate(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._server_check_gate_runtime = SimpleNamespace(request_id=8)
        runtime._server_check_gate_pending = True
        runtime._schedule_server_check_gate_start = Mock()

        update_page_runtime.UpdatePageRuntime._on_server_check_gate_worker_finished(
            runtime,
            SimpleNamespace(_request_id=7),
        )

        runtime._schedule_server_check_gate_start.assert_not_called()

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

    def test_cache_invalidate_queue_state_lives_in_state_object(self) -> None:
        init_source = inspect.getsource(update_page_runtime.UpdatePageRuntime.__init__)
        finished_source = inspect.getsource(update_page_runtime.UpdatePageRuntime._on_update_cache_invalidate_worker_finished)
        state_source = inspect.getsource(update_page_runtime.UpdateLatestValueWorkerState)

        self.assertIn("_cache_invalidate_state = UpdateLatestValueWorkerState", init_source)
        self.assertIn("schedule_pending_after_finish", finished_source)
        self.assertIn("def schedule_pending_after_finish", state_source)

    def test_stale_cache_invalidate_finish_does_not_restart_pending_invalidate(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._cache_invalidate_runtime = SimpleNamespace(request_id=7)
        runtime._cache_invalidate_pending_context = "manual_check"
        runtime._schedule_update_cache_invalidate_start = Mock()

        update_page_runtime.UpdatePageRuntime._on_update_cache_invalidate_worker_finished(
            runtime,
            SimpleNamespace(_request_id=6),
        )

        runtime._schedule_update_cache_invalidate_start.assert_not_called()

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

    def test_cache_invalidate_result_ignored_when_new_context_is_pending(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._cache_invalidate_pending_context = "install_update"
        runtime._cache_invalidate_runtime = Mock()
        runtime._cache_invalidate_runtime.is_current.return_value = True
        runtime._continue_after_update_cache_invalidate = Mock()

        update_page_runtime.UpdatePageRuntime._on_update_cache_invalidate_finished(
            runtime,
            10,
            "manual_check",
        )

        runtime._continue_after_update_cache_invalidate.assert_not_called()

    def test_install_update_enters_download_ui_before_cache_invalidate_finishes(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._found_state = update_page_runtime.UpdateFoundState(
            is_available=True,
            version="21.0.0.144",
            release_notes="",
        )
        runtime._download_state = update_page_runtime.UpdateDownloadState()
        runtime._is_download_in_progress = Mock(return_value=False)
        runtime._request_update_cache_invalidate = Mock()
        runtime._view = Mock()

        update_page_runtime.UpdatePageRuntime.install_update(runtime)

        runtime._view.start_update_download.assert_called_once_with("21.0.0.144")
        runtime._view.hide_update_status_card.assert_called_once_with()
        runtime._view.set_update_check_enabled.assert_called_once_with(False)
        runtime._request_update_cache_invalidate.assert_called_once_with("install_update")

    def test_update_worker_progress_shows_preparation_messages_only(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._view = Mock()

        with patch.object(update_page_runtime, "log"):
            update_page_runtime.UpdatePageRuntime._on_update_worker_progress(
                runtime,
                "Остановка DPI для скачивания...",
            )
            update_page_runtime.UpdatePageRuntime._on_update_worker_progress(
                runtime,
                "Скачивание… 12%",
            )

        runtime._view.update_download_status_text.assert_called_once_with(
            "Остановка DPI для скачивания..."
        )

    def test_cache_invalidate_error_ignored_when_new_context_is_pending(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._cache_invalidate_pending_context = "install_update"
        runtime._cache_invalidate_runtime = Mock()
        runtime._cache_invalidate_runtime.is_current.return_value = True
        runtime._continue_after_update_cache_invalidate = Mock()

        with patch.object(update_page_runtime, "log") as log_mock:
            update_page_runtime.UpdatePageRuntime._on_update_cache_invalidate_failed(
                runtime,
                10,
                "manual_check",
                "old invalidate failed",
            )

        log_mock.assert_not_called()
        runtime._continue_after_update_cache_invalidate.assert_not_called()

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

    def test_auto_check_save_queue_state_lives_in_state_object(self) -> None:
        init_source = inspect.getsource(update_page_runtime.UpdatePageRuntime.__init__)
        finished_source = inspect.getsource(update_page_runtime.UpdatePageRuntime._on_auto_check_save_finished)
        state_source = inspect.getsource(update_page_runtime.UpdateLatestValueWorkerState)

        self.assertIn("_auto_check_save_state = UpdateLatestValueWorkerState", init_source)
        self.assertIn("schedule_pending_after_finish", finished_source)
        self.assertIn("def schedule_pending_after_finish", state_source)

    def test_stale_auto_check_save_finish_does_not_restart_pending_save(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._auto_check_save_runtime = SimpleNamespace(request_id=9)
        runtime._auto_check_enabled = True
        runtime._auto_check_save_pending = True
        runtime._schedule_auto_check_save_start = Mock()

        update_page_runtime.UpdatePageRuntime._on_auto_check_save_finished(
            runtime,
            SimpleNamespace(_request_id=8),
        )

        runtime._schedule_auto_check_save_start.assert_not_called()

    def test_auto_check_save_error_ignored_when_new_save_is_pending(self) -> None:
        runtime = update_page_runtime.UpdatePageRuntime.__new__(update_page_runtime.UpdatePageRuntime)
        runtime._cleanup_in_progress = False
        runtime._auto_check_save_pending = False
        runtime._auto_check_save_runtime = Mock()
        runtime._auto_check_save_runtime.is_current.return_value = True

        with patch.object(update_page_runtime, "log") as log_mock:
            update_page_runtime.UpdatePageRuntime._on_auto_check_save_failed(
                runtime,
                13,
                "old save failed",
            )

        log_mock.assert_not_called()

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
