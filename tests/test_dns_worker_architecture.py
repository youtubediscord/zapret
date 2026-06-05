from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.feature_facades.dns import build_dns_feature
from dns import dns_check_worker, dns_worker, page_workers
import dns.ui.page as network_page
from dns.ui.dns_check_page import DNSCheckPage
from dns.ui.page import NetworkPage


class DnsWorkerArchitectureTests(unittest.TestCase):
    def test_network_action_workers_receive_feature_action_callables(self) -> None:
        feature_source = inspect.getsource(build_dns_feature)
        worker_source = "\n".join(
            (
                inspect.getsource(page_workers.DnsForceDnsActionWorker),
                inspect.getsource(page_workers.DnsFlushCacheWorker),
                inspect.getsource(page_workers.DnsIspWarningWorker),
                inspect.getsource(page_workers.DnsApplyWorker),
            )
        )

        self.assertNotIn("dns_feature=feature", feature_source)
        self.assertNotIn("self._dns =", worker_source)
        self.assertNotIn("self._dns.", worker_source)
        self.assertNotIn("import dns.public", worker_source)
        self.assertNotIn("dns_public.", worker_source)
        self.assertNotIn("from dns.ui import page_plans", worker_source)
        self.assertIn("from dns import page_plans", worker_source)

        for expected in (
            "get_force_dns_status=get_force_dns_status",
            "enable_force_dns=enable_force_dns",
            "disable_force_dns=disable_force_dns",
            "flush_dns_cache=flush_dns_cache",
            "apply_auto_dns=apply_auto_dns",
            "apply_provider_dns=apply_provider_dns",
            "apply_custom_dns=apply_custom_dns",
            "refresh_dns_info=refresh_dns_info",
            "is_isp_dns_warning_shown=is_isp_dns_warning_shown",
            "mark_isp_dns_warning_shown=mark_isp_dns_warning_shown",
            "normalize_adapter_alias=feature.normalize_adapter_alias",
        ):
            self.assertIn(expected, feature_source)

        for expected in (
            "_get_force_dns_status",
            "_enable_force_dns",
            "_disable_force_dns",
            "_flush_dns_cache",
            "_apply_auto_dns",
            "_apply_provider_dns",
            "_apply_custom_dns",
            "_refresh_dns_info",
            "_is_isp_dns_warning_shown",
            "_mark_isp_dns_warning_shown",
            "_normalize_adapter_alias",
        ):
            self.assertIn(expected, worker_source)

    def test_dns_check_workers_receive_feature_action_callables(self) -> None:
        feature_source = inspect.getsource(build_dns_feature)
        worker_source = "\n".join(
            (
                inspect.getsource(dns_check_worker.DNSCheckWorker),
                inspect.getsource(dns_check_worker.DNSCheckSaveWorker),
                inspect.getsource(dns_check_worker.DNSQuickCheckWorker),
            )
        )

        for expected in (
            "run_dns_poisoning_check=run_dns_poisoning_check",
            "save_dns_check_results=save_dns_check_results",
            "run_quick_dns_check=run_quick_dns_check",
        ):
            self.assertIn(expected, feature_source)

        for expected in (
            "_run_dns_poisoning_check",
            "_save_dns_check_results",
            "_run_quick_dns_check",
        ):
            self.assertIn(expected, worker_source)

        self.assertNotIn("from dns import commands", worker_source)
        self.assertNotIn("from dns.commands import", worker_source)
        self.assertNotIn("dns_commands.", worker_source)

    def test_network_page_uses_one_shot_runtime_for_action_workers(self) -> None:
        page_source = inspect.getsource(NetworkPage)
        apply_source = inspect.getsource(NetworkPage._start_dns_apply_worker)
        force_source = inspect.getsource(NetworkPage._start_force_dns_action_worker)
        flush_source = inspect.getsource(NetworkPage._start_dns_flush_cache_worker)
        warning_source = inspect.getsource(NetworkPage._request_isp_dns_warning_plan)
        cleanup_source = inspect.getsource(NetworkPage.cleanup)

        self.assertIn("OneShotWorkerRuntime", page_source)
        for name in (
            "_dns_apply_runtime",
            "_force_dns_action_runtime",
            "_dns_flush_cache_runtime",
            "_isp_warning_runtime",
        ):
            self.assertIn(name, page_source)
        for source in (apply_source, force_source, flush_source, warning_source):
            self.assertIn("start_qthread_worker", source)
            self.assertNotIn("worker.start()", source)
        for name in (
            "_dns_apply_runtime.stop",
            "_force_dns_action_runtime.stop",
            "_dns_flush_cache_runtime.stop",
            "_isp_warning_runtime.stop",
        ):
            self.assertIn(name, cleanup_source)

    def test_dns_apply_pending_restarts_after_event_loop_turn(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_apply_pending = [{"action": "auto", "adapters": ["Ethernet"]}]
        page._start_dns_apply_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            NetworkPage._on_dns_apply_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_dns_apply_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_dns_apply_worker.assert_called_once_with({"action": "auto", "adapters": ["Ethernet"]})

    def test_stale_dns_apply_worker_finished_does_not_restart_pending_action(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_apply_runtime = SimpleNamespace(request_id=3)
        page._dns_apply_pending = [{"action": "auto", "adapters": ["Ethernet"]}]
        page._start_next_dns_mutation_action = Mock()

        NetworkPage._on_dns_apply_worker_finished(page, SimpleNamespace(_request_id=2))

        page._start_next_dns_mutation_action.assert_not_called()

    def test_stale_dns_apply_worker_object_finished_does_not_restart_pending_action(self) -> None:
        old_worker = object()
        current_worker = object()
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_apply_runtime = SimpleNamespace(request_id=3, worker=current_worker)
        page._dns_apply_pending = [{"action": "auto", "adapters": ["Ethernet"]}]
        page._start_next_dns_mutation_action = Mock()

        NetworkPage._on_dns_apply_worker_finished(page, old_worker)

        page._start_next_dns_mutation_action.assert_not_called()

    def test_dns_apply_scheduled_start_uses_latest_pending_request(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return False

        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_apply_runtime = _Runtime()
        page._dns_apply_pending = [{"action": "auto", "adapters": ["Ethernet"]}]
        page._dns_apply_start_scheduled = False
        page._start_dns_apply_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            NetworkPage._on_dns_apply_worker_finished(page, object())
            NetworkPage._request_dns_apply(
                page,
                "provider",
                adapters=["Ethernet"],
                name="cloudflare",
                data={"primary": "1.1.1.1"},
            )

        page._start_dns_apply_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_dns_apply_worker.assert_called_once_with(
            {
                "action": "provider",
                "adapters": ["Ethernet"],
                "name": "cloudflare",
                "data": {"primary": "1.1.1.1"},
            }
        )
        self.assertEqual(page._dns_apply_pending, [])

    def test_dns_apply_running_worker_keeps_latest_pending_request(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = NetworkPage.__new__(NetworkPage)
        page._dns_apply_runtime = _Runtime()
        page._dns_apply_start_scheduled = False
        page._dns_apply_pending = []
        page._start_dns_apply_worker = Mock()

        NetworkPage._request_dns_apply(page, "auto", adapters=["Ethernet"])
        NetworkPage._request_dns_apply(
            page,
            "custom",
            adapters=["Ethernet"],
            primary="9.9.9.9",
            secondary="149.112.112.112",
        )

        page._start_dns_apply_worker.assert_not_called()
        self.assertEqual(
            page._dns_apply_pending,
            [
                {
                    "action": "custom",
                    "adapters": ["Ethernet"],
                    "primary": "9.9.9.9",
                    "secondary": "149.112.112.112",
                }
            ],
        )

    def test_dns_apply_waits_while_force_dns_worker_runs(self) -> None:
        class _Runtime:
            def __init__(self, running: bool) -> None:
                self._running = running

            def is_running(self) -> bool:
                return self._running

        page = NetworkPage.__new__(NetworkPage)
        page._dns_apply_runtime = _Runtime(False)
        page._force_dns_action_runtime = _Runtime(True)
        page._dns_apply_start_scheduled = False
        page._force_dns_action_start_scheduled = False
        page._dns_apply_pending = []
        page._start_dns_apply_worker = Mock()

        NetworkPage._request_dns_apply(page, "auto", adapters=["Ethernet"])

        page._start_dns_apply_worker.assert_not_called()
        self.assertEqual(page._dns_apply_pending, [{"action": "auto", "adapters": ["Ethernet"]}])

    def test_force_dns_waits_while_dns_apply_worker_runs(self) -> None:
        class _Runtime:
            def __init__(self, running: bool) -> None:
                self._running = running

            def is_running(self) -> bool:
                return self._running

        page = NetworkPage.__new__(NetworkPage)
        page._dns_apply_runtime = _Runtime(True)
        page._force_dns_action_runtime = _Runtime(False)
        page._dns_apply_start_scheduled = False
        page._force_dns_action_start_scheduled = False
        page._force_dns_action_pending = []
        page._start_force_dns_action_worker = Mock()

        NetworkPage._request_force_dns_action(page, "toggle", enabled=True)

        page._start_force_dns_action_worker.assert_not_called()
        self.assertEqual(page._force_dns_action_pending, [{"action": "toggle", "enabled": True}])

    def test_force_dns_restarts_after_dns_apply_worker_finished(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return False

        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_apply_runtime = _Runtime()
        page._force_dns_action_runtime = _Runtime()
        page._dns_apply_start_scheduled = False
        page._force_dns_action_start_scheduled = False
        page._dns_apply_pending = []
        page._force_dns_action_pending = [{"action": "toggle", "enabled": True}]
        page._start_force_dns_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            NetworkPage._on_dns_apply_worker_finished(page, object())

        page._start_force_dns_action_worker.assert_not_called()
        single_shot.assert_called_once()

        single_shot.call_args.args[1]()

        page._start_force_dns_action_worker.assert_called_once_with({"action": "toggle", "enabled": True})

    def test_dns_apply_restarts_after_force_dns_worker_finished(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return False

        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_apply_runtime = _Runtime()
        page._force_dns_action_runtime = _Runtime()
        page._dns_apply_start_scheduled = False
        page._force_dns_action_start_scheduled = False
        page._dns_apply_pending = [{"action": "auto", "adapters": ["Ethernet"]}]
        page._force_dns_action_pending = []
        page._start_dns_apply_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            NetworkPage._on_force_dns_action_worker_finished(page, object())

        page._start_dns_apply_worker.assert_not_called()
        single_shot.assert_called_once()

        single_shot.call_args.args[1]()

        page._start_dns_apply_worker.assert_called_once_with({"action": "auto", "adapters": ["Ethernet"]})

    def test_dns_mutation_queue_preserves_cross_action_order(self) -> None:
        class _Runtime:
            def __init__(self, running: bool) -> None:
                self._running = running

            def is_running(self) -> bool:
                return self._running

        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_apply_runtime = _Runtime(True)
        page._force_dns_action_runtime = _Runtime(False)
        page._dns_apply_start_scheduled = False
        page._force_dns_action_start_scheduled = False
        page._dns_apply_pending = []
        page._force_dns_action_pending = []
        page._dns_mutation_pending_order = []
        page._start_dns_apply_worker = Mock()
        page._start_force_dns_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        NetworkPage._request_force_dns_action(page, "toggle", enabled=True)
        NetworkPage._request_dns_apply(page, "auto", adapters=["Ethernet"])
        page._dns_apply_runtime._running = False

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            NetworkPage._on_dns_apply_worker_finished(page, object())

        single_shot.assert_called_once()
        single_shot.call_args.args[1]()

        page._start_force_dns_action_worker.assert_called_once_with({"action": "toggle", "enabled": True})
        page._start_dns_apply_worker.assert_not_called()
        self.assertEqual(page._dns_apply_pending, [{"action": "auto", "adapters": ["Ethernet"]}])

    def test_dns_apply_result_ignored_when_new_dns_mutation_is_pending(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_apply_runtime = Mock()
        page._dns_apply_runtime.is_current.return_value = True
        page._dns_apply_pending = []
        page._force_dns_action_pending = [{"action": "toggle", "enabled": True}]
        page._dns_mutation_pending_order = ["force_dns"]
        page._apply_refreshed_adapter_dns_info = Mock()

        NetworkPage._on_dns_apply_finished(
            page,
            7,
            {"dns_info": {"Ethernet": {"dns": ["1.1.1.1"]}}},
        )

        page._apply_refreshed_adapter_dns_info.assert_not_called()

    def test_dns_apply_error_ignored_when_new_dns_mutation_is_pending(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_apply_runtime = Mock()
        page._dns_apply_runtime.is_current.return_value = True
        page._dns_apply_pending = []
        page._force_dns_action_pending = [{"action": "toggle", "enabled": True}]
        page._dns_mutation_pending_order = ["force_dns"]

        with patch("dns.ui.page.log") as log_mock:
            NetworkPage._on_dns_apply_failed(page, 7, "old error")

        log_mock.assert_not_called()

    def test_force_dns_result_ignored_when_new_dns_mutation_is_pending(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._force_dns_action_runtime = Mock()
        page._force_dns_action_runtime.is_current.return_value = True
        page._dns_apply_pending = [{"action": "auto", "adapters": ["Ethernet"]}]
        page._force_dns_action_pending = []
        page._dns_mutation_pending_order = ["dns_apply"]
        page._apply_force_dns_toggle_worker_result = Mock()
        page._apply_force_dns_reset_worker_result = Mock()

        NetworkPage._on_force_dns_action_finished(
            page,
            9,
            "toggle",
            {"message": "", "changed": True},
            {},
        )

        page._apply_force_dns_toggle_worker_result.assert_not_called()
        page._apply_force_dns_reset_worker_result.assert_not_called()

    def test_force_dns_error_ignored_when_new_dns_mutation_is_pending(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._force_dns_action_runtime = Mock()
        page._force_dns_action_runtime.is_current.return_value = True
        page._dns_apply_pending = [{"action": "auto", "adapters": ["Ethernet"]}]
        page._force_dns_action_pending = []
        page._dns_mutation_pending_order = ["dns_apply"]
        page._apply_force_dns_toggle_worker_result = Mock()
        page._tr = Mock(return_value="Ошибка")
        page.window = Mock(return_value=None)

        with (
            patch("dns.ui.page.log") as log_mock,
            patch("dns.ui.page.InfoBar.warning") as warning,
        ):
            NetworkPage._on_force_dns_action_failed(
                page,
                9,
                "toggle",
                "old error",
                {"enabled": True},
            )

        log_mock.assert_not_called()
        warning.assert_not_called()
        page._apply_force_dns_toggle_worker_result.assert_not_called()

    def test_force_dns_pending_restarts_after_event_loop_turn(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._force_dns_action_pending = [{"action": "toggle", "enabled": True}]
        page._start_force_dns_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            NetworkPage._on_force_dns_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_force_dns_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_force_dns_action_worker.assert_called_once_with({"action": "toggle", "enabled": True})

    def test_stale_force_dns_worker_finished_does_not_restart_pending_action(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._force_dns_action_runtime = SimpleNamespace(request_id=5)
        page._force_dns_action_pending = [{"action": "toggle", "enabled": True}]
        page._start_next_dns_mutation_action = Mock()

        NetworkPage._on_force_dns_action_worker_finished(page, SimpleNamespace(_request_id=4))

        page._start_next_dns_mutation_action.assert_not_called()

    def test_stale_force_dns_worker_object_finished_does_not_restart_pending_action(self) -> None:
        old_worker = object()
        current_worker = object()
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._force_dns_action_runtime = SimpleNamespace(request_id=5, worker=current_worker)
        page._force_dns_action_pending = [{"action": "toggle", "enabled": True}]
        page._start_next_dns_mutation_action = Mock()

        NetworkPage._on_force_dns_action_worker_finished(page, old_worker)

        page._start_next_dns_mutation_action.assert_not_called()

    def test_force_dns_scheduled_toggle_uses_latest_pending_value(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return False

        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._force_dns_action_runtime = _Runtime()
        page._force_dns_action_pending = [{"action": "toggle", "enabled": True}]
        page._force_dns_action_start_scheduled = False
        page._start_force_dns_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            NetworkPage._on_force_dns_action_worker_finished(page, object())
            NetworkPage._request_force_dns_action(page, "toggle", enabled=False)

        page._start_force_dns_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_force_dns_action_worker.assert_called_once_with(
            {"action": "toggle", "enabled": False}
        )
        self.assertEqual(page._force_dns_action_pending, [])

    def test_force_dns_running_toggle_keeps_latest_pending_value(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._force_dns_action_runtime = _Runtime()
        page._force_dns_action_pending = []
        page._force_dns_action_start_scheduled = False
        page._start_force_dns_action_worker = Mock()

        NetworkPage._request_force_dns_action(page, "toggle", enabled=True)
        NetworkPage._request_force_dns_action(page, "toggle", enabled=False)

        page._start_force_dns_action_worker.assert_not_called()
        self.assertEqual(page._force_dns_action_pending, [{"action": "toggle", "enabled": False}])

    def test_force_dns_running_reset_dhcp_is_queued_once(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._force_dns_action_runtime = _Runtime()
        page._force_dns_action_pending = []
        page._force_dns_action_start_scheduled = False
        page._start_force_dns_action_worker = Mock()

        NetworkPage._request_force_dns_action(page, "reset_dhcp")
        NetworkPage._request_force_dns_action(page, "reset_dhcp")

        page._start_force_dns_action_worker.assert_not_called()
        self.assertEqual(
            page._force_dns_action_pending,
            [{"action": "reset_dhcp", "enabled": None}],
        )

    def test_dns_flush_cache_pending_restarts_after_event_loop_turn(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_flush_cache_pending = True
        page._start_dns_flush_cache_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            NetworkPage._on_dns_flush_cache_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_dns_flush_cache_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_dns_flush_cache_worker.assert_called_once_with()

    def test_stale_dns_flush_cache_worker_finished_does_not_restart_pending_flush(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_flush_cache_runtime = SimpleNamespace(request_id=8)
        page._dns_flush_cache_pending = True
        page._schedule_dns_flush_cache_worker_start = Mock()

        NetworkPage._on_dns_flush_cache_worker_finished(page, SimpleNamespace(_request_id=7))

        page._schedule_dns_flush_cache_worker_start.assert_not_called()

    def test_stale_dns_flush_cache_worker_object_finished_does_not_restart_pending_flush(self) -> None:
        old_worker = object()
        current_worker = object()
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_flush_cache_runtime = SimpleNamespace(request_id=8, worker=current_worker)
        page._dns_flush_cache_pending = True
        page._schedule_dns_flush_cache_worker_start = Mock()

        NetworkPage._on_dns_flush_cache_worker_finished(page, old_worker)

        page._schedule_dns_flush_cache_worker_start.assert_not_called()
        self.assertTrue(page._dns_flush_cache_pending)

    def test_dns_flush_cache_scheduled_start_queues_next_flush(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._dns_flush_cache_start_scheduled = False
        page._dns_flush_cache_pending = False
        page._start_dns_flush_cache_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            NetworkPage._schedule_dns_flush_cache_worker_start(page)
            NetworkPage._schedule_dns_flush_cache_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._dns_flush_cache_pending)

        single_shot.call_args.args[1]()

        page._start_dns_flush_cache_worker.assert_called_once_with()
        self.assertTrue(page._dns_flush_cache_pending)

    def test_network_page_load_and_connectivity_use_feature_worker_runtime(self) -> None:
        feature_source = inspect.getsource(build_dns_feature)
        page_source = inspect.getsource(NetworkPage)
        loading_source = inspect.getsource(NetworkPage._start_loading)
        test_source = inspect.getsource(NetworkPage._test_connection)
        cleanup_source = inspect.getsource(NetworkPage.cleanup)

        for name in (
            "create_page_load_worker",
            "create_connectivity_test_worker",
        ):
            self.assertIn(name, feature_source)
            self.assertIn(name, page_source)
        for name in (
            "_page_load_runtime",
            "_connectivity_test_runtime",
        ):
            self.assertIn(name, page_source)
            self.assertIn(f"{name}.stop", cleanup_source)
        for source in (loading_source, test_source):
            self.assertIn("start_qthread_worker", source)
            self.assertNotIn("worker.start()", source)
        self.assertNotIn("start_background_loading(", loading_source)
        self.assertNotIn("start_connectivity_test(", test_source)

    def test_network_page_load_queues_while_worker_runs(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._page_load_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        page._page_load_pending = False

        NetworkPage._start_loading(page)

        page._page_load_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._page_load_pending)

    def test_pending_network_page_load_restarts_after_event_loop_turn(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._page_load_pending = True
        page._page_load_start_scheduled = False
        page._start_loading = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            NetworkPage._on_page_load_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_loading.assert_not_called()

        single_shot.call_args.args[1]()

        self.assertFalse(page._page_load_pending)
        page._start_loading.assert_called_once_with()

    def test_stale_network_page_load_worker_finished_does_not_restart_load(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._page_load_runtime = SimpleNamespace(request_id=11)
        page._page_load_pending = True
        page._schedule_page_load_worker_start = Mock()

        NetworkPage._on_page_load_worker_finished(page, SimpleNamespace(_request_id=10))

        page._schedule_page_load_worker_start.assert_not_called()

    def test_stale_network_page_load_worker_object_finished_does_not_restart_load(self) -> None:
        old_worker = object()
        current_worker = object()
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._page_load_runtime = SimpleNamespace(request_id=11, worker=current_worker)
        page._page_load_pending = True
        page._schedule_page_load_worker_start = Mock()

        NetworkPage._on_page_load_worker_finished(page, old_worker)

        page._schedule_page_load_worker_start.assert_not_called()
        self.assertTrue(page._page_load_pending)

    def test_isp_warning_plan_queues_while_worker_runs(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._isp_warning_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        page._isp_warning_pending = False

        NetworkPage._request_isp_dns_warning_plan(page)

        page._isp_warning_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._isp_warning_pending)

    def test_pending_isp_warning_plan_restarts_after_event_loop_turn(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._isp_warning_pending = True
        page._isp_warning_start_scheduled = False
        page._request_isp_dns_warning_plan = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            NetworkPage._on_isp_dns_warning_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_isp_dns_warning_plan.assert_not_called()

        single_shot.call_args.args[1]()

        self.assertFalse(page._isp_warning_pending)
        page._request_isp_dns_warning_plan.assert_called_once_with()

    def test_stale_isp_warning_worker_finished_does_not_restart_warning_plan(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._isp_warning_runtime = SimpleNamespace(request_id=14)
        page._isp_warning_pending = True
        page._schedule_isp_warning_worker_start = Mock()

        NetworkPage._on_isp_dns_warning_worker_finished(page, SimpleNamespace(_request_id=13))

        page._schedule_isp_warning_worker_start.assert_not_called()

    def test_stale_isp_warning_worker_object_finished_does_not_restart_warning_plan(self) -> None:
        old_worker = object()
        current_worker = object()
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._isp_warning_runtime = SimpleNamespace(request_id=14, worker=current_worker)
        page._isp_warning_pending = True
        page._schedule_isp_warning_worker_start = Mock()

        NetworkPage._on_isp_dns_warning_worker_finished(page, old_worker)

        page._schedule_isp_warning_worker_start.assert_not_called()
        self.assertTrue(page._isp_warning_pending)

    def test_isp_warning_plan_result_ignored_when_new_plan_is_pending(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._isp_warning_pending = True
        page._isp_warning_runtime = Mock()
        page._isp_warning_runtime.is_current.return_value = True
        page._render_isp_warning_styles = Mock()
        page.add_widget = Mock()
        page.dns_cards_container = object()
        page._accept_isp_dns_recommendation = Mock()
        page._dismiss_isp_dns_warning = Mock()

        with patch.object(network_page, "show_isp_dns_warning") as show_warning:
            NetworkPage._on_isp_dns_warning_plan_loaded(page, 14, object())

        show_warning.assert_not_called()

    def test_isp_warning_plan_error_ignored_when_new_plan_is_pending(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._isp_warning_pending = True
        page._isp_warning_runtime = Mock()
        page._isp_warning_runtime.is_current.return_value = True

        with patch.object(network_page, "log") as log_mock:
            NetworkPage._on_isp_dns_warning_plan_failed(page, 14, "old warning failed")

        log_mock.assert_not_called()

    def test_connectivity_test_queues_while_worker_runs(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._connectivity_test_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._connectivity_test_pending = False
        page._update_test_action_text = Mock()

        NetworkPage._test_connection(page)

        self.assertTrue(page._connectivity_test_pending)
        page._update_test_action_text.assert_not_called()

    def test_pending_connectivity_test_restarts_after_event_loop_turn(self) -> None:
        import dns.ui.page as network_page_module

        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._connectivity_test_pending = True
        page._connectivity_test_start_scheduled = False
        page._test_connection = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(network_page_module, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            NetworkPage._on_connectivity_test_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._test_connection.assert_not_called()

        single_shot.call_args.args[1]()

        self.assertFalse(page._connectivity_test_pending)
        page._test_connection.assert_called_once_with()

    def test_stale_connectivity_worker_finished_does_not_restart_test(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._connectivity_test_runtime = SimpleNamespace(request_id=17)
        page._connectivity_test_pending = True
        page._schedule_connectivity_test_start = Mock()

        NetworkPage._on_connectivity_test_worker_finished(page, SimpleNamespace(_request_id=16))

        page._schedule_connectivity_test_start.assert_not_called()

    def test_stale_connectivity_worker_object_finished_does_not_restart_test(self) -> None:
        old_worker = object()
        current_worker = object()
        page = NetworkPage.__new__(NetworkPage)
        page._cleanup_in_progress = False
        page._connectivity_test_runtime = SimpleNamespace(request_id=17, worker=current_worker)
        page._connectivity_test_pending = True
        page._schedule_connectivity_test_start = Mock()

        NetworkPage._on_connectivity_test_worker_finished(page, old_worker)

        page._schedule_connectivity_test_start.assert_not_called()
        self.assertTrue(page._connectivity_test_pending)

    def test_dns_check_page_uses_one_shot_runtime_for_check_save_and_quick(self) -> None:
        page_source = inspect.getsource(DNSCheckPage)
        start_source = inspect.getsource(DNSCheckPage.start_check)
        quick_source = inspect.getsource(DNSCheckPage._start_quick_dns_check_worker)
        save_source = inspect.getsource(DNSCheckPage._start_save_results_worker)
        cleanup_source = inspect.getsource(DNSCheckPage.cleanup)

        self.assertIn("OneShotWorkerRuntime", page_source)
        for name in (
            "_check_runtime",
            "_quick_runtime",
            "_save_runtime",
        ):
            self.assertIn(name, page_source)
            self.assertIn(f"{name}.stop", cleanup_source)
        self.assertIn("start_qobject_worker", start_source)
        for source in (quick_source, save_source):
            self.assertIn("start_qthread_worker", source)
        for source in (start_source, quick_source, save_source):
            self.assertNotIn("worker.start()", source)
        self.assertNotIn("self.thread = QThread", start_source)

    def test_dns_check_save_queues_while_worker_runs(self) -> None:
        page = DNSCheckPage.__new__(DNSCheckPage)
        page._save_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        page._save_results_pending = None

        DNSCheckPage._start_save_results_worker(page, file_path="first.txt", plain_text="latest")

        page._save_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(page._save_results_pending, {"file_path": "first.txt", "plain_text": "latest"})

    def test_dns_check_pending_save_restarts_after_event_loop_turn(self) -> None:
        import dns.ui.dns_check_page as dns_check_page

        page = DNSCheckPage.__new__(DNSCheckPage)
        page._cleanup_in_progress = False
        page._save_results_pending = {"file_path": "first.txt", "plain_text": "latest"}
        page._start_save_results_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(dns_check_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DNSCheckPage._on_save_results_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_save_results_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_save_results_worker.assert_called_once_with(
            file_path="first.txt",
            plain_text="latest",
        )

    def test_stale_dns_check_save_finish_does_not_restart_pending_save(self) -> None:
        import dns.ui.dns_check_page as dns_check_page

        page = DNSCheckPage.__new__(DNSCheckPage)
        page._cleanup_in_progress = False
        page._save_runtime = SimpleNamespace(worker=object())
        page._save_results_pending = {"file_path": "first.txt", "plain_text": "latest"}
        page._save_results_start_scheduled = False
        page._start_save_results_worker = Mock()
        single_shot = Mock()

        with patch.object(dns_check_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DNSCheckPage._on_save_results_worker_finished(page, object())

        single_shot.assert_not_called()
        page._start_save_results_worker.assert_not_called()
        self.assertEqual(page._save_results_pending, {"file_path": "first.txt", "plain_text": "latest"})

    def test_dns_check_scheduled_save_uses_latest_pending_payload(self) -> None:
        page = DNSCheckPage.__new__(DNSCheckPage)
        page._cleanup_in_progress = False
        page._save_results_pending = {"file_path": "second.txt", "plain_text": "newer"}
        page._save_results_start_scheduled = True
        page._start_save_results_worker = Mock()

        DNSCheckPage._run_scheduled_save_results_worker_start(page)

        page._start_save_results_worker.assert_called_once_with(
            file_path="second.txt",
            plain_text="newer",
        )

    def test_stale_dns_full_check_finish_does_not_restart_pending_check(self) -> None:
        import dns.ui.dns_check_page as dns_check_page

        page = DNSCheckPage.__new__(DNSCheckPage)
        page._cleanup_in_progress = False
        page._check_runtime = SimpleNamespace(request_id=2)
        page._check_pending = True
        page._check_start_scheduled = False
        page.start_check = Mock()
        single_shot = Mock()

        with patch.object(dns_check_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DNSCheckPage._on_check_worker_finished(page, 1, object())

        single_shot.assert_not_called()
        page.start_check.assert_not_called()
        self.assertTrue(page._check_pending)

    def test_dns_full_check_queues_while_worker_runs(self) -> None:
        page = DNSCheckPage.__new__(DNSCheckPage)
        page._check_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._check_pending = False
        page.result_text = Mock()
        page._apply_interaction_state = Mock()
        page._set_status = Mock()

        DNSCheckPage.start_check(page)

        self.assertTrue(page._check_pending)
        page.result_text.clear.assert_not_called()
        page._apply_interaction_state.assert_not_called()
        page._set_status.assert_not_called()

    def test_dns_pending_full_check_restarts_after_event_loop_turn(self) -> None:
        import dns.ui.dns_check_page as dns_check_page

        page = DNSCheckPage.__new__(DNSCheckPage)
        page._cleanup_in_progress = False
        page._check_pending = True
        page._check_start_scheduled = False
        page.start_check = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(dns_check_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DNSCheckPage._on_check_worker_finished(page, 1, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page.start_check.assert_not_called()

        single_shot.call_args.args[1]()

        self.assertFalse(page._check_pending)
        page.start_check.assert_called_once_with()

    def test_dns_quick_check_queues_while_worker_runs(self) -> None:
        page = DNSCheckPage.__new__(DNSCheckPage)
        page._quick_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._quick_check_pending = False
        page.result_text = Mock()
        page._apply_interaction_state = Mock()
        page._set_status = Mock()
        page._start_quick_dns_check_worker = Mock()

        DNSCheckPage.quick_dns_check(page)

        self.assertTrue(page._quick_check_pending)
        page.result_text.clear.assert_not_called()
        page._apply_interaction_state.assert_not_called()
        page._set_status.assert_not_called()
        page._start_quick_dns_check_worker.assert_not_called()

    def test_dns_pending_quick_check_restarts_after_event_loop_turn(self) -> None:
        import dns.ui.dns_check_page as dns_check_page

        page = DNSCheckPage.__new__(DNSCheckPage)
        page._cleanup_in_progress = False
        page._quick_check_pending = True
        page._quick_check_start_scheduled = False
        page.quick_dns_check = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(dns_check_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DNSCheckPage._on_quick_dns_check_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page.quick_dns_check.assert_not_called()

        single_shot.call_args.args[1]()

        self.assertFalse(page._quick_check_pending)
        page.quick_dns_check.assert_called_once_with()

    def test_stale_dns_quick_check_finish_does_not_restart_pending_check(self) -> None:
        import dns.ui.dns_check_page as dns_check_page

        page = DNSCheckPage.__new__(DNSCheckPage)
        page._cleanup_in_progress = False
        page._quick_runtime = SimpleNamespace(worker=object())
        page._quick_check_pending = True
        page._quick_check_start_scheduled = False
        page.quick_dns_check = Mock()
        single_shot = Mock()

        with patch.object(dns_check_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DNSCheckPage._on_quick_dns_check_worker_finished(page, object())

        single_shot.assert_not_called()
        page.quick_dns_check.assert_not_called()
        self.assertTrue(page._quick_check_pending)

    def test_startup_dns_apply_uses_one_shot_runtime(self) -> None:
        module_source = inspect.getsource(dns_worker)
        async_source = inspect.getsource(dns_worker.apply_dns_on_startup_async)
        cleanup_source = inspect.getsource(dns_worker._cleanup_startup_worker)

        self.assertIn("_startup_runtime = OneShotWorkerRuntime()", module_source)
        self.assertIn("_startup_runtime.is_running()", async_source)
        self.assertIn("_startup_runtime.start_qthread_worker", async_source)
        self.assertIn("_startup_runtime.stop", cleanup_source)
        self.assertIn("_startup_runtime.cancel", cleanup_source)
        self.assertNotIn("_startup_worker = None", module_source)
        self.assertNotIn("global _startup_worker", async_source)
        self.assertNotIn("worker.start()", async_source)
        self.assertNotIn("worker.deleteLater()", cleanup_source)

    def test_dns_feature_does_not_expose_heavy_direct_commands(self) -> None:
        feature = build_dns_feature()

        for attr_name in (
            "load_page_data",
            "refresh_dns_info",
            "apply_auto_dns",
            "apply_provider_dns",
            "apply_custom_dns",
            "get_force_dns_status",
            "is_isp_dns_warning_shown",
            "mark_isp_dns_warning_shown",
            "enable_force_dns",
            "disable_force_dns",
            "flush_dns_cache",
            "run_connectivity_test",
            "run_dns_poisoning_check",
            "save_dns_check_results",
            "run_quick_dns_check",
        ):
            self.assertFalse(hasattr(feature, attr_name), attr_name)


if __name__ == "__main__":
    unittest.main()
