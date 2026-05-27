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

    def test_same_filter_exit_message_is_retryable_conflict(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        runner = object.__new__(Winws2StrategyRunner)

        self.assertTrue(
            runner._is_windivert_conflict_error(
                "Error: A copy of winws2 is already running with the same filter",
                1,
            )
        )

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

    def test_fast_switch_cleans_existing_winws_process_not_owned_by_runner(self) -> None:
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
                )
            )
            runner._spawn_process_locked = Mock(return_value=True)
            runner._perform_standard_windivert_cleanup = Mock()
            runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)

            with patch(
                "winws_runtime.runners.zapret2_runner.get_all_winws_process_pids",
                return_value=[777],
            ):
                self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            runner._perform_standard_windivert_cleanup.assert_called_once()
            runner._spawn_process_locked.assert_called_once()

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

            with patch("winws_runtime.runners.zapret1_runner.get_process_pids_by_name", return_value=[]):
                self.assertTrue(runner.switch_preset_file_fast(str(preset_path), "Selected"))

            self.assertEqual(runner._spawn_process_locked.call_count, 2)
            runner._start_from_preset_file_locked.assert_not_called()
            runner._prepare_cleanup_before_spawn_locked.assert_called_once_with(retry_count=1)


if __name__ == "__main__":
    unittest.main()
