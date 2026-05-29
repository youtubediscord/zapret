from __future__ import annotations

import sys
import unittest
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class ServerStatusWorkerContractTests(unittest.TestCase):
    def test_background_server_check_does_not_stop_running_dpi_on_network_error(self) -> None:
        from updater import server_status_workers

        runtime_feature = SimpleNamespace(
            is_any_running=Mock(return_value=True),
            shutdown_sync=Mock(),
        )
        pool = SimpleNamespace(
            servers=[
                {
                    "id": "primary",
                    "name": "Primary",
                    "host": "example.invalid",
                    "https_port": 443,
                    "http_port": 80,
                }
            ],
            stats={},
            record_failure=Mock(),
            record_success=Mock(),
        )
        worker = server_status_workers.ServerCheckWorker(
            update_pool_stats=True,
            telegram_only=False,
        )

        with (
            patch.object(server_status_workers, "should_verify_ssl", return_value=False),
            patch.object(server_status_workers.ServerCheckWorker, "_request_versions_json", return_value=(None, "timeout", "direct")),
            patch("updater.server_pool.get_server_pool", return_value=pool),
            patch("updater.telegram_updater.is_telegram_available", return_value=False),
            patch("updater.github_release.check_rate_limit", return_value={"remaining": 1, "limit": 60}),
            patch.object(server_status_workers._time, "sleep"),
        ):
            worker.run()

        runtime_feature.shutdown_sync.assert_not_called()
        pool.record_failure.assert_called_once()

    def test_background_server_worker_has_no_runtime_shutdown_dependency(self) -> None:
        from updater import server_status_workers

        init_signature = inspect.signature(server_status_workers.ServerCheckWorker.__init__)
        worker_source = inspect.getsource(server_status_workers.ServerCheckWorker)

        self.assertNotIn("runtime_feature", init_signature.parameters)
        self.assertNotIn("shutdown_sync", worker_source)
        self.assertNotIn("is_any_running", worker_source)


