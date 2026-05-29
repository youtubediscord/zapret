import inspect
import unittest
from unittest.mock import Mock, patch

from telegram_proxy import commands as telegram_proxy_commands
from telegram_proxy import workers as telegram_proxy_workers


class TelegramProxyWorkerArchitectureTests(unittest.TestCase):
    def test_relay_reachability_probe_is_owned_by_commands(self) -> None:
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyRelayCheckWorker.run)

        self.assertTrue(hasattr(telegram_proxy_commands, "check_relay_reachable"))
        command_source = inspect.getsource(telegram_proxy_commands.check_relay_reachable)

        self.assertIn("telegram_proxy_commands.check_relay_reachable", worker_source)
        self.assertNotIn("telegram_proxy.wss_proxy", worker_source)
        self.assertIn("telegram_proxy.wss_proxy", command_source)
        self.assertIn("check_relay_reachable", command_source)

    def test_start_worker_loads_upstream_config_outside_ui_runtime(self) -> None:
        from telegram_proxy.ui import proxy_runtime_workflow

        runtime_source = inspect.getsource(proxy_runtime_workflow.start_proxy_runtime)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyStartWorker.run)

        self.assertTrue(hasattr(telegram_proxy_commands, "build_upstream_config"))
        self.assertNotIn("telegram_proxy.settings", runtime_source)
        self.assertNotIn("build_upstream_config", runtime_source)
        self.assertIn("telegram_proxy_commands.build_upstream_config", worker_source)

    def test_start_worker_passes_command_loaded_upstream_config_to_manager(self) -> None:
        manager = Mock()
        manager.start_proxy.return_value = True
        upstream_config = object()
        worker = telegram_proxy_workers.TelegramProxyStartWorker(
            manager=manager,
            port=1353,
            mode="socks5",
            host="127.0.0.1",
        )

        with patch.object(telegram_proxy_commands, "build_upstream_config", return_value=upstream_config):
            worker.run()

        manager.start_proxy.assert_called_once_with(
            port=1353,
            mode="socks5",
            host="127.0.0.1",
            upstream_config=upstream_config,
        )


if __name__ == "__main__":
    unittest.main()
