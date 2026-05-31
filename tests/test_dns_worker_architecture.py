from __future__ import annotations

import inspect
import unittest

from app.feature_facades.dns import build_dns_feature
from dns import dns_check_worker, dns_worker, page_workers
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

        for expected in (
            "get_force_dns_status=feature.get_force_dns_status",
            "enable_force_dns=feature.enable_force_dns",
            "disable_force_dns=feature.disable_force_dns",
            "flush_dns_cache=feature.flush_dns_cache",
            "apply_auto_dns=feature.apply_auto_dns",
            "apply_provider_dns=feature.apply_provider_dns",
            "apply_custom_dns=feature.apply_custom_dns",
            "refresh_dns_info=feature.refresh_dns_info",
            "is_isp_dns_warning_shown=feature.is_isp_dns_warning_shown",
            "mark_isp_dns_warning_shown=feature.mark_isp_dns_warning_shown",
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
            "run_dns_poisoning_check=feature.run_dns_poisoning_check",
            "save_dns_check_results=feature.save_dns_check_results",
            "run_quick_dns_check=feature.run_quick_dns_check",
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


if __name__ == "__main__":
    unittest.main()
