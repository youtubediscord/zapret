import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from blockcheck import strategy_scan_targeting
from blockcheck.ui.strategy_scan_page import StrategyScanPage


class StrategyScanQuickTargetsRuntimeArchitectureTests(unittest.TestCase):
    def test_quick_targets_menu_uses_runtime_not_manual_page_worker(self) -> None:
        page_source = inspect.getsource(StrategyScanPage)
        request_source = inspect.getsource(StrategyScanPage._request_quick_targets_menu)
        loaded_source = inspect.getsource(StrategyScanPage._on_quick_targets_loaded)
        failed_source = inspect.getsource(StrategyScanPage._on_quick_targets_failed)
        cleanup_source = inspect.getsource(StrategyScanPage.cleanup)

        self.assertIn("_quick_targets_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("_quick_targets_runtime.is_running()", request_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertIn("bind_worker", request_source)
        self.assertIn("_quick_targets_runtime.is_current", loaded_source)
        self.assertIn("_quick_targets_runtime.is_current", failed_source)
        self.assertIn("_quick_targets_runtime.stop", cleanup_source)
        self.assertIn("_quick_targets_runtime.cancel", cleanup_source)
        self.assertNotIn("_quick_targets_worker =", page_source)
        self.assertNotIn("_quick_targets_request_id", page_source)
        self.assertNotIn("worker.start()", request_source)

    def test_quick_domain_targets_cache_after_first_load(self) -> None:
        strategy_scan_targeting._quick_domains_cache = None

        with patch("blockcheck.targets.load_domains", return_value=[" Example.COM ", "example.com", "youtu.be"]):
            first = strategy_scan_targeting.load_quick_domains()
            second = strategy_scan_targeting.load_quick_domains()

        self.assertEqual(first, ["example.com", "youtu.be"])
        self.assertEqual(second, first)

    def test_quick_targets_pending_menu_restarts_after_event_loop_turn(self) -> None:
        import blockcheck.ui.strategy_scan_page as strategy_scan_page

        page = StrategyScanPage.__new__(StrategyScanPage)
        page._cleanup_in_progress = False
        page._quick_targets_pending = {"scan_protocol": "udp", "current_value": "latest"}
        page._request_quick_targets_menu = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(strategy_scan_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            StrategyScanPage._on_quick_targets_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_quick_targets_menu.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_quick_targets_menu.assert_called_once_with(
            scan_protocol="udp",
            current_value="latest",
        )

    def test_stale_quick_targets_worker_finished_does_not_restart_pending_menu(self) -> None:
        import blockcheck.ui.strategy_scan_page as strategy_scan_page

        page = StrategyScanPage.__new__(StrategyScanPage)
        page._cleanup_in_progress = False
        page._quick_targets_runtime = SimpleNamespace(worker=object())
        page._quick_targets_pending = {"scan_protocol": "udp", "current_value": "latest"}
        page._request_quick_targets_menu = Mock()
        single_shot = Mock()

        with patch.object(strategy_scan_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            StrategyScanPage._on_quick_targets_worker_finished(page, object())

        single_shot.assert_not_called()
        page._request_quick_targets_menu.assert_not_called()
        self.assertEqual(
            page._quick_targets_pending,
            {"scan_protocol": "udp", "current_value": "latest"},
        )

    def test_quick_targets_request_waits_while_restart_is_scheduled(self) -> None:
        page = StrategyScanPage.__new__(StrategyScanPage)
        page._quick_targets_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())
        page._quick_targets_start_scheduled = True
        page._quick_targets_pending = None

        StrategyScanPage._request_quick_targets_menu(
            page,
            scan_protocol="tcp_http",
            current_value="example.com",
        )

        page._quick_targets_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(
            page._quick_targets_pending,
            {"scan_protocol": "tcp_http", "current_value": "example.com"},
        )

    def test_quick_targets_result_is_ignored_when_new_menu_is_pending(self) -> None:
        page = StrategyScanPage.__new__(StrategyScanPage)
        page._cleanup_in_progress = False
        page._quick_targets_pending = {"scan_protocol": "udp", "current_value": "latest"}
        page._quick_targets_runtime = Mock()
        page._quick_targets_runtime.is_current.return_value = True
        page._open_quick_targets_menu = Mock()

        StrategyScanPage._on_quick_targets_loaded(page, 3, object())

        page._open_quick_targets_menu.assert_not_called()

    def test_quick_stun_targets_cache_after_first_load(self) -> None:
        strategy_scan_targeting._quick_stun_targets_cache = None

        with patch(
            "blockcheck.targets.get_default_stun_targets",
            return_value=[
                {"value": "stun.discord.media:50000"},
                {"value": "stun.discord.media:50000"},
                {"value": "stun.l.google.com:19302"},
            ],
        ):
            first = strategy_scan_targeting.load_quick_stun_targets()
            second = strategy_scan_targeting.load_quick_stun_targets()

        self.assertEqual(first, ["stun.discord.media:50000", "stun.l.google.com:19302"])
        self.assertEqual(second, first)


if __name__ == "__main__":
    unittest.main()
