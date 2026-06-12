import unittest
import inspect
from unittest.mock import Mock, patch


class WinDivertServiceRecoveryTests(unittest.TestCase):
    def test_regular_runner_stop_does_not_delete_monkey_service(self) -> None:
        from winws_runtime.runners import runner_base

        class DummyRunner(runner_base.StrategyRunnerBase):
            def start_from_preset_file(self, preset_path: str, strategy_name: str = "Preset") -> bool:
                return True

            def switch_preset_file_fast(self, preset_path: str, strategy_name: str = "Preset", *, is_current=None) -> bool:
                return True

        with (
            patch.object(runner_base.os.path, "exists", return_value=True),
            patch.object(runner_base, "standard_windivert_cleanup_runtime") as standard_cleanup,
            patch.object(runner_base, "force_kill_all_winws_processes", return_value=True),
            patch.object(runner_base, "stop_and_delete_named_service") as stop_and_delete,
        ):
            runner = DummyRunner(r"C:\Zapret\Dev\exe\winws2.exe")
            stopped = runner.stop(cleanup_services=True)

        self.assertTrue(stopped)
        standard_cleanup.assert_called_once_with()
        stop_and_delete.assert_not_called()

    def test_stop_and_delete_waits_until_service_is_really_removed(self) -> None:
        from utils import service_manager

        with (
            patch.object(service_manager, "stop_service", return_value=True),
            patch.object(service_manager, "delete_service", return_value=True),
            patch.object(service_manager, "service_exists", return_value=True) as service_exists,
            patch.object(service_manager.time, "sleep"),
        ):
            removed = service_manager.stop_and_delete_service("Monkey", retry_count=1)

        self.assertFalse(removed)
        service_exists.assert_called_with("Monkey")

    def test_monkey_disabled_service_is_reported_as_windivert_driver_problem(self) -> None:
        from winws_runtime.health import process_health_check

        fake_winreg = Mock()
        fake_winreg.HKEY_LOCAL_MACHINE = object()
        fake_winreg.KEY_READ = 0
        fake_key = Mock()
        fake_key.__enter__ = Mock(return_value=fake_key)
        fake_key.__exit__ = Mock(return_value=False)

        def open_key(_root, path, *_args):
            if path.endswith("\\Monkey"):
                return fake_key
            raise FileNotFoundError(path)

        fake_winreg.OpenKey.side_effect = open_key
        fake_winreg.QueryValueEx.return_value = (4, None)

        with patch.dict("sys.modules", {"winreg": fake_winreg}):
            service_name = process_health_check._find_disabled_windivert_driver_service()

        self.assertEqual(service_name, "Monkey")

    def test_aggressive_cleanup_wait_treats_stopped_monkey_service_as_stale(self) -> None:
        from winws_runtime.runtime import system_ops

        with (
            patch.object(system_ops, "get_all_winws_process_pids", return_value=[]),
            patch.object(
                system_ops,
                "get_known_windivert_service_states_runtime",
                return_value={"Monkey": system_ops._SERVICE_STOPPED},
            ),
            patch.object(system_ops, "stop_and_delete_runtime_services") as stop_and_delete,
            patch.object(system_ops, "unload_known_windivert_drivers_runtime"),
            patch.object(system_ops, "log"),
            patch.object(system_ops.time, "sleep"),
        ):
            settled = system_ops.wait_for_windivert_cleanup_settle_runtime(
                max_wait_seconds=0.01,
                poll_interval=0.001,
                retry_cleanup=True,
            )

        self.assertFalse(settled)
        stop_and_delete.assert_called()

    def test_aggressive_cleanup_restores_leftover_windivert_services_to_manual_start(self) -> None:
        from winws_runtime.runtime import system_ops

        with (
            patch.object(system_ops, "force_kill_all_winws_processes", return_value=True),
            patch.object(system_ops, "unload_known_windivert_drivers_runtime", return_value=True),
            patch.object(system_ops, "stop_and_delete_runtime_services", return_value=False),
            patch.object(system_ops, "restore_known_windivert_services_demand_start_runtime") as restore_start,
            patch.object(system_ops, "wait_for_windivert_cleanup_settle_runtime", return_value=True),
            patch.object(system_ops.time, "sleep"),
            patch.object(system_ops, "log"),
        ):
            system_ops.aggressive_windivert_cleanup_runtime()

        restore_start.assert_called_once_with()

    def test_spawn_readiness_restores_disabled_windivert_service_before_retry(self) -> None:
        from winws_runtime.runtime import system_ops

        disabled_probe = system_ops.WinDivertRuntimeProbeResult(
            installed=False,
            ready=False,
            error_code=1058,
            stage="network_open",
        )
        ready_probe = system_ops.WinDivertRuntimeProbeResult(
            installed=True,
            ready=True,
            error_code=None,
            stage="network_open",
        )

        with (
            patch.object(
                system_ops,
                "probe_windivert_state_runtime",
                side_effect=[disabled_probe, ready_probe],
            ),
            patch.object(system_ops, "restore_known_windivert_services_demand_start_runtime") as restore_start,
            patch.object(system_ops.time, "sleep"),
            patch.object(system_ops, "log"),
        ):
            result = system_ops.wait_for_windivert_spawn_ready_runtime(
                max_wait_seconds=1.0,
                poll_interval=0.001,
            )

        self.assertTrue(result.ready)
        restore_start.assert_called_once_with()

    def test_spawn_readiness_logs_when_disabled_service_restore_fails(self) -> None:
        from winws_runtime.runtime import system_ops

        disabled_probe = system_ops.WinDivertRuntimeProbeResult(
            installed=False,
            ready=False,
            error_code=1058,
            stage="network_open",
        )

        with (
            patch.object(system_ops, "probe_windivert_state_runtime", return_value=disabled_probe),
            patch.object(
                system_ops,
                "restore_known_windivert_services_demand_start_runtime",
                return_value=False,
            ) as restore_start,
            patch.object(system_ops.time, "sleep"),
            patch.object(system_ops, "log") as log,
        ):
            result = system_ops.wait_for_windivert_spawn_ready_runtime(
                max_wait_seconds=0.01,
                poll_interval=0.001,
            )

        self.assertFalse(result.ready)
        restore_start.assert_called_once_with()
        self.assertTrue(
            any("administrator rights" in call.args[0] for call in log.call_args_list)
        )

    def test_running_disabled_delete_pending_monkey_is_detected_as_stale(self) -> None:
        from winws_runtime.runtime import system_ops

        with (
            patch.object(
                system_ops,
                "get_known_windivert_service_states_runtime",
                return_value={"Monkey": system_ops._SERVICE_RUNNING},
            ),
            patch.object(
                system_ops,
                "get_known_windivert_service_registry_flags_runtime",
                return_value={"Monkey": {"start": system_ops._SERVICE_DISABLED, "delete_flag": 1}},
            ),
        ):
            stale_services = system_ops.find_stale_windivert_delete_pending_services_runtime()

        self.assertEqual(stale_services, ["Monkey"])

    def test_spawn_readiness_reports_running_disabled_delete_pending_monkey_as_not_ready(self) -> None:
        from winws_runtime.runtime import system_ops

        ready_probe = system_ops.WinDivertRuntimeProbeResult(
            installed=True,
            ready=True,
            error_code=None,
            stage="network_open",
        )

        with (
            patch.object(system_ops, "probe_windivert_state_runtime", return_value=ready_probe),
            patch.object(
                system_ops,
                "find_stale_windivert_delete_pending_services_runtime",
                return_value=["Monkey"],
            ),
            patch.object(system_ops, "log"),
        ):
            result = system_ops.wait_for_windivert_spawn_ready_runtime(
                max_wait_seconds=1.0,
                poll_interval=0.001,
            )

        self.assertFalse(result.ready)
        self.assertEqual(result.error_code, system_ops._ERROR_SERVICE_MARKED_FOR_DELETE)
        self.assertEqual(result.stage, "stale_delete_pending:Monkey")

    def test_runner_treats_access_denied_readiness_as_transient_cleanup_case(self) -> None:
        from winws_runtime.runners import runner_base
        from winws_runtime.runtime.system_ops import WinDivertRuntimeProbeResult

        class DummyRunner(runner_base.StrategyRunnerBase):
            def start_from_preset_file(self, preset_path: str, strategy_name: str = "Preset") -> bool:
                return True

            def switch_preset_file_fast(self, preset_path: str, strategy_name: str = "Preset", *, is_current=None) -> bool:
                return True

        blocked_probe = WinDivertRuntimeProbeResult(
            installed=True,
            ready=False,
            error_code=5,
            stage="network_open",
        )
        ready_probe = WinDivertRuntimeProbeResult(
            installed=True,
            ready=True,
            error_code=None,
            stage="network_open",
        )

        with (
            patch.object(runner_base.os.path, "exists", return_value=True),
            patch.object(runner_base, "wait_for_windivert_spawn_ready_runtime", return_value=ready_probe)
            as wait_ready,
            patch.object(DummyRunner, "_aggressive_windivert_cleanup") as cleanup,
            patch.object(DummyRunner, "_wait_after_aggressive_windivert_cleanup"),
        ):
            runner = DummyRunner(r"C:\Zapret\Dev\exe\winws2.exe")
            result = runner._retry_windivert_spawn_readiness_after_recovery(blocked_probe)

        self.assertTrue(result.ready)
        cleanup.assert_called_once_with()
        wait_ready.assert_called_once()

    def test_runner_treats_delete_pending_monkey_readiness_as_transient_cleanup_case(self) -> None:
        from winws_runtime.runners import runner_base
        from winws_runtime.runtime.system_ops import WinDivertRuntimeProbeResult

        class DummyRunner(runner_base.StrategyRunnerBase):
            def start_from_preset_file(self, preset_path: str, strategy_name: str = "Preset") -> bool:
                return True

            def switch_preset_file_fast(self, preset_path: str, strategy_name: str = "Preset", *, is_current=None) -> bool:
                return True

        blocked_probe = WinDivertRuntimeProbeResult(
            installed=True,
            ready=False,
            error_code=runner_base._ERROR_SERVICE_MARKED_FOR_DELETE,
            stage="stale_delete_pending:Monkey",
        )
        ready_probe = WinDivertRuntimeProbeResult(
            installed=True,
            ready=True,
            error_code=None,
            stage="network_open",
        )

        with (
            patch.object(runner_base.os.path, "exists", return_value=True),
            patch.object(runner_base, "wait_for_windivert_spawn_ready_runtime", return_value=ready_probe)
            as wait_ready,
            patch.object(DummyRunner, "_aggressive_windivert_cleanup") as cleanup,
            patch.object(DummyRunner, "_wait_after_aggressive_windivert_cleanup"),
        ):
            runner = DummyRunner(r"C:\Zapret\Dev\exe\winws2.exe")
            result = runner._retry_windivert_spawn_readiness_after_recovery(blocked_probe)

        self.assertTrue(result.ready)
        cleanup.assert_called_once_with()
        wait_ready.assert_called_once()

    def test_runtime_cleanup_keeps_windivert_service_running(self) -> None:
        from winws_runtime.runtime import runtime_api

        api = runtime_api.PresetLaunchRuntimeApi(r"C:\Zapret\Dev\exe\winws2.exe")
        calls: list[str] = []

        with (
            patch.object(
                runtime_api,
                "restore_known_windivert_services_demand_start_runtime",
                side_effect=lambda: calls.append("restore") or True,
            ),
        ):
            cleaned = api.cleanup_windivert_service()

        self.assertTrue(cleaned)
        self.assertEqual(calls, ["restore"])
        cleanup_source = inspect.getsource(runtime_api.PresetLaunchRuntimeApi.cleanup_windivert_service)
        self.assertNotIn("stop_known_windivert_services_runtime", cleanup_source)
        self.assertNotIn("unload_known_windivert_drivers_runtime", cleanup_source)

    def test_standard_cleanup_keeps_windivert_service_running(self) -> None:
        from winws_runtime.runtime import system_ops

        with (
            patch.object(system_ops, "force_kill_all_winws_processes", return_value=True),
            patch.object(system_ops, "restore_known_windivert_services_demand_start_runtime") as restore_start,
            patch.object(system_ops, "unload_known_windivert_drivers_runtime") as unload_driver,
            patch.object(system_ops, "wait_for_windivert_cleanup_settle_runtime") as wait_cleanup,
            patch.object(system_ops.time, "sleep"),
        ):
            cleaned = system_ops.standard_windivert_cleanup_runtime(sleep_seconds=0.01)

        self.assertTrue(cleaned)
        restore_start.assert_called_once_with()
        unload_driver.assert_not_called()
        wait_cleanup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
