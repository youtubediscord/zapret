from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.feature_facades.logs import LogsFeature
import log.ui.page as logs_page
import log.open_folder_worker as open_folder_worker
import log.support_worker as support_worker


class LogsWorkerArchitectureTests(unittest.TestCase):
    def test_logs_workers_receive_feature_actions_not_feature_object(self) -> None:
        feature_source = inspect.getsource(LogsFeature)
        worker_source = "\n".join(
            (
                inspect.getsource(open_folder_worker.LogsOpenFolderWorker),
                inspect.getsource(support_worker.LogsSupportPrepareWorker),
            )
        )

        self.assertNotIn("logs_feature=self", feature_source)
        self.assertNotIn("self._logs", worker_source)
        self.assertIn("open_logs_folder=self.open_logs_folder", feature_source)
        self.assertIn("open_logs_folder", inspect.signature(open_folder_worker.LogsOpenFolderWorker.__init__).parameters)
        self.assertIn("self._open_logs_folder", inspect.getsource(open_folder_worker.LogsOpenFolderWorker.run))
        self.assertNotIn("import log.commands", inspect.getsource(open_folder_worker.LogsOpenFolderWorker.run))
        self.assertIn("prepare_support_bundle=self.prepare_support_bundle", feature_source)
        self.assertIn("_prepare_support_bundle", worker_source)
        self.assertNotIn("log_commands.prepare_support_bundle", worker_source)
        self.assertNotIn("import log.commands", inspect.getsource(support_worker.LogsSupportPrepareWorker.run))

    def test_open_folder_pending_restarts_after_event_loop_turn(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._open_folder_pending = True
        page._request_open_logs_folder = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(logs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            logs_page.LogsPage._on_open_logs_folder_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_open_logs_folder.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_open_logs_folder.assert_called_once_with()

    def test_stale_open_folder_worker_finished_does_not_restart_pending_open(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._open_folder_runtime = SimpleNamespace(request_id=2)
        page._open_folder_pending = True
        page._request_open_logs_folder = Mock()
        single_shot = Mock()

        with patch.object(logs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            logs_page.LogsPage._on_open_logs_folder_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_not_called()
        page._request_open_logs_folder.assert_not_called()
        self.assertTrue(page._open_folder_pending)

    def test_stale_open_folder_worker_object_finished_does_not_restart_pending_open(self) -> None:
        old_worker = object()
        current_worker = object()
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._open_folder_runtime = SimpleNamespace(request_id=2, worker=current_worker)
        page._open_folder_pending = True
        page._request_open_logs_folder = Mock()
        single_shot = Mock()

        with patch.object(logs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            logs_page.LogsPage._on_open_logs_folder_worker_finished(page, old_worker)

        single_shot.assert_not_called()
        page._request_open_logs_folder.assert_not_called()
        self.assertTrue(page._open_folder_pending)

    def test_open_folder_scheduled_start_is_not_duplicated(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._open_folder_pending = False
        page._open_folder_start_scheduled = False
        page._request_open_logs_folder = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(logs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            logs_page.LogsPage._schedule_open_logs_folder_start(page)
            logs_page.LogsPage._schedule_open_logs_folder_start(page)

        single_shot.assert_called_once()
        self.assertFalse(page._open_folder_pending)
        page._request_open_logs_folder.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_open_logs_folder.assert_called_once_with()

    def test_logs_overview_pending_cleanup_restarts_after_event_loop_turn(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._logs_overview_pending_cleanup = True
        page._logs_overview_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._refresh_logs_list = Mock()
        page._stop_refresh_animation = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(logs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            logs_page.LogsPage._on_logs_overview_finished(page, 7, object())

        self.assertEqual(single_shot.call_count, 2)
        self.assertEqual(single_shot.call_args_list[0].args[0], 500)
        self.assertEqual(single_shot.call_args_list[1].args[0], 0)
        page._refresh_logs_list.assert_not_called()

        single_shot.call_args_list[1].args[1]()

        page._refresh_logs_list.assert_called_once_with(run_cleanup=True)

    def test_support_prepare_pending_restarts_after_event_loop_turn(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = True
        page._request_support_prepare = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(logs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            logs_page.LogsPage._on_support_prepare_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_support_prepare.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_support_prepare.assert_called_once_with()

    def test_stale_support_prepare_worker_finished_does_not_restart_pending_prepare(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._support_prepare_runtime = SimpleNamespace(request_id=2)
        page._support_prepare_pending = True
        page._request_support_prepare = Mock()
        single_shot = Mock()

        with patch.object(logs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            logs_page.LogsPage._on_support_prepare_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_not_called()
        page._request_support_prepare.assert_not_called()
        self.assertTrue(page._support_prepare_pending)

    def test_stale_support_prepare_worker_object_finished_does_not_restart_pending_prepare(self) -> None:
        old_worker = object()
        current_worker = object()
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._support_prepare_runtime = SimpleNamespace(request_id=2, worker=current_worker)
        page._support_prepare_pending = True
        page._request_support_prepare = Mock()
        single_shot = Mock()

        with patch.object(logs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            logs_page.LogsPage._on_support_prepare_worker_finished(page, old_worker)

        single_shot.assert_not_called()
        page._request_support_prepare.assert_not_called()
        self.assertTrue(page._support_prepare_pending)

    def test_support_prepare_request_waits_while_restart_is_scheduled(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._support_prepare_start_scheduled = True
        page._support_prepare_pending = False
        page._support_prepare_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        logs_page.LogsPage._request_support_prepare(page)

        page._support_prepare_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._support_prepare_pending)

    def test_support_prepare_result_ignored_when_new_prepare_is_pending(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = True
        page._support_prepare_runtime = Mock()
        page._support_prepare_runtime.is_current.return_value = True
        page._logs = Mock()
        page._render_send_status_label = Mock()
        page.window = Mock(return_value=None)

        with patch.object(logs_page, "apply_support_feedback") as apply_feedback:
            logs_page.LogsPage._on_support_prepare_finished(page, 9, object())

        apply_feedback.assert_not_called()
        page._render_send_status_label.assert_not_called()

    def test_support_prepare_error_ignored_when_new_prepare_is_pending(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._support_prepare_pending = True
        page._support_prepare_runtime = Mock()
        page._support_prepare_runtime.is_current.return_value = True
        page._logs = Mock()
        page._logs.build_support_error_feedback.return_value = SimpleNamespace(
            status_text="old",
            status_tone="error",
            infobar_title="Ошибка",
            infobar_content="old",
        )
        page._render_send_status_label = Mock()
        page.window = Mock(return_value=None)

        with (
            patch.object(logs_page, "InfoBar") as info_bar,
            patch.object(logs_page, "log") as log_mock,
        ):
            logs_page.LogsPage._on_support_prepare_failed(page, 9, "old error")

        page._logs.build_support_error_feedback.assert_not_called()
        page._render_send_status_label.assert_not_called()
        info_bar.warning.assert_not_called()
        log_mock.assert_not_called()

    def test_open_folder_error_ignored_when_new_open_is_pending(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._open_folder_pending = True
        page._open_folder_runtime = Mock()
        page._open_folder_runtime.is_current.return_value = True

        with patch.object(logs_page, "log") as log_mock:
            logs_page.LogsPage._on_open_logs_folder_failed(page, 10, "old error")

        log_mock.assert_not_called()

    def test_cleanup_does_not_block_one_shot_support_or_open_folder_workers(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._cleanup_in_progress = False
        page._logs_overview_restart_scheduled = True
        page._spin_timer = Mock()
        page._stop_logs_overview_worker = Mock()
        page._stop_support_prepare_worker = Mock()
        page._open_folder_runtime = Mock()
        page._open_folder_pending = True
        page._open_folder_start_scheduled = True
        page._stop_tail_worker = Mock()

        logs_page.LogsPage.cleanup(page)

        self.assertTrue(page._cleanup_in_progress)
        self.assertFalse(page._logs_overview_restart_scheduled)
        self.assertFalse(page._open_folder_pending)
        self.assertFalse(page._open_folder_start_scheduled)
        page._spin_timer.stop.assert_called_once()
        page._stop_logs_overview_worker.assert_called_once_with(blocking=True)
        page._stop_support_prepare_worker.assert_called_once_with(blocking=False)
        page._open_folder_runtime.stop.assert_called_once_with(
            blocking=False,
            log_fn=logs_page.log,
            warning_prefix="Logs open folder worker",
        )
        page._open_folder_runtime.cancel.assert_called_once()
        page._stop_tail_worker.assert_called_once_with(blocking=True)


if __name__ == "__main__":
    unittest.main()
