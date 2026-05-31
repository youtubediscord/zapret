import inspect
import unittest
from unittest.mock import Mock

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


if __name__ == "__main__":
    unittest.main()
