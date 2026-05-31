import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from telegram_proxy import commands as telegram_proxy_commands
from telegram_proxy import workers as telegram_proxy_workers
from app.feature_facades.telegram_proxy import TelegramProxyFeature


class TelegramProxyWorkerArchitectureTests(unittest.TestCase):
    def test_runtime_workflow_receives_worker_factories_not_full_feature(self) -> None:
        from telegram_proxy.ui import proxy_runtime_workflow
        from telegram_proxy.ui.page import TelegramProxyPage

        for function_name in (
            "restart_proxy_if_running",
            "start_proxy_runtime",
            "start_relay_check",
            "stop_proxy_runtime",
        ):
            signature = inspect.signature(getattr(proxy_runtime_workflow, function_name))
            self.assertNotIn("telegram_proxy_feature", signature.parameters)

        self.assertIn(
            "create_stop_runtime_worker",
            inspect.signature(proxy_runtime_workflow.restart_proxy_if_running).parameters,
        )
        self.assertIn(
            "create_start_worker",
            inspect.signature(proxy_runtime_workflow.start_proxy_runtime).parameters,
        )
        self.assertIn(
            "create_relay_check_worker",
            inspect.signature(proxy_runtime_workflow.start_relay_check).parameters,
        )
        self.assertIn(
            "create_stop_runtime_worker",
            inspect.signature(proxy_runtime_workflow.stop_proxy_runtime).parameters,
        )
        workflow_source = inspect.getsource(proxy_runtime_workflow)
        page_source = inspect.getsource(TelegramProxyPage)

        self.assertIn("start_qthread_worker", workflow_source)
        self.assertNotIn("worker.start()", workflow_source)
        self.assertIn("_proxy_start_runtime", page_source)
        self.assertIn("_proxy_stop_runtime", page_source)
        self.assertIn("_restart_stop_runtime", page_source)
        self.assertIn("_relay_check_runtime", page_source)
        self.assertNotIn("_proxy_start_worker =", page_source)
        self.assertNotIn("_proxy_stop_worker =", page_source)
        self.assertNotIn("_restart_stop_worker =", page_source)
        self.assertNotIn("_relay_check_worker =", page_source)

    def test_page_receives_zapret_running_callable_not_runtime_feature(self) -> None:
        from app.page_names import PageName
        from telegram_proxy.ui.page import TelegramProxyPage
        from ui.page_deps.system import build_telegram_proxy_page_kwargs

        init_source = inspect.getsource(TelegramProxyPage.__init__)
        relay_source = "\n".join(
            (
                inspect.getsource(TelegramProxyPage._check_relay_after_start),
                inspect.getsource(TelegramProxyPage._start_relay_check_worker),
            )
        )
        page_source = inspect.getsource(TelegramProxyPage)

        self.assertNotIn("runtime_feature", init_source)
        self.assertNotIn("self._runtime_feature", page_source)
        self.assertIn("get_zapret_running", init_source)
        self.assertIn("self._get_zapret_running", relay_source)

        runtime_feature = Mock()
        runtime_feature.is_any_running.return_value = True
        kwargs = build_telegram_proxy_page_kwargs(
            page_name=PageName.TELEGRAM_PROXY,
            runtime_feature=runtime_feature,
            telegram_proxy_feature=Mock(),
        )

        self.assertNotIn("runtime_feature", kwargs)
        self.assertIn("get_zapret_running", kwargs)
        self.assertTrue(kwargs["get_zapret_running"]())
        runtime_feature.is_any_running.assert_called_once_with(silent=True)

    def test_relay_reachability_probe_is_owned_by_commands(self) -> None:
        feature_source = inspect.getsource(TelegramProxyFeature)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyRelayCheckWorker.run)

        self.assertTrue(hasattr(telegram_proxy_commands, "check_relay_reachable"))
        command_source = inspect.getsource(telegram_proxy_commands.check_relay_reachable)

        self.assertIn("check_relay_reachable=self.check_relay_reachable", feature_source)
        self.assertIn("_check_relay_reachable", worker_source)
        self.assertNotIn("telegram_proxy.commands", worker_source)
        self.assertNotIn("telegram_proxy.wss_proxy", worker_source)
        self.assertIn("telegram_proxy.wss_proxy", command_source)
        self.assertIn("check_relay_reachable", command_source)

    def test_start_worker_loads_upstream_config_outside_ui_runtime(self) -> None:
        from telegram_proxy.ui import proxy_runtime_workflow

        runtime_source = inspect.getsource(proxy_runtime_workflow.start_proxy_runtime)
        feature_source = inspect.getsource(TelegramProxyFeature)
        toggle_source = inspect.getsource(TelegramProxyFeature.toggle_async)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyStartWorker.run)

        self.assertTrue(hasattr(telegram_proxy_commands, "build_upstream_config"))
        self.assertNotIn("telegram_proxy.settings", runtime_source)
        self.assertNotIn("build_upstream_config", runtime_source)
        self.assertIn("build_upstream_config=self.build_upstream_config", feature_source)
        self.assertIn("_tray_start_runtime", feature_source)
        self.assertIn("start_qthread_worker", toggle_source)
        self.assertNotIn("worker.start()", toggle_source)
        self.assertNotIn("_tray_start_worker", toggle_source)
        self.assertIn("_build_upstream_config", worker_source)
        self.assertNotIn("telegram_proxy.commands", worker_source)

    def test_tray_toggle_stops_proxy_through_worker_runtime(self) -> None:
        feature_source = inspect.getsource(TelegramProxyFeature)
        toggle_source = inspect.getsource(TelegramProxyFeature.toggle_async)

        self.assertIn("_tray_stop_runtime", feature_source)
        self.assertIn("create_stop_runtime_worker", toggle_source)
        self.assertIn("_tray_stop_runtime.start_qthread_worker", toggle_source)
        self.assertNotIn("manager.stop_proxy()", toggle_source)
        self.assertNotIn("self.set_enabled(False)", toggle_source)

    def test_tray_toggle_running_proxy_starts_stop_runtime(self) -> None:
        class _Runtime:
            def __init__(self) -> None:
                self.started = None

            def is_running(self) -> bool:
                return False

            def start_qthread_worker(self, **kwargs) -> None:
                self.started = kwargs

        manager = Mock()
        manager.is_running = True
        stop_runtime = _Runtime()
        enabled_values = []
        feature = TelegramProxyFeature(
            start_proxy_if_enabled_async=Mock(),
            get_proxy_manager=Mock(return_value=manager),
            get_start_config=Mock(),
            set_enabled=lambda value: enabled_values.append(bool(value)),
            build_upstream_config=Mock(),
            load_page_initial_state=Mock(),
            save_settings_action=Mock(),
            check_relay_reachable=Mock(),
            check_relay_http=Mock(),
            build_diagnostics_start_plan=Mock(),
            build_diagnostics_poll_plan=Mock(),
            build_diagnostics_finish_plan=Mock(),
            copy_text=Mock(),
            open_log_file=Mock(),
            open_external_link=Mock(),
            ensure_telegram_hosts=Mock(),
            run_diagnostics=Mock(),
            append_log_line=Mock(),
            consume_auto_deeplink_request=Mock(),
            _tray_stop_runtime=stop_runtime,
        )

        feature.toggle_async()

        manager.stop_proxy.assert_not_called()
        self.assertEqual(enabled_values, [])
        self.assertIsNotNone(stop_runtime.started)
        self.assertEqual(stop_runtime.started.get("loaded_signal_name"), "stopped")
        worker = stop_runtime.started["worker_factory"](1)

        worker.run()

        manager.stop_proxy.assert_called_once_with()
        self.assertEqual(enabled_values, [False])

    def test_start_worker_passes_command_loaded_upstream_config_to_manager(self) -> None:
        manager = Mock()
        manager.start_proxy.return_value = True
        upstream_config = object()
        worker = telegram_proxy_workers.TelegramProxyStartWorker(
            manager=manager,
            port=1353,
            mode="socks5",
            host="127.0.0.1",
            build_upstream_config=Mock(return_value=upstream_config),
        )

        worker.run()

        manager.start_proxy.assert_called_once_with(
            port=1353,
            mode="socks5",
            host="127.0.0.1",
            upstream_config=upstream_config,
        )

    def test_external_links_are_queued_while_worker_runs(self) -> None:
        from telegram_proxy.ui.page import TelegramProxyPage

        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._external_link_runtime = _Runtime()
        page._external_link_pending = []
        page.create_external_link_worker = Mock()

        TelegramProxyPage._start_external_link_worker(
            page,
            "tg://proxy-one",
            success_log="one",
            error_prefix="bad one",
        )
        TelegramProxyPage._start_external_link_worker(
            page,
            "tg://proxy-two",
            success_log="two",
            error_prefix="bad two",
        )

        self.assertEqual(
            page._external_link_pending,
            [
                {"url": "tg://proxy-one", "success_log": "one", "error_prefix": "bad one"},
                {"url": "tg://proxy-two", "success_log": "two", "error_prefix": "bad two"},
            ],
        )
        page.create_external_link_worker.assert_not_called()

    def test_external_link_worker_finished_schedules_next_queued_link(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._external_link_pending = [
            {"url": "tg://proxy-one", "success_log": "one", "error_prefix": "bad one"},
            {"url": "tg://proxy-two", "success_log": "two", "error_prefix": "bad two"},
        ]
        page._start_external_link_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_external_link_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_external_link_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_external_link_worker.assert_called_once_with(
            "tg://proxy-one",
            success_log="one",
            error_prefix="bad one",
        )
        self.assertEqual(
            page._external_link_pending,
            [{"url": "tg://proxy-two", "success_log": "two", "error_prefix": "bad two"}],
        )

    def test_open_log_file_requests_are_queued_while_worker_runs(self) -> None:
        from telegram_proxy.ui.page import TelegramProxyPage

        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._open_log_file_runtime = _Runtime()
        page._open_log_file_pending = []
        page.create_open_log_file_worker = Mock()

        TelegramProxyPage._start_open_log_file_worker(page, "first.log")
        TelegramProxyPage._start_open_log_file_worker(page, "second.log")

        self.assertEqual(page._open_log_file_pending, ["first.log", "second.log"])
        page.create_open_log_file_worker.assert_not_called()

    def test_open_log_file_worker_finished_schedules_next_queued_path(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._open_log_file_pending = ["first.log", "second.log"]
        page._start_open_log_file_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_open_log_file_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_open_log_file_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_open_log_file_worker.assert_called_once_with("first.log")
        self.assertEqual(page._open_log_file_pending, ["second.log"])

    def test_log_line_worker_finished_schedules_next_queued_line(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._log_line_pending = ["first", "second"]
        page._start_log_line_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_log_line_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_log_line_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_log_line_worker.assert_called_once_with("first")
        self.assertEqual(page._log_line_pending, ["second"])

    def test_settings_save_worker_finished_schedules_next_queued_save(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._settings_save_pending = [{"action": "port", "port": 8080}]
        page._start_settings_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_settings_save_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_settings_save_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_settings_save_worker.assert_called_once_with({"action": "port", "port": 8080})

    def test_relay_check_pending_restarts_after_event_loop_turn(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._relay_check_pending = True
        page._relay_check_start_scheduled = False
        page._start_relay_check_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_relay_check_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_relay_check_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_relay_check_worker.assert_called_once_with()
        self.assertFalse(page._relay_check_pending)


if __name__ == "__main__":
    unittest.main()
