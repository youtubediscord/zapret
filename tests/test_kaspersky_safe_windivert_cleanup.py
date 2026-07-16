import unittest
from unittest.mock import patch


class KasperskyProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._reset_probe_cache()
        self.addCleanup(self._reset_probe_cache)

    @staticmethod
    def _reset_probe_cache() -> None:
        from utils import antivirus_probe

        antivirus_probe._cached_result = None
        antivirus_probe._cached_at = 0.0

    def test_detects_kaspersky_by_process_name(self) -> None:
        from utils import antivirus_probe

        with (
            patch.object(antivirus_probe, "iter_process_names_winapi", return_value=["explorer.exe", "AVP.exe"]),
            patch.object(antivirus_probe, "iter_uninstall_display_names", return_value=[]),
        ):
            self.assertTrue(antivirus_probe.is_kaspersky_present(force_refresh=True))

    def test_detects_kaspersky_by_uninstall_display_name_latin_and_cyrillic(self) -> None:
        from utils import antivirus_probe

        for display_name in ("Kaspersky Total Security", "Антивирус Касперского"):
            with (
                patch.object(antivirus_probe, "iter_process_names_winapi", return_value=[]),
                patch.object(antivirus_probe, "iter_uninstall_display_names", return_value=[display_name]),
            ):
                self.assertTrue(
                    antivirus_probe.is_kaspersky_present(force_refresh=True),
                    display_name,
                )

    def test_no_kaspersky_detected(self) -> None:
        from utils import antivirus_probe

        with (
            patch.object(antivirus_probe, "iter_process_names_winapi", return_value=["explorer.exe"]),
            patch.object(antivirus_probe, "iter_uninstall_display_names", return_value=["7-Zip"]),
        ):
            self.assertFalse(antivirus_probe.is_kaspersky_present(force_refresh=True))

    def test_probe_exception_yields_false_not_raise(self) -> None:
        from utils import antivirus_probe

        with patch.object(antivirus_probe, "iter_process_names_winapi", side_effect=OSError("boom")):
            self.assertFalse(antivirus_probe.is_kaspersky_present(force_refresh=True))

    def test_result_is_cached_within_ttl(self) -> None:
        from utils import antivirus_probe

        with (
            patch.object(antivirus_probe, "iter_process_names_winapi", return_value=["avp.exe"]) as processes,
            patch.object(antivirus_probe, "iter_uninstall_display_names", return_value=[]),
            patch.object(antivirus_probe.time, "monotonic", side_effect=[100.0, 100.0 + 1.0]),
        ):
            self.assertTrue(antivirus_probe.is_kaspersky_present())
            self.assertTrue(antivirus_probe.is_kaspersky_present())

        processes.assert_called_once()

    def test_cache_expires_after_ttl(self) -> None:
        from utils import antivirus_probe

        ttl = antivirus_probe._CACHE_TTL_SECONDS
        with (
            patch.object(antivirus_probe, "iter_process_names_winapi", return_value=[]) as processes,
            patch.object(antivirus_probe, "iter_uninstall_display_names", return_value=[]),
            patch.object(antivirus_probe.time, "monotonic", side_effect=[100.0, 100.0 + ttl + 1.0]),
        ):
            antivirus_probe.is_kaspersky_present()
            antivirus_probe.is_kaspersky_present()

        self.assertEqual(processes.call_count, 2)

    def test_startup_kaspersky_delegates_to_shared_probe(self) -> None:
        from startup import kaspersky

        self.assertFalse(hasattr(kaspersky, "_KASPERSKY_PROCESS_NAMES"))
        with patch.object(kaspersky, "is_kaspersky_present", return_value=True) as probe:
            self.assertTrue(kaspersky._check_kaspersky_antivirus())
        probe.assert_called_once()


