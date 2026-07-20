from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import SimpleNamespace
import threading
import tempfile
import unittest
from unittest.mock import Mock, patch


class Winws2PresetSwitchTests(unittest.TestCase):
    def test_preset_cache_key_changes_when_same_size_file_content_changes(self) -> None:
        from winws_runtime.runners.preset_runner_support import preset_cache_key

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            fixed_ns = 1_779_890_000_000_000_000

            preset_path.write_text("--wf-tcp-out=443\n", encoding="utf-8")
            os.utime(preset_path, ns=(fixed_ns, fixed_ns))
            first_key = preset_cache_key(str(preset_path))

            preset_path.write_text("--wf-udp-out=443\n", encoding="utf-8")
            os.utime(preset_path, ns=(fixed_ns, fixed_ns))
            second_key = preset_cache_key(str(preset_path))

            self.assertNotEqual(first_key, second_key)

    def test_winws2_compile_rebuilds_at_config_when_same_size_content_changes(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            preset_path = root / "selected.txt"
            fixed_ns = 1_779_890_000_000_000_000

            runner = object.__new__(Winws2StrategyRunner)
            runner.work_dir = str(root)
            runner.lists_dir = str(root / "lists")
            runner.bin_dir = str(root / "bin")
            runner._state_lock = threading.RLock()
            runner._prepared_preset_cache = {}

            preset_path.write_text("--wf-tcp-out=443\n", encoding="utf-8")
            os.utime(preset_path, ns=(fixed_ns, fixed_ns))
            first_artifact = runner._compile_preset_artifact(str(preset_path))
            first_config = Path(first_artifact.launch_args[0][1:]).read_text(encoding="utf-8")

            preset_path.write_text("--wf-udp-out=443\n", encoding="utf-8")
            os.utime(preset_path, ns=(fixed_ns, fixed_ns))
            second_artifact = runner._compile_preset_artifact(str(preset_path))
            second_config = Path(second_artifact.launch_args[0][1:]).read_text(encoding="utf-8")

            self.assertIn("--wf-tcp-out=443", first_config)
            self.assertIn("--wf-udp-out=443", second_config)
            self.assertNotEqual(first_artifact.cache_key, second_artifact.cache_key)
            self.assertNotEqual(first_config, second_config)

    def test_winws2_at_config_prunes_old_cached_files(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            preset_path = root / "selected.txt"
            preset_path.write_text("--wf-tcp-out=443\n", encoding="utf-8")
            config_dir = root / "tmp" / "winws2_at_config"
            config_dir.mkdir(parents=True)
            for index in range(70):
                stale = config_dir / f"winws2_at_stale_{index:02d}.txt"
                stale.write_text("--old\n", encoding="utf-8")
                os.utime(stale, (index, index))

            runner = object.__new__(Winws2StrategyRunner)
            runner.work_dir = str(root)
            runner.lists_dir = str(root / "lists")
            runner.bin_dir = str(root / "bin")
            runner._state_lock = threading.RLock()
            runner._prepared_preset_cache = {}

            artifact = runner._compile_preset_artifact(str(preset_path))
            active_config = Path(artifact.launch_args[0][1:])

            self.assertTrue(active_config.exists())
            self.assertLessEqual(len(list(config_dir.glob("winws2_at_*.txt"))), 64)
            self.assertFalse((config_dir / "winws2_at_stale_00.txt").exists())

    def test_winws1_at_config_prunes_old_cached_files(self) -> None:
        from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            preset_path = root / "selected.txt"
            preset_path.write_text("--wf-tcp=443\n", encoding="utf-8")
            config_dir = root / "tmp" / "winws1_at_config"
            config_dir.mkdir(parents=True)
            for index in range(70):
                stale = config_dir / f"winws1_at_stale_{index:02d}.txt"
                stale.write_text("--old\n", encoding="utf-8")
                os.utime(stale, (index, index))

            runner = object.__new__(Winws1StrategyRunner)
            runner.work_dir = str(root)
            runner.lists_dir = str(root / "lists")
            runner.bin_dir = str(root / "bin")
            runner._state_lock = threading.RLock()
            runner._prepared_preset_cache = {}

            artifact = runner._compile_preset_artifact(str(preset_path))
            active_config = Path(artifact.launch_args[0][1:])

            self.assertTrue(active_config.exists())
            self.assertLessEqual(len(list(config_dir.glob("winws1_at_*.txt"))), 64)
            self.assertFalse((config_dir / "winws1_at_stale_00.txt").exists())

    def test_winws1_fast_switch_skips_stale_request_before_stopping_process(self) -> None:
        from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp=443\n", encoding="utf-8")

            runner = object.__new__(Winws1StrategyRunner)
            runner._state_lock = threading.RLock()
            runner._set_last_error = Mock()
            runner._compile_preset_artifact = Mock(
                return_value=SimpleNamespace(validation_ok=True, validation_report="")
            )
            runner._refresh_artifact_if_source_changed_locked = Mock(
                side_effect=AssertionError("stale winws1 switch must not refresh after compile")
            )
            runner.running_process = object()
            runner.is_running = Mock(return_value=True)
            runner._stop_process_only_locked = Mock(
                side_effect=AssertionError("stale winws1 switch must not stop current process")
            )

            self.assertTrue(
                runner.switch_preset_file_fast(
                    str(preset_path),
                    "Selected",
                    is_current=lambda: False,
                )
            )

            runner._compile_preset_artifact.assert_called_once_with(str(preset_path))
            runner._refresh_artifact_if_source_changed_locked.assert_not_called()
            runner._stop_process_only_locked.assert_not_called()

    def test_winws2_fast_switch_skips_stale_request_before_spawning_process(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp-out=443\n", encoding="utf-8")

            artifact = SimpleNamespace(validation_ok=True, validation_report="")
            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = threading.RLock()
            runner._set_last_error = Mock()
            runner._compile_preset_artifact = Mock(return_value=artifact)
            runner._refresh_artifact_if_source_changed_locked = Mock(return_value=artifact)
            runner.running_process = object()
            runner.is_running = Mock(return_value=True)
            runner._artifact_for_handoff_locked = Mock(
                side_effect=AssertionError("stale winws2 switch must not prepare handoff")
            )
            runner._spawn_process_locked = Mock(
                side_effect=AssertionError("stale winws2 switch must not spawn process")
            )
            runner._stop_previous_process_after_handoff_locked = Mock()

            self.assertTrue(
                runner.switch_preset_file_fast(
                    str(preset_path),
                    "Selected",
                    is_current=lambda: False,
                )
            )

            runner._compile_preset_artifact.assert_called_once_with(str(preset_path))
            runner._refresh_artifact_if_source_changed_locked.assert_called_once_with(artifact)
            runner._artifact_for_handoff_locked.assert_not_called()
            runner._spawn_process_locked.assert_not_called()
            runner._stop_previous_process_after_handoff_locked.assert_not_called()

    def test_same_filter_exit_message_is_retryable_conflict(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        runner = object.__new__(Winws2StrategyRunner)

        self.assertTrue(
            runner._is_windivert_conflict_error(
                "Error: A copy of winws2 is already running with the same filter",
                1,
            )
        )

    def test_fast_switch_uses_windivert_error_instead_of_version_header(self) -> None:
        from winws_runtime.health.winws_exit_diagnosis import WinDivertDiagnosis
        from winws_runtime.runners import zapret2_runner
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        runner = object.__new__(Winws2StrategyRunner)
        runner.last_error = None
        output = "\n".join(
            (
                "github version v1.0.1 lua_compat_ver 6",
                "Loading hostlist /lists/youtube.txt",
                "windivert: error opening filter: The service cannot be started, "
                "either because it is disabled or because it has no enabled devices associated with it.",
            )
        )
        diagnosis = WinDivertDiagnosis(
            cause="Служба драйвера WinDivert (Monkey) отключена в системе",
            solution="Выполните аварийную очистку драйвера и повторите запуск",
            exit_code=34,
            win32_error=1058,
        )

        with (
            patch.object(zapret2_runner, "diagnose_winws_exit", return_value=diagnosis),
            patch.object(zapret2_runner, "log"),
        ):
            runner._set_spawn_exit_error(34, output)

        self.assertNotIn("github version", str(runner.last_error))
        self.assertIn("WinDivert", str(runner.last_error))
        self.assertIn("код ошибки Windows 1058", str(runner.last_error))
        self.assertIn("код завершения процесса 34", str(runner.last_error))

    def test_runner_state_allows_handoff_start_from_running(self) -> None:
        from winws_runtime.runners.preset_runner_support import PresetRunnerState, PresetRunnerStateMachine

        machine = PresetRunnerStateMachine()
        machine.transition(PresetRunnerState.STARTING, preset_path="old.txt", strategy_name="Old")
        machine.transition(PresetRunnerState.RUNNING, preset_path="old.txt", strategy_name="Old", pid=111)

        snapshot = machine.transition(PresetRunnerState.STARTING, preset_path="new.txt", strategy_name="New")

        self.assertEqual(snapshot.state, PresetRunnerState.STARTING)
        self.assertEqual(snapshot.preset_path, "new.txt")

    def test_winws2_launch_logs_exact_command_and_at_config(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "winws2_at_test.txt"
            config_path.write_text("--wf-tcp-out=443\n", encoding="utf-8")
            preset_path = Path(tmp_dir) / "Default v1 (game filter).txt"
            preset_path.write_text("--wf-tcp-out=443\n", encoding="utf-8")

            runner = object.__new__(Winws2StrategyRunner)
            runner.winws_exe = str(Path(tmp_dir) / "winws2.exe")
            runner.work_dir = tmp_dir

            artifact = SimpleNamespace(
                launch_args=(f"@{config_path}",),
                preset_path=str(preset_path),
            )

            with patch("winws_runtime.runners.zapret2_runner.log") as log_mock:
                runner._log_winws2_launch_command(
                    cmd=[runner.winws_exe, *artifact.launch_args],
                    artifact=artifact,
                )

            messages = [str(call.args[0]) for call in log_mock.call_args_list]
            self.assertTrue(any("Winws2 launch command:" in message for message in messages))
            self.assertTrue(any(str(config_path) in message for message in messages))
            self.assertTrue(any("Winws2 launch cwd:" in message for message in messages))
            self.assertTrue(any("Winws2 launch @config:" in message for message in messages))
            self.assertTrue(any("sha1=" in message for message in messages))
            self.assertTrue(any(str(preset_path) in message for message in messages))

    def test_runner_file_watcher_restart_path_is_removed(self) -> None:
        from winws_runtime.runners import preset_runner_support, zapret1_runner, zapret2_runner

        combined_source = "\n".join(
            (
                inspect.getsource(zapret1_runner),
                inspect.getsource(zapret2_runner),
                inspect.getsource(preset_runner_support),
            )
        )

        self.assertNotIn("ConfigFileWatcher", combined_source)
        self.assertNotIn("_on_config_changed", combined_source)

    def test_winws2_fast_switch_starts_new_process_before_stopping_old(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp-out=80", encoding="utf-8")
            calls: list[str] = []

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = threading.RLock()
            runner.work_dir = tmp_dir
            runner.running_process = Mock(pid=111)
            runner.current_launch_label = "Old"
            runner._preset_file_path = "old.txt"
            runner.current_strategy_args = ["--wf-tcp-out=443"]
            runner._set_last_error = Mock()
            runner.is_running = Mock(return_value=True)
            runner._compile_preset_artifact = Mock(
                return_value=SimpleNamespace(
                    validation_ok=True,
                    validation_report="",
                    preset_path=str(preset_path),
                    cache_key=None,
                    normalized_text="--wf-tcp-out=80\n",
                    launch_args=("--wf-tcp-out=80",),
                )
            )
            runner._spawn_process_locked = Mock(side_effect=lambda *_args, **_kwargs: calls.append("spawn") or True)
            runner._stop_previous_process_after_handoff_locked = Mock(
                side_effect=lambda *_args, **_kwargs: calls.append("stop_old")
            )
            runner._stop_process_only_locked = Mock()
            runner._perform_standard_windivert_cleanup = Mock()
            runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)

            self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            self.assertEqual(calls, ["spawn", "stop_old"])
            runner._stop_process_only_locked.assert_not_called()
            runner._perform_standard_windivert_cleanup.assert_not_called()
            runner._ensure_windivert_ready_before_spawn.assert_not_called()
            runner._spawn_process_locked.assert_called_once()
            spawned_artifact = runner._spawn_process_locked.call_args.args[0]
            handoff_config = Path(str(spawned_artifact.launch_args[0])[1:]).read_text(encoding="utf-8")
            self.assertIn("--wf-tcp-out=80", handoff_config)
            self.assertIn("--wf-dup-check=0", handoff_config)

    def test_fast_switch_does_not_need_runner_file_watcher(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp-out=80", encoding="utf-8")

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = threading.RLock()
            runner.running_process = None
            runner._preset_file_path = ""
            runner._set_last_error = Mock()
            runner._compile_preset_artifact = Mock(
                return_value=SimpleNamespace(
                    validation_ok=True,
                    validation_report="",
                    preset_path=str(preset_path),
                    launch_args=("--wf-tcp-out=80",),
                )
            )
            runner._spawn_process_locked = Mock(return_value=True)
            runner._perform_standard_windivert_cleanup = Mock()
            runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)

            with patch("winws_runtime.runners.zapret2_runner.get_all_winws_process_pids", return_value=[]):
                self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

    def test_winws2_fast_switch_rebuilds_artifact_if_preset_changes_before_spawn(self) -> None:
        from winws_runtime.runners.preset_runner_support import preset_cache_key
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp-out=80", encoding="utf-8")

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = threading.RLock()
            runner.work_dir = tmp_dir
            runner.running_process = Mock()
            runner._preset_file_path = ""
            runner._set_last_error = Mock()
            runner._perform_standard_windivert_cleanup = Mock()
            runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)

            def compile_artifact(path: str):
                text = Path(path).read_text(encoding="utf-8")
                return SimpleNamespace(
                    validation_ok=True,
                    validation_report="",
                    preset_path=str(path),
                    cache_key=preset_cache_key(path),
                    normalized_text=text,
                    launch_args=(text.strip(),),
                )

            runner._compile_preset_artifact = Mock(side_effect=compile_artifact)

            runner.is_running = Mock(return_value=True)

            runner._spawn_process_locked = Mock(return_value=True)
            runner._stop_previous_process_after_handoff_locked = Mock()

            def refresh_artifact(artifact):
                preset_path.write_text("--wf-tcp-out=443", encoding="utf-8")
                return runner._compile_preset_artifact(str(preset_path))

            runner._refresh_artifact_if_source_changed_locked = Mock(side_effect=refresh_artifact)

            with patch("winws_runtime.runners.zapret2_runner.get_all_winws_process_pids", return_value=[]):
                self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            self.assertEqual(runner._compile_preset_artifact.call_count, 2)
            spawned_artifact = runner._spawn_process_locked.call_args.args[0]
            self.assertIn("--wf-tcp-out=443", spawned_artifact.normalized_text)
            self.assertIn("--wf-dup-check=0", spawned_artifact.normalized_text)

    def test_winws2_handoff_failure_keeps_old_process_running(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp-out=80", encoding="utf-8")
            old_process = Mock(pid=111)

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = threading.RLock()
            runner.work_dir = tmp_dir
            runner.running_process = old_process
            runner.current_launch_label = "Old"
            runner.current_strategy_args = ["--wf-tcp-out=443"]
            runner._preset_file_path = "old.txt"
            runner.last_error = None
            runner._last_spawn_exit_code = None
            runner._last_spawn_stderr = ""
            runner._set_last_error = Mock()
            runner.is_running = Mock(return_value=True)
            runner._compile_preset_artifact = Mock(
                return_value=SimpleNamespace(
                    validation_ok=True,
                    validation_report="",
                    preset_path=str(preset_path),
                    cache_key=None,
                    normalized_text="--wf-tcp-out=80\n",
                    launch_args=("--wf-tcp-out=80",),
                )
            )
            runner._spawn_process_locked = Mock(return_value=False)
            runner._stop_previous_process_after_handoff_locked = Mock()
            runner._stop_process_only_locked = Mock()
            runner._perform_standard_windivert_cleanup = Mock()

            self.assertFalse(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            self.assertIs(runner.running_process, old_process)
            self.assertEqual(runner.current_launch_label, "Old")
            self.assertEqual(runner._preset_file_path, "old.txt")
            runner._stop_previous_process_after_handoff_locked.assert_not_called()
            runner._stop_process_only_locked.assert_not_called()

    def test_fast_switch_retries_winws2_conflict_inside_switch_without_full_start_fallback(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp-out=80", encoding="utf-8")

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = threading.RLock()
            runner.running_process = None
            runner._preset_file_path = ""
            runner.last_error = None
            runner._last_spawn_exit_code = None
            runner._last_spawn_stderr = ""
            runner._set_last_error = Mock()
            runner._perform_standard_windivert_cleanup = Mock()
            runner._aggressive_windivert_cleanup = Mock()
            runner._wait_after_aggressive_windivert_cleanup = Mock()
            runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)
            runner._compile_preset_artifact = Mock(
                return_value=SimpleNamespace(
                    validation_ok=True,
                    validation_report="",
                    preset_path=str(preset_path),
                    launch_args=("--wf-tcp-out=80",),
                )
            )
            runner._start_from_preset_file_locked = Mock(return_value=True)

            def spawn_then_conflict_then_success(*_args, **_kwargs):
                if runner._spawn_process_locked.call_count == 1:
                    runner._last_spawn_exit_code = 1
                    runner._last_spawn_stderr = "A copy of winws2 is already running with the same filter"
                    return False
                return True

            runner._spawn_process_locked = Mock(side_effect=spawn_then_conflict_then_success)

            self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            self.assertEqual(runner._spawn_process_locked.call_count, 2)
            runner._start_from_preset_file_locked.assert_not_called()
            runner._aggressive_windivert_cleanup.assert_called_once()

    def test_fast_switch_retries_winws2_dll_init_failure_inside_switch(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp-out=80", encoding="utf-8")

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = threading.RLock()
            runner.running_process = None
            runner._preset_file_path = ""
            runner.last_error = None
            runner._last_spawn_exit_code = None
            runner._last_spawn_stderr = ""
            runner._set_last_error = Mock()
            runner._perform_standard_windivert_cleanup = Mock()
            runner._aggressive_windivert_cleanup = Mock()
            runner._wait_after_aggressive_windivert_cleanup = Mock()
            runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)
            runner._compile_preset_artifact = Mock(
                return_value=SimpleNamespace(
                    validation_ok=True,
                    validation_report="",
                    preset_path=str(preset_path),
                    launch_args=("--wf-tcp-out=80",),
                )
            )
            runner._start_from_preset_file_locked = Mock(return_value=True)

            def spawn_then_dll_init_failure_then_success(*_args, **_kwargs):
                if runner._spawn_process_locked.call_count == 1:
                    runner._last_spawn_exit_code = 0xC0000142
                    runner._last_spawn_stderr = ""
                    return False
                return True

            runner._spawn_process_locked = Mock(side_effect=spawn_then_dll_init_failure_then_success)

            self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            self.assertEqual(runner._spawn_process_locked.call_count, 2)
            runner._start_from_preset_file_locked.assert_not_called()
            runner._aggressive_windivert_cleanup.assert_called_once()

    def test_winws2_handoff_retries_dll_init_failure_before_stopping_old_process(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp-out=80", encoding="utf-8")
            old_process = Mock(pid=111)
            calls: list[str] = []

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = threading.RLock()
            runner.work_dir = tmp_dir
            runner.running_process = old_process
            runner.current_launch_label = "Old"
            runner.current_strategy_args = ["--wf-tcp-out=443"]
            runner._preset_file_path = "old.txt"
            runner.last_error = None
            runner._last_spawn_exit_code = None
            runner._last_spawn_stderr = ""
            runner._set_last_error = Mock()
            runner.is_running = Mock(return_value=True)
            runner._compile_preset_artifact = Mock(
                return_value=SimpleNamespace(
                    validation_ok=True,
                    validation_report="",
                    preset_path=str(preset_path),
                    cache_key=None,
                    normalized_text="--wf-tcp-out=80\n",
                    launch_args=("--wf-tcp-out=80",),
                )
            )
            runner._stop_previous_process_after_handoff_locked = Mock(
                side_effect=lambda *_args, **_kwargs: calls.append("stop_old")
            )

            def spawn_then_dll_init_failure_then_success(*_args, **_kwargs):
                calls.append("spawn")
                if runner._spawn_process_locked.call_count == 1:
                    runner._last_spawn_exit_code = 0xC0000142
                    runner._last_spawn_stderr = ""
                    return False
                return True

            runner._spawn_process_locked = Mock(side_effect=spawn_then_dll_init_failure_then_success)

            with patch("winws_runtime.runners.zapret2_runner.time.sleep") as sleep:
                self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            self.assertEqual(calls, ["spawn", "spawn", "stop_old"])
            self.assertEqual(runner._spawn_process_locked.call_count, 2)
            runner._stop_previous_process_after_handoff_locked.assert_called_once_with(
                old_process,
                "Old",
                "old.txt",
            )
            sleep.assert_called_once()

    def test_fast_switch_retries_winws1_conflict_inside_switch_without_full_start_fallback(self) -> None:
        from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp-out=80", encoding="utf-8")

            runner = object.__new__(Winws1StrategyRunner)
            runner.winws_exe = "winws.exe"
            runner._state_lock = threading.RLock()
            runner.running_process = None
            runner._preset_file_path = ""
            runner.last_error = None
            runner._last_spawn_exit_code = None
            runner._last_spawn_stderr = ""
            runner._set_last_error = Mock()
            runner._prepare_cleanup_before_spawn_locked = Mock()
            runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)
            runner._compile_preset_artifact = Mock(
                return_value=SimpleNamespace(
                    validation_ok=True,
                    validation_report="",
                    preset_path=str(preset_path),
                    launch_args=("--wf-tcp-out=80",),
                )
            )
            runner._start_from_preset_file_locked = Mock(return_value=True)

            def spawn_then_conflict_then_success(*_args, **_kwargs):
                if runner._spawn_process_locked.call_count == 1:
                    runner._last_spawn_exit_code = 1
                    runner._last_spawn_stderr = "A copy of winws is already running with the same filter"
                    return False
                return True

            runner._spawn_process_locked = Mock(side_effect=spawn_then_conflict_then_success)

            self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            self.assertEqual(runner._spawn_process_locked.call_count, 2)
            runner._start_from_preset_file_locked.assert_not_called()
            runner._prepare_cleanup_before_spawn_locked.assert_called_once_with(retry_count=1)

    def test_winws1_fast_switch_rebuilds_artifact_if_preset_changes_before_spawn(self) -> None:
        from winws_runtime.runners.preset_runner_support import preset_cache_key
        from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text("--wf-tcp=80", encoding="utf-8")

            runner = object.__new__(Winws1StrategyRunner)
            runner.winws_exe = "winws.exe"
            runner._state_lock = threading.RLock()
            runner.running_process = Mock()
            runner._preset_file_path = ""
            runner._set_last_error = Mock()
            runner._prepare_cleanup_before_spawn_locked = Mock()
            runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)

            def compile_artifact(path: str):
                text = Path(path).read_text(encoding="utf-8")
                return SimpleNamespace(
                    validation_ok=True,
                    validation_report="",
                    preset_path=str(path),
                    cache_key=preset_cache_key(path),
                    launch_args=(text.strip(),),
                )

            runner._compile_preset_artifact = Mock(side_effect=compile_artifact)

            runner.is_running = Mock(return_value=True)

            def change_preset_before_spawn():
                preset_path.write_text("--wf-tcp=443", encoding="utf-8")
                return True

            runner._stop_process_only_locked = Mock(side_effect=change_preset_before_spawn)
            runner._spawn_process_locked = Mock(return_value=True)

            with patch("winws_runtime.runners.zapret1_runner.get_process_pids_by_name", return_value=[]):
                self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            self.assertEqual(runner._compile_preset_artifact.call_count, 2)
            spawned_artifact = runner._spawn_process_locked.call_args.args[0]
            self.assertEqual(spawned_artifact.launch_args, ("--wf-tcp=443",))


if __name__ == "__main__":
    unittest.main()
