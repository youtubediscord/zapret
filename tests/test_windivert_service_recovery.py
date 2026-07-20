import unittest
import inspect
from pathlib import Path
import tempfile
from unittest.mock import Mock, call, patch


class WinDivertServiceRecoveryTests(unittest.TestCase):
    def test_packaged_monkey_driver_is_accepted_as_windivert_file(self) -> None:
        from config import config as app_config
        from winws_runtime.health.winws_exit_diagnosis import _check_windivert_files

        with tempfile.TemporaryDirectory() as tmp_dir:
            exe_dir = Path(tmp_dir)
            (exe_dir / "WinDivert.dll").write_bytes(b"dll")
            (exe_dir / "Monkey64.sys").write_bytes(b"driver")

            with patch.object(app_config, "EXE_FOLDER", str(exe_dir)):
                self.assertEqual(_check_windivert_files(), [])

            (exe_dir / "Monkey64.sys").unlink()
            with patch.object(app_config, "EXE_FOLDER", str(exe_dir)):
                missing = _check_windivert_files()

        self.assertEqual(
            missing,
            ["драйвер WinDivert (Monkey64.sys или WinDivert64.sys)"],
        )

    def test_detailed_diagnosis_explains_windows_and_process_codes(self) -> None:
        from winws_runtime.health.winws_exit_diagnosis import (
            WinDivertDiagnosis,
            format_winws_exit_diagnosis,
        )

        diagnosis = WinDivertDiagnosis(
            cause="Служба драйвера WinDivert (Monkey) отключена в системе",
            solution="Выполните аварийную очистку драйвера и повторите запуск",
            exit_code=34,
            win32_error=1058,
        )

        message = format_winws_exit_diagnosis(diagnosis, exe_name="winws2")

        self.assertIn("Найдена причина", message)
        self.assertIn("код ошибки Windows 1058", message)
        self.assertIn("код завершения процесса 34", message)
        self.assertIn("Что сделать", message)

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
            patch.object(service_manager, "stop_and_delete_service_sc_fallback", return_value=False),
            patch.object(service_manager.time, "sleep"),
        ):
            removed = service_manager.stop_and_delete_service("Monkey", retry_count=1)

        self.assertFalse(removed)
        service_exists.assert_called_with("Monkey")

    def test_stop_and_delete_uses_sc_fallback_when_winapi_leaves_service_visible(self) -> None:
        from utils import service_manager

        with (
            patch.object(service_manager, "stop_service", return_value=True),
            patch.object(service_manager, "delete_service", return_value=True),
            patch.object(service_manager, "service_exists", return_value=True),
            patch.object(service_manager, "stop_and_delete_service_sc_fallback", return_value=True) as fallback,
            patch.object(service_manager.time, "sleep"),
        ):
            removed = service_manager.stop_and_delete_service("Monkey", retry_count=1)

        self.assertTrue(removed)
        fallback.assert_called_once_with("Monkey")

    def test_stop_and_delete_uses_fallback_when_registry_key_survives_delete(self) -> None:
        from utils import service_manager

        with (
            patch.object(service_manager, "stop_service", return_value=True),
            patch.object(service_manager, "delete_service", return_value=True),
            patch.object(service_manager, "service_exists", return_value=False),
            patch.object(service_manager, "service_registry_exists", return_value=True),
            patch.object(service_manager, "stop_and_delete_service_sc_fallback", return_value=True) as fallback,
            patch.object(service_manager.time, "sleep"),
        ):
            removed = service_manager.stop_and_delete_service("Monkey", retry_count=1)

        self.assertTrue(removed)
        fallback.assert_called_once_with("Monkey")

    def test_sc_fallback_deletes_stopped_service_registry_tree_when_scm_keeps_entry(self) -> None:
        from utils import service_manager

        completed = Mock(returncode=0, stdout="", stderr="")

        with (
            patch.object(service_manager.subprocess, "run", return_value=completed) as run,
            patch.object(service_manager, "service_exists", return_value=True),
            patch.object(service_manager, "service_registry_exists", return_value=True),
            patch.object(service_manager, "stop_and_delete_service_pywin32_fallback", return_value=False),
            patch.object(service_manager, "delete_stopped_service_registry_tree", return_value=True) as delete_registry,
            patch.object(service_manager.time, "time", side_effect=[0, 3, 0, 3, 0, 3]),
            patch.object(service_manager.time, "sleep"),
        ):
            removed = service_manager.stop_and_delete_service_sc_fallback("Monkey")

        self.assertFalse(removed)
        self.assertEqual(run.call_count, 2)
        delete_registry.assert_called_once_with("Monkey")

    def test_sc_fallback_keeps_deleting_when_stop_leaves_registry_key(self) -> None:
        from utils import service_manager

        completed = Mock(returncode=0, stdout="", stderr="")

        with (
            patch.object(service_manager.subprocess, "run", return_value=completed) as run,
            patch.object(service_manager, "service_exists", return_value=False),
            patch.object(service_manager, "service_registry_exists", return_value=True),
            patch.object(service_manager, "stop_and_delete_service_pywin32_fallback", return_value=False),
            patch.object(service_manager, "delete_stopped_service_registry_tree", return_value=False),
            patch.object(service_manager.time, "time", side_effect=[0, 1, 1, 1, 1, 1]),
            patch.object(service_manager.time, "sleep"),
        ):
            removed = service_manager.stop_and_delete_service_sc_fallback("Monkey")

        self.assertFalse(removed)
        self.assertEqual(
            [call.args[0][:2] for call in run.call_args_list],
            [["sc.exe", "stop"], ["sc.exe", "delete"]],
        )

    def test_registry_tree_delete_skips_running_service(self) -> None:
        from utils import service_manager

        with (
            patch.object(service_manager, "get_service_state", return_value=service_manager.SERVICE_RUNNING),
            patch.object(service_manager, "_delete_registry_tree") as delete_tree,
        ):
            deleted = service_manager.delete_stopped_service_registry_tree("Monkey")

        self.assertFalse(deleted)
        delete_tree.assert_not_called()

    def test_service_state_query_uses_minimal_sc_manager_access(self) -> None:
        from utils import service_manager

        def query_status(_service, status_ptr) -> bool:
            status_ptr._obj.dwCurrentState = service_manager.SERVICE_RUNNING
            return True

        with (
            patch.object(service_manager, "advapi32", object()),
            patch.object(service_manager, "OpenSCManager", return_value=111) as open_sc_manager,
            patch.object(service_manager, "OpenService", return_value=222),
            patch.object(service_manager, "QueryServiceStatus", side_effect=query_status),
            patch.object(service_manager, "CloseServiceHandle"),
        ):
            state = service_manager.get_service_state("Monkey")

        self.assertEqual(state, service_manager.SERVICE_RUNNING)
        open_sc_manager.assert_called_once_with(None, None, 0x0001)

    def test_stop_service_uses_minimal_sc_manager_access(self) -> None:
        from utils import service_manager

        def query_status(_service, status_ptr) -> bool:
            status_ptr._obj.dwCurrentState = service_manager.SERVICE_STOPPED
            return True

        with (
            patch.object(service_manager, "advapi32", object()),
            patch.object(service_manager, "OpenSCManager", return_value=111) as open_sc_manager,
            patch.object(service_manager, "OpenService", return_value=222),
            patch.object(service_manager, "ControlService", Mock()),
            patch.object(service_manager, "QueryServiceStatus", side_effect=query_status),
            patch.object(service_manager, "CloseServiceHandle"),
        ):
            stopped = service_manager.stop_service("Monkey")

        self.assertTrue(stopped)
        open_sc_manager.assert_called_once_with(None, None, 0x0001)

    def test_delete_service_uses_minimal_sc_manager_access(self) -> None:
        from utils import service_manager

        def query_status(_service, status_ptr) -> bool:
            status_ptr._obj.dwCurrentState = service_manager.SERVICE_STOPPED
            return True

        with (
            patch.object(service_manager, "advapi32", object()),
            patch.object(service_manager, "OpenSCManager", return_value=111) as open_sc_manager,
            patch.object(service_manager, "OpenService", return_value=222),
            patch.object(service_manager, "QueryServiceStatus", side_effect=query_status),
            patch.object(service_manager, "DeleteService", return_value=True),
            patch.object(service_manager, "CloseServiceHandle"),
        ):
            deleted = service_manager.delete_service("Monkey")

        self.assertTrue(deleted)
        open_sc_manager.assert_called_once_with(None, None, 0x0001)

    def test_service_start_type_falls_back_to_registry_when_change_config_fails(self) -> None:
        import sys
        from utils import service_manager

        fake_winreg = Mock()
        fake_winreg.HKEY_LOCAL_MACHINE = object()
        fake_winreg.KEY_SET_VALUE = 0
        fake_winreg.REG_DWORD = 4
        fake_key = Mock()
        fake_key.__enter__ = Mock(return_value=fake_key)
        fake_key.__exit__ = Mock(return_value=False)
        fake_winreg.OpenKey.return_value = fake_key

        with (
            patch.object(service_manager, "advapi32", object()),
            patch.object(service_manager, "OpenSCManager", return_value=111),
            patch.object(service_manager, "OpenService", return_value=222),
            patch.object(service_manager, "ChangeServiceConfig", return_value=False),
            patch.object(service_manager, "CloseServiceHandle"),
            patch.dict(sys.modules, {"winreg": fake_winreg}),
        ):
            changed = service_manager.set_service_demand_start("Monkey")

        self.assertTrue(changed)
        fake_winreg.SetValueEx.assert_called_once_with(
            fake_key,
            "Start",
            0,
            fake_winreg.REG_DWORD,
            service_manager.SERVICE_DEMAND_START,
        )

    def test_empty_exit_34_is_treated_as_transient_windivert_1058(self) -> None:
        from winws_runtime.runners import runner_base

        class DummyRunner(runner_base.StrategyRunnerBase):
            def start_from_preset_file(self, preset_path: str, strategy_name: str = "Preset") -> bool:
                return True

            def switch_preset_file_fast(self, preset_path: str, strategy_name: str = "Preset", *, is_current=None) -> bool:
                return True

        with (
            patch.object(runner_base.os.path, "exists", return_value=True),
            patch(
                "winws_runtime.health.winws_exit_diagnosis._probe_service_disabled_cause",
                return_value=(
                    "WinDivert ещё не готов после предыдущего запуска или очистки",
                    "Повторите запуск после очистки",
                    None,
                ),
            ),
        ):
            runner = DummyRunner(r"C:\Zapret\Dev\exe\winws2.exe")
            retry = runner._should_retry_transient_windivert_service_error(
                "",
                34,
                retry_count=0,
                max_retry_count=1,
            )

        self.assertTrue(retry)

    def test_windivert_error_after_lua_header_is_reported_as_service_problem(self) -> None:
        from winws_runtime.health import process_health_check, winws_exit_diagnosis

        stderr = "\n".join(
            (
                "github version v1.0.1 lua_compat_ver 6",
                "Loading hostlist /lists/youtube.txt",
                "windivert: error opening filter: The service cannot be started, either because it is disabled or because it has no enabled devices associated with it.",
            )
        )

        with patch.object(
            winws_exit_diagnosis,
            "_probe_service_disabled_cause",
            return_value=("WinDivert service disabled", "Restore service", None),
        ):
            diagnosis = process_health_check.diagnose_winws_exit(87, stderr)

        self.assertIsNotNone(diagnosis)
        self.assertEqual(diagnosis.win32_error, 1058)
        self.assertEqual(diagnosis.cause, "WinDivert service disabled")

    def test_runner_runs_safe_windivert_autofix_once_after_failed_spawn(self) -> None:
        from winws_runtime.health.process_health_check import WinDivertDiagnosis
        from winws_runtime.runners import runner_base

        class DummyRunner(runner_base.StrategyRunnerBase):
            def start_from_preset_file(self, preset_path: str, strategy_name: str = "Preset") -> bool:
                return True

            def switch_preset_file_fast(self, preset_path: str, strategy_name: str = "Preset", *, is_current=None) -> bool:
                return True

        diagnosis = WinDivertDiagnosis(
            cause="Служба Base Filtering Engine (BFE) отключена",
            solution="Включите BFE",
            auto_fix="enable_bfe",
            exit_code=1068,
            win32_error=1068,
        )

        with (
            patch.object(runner_base.os.path, "exists", return_value=True),
            patch.object(runner_base, "diagnose_winws_exit", return_value=diagnosis),
            patch.object(runner_base, "execute_windivert_auto_fix", return_value=(True, "BFE запущена")) as auto_fix,
        ):
            runner = DummyRunner(r"C:\Zapret\Dev\exe\winws2.exe")
            recovered = runner._maybe_run_windivert_auto_fix_after_failed_spawn(
                "dependency service failed",
                1068,
                retry_count=0,
            )

        self.assertTrue(recovered)
        auto_fix.assert_called_once_with("enable_bfe")

    def test_runner_does_not_autofix_same_failure_twice(self) -> None:
        from winws_runtime.health.process_health_check import WinDivertDiagnosis
        from winws_runtime.runners import runner_base

        class DummyRunner(runner_base.StrategyRunnerBase):
            def start_from_preset_file(self, preset_path: str, strategy_name: str = "Preset") -> bool:
                return True

            def switch_preset_file_fast(self, preset_path: str, strategy_name: str = "Preset", *, is_current=None) -> bool:
                return True

        diagnosis = WinDivertDiagnosis(
            cause="Служба Base Filtering Engine (BFE) отключена",
            solution="Включите BFE",
            auto_fix="enable_bfe",
            exit_code=1068,
            win32_error=1068,
        )

        with (
            patch.object(runner_base.os.path, "exists", return_value=True),
            patch.object(runner_base, "diagnose_winws_exit", return_value=diagnosis),
            patch.object(runner_base, "execute_windivert_auto_fix", return_value=(True, "BFE запущена")) as auto_fix,
        ):
            runner = DummyRunner(r"C:\Zapret\Dev\exe\winws2.exe")
            recovered = runner._maybe_run_windivert_auto_fix_after_failed_spawn(
                "dependency service failed",
                1068,
                retry_count=1,
            )

        self.assertFalse(recovered)
        auto_fix.assert_not_called()

    def test_winws2_retries_after_successful_windivert_autofix(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner
        import winws_runtime.runners.zapret2_runner as zapret2_runner

        runner = object.__new__(Winws2StrategyRunner)
        runner._last_spawn_exit_code = 1068
        runner._last_spawn_stderr = "dependency service failed"
        runner._should_retry_transient_windivert_service_error = Mock(return_value=False)
        runner._is_windivert_system_error = Mock(return_value=True)
        runner._is_windivert_conflict_error = Mock(return_value=False)
        runner._maybe_run_windivert_auto_fix_after_failed_spawn = Mock(return_value=True)
        runner._start_from_preset_file_locked = Mock(return_value=True)

        with patch.object(
            zapret2_runner,
            "find_stale_windivert_delete_pending_services_runtime",
            return_value=[],
        ):
            retried = runner._maybe_retry_after_failed_spawn_locked(
                "preset.txt",
                "Preset",
                cleanup_required=False,
                retry_count=0,
                stable_start_window_seconds=0.35,
            )

        self.assertTrue(retried)
        runner._maybe_run_windivert_auto_fix_after_failed_spawn.assert_called_once_with(
            "dependency service failed",
            1068,
            retry_count=0,
        )
        runner._start_from_preset_file_locked.assert_called_once_with(
            "preset.txt",
            "Preset",
            force_cleanup=True,
            retry_count=1,
            stable_start_window_seconds=0.35,
        )

    def test_winws1_retries_after_successful_windivert_autofix(self) -> None:
        from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

        runner = object.__new__(Winws1StrategyRunner)
        runner._last_spawn_exit_code = 1068
        runner._last_spawn_stderr = "dependency service failed"
        runner._should_retry_transient_windivert_service_error = Mock(return_value=False)
        runner._should_retry_unclassified_code_one = Mock(return_value=False)
        runner._is_windivert_system_error = Mock(return_value=True)
        runner._is_windivert_conflict_error = Mock(return_value=False)
        runner._maybe_run_windivert_auto_fix_after_failed_spawn = Mock(return_value=True)
        runner._start_from_preset_file_locked = Mock(return_value=True)

        retried = runner._maybe_retry_after_failed_spawn_locked(
            "preset.txt",
            "Preset",
            retry_count=0,
            max_retries=2,
            stable_start_window_seconds=0.35,
        )

        self.assertTrue(retried)
        runner._maybe_run_windivert_auto_fix_after_failed_spawn.assert_called_once_with(
            "dependency service failed",
            1068,
            retry_count=0,
        )
        runner._start_from_preset_file_locked.assert_called_once_with(
            "preset.txt",
            "Preset",
            retry_count=1,
            max_retries=2,
            stable_start_window_seconds=0.35,
        )

    def test_generic_service_disabled_does_not_blame_secure_boot_without_signature_error(self) -> None:
        from winws_runtime.health import process_health_check, winws_exit_diagnosis

        stderr = (
            "windivert: error opening filter: The service cannot be started, "
            "either because it is disabled or because it has no enabled devices associated with it."
        )

        with (
            patch.object(winws_exit_diagnosis, "_check_windivert_files", return_value=[]),
            patch.object(winws_exit_diagnosis, "_check_bfe_service", return_value=True),
            patch.object(winws_exit_diagnosis, "_check_secure_boot", return_value=True),
            patch.object(winws_exit_diagnosis, "_find_disabled_windivert_driver_service", return_value=None),
            patch.object(winws_exit_diagnosis, "_detect_active_antivirus", return_value=None),
            patch.object(winws_exit_diagnosis, "_check_network_adapters", return_value=True),
        ):
            diagnosis = process_health_check.diagnose_winws_exit(34, stderr)

        self.assertIsNotNone(diagnosis)
        self.assertEqual(diagnosis.win32_error, 1058)
        self.assertNotIn("Secure Boot блокирует", diagnosis.cause)
        self.assertIn("WinDivert не может запустить службу драйвера", diagnosis.cause)

    def test_lua_compat_mismatch_is_reported_as_version_mismatch(self) -> None:
        from winws_runtime.health import process_health_check

        stderr = "\n".join(
            (
                "github version v1.0.1 lua_compat_ver 6",
                "Error: LUA ERROR: /lua/zapret-lib.lua:4: Incompatible NFQWS2_COMPAT_VER. Use pktws and lua scripts from the same release !",
            )
        )

        diagnosis = process_health_check.diagnose_winws_exit(87, stderr)

        self.assertIsNotNone(diagnosis)
        self.assertEqual(diagnosis.cause, "winws2.exe и Lua-скрипты от разных версий")
        self.assertIn("Обновите папку lua", diagnosis.solution)

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
            patch.object(system_ops, "_is_kaspersky_present_safe", return_value=False),
            patch.object(system_ops, "force_kill_all_winws_processes", return_value=True),
            patch.object(system_ops, "unload_known_windivert_drivers_runtime", return_value=True),
            patch.object(system_ops, "stop_and_delete_runtime_services", return_value=False),
            patch.object(system_ops, "clear_stopped_windivert_delete_flags_runtime") as clear_delete_flag,
            patch.object(system_ops, "restore_known_windivert_services_demand_start_runtime") as restore_start,
            patch.object(system_ops, "wait_for_windivert_cleanup_settle_runtime", return_value=True),
            patch.object(system_ops.time, "sleep"),
            patch.object(system_ops, "log"),
        ):
            system_ops.aggressive_windivert_cleanup_runtime()

        clear_delete_flag.assert_called_once_with()
        restore_start.assert_called_once_with()

    def test_aggressive_cleanup_retries_delete_after_clearing_stale_service_flags(self) -> None:
        from winws_runtime.runtime import system_ops

        with (
            patch.object(system_ops, "_is_kaspersky_present_safe", return_value=False),
            patch.object(system_ops, "force_kill_all_winws_processes", return_value=True),
            patch.object(system_ops, "unload_known_windivert_drivers_runtime", return_value=True),
            patch.object(
                system_ops,
                "stop_and_delete_runtime_services",
                side_effect=[False, True],
            ) as stop_and_delete,
            patch.object(system_ops, "clear_stopped_windivert_delete_flags_runtime", return_value=True),
            patch.object(system_ops, "restore_known_windivert_services_demand_start_runtime", return_value=True),
            patch.object(system_ops, "wait_for_windivert_cleanup_settle_runtime", return_value=True) as wait_cleanup,
            patch.object(system_ops.time, "sleep"),
            patch.object(system_ops, "log"),
        ):
            cleaned = system_ops.aggressive_windivert_cleanup_runtime()

        self.assertTrue(cleaned)
        self.assertEqual(stop_and_delete.call_count, 2)
        stop_and_delete.assert_any_call(retry_count=3)
        stop_and_delete.assert_any_call(retry_count=2)
        # Pre-unload settle (retry_cleanup=False) + финальный settle (retry_cleanup=True)
        self.assertEqual(
            wait_cleanup.call_args_list,
            [
                call(max_wait_seconds=5.0, poll_interval=0.25, retry_cleanup=False),
                call(max_wait_seconds=5.0, poll_interval=0.25, retry_cleanup=True),
            ],
        )

    def test_clear_stopped_windivert_delete_flags_skips_running_services(self) -> None:
        from utils import service_manager
        from winws_runtime.runtime import system_ops

        with (
            patch.object(
                system_ops,
                "get_known_windivert_service_states_runtime",
                return_value={
                    "WinDivert": system_ops._SERVICE_RUNNING,
                    "Monkey": system_ops._SERVICE_STOPPED,
                },
            ),
            patch.object(
                system_ops,
                "get_known_windivert_service_registry_flags_runtime",
                return_value={
                    "WinDivert": {"start": system_ops._SERVICE_DISABLED, "delete_flag": 1},
                    "Monkey": {"start": system_ops._SERVICE_DISABLED, "delete_flag": 1},
                },
            ),
            patch.object(service_manager, "clear_service_delete_flag", return_value=True) as clear_flag,
        ):
            cleared = system_ops.clear_stopped_windivert_delete_flags_runtime()

        self.assertTrue(cleared)
        clear_flag.assert_called_once_with("Monkey")

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
            patch.object(
                system_ops,
                "find_stale_windivert_delete_pending_services_runtime",
                return_value=[],
            ),
            patch.object(
                system_ops,
                "find_blocking_windivert_registry_services_runtime",
                return_value=["Monkey"],
            ),
            patch.object(system_ops, "restore_known_windivert_services_demand_start_runtime") as restore_start,
            patch.object(system_ops.time, "sleep"),
            patch.object(system_ops, "log"),
        ):
            result = system_ops.wait_for_windivert_spawn_ready_runtime(
                max_wait_seconds=0.01,
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
                "find_stale_windivert_delete_pending_services_runtime",
                return_value=[],
            ),
            patch.object(
                system_ops,
                "find_blocking_windivert_registry_services_runtime",
                return_value=["Monkey"],
            ),
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

    def test_probe_uses_no_install_for_network_readiness(self) -> None:
        from winws_runtime.runtime import system_ops

        with (
            patch.object(system_ops, "_load_windivert_dll_runtime", return_value=object()),
            patch.object(
                system_ops,
                "_probe_windivert_open_runtime",
                side_effect=[(False, 1060), (False, 1060)],
            ) as open_probe,
        ):
            result = system_ops.probe_windivert_state_runtime()

        self.assertFalse(result.installed)
        self.assertFalse(result.ready)
        network_flags = open_probe.call_args_list[1].kwargs["flags"]
        self.assertTrue(network_flags & system_ops._WINDIVERT_FLAG_NO_INSTALL)

    def test_spawn_readiness_allows_winws_when_1058_probe_has_clean_registry(self) -> None:
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
                return_value=True,
            ) as restore_start,
            patch.object(
                system_ops,
                "find_stale_windivert_delete_pending_services_runtime",
                return_value=[],
            ),
            patch.object(
                system_ops,
                "unload_known_windivert_drivers_runtime",
                return_value=True,
            ),
            patch.object(
                system_ops,
                "find_blocking_windivert_registry_services_runtime",
                return_value=[],
            ),
            patch.object(system_ops.time, "sleep"),
            patch.object(system_ops, "log") as log,
        ):
            result = system_ops.wait_for_windivert_spawn_ready_runtime(
                max_wait_seconds=1.0,
                poll_interval=0.001,
            )

        self.assertTrue(result.ready)
        self.assertEqual(result.stage, "network_open_probe_bypassed:registry_clean")
        restore_start.assert_not_called()
        self.assertTrue(
            any("allowing winws2" in call.args[0] for call in log.call_args_list)
        )

    def test_spawn_readiness_allows_winws_to_install_driver_when_service_is_absent(self) -> None:
        from winws_runtime.runtime import system_ops

        missing_driver_probe = system_ops.WinDivertRuntimeProbeResult(
            installed=False,
            ready=False,
            error_code=1060,
            stage="network_open",
        )

        with (
            patch.object(system_ops, "probe_windivert_state_runtime", return_value=missing_driver_probe),
            patch.object(
                system_ops,
                "find_stale_windivert_delete_pending_services_runtime",
                return_value=[],
            ),
            patch.object(
                system_ops,
                "unload_known_windivert_drivers_runtime",
                return_value=True,
            ),
            patch.object(
                system_ops,
                "find_blocking_windivert_registry_services_runtime",
                return_value=[],
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
        self.assertEqual(result.stage, "network_open_probe_bypassed:registry_clean")
        restore_start.assert_not_called()

    def test_spawn_readiness_unloads_zombie_driver_before_registry_clean_bypass(self) -> None:
        """Зомби-драйвер после недавнего stop: registry чист, но open падает.

        Один unload + повторная проба должны дать честный ready вместо bypass,
        чтобы первый запуск winws2 не умирал с 0xC0000142.
        """
        from winws_runtime.runtime import system_ops

        zombie_probe = system_ops.WinDivertRuntimeProbeResult(
            installed=False,
            ready=False,
            error_code=1060,
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
                side_effect=[zombie_probe, ready_probe],
            ),
            patch.object(
                system_ops,
                "find_stale_windivert_delete_pending_services_runtime",
                return_value=[],
            ),
            patch.object(
                system_ops,
                "unload_known_windivert_drivers_runtime",
                return_value=True,
            ) as unload_drivers,
            patch.object(
                system_ops,
                "find_blocking_windivert_registry_services_runtime",
                return_value=[],
            ),
            patch.object(system_ops.time, "sleep"),
            patch.object(system_ops, "log"),
        ):
            result = system_ops.wait_for_windivert_spawn_ready_runtime(
                max_wait_seconds=1.0,
                poll_interval=0.001,
            )

        self.assertTrue(result.ready)
        self.assertEqual(result.stage, "network_open")
        unload_drivers.assert_called_once_with()

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

    def test_disabled_delete_pending_service_is_stale_when_state_cannot_be_read(self) -> None:
        from winws_runtime.runtime import system_ops

        with (
            patch.object(
                system_ops,
                "get_known_windivert_service_states_runtime",
                return_value={"Monkey": None},
            ),
            patch.object(
                system_ops,
                "get_known_windivert_service_registry_flags_runtime",
                return_value={"Monkey": {"start": system_ops._SERVICE_DISABLED, "delete_flag": 1}},
            ),
        ):
            stale_services = system_ops.find_stale_windivert_delete_pending_services_runtime()

        self.assertEqual(stale_services, ["Monkey"])

    def test_stop_pending_disabled_delete_pending_windivert_is_detected_as_stale(self) -> None:
        from winws_runtime.runtime import system_ops

        with (
            patch.object(
                system_ops,
                "get_known_windivert_service_states_runtime",
                return_value={
                    "WinDivert": system_ops._SERVICE_STOP_PENDING,
                    "Monkey": system_ops._SERVICE_RUNNING,
                },
            ),
            patch.object(
                system_ops,
                "get_known_windivert_service_registry_flags_runtime",
                return_value={
                    "WinDivert": {"start": system_ops._SERVICE_DISABLED, "delete_flag": 1},
                    "Monkey": {"start": system_ops._SERVICE_DISABLED, "delete_flag": 1},
                },
            ),
        ):
            stale_services = system_ops.find_stale_windivert_delete_pending_services_runtime()

        self.assertEqual(stale_services, ["WinDivert", "Monkey"])

    def test_stop_and_delete_runtime_services_checks_every_known_windivert_service(self) -> None:
        from utils import service_manager
        from winws_runtime.runtime import system_ops

        stopped_services: list[str] = []

        def stop_and_delete(service_name: str, *, retry_count: int = 3) -> bool:
            stopped_services.append(f"{service_name}:{retry_count}")
            return True

        with patch.object(service_manager, "stop_and_delete_service", side_effect=stop_and_delete):
            removed = system_ops.stop_and_delete_runtime_services(retry_count=7)

        self.assertTrue(removed)
        self.assertEqual(
            stopped_services,
            [f"{service_name}:7" for service_name in system_ops._KNOWN_WINDIVERT_SERVICES],
        )

    def test_spawn_readiness_allows_delete_pending_monkey_for_fast_restart(self) -> None:
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
            patch.object(system_ops.time, "sleep") as sleep,
            patch.object(system_ops, "log"),
        ):
            result = system_ops.wait_for_windivert_spawn_ready_runtime(
                max_wait_seconds=1.0,
                poll_interval=0.001,
            )

        self.assertTrue(result.ready)
        self.assertEqual(result.error_code, system_ops._ERROR_SERVICE_MARKED_FOR_DELETE)
        self.assertEqual(result.stage, "stale_delete_pending_bypassed:Monkey")
        sleep.assert_not_called()

    def test_runner_treats_access_denied_readiness_as_transient_cleanup_case(self) -> None:
        from winws_runtime.health import windivert_diagnostics
        from winws_runtime.runners import runner_base
        from winws_runtime.runtime import system_ops
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
            patch.object(system_ops, "wait_for_windivert_spawn_ready_runtime", return_value=ready_probe)
            as wait_ready,
            patch.object(DummyRunner, "_aggressive_windivert_cleanup") as cleanup,
            patch.object(DummyRunner, "_wait_after_aggressive_windivert_cleanup"),
        ):
            runner = DummyRunner(r"C:\Zapret\Dev\exe\winws2.exe")
            result = windivert_diagnostics.retry_windivert_spawn_readiness_after_recovery(
                blocked_probe,
                aggressive_cleanup=runner._aggressive_windivert_cleanup,
                wait_after_cleanup=runner._wait_after_aggressive_windivert_cleanup,
            )

        self.assertTrue(result.ready)
        cleanup.assert_called_once_with()
        wait_ready.assert_called_once()

    def test_runner_treats_delete_pending_monkey_readiness_as_transient_cleanup_case(self) -> None:
        from winws_runtime.health import windivert_diagnostics
        from winws_runtime.runners import runner_base
        from winws_runtime.runtime import system_ops
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
            patch.object(system_ops, "wait_for_windivert_spawn_ready_runtime", return_value=ready_probe)
            as wait_ready,
            patch.object(DummyRunner, "_aggressive_windivert_cleanup") as cleanup,
            patch.object(DummyRunner, "_wait_after_aggressive_windivert_cleanup"),
        ):
            runner = DummyRunner(r"C:\Zapret\Dev\exe\winws2.exe")
            result = windivert_diagnostics.retry_windivert_spawn_readiness_after_recovery(
                blocked_probe,
                aggressive_cleanup=runner._aggressive_windivert_cleanup,
                wait_after_cleanup=runner._wait_after_aggressive_windivert_cleanup,
            )

        self.assertTrue(result.ready)
        cleanup.assert_called_once_with()
        wait_ready.assert_called_once()

    def test_winws2_runner_does_not_retry_stale_service_cleanup_for_invalid_parameter_exit(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner
        import winws_runtime.runners.zapret2_runner as zapret2_runner

        runner = object.__new__(Winws2StrategyRunner)
        runner._last_spawn_exit_code = 87
        runner._last_spawn_stderr = ""
        runner._should_retry_transient_windivert_service_error = Mock(return_value=False)
        runner._is_windivert_system_error = Mock(return_value=False)
        runner._is_windivert_conflict_error = Mock(return_value=False)
        runner._aggressive_windivert_cleanup = Mock()
        runner._start_from_preset_file_locked = Mock(return_value=True)

        with patch.object(
            zapret2_runner,
            "find_stale_windivert_delete_pending_services_runtime",
            return_value=["Monkey"],
        ):
            retried = runner._maybe_retry_after_failed_spawn_locked(
                "preset.txt",
                "Preset",
                cleanup_required=True,
                retry_count=0,
            )

        self.assertFalse(retried)
        runner._start_from_preset_file_locked.assert_not_called()
        runner._aggressive_windivert_cleanup.assert_called_once_with()

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