class AggressiveCleanupKasperskySafeTests(unittest.TestCase):
    def _run_cleanup(self, *, kaspersky: bool, settled: bool = True):
        from winws_runtime.runtime import system_ops

        with (
            patch.object(system_ops, "_is_kaspersky_present_safe", return_value=kaspersky),
            patch.object(system_ops, "force_kill_all_winws_processes", return_value=True) as force_kill,
            patch.object(
                system_ops, "wait_for_windivert_cleanup_settle_runtime", return_value=settled
            ) as settle,
            patch.object(system_ops, "unload_known_windivert_drivers_runtime", return_value=True) as unload,
            patch.object(system_ops, "stop_and_delete_runtime_services", return_value=True) as stop_delete,
            patch.object(
                system_ops, "clear_stopped_windivert_delete_flags_runtime", return_value=True
            ) as clear_flags,
            patch.object(
                system_ops, "restore_known_windivert_services_demand_start_runtime", return_value=True
            ) as restore_start,
            patch.object(system_ops.time, "sleep"),
        ):
            result = system_ops.aggressive_windivert_cleanup_runtime()

        return result, {
            "force_kill": force_kill,
            "settle": settle,
            "unload": unload,
            "stop_delete": stop_delete,
            "clear_flags": clear_flags,
            "restore_start": restore_start,
        }

    def test_kaspersky_skips_driver_unload_and_service_deletion(self) -> None:
        result, mocks = self._run_cleanup(kaspersky=True)

        self.assertTrue(result)
        mocks["unload"].assert_not_called()
        mocks["stop_delete"].assert_not_called()
        mocks["clear_flags"].assert_called_once()
        mocks["restore_start"].assert_called_once()
        self.assertGreaterEqual(mocks["force_kill"].call_count, 2)

    def test_without_kaspersky_unload_and_deletion_happen(self) -> None:
        result, mocks = self._run_cleanup(kaspersky=False)

        self.assertTrue(result)
        mocks["unload"].assert_called_once()
        mocks["stop_delete"].assert_called()

    def test_settle_wait_runs_before_driver_unload(self) -> None:
        from winws_runtime.runtime import system_ops

        call_order: list[str] = []

        with (
            patch.object(system_ops, "_is_kaspersky_present_safe", return_value=False),
            patch.object(system_ops, "force_kill_all_winws_processes", return_value=True),
            patch.object(
                system_ops,
                "wait_for_windivert_cleanup_settle_runtime",
                side_effect=lambda **kw: call_order.append("settle") or True,
            ),
            patch.object(
                system_ops,
                "unload_known_windivert_drivers_runtime",
                side_effect=lambda: call_order.append("unload") or True,
            ),
            patch.object(system_ops, "stop_and_delete_runtime_services", return_value=True),
            patch.object(system_ops, "clear_stopped_windivert_delete_flags_runtime", return_value=True),
            patch.object(
                system_ops, "restore_known_windivert_services_demand_start_runtime", return_value=True
            ),
            patch.object(system_ops.time, "sleep"),
        ):
            system_ops.aggressive_windivert_cleanup_runtime()

        self.assertIn("settle", call_order)
        self.assertIn("unload", call_order)
        self.assertLess(call_order.index("settle"), call_order.index("unload"))

    def test_pre_unload_settle_timeout_does_not_fail_cleanup(self) -> None:
        from winws_runtime.runtime import system_ops

        settle_results = iter([False, True])

        with (
            patch.object(system_ops, "_is_kaspersky_present_safe", return_value=False),
            patch.object(system_ops, "force_kill_all_winws_processes", return_value=True),
            patch.object(
                system_ops,
                "wait_for_windivert_cleanup_settle_runtime",
                side_effect=lambda **kw: next(settle_results),
            ),
            patch.object(system_ops, "unload_known_windivert_drivers_runtime", return_value=True) as unload,
            patch.object(system_ops, "stop_and_delete_runtime_services", return_value=True),
            patch.object(system_ops, "clear_stopped_windivert_delete_flags_runtime", return_value=True),
            patch.object(
                system_ops, "restore_known_windivert_services_demand_start_runtime", return_value=True
            ),
            patch.object(system_ops.time, "sleep"),
        ):
            result = system_ops.aggressive_windivert_cleanup_runtime()

        self.assertTrue(result)
        unload.assert_called_once()

    def test_kaspersky_detection_failure_falls_back_to_full_cleanup(self) -> None:
        from winws_runtime.runtime import system_ops

        with patch(
            "utils.antivirus_probe.is_kaspersky_present", side_effect=RuntimeError("probe broken")
        ):
            self.assertFalse(system_ops._is_kaspersky_present_safe())


class StrategyScannerCooldownTests(unittest.TestCase):
    def test_cooldown_pause_with_kaspersky(self) -> None:
        from blockcheck import strategy_scanner

        with patch("utils.antivirus_probe.is_kaspersky_present", return_value=True):
            pause = strategy_scanner._strategy_cleanup_pause_seconds()

        self.assertEqual(pause, strategy_scanner._KASPERSKY_STRATEGY_COOLDOWN_SECONDS)

    def test_default_pause_without_kaspersky(self) -> None:
        from blockcheck import strategy_scanner

        with patch("utils.antivirus_probe.is_kaspersky_present", return_value=False):
            self.assertEqual(strategy_scanner._strategy_cleanup_pause_seconds(), 0.8)

    def test_probe_failure_uses_default_pause(self) -> None:
        from blockcheck import strategy_scanner

        with patch("utils.antivirus_probe.is_kaspersky_present", side_effect=OSError("boom")):
            self.assertEqual(strategy_scanner._strategy_cleanup_pause_seconds(), 0.8)


if __name__ == "__main__":
    unittest.main()