class UpdatePageRuntimeServerRecoveryTests(unittest.TestCase):
    def _make_runtime(self):
        from updater.update_page_runtime import UpdatePageRuntime

        view = SimpleNamespace(
            get_ui_language=Mock(return_value="ru"),
            window=Mock(return_value=None),
            is_update_download_in_progress=Mock(return_value=False),
            reset_server_rows=Mock(),
            upsert_server_status=Mock(),
            start_checking=Mock(),
            finish_checking=Mock(),
            show_found_update_source=Mock(),
            show_update_offer=Mock(),
            hide_update_offer=Mock(),
            start_update_download=Mock(),
            update_download_progress=Mock(),
            mark_update_download_complete=Mock(),
            mark_update_download_failed=Mock(),
            show_update_download_error=Mock(),
            show_update_deferred=Mock(),
            show_checked_ago=Mock(),
            show_manual_hint=Mock(),
            show_auto_enabled_hint=Mock(),
            hide_update_status_card=Mock(),
            show_update_status_card=Mock(),
            set_update_check_enabled=Mock(),
            set_auto_check_toggle_checked=Mock(),
        )
        runtime_feature = SimpleNamespace(
            is_any_running=Mock(return_value=True),
            shutdown_sync=Mock(return_value=SimpleNamespace(still_running=False)),
            is_available=Mock(return_value=True),
            restart=Mock(),
        )
        runtime = UpdatePageRuntime(
            view,
            runtime_feature=runtime_feature,
            updater_feature=SimpleNamespace(),
        )
        return runtime, view, runtime_feature

    def _stub_retry_worker_start(self, runtime):
        retry_runtime = runtime._server_retry_without_dpi_runtime

        def _start_qthread_worker(**_kwargs):
            request_id = retry_runtime.next_request_id()
            retry_runtime.worker = object()
            return request_id, retry_runtime.worker

        return patch.object(retry_runtime, "start_qthread_worker", side_effect=_start_qthread_worker)

    def _stub_dpi_restart_worker_start(self, runtime):
        restart_runtime = runtime._dpi_restart_runtime

        def _start_qthread_worker(**_kwargs):
            request_id = restart_runtime.next_request_id()
            restart_runtime.worker = object()
            return request_id, restart_runtime.worker

        return patch.object(restart_runtime, "start_qthread_worker", side_effect=_start_qthread_worker)

    def test_retry_without_dpi_worker_stops_dpi_in_background(self) -> None:
        import updater.commands as updater_commands
        from updater.retry_workers import UpdaterServerRetryWithoutDpiWorker

        worker_source = inspect.getsource(UpdaterServerRetryWithoutDpiWorker.run)
        init_signature = inspect.signature(UpdaterServerRetryWithoutDpiWorker.__init__)
        self.assertTrue(hasattr(updater_commands, "retry_server_check_without_dpi"))
        command_signature = inspect.signature(updater_commands.retry_server_check_without_dpi)
        command_source = inspect.getsource(updater_commands.retry_server_check_without_dpi)

        self.assertIn("updater_commands.retry_server_check_without_dpi", worker_source)
        self.assertNotIn("runtime_feature", init_signature.parameters)
        self.assertNotIn("runtime_feature", command_signature.parameters)
        self.assertNotIn("_runtime_feature", inspect.getsource(UpdaterServerRetryWithoutDpiWorker))
        self.assertNotIn("self._shutdown_sync(", worker_source)
        self.assertNotIn("self._is_any_running(", worker_source)
        self.assertIn("shutdown_sync", command_source)
        self.assertIn("is_any_running", command_source)

        runtime_feature = SimpleNamespace(
            is_any_running=Mock(return_value=True),
            shutdown_sync=Mock(return_value=SimpleNamespace(still_running=False)),
        )
        worker = UpdaterServerRetryWithoutDpiWorker(
            7,
            is_any_running=runtime_feature.is_any_running,
            shutdown_sync=runtime_feature.shutdown_sync,
        )
        results = []
        worker.loaded.connect(lambda *args: results.append(args))

        worker.run()

        runtime_feature.shutdown_sync.assert_called_once_with(
            reason="server_status_probe_retry",
            include_cleanup=True,
        )
        self.assertEqual(results, [(7, True, True, "")])

    def test_dpi_restart_worker_restarts_runtime_in_background(self) -> None:
        import updater.commands as updater_commands
        from updater.retry_workers import UpdaterDpiRestartWorker

        worker_source = inspect.getsource(UpdaterDpiRestartWorker.run)
        init_signature = inspect.signature(UpdaterDpiRestartWorker.__init__)
        self.assertTrue(hasattr(updater_commands, "restart_dpi_after_update"))
        command_signature = inspect.signature(updater_commands.restart_dpi_after_update)
        command_source = inspect.getsource(updater_commands.restart_dpi_after_update)

        self.assertIn("updater_commands.restart_dpi_after_update", worker_source)
        self.assertNotIn("runtime_feature", init_signature.parameters)
        self.assertNotIn("runtime_feature", command_signature.parameters)
        self.assertNotIn("_runtime_feature", inspect.getsource(UpdaterDpiRestartWorker))
        self.assertNotIn("self._restart()", worker_source)
        self.assertNotIn("self._is_available()", worker_source)
        self.assertIn("restart", command_source)
        self.assertIn("is_available", command_source)

        runtime_feature = SimpleNamespace(
            is_available=Mock(return_value=True),
            restart=Mock(return_value=True),
        )
        worker = UpdaterDpiRestartWorker(
            9,
            is_available=runtime_feature.is_available,
            restart=runtime_feature.restart,
            context="test",
        )
        results = []
        worker.loaded.connect(lambda *args: results.append(args))

        worker.run()

        runtime_feature.restart.assert_called_once_with()
        self.assertEqual(results, [(9, True)])

    def test_page_runtime_retries_server_check_without_dpi_after_full_source_failure(self) -> None:
        runtime, _view, runtime_feature = self._make_runtime()

        with (
            patch("updater.update_page_runtime.UpdateRateLimiter.record_servers_full_check"),
            patch.object(runtime, "_start_server_check_workflow") as start_server_check,
            patch.object(runtime, "_start_version_check_workflow") as start_version_check,
            self._stub_retry_worker_start(runtime),
        ):
            runtime.start_checks(telegram_only=False, skip_server_rate_limit=True)
            runtime._on_server_checked("Telegram Bot", {"status": "offline"})
            runtime._on_server_checked("Primary", {"status": "error"})
            runtime._on_server_checked("GitHub API", {"status": "error"})
            runtime._on_servers_complete()
            retry_request_id = runtime._server_retry_without_dpi_runtime.request_id
            runtime._on_server_retry_without_dpi_finished(retry_request_id, True, True, "")

        runtime_feature.shutdown_sync.assert_not_called()
        self.assertEqual(start_server_check.call_count, 2)
        start_server_check.assert_called_with(telegram_only=False)
        start_version_check.assert_not_called()

    def test_page_runtime_restarts_dpi_after_retry_before_version_check(self) -> None:
        runtime, _view, runtime_feature = self._make_runtime()

        with (
            patch("updater.update_page_runtime.UpdateRateLimiter.record_servers_full_check"),
            patch.object(runtime, "_start_server_check_workflow"),
            patch.object(runtime, "_start_version_check_workflow") as start_version_check,
            self._stub_retry_worker_start(runtime),
            self._stub_dpi_restart_worker_start(runtime),
        ):
            runtime.start_checks(telegram_only=False, skip_server_rate_limit=True)
            runtime._on_server_checked("GitHub API", {"status": "error"})
            runtime._on_servers_complete()
            retry_request_id = runtime._server_retry_without_dpi_runtime.request_id
            runtime._on_server_retry_without_dpi_finished(retry_request_id, True, True, "")
            runtime._on_server_checked("Primary", {"status": "online", "is_current": True})
            runtime._on_servers_complete()
            start_version_check.assert_not_called()
            restart_request_id = runtime._dpi_restart_runtime.request_id
            runtime._on_dpi_restart_finished(restart_request_id, True)

        runtime_feature.shutdown_sync.assert_not_called()
        runtime_feature.restart.assert_not_called()
        start_version_check.assert_called_once()

    def test_page_runtime_does_not_retry_without_dpi_when_any_source_is_online(self) -> None:
        runtime, _view, runtime_feature = self._make_runtime()

        with (
            patch("updater.update_page_runtime.UpdateRateLimiter.record_servers_full_check"),
            patch.object(runtime, "_start_server_check_workflow"),
            patch.object(runtime, "_start_version_check_workflow") as start_version_check,
        ):
            runtime.start_checks(telegram_only=False, skip_server_rate_limit=True)
            runtime._on_server_checked("Telegram Bot", {"status": "offline"})
            runtime._on_server_checked("Primary", {"status": "online", "is_current": True})
            runtime._on_servers_complete()

        runtime_feature.shutdown_sync.assert_not_called()
        runtime_feature.restart.assert_not_called()
        start_version_check.assert_called_once()


if __name__ == "__main__":
    unittest.main()
