"""Launch-layer refactor acceptance tests (.agent/tasks/launch-layer-refactor/spec.md).

AC1: a transient first spawn attempt followed by a successful retry stays quiet
     (no ERROR logs, no launch-error notification, no runner-failure publication).
AC2: a fully failed operation publishes exactly once.
AC4: the post-dry-run settle pause applies to normal start too.
AC5: unified spawn failure classification.
AC6: fast switch never emits launch-error notifications.
AC7: zapret1 runner behaves the same way as zapret2.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class _LogRecorder:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def __call__(self, message, level="INFO", *args, **kwargs) -> None:
        self.records.append((str(message), str(level)))

    def levels(self) -> list[str]:
        return [level for _message, level in self.records]

    def error_messages(self) -> list[str]:
        return [message for message, level in self.records if level == "ERROR"]


def _make_winws2_runner(tmp_dir: str):
    from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

    runner = object.__new__(Winws2StrategyRunner)
    runner.winws_exe = "winws2.exe"
    runner.work_dir = tmp_dir
    runner._state_lock = threading.RLock()
    runner.running_process = None
    runner.current_launch_label = None
    runner.current_strategy_args = None
    runner._preset_file_path = None
    runner.last_error = None
    runner._last_spawn_exit_code = None
    runner._last_spawn_stderr = ""
    runner._transition_in_progress_callback = None
    runner._runner_failure_callback = Mock()
    runner._launch_error_callback = Mock()
    runner._active_preset_content_changed_callback = None

    runner._compile_preset_artifact = Mock(
        return_value=SimpleNamespace(
            validation_ok=True,
            validation_report="",
            preset_path="preset.txt",
            cache_key=None,
            normalized_text="--wf-tcp-out=443\n",
            launch_args=("--wf-tcp-out=443",),
        )
    )
    runner._resolve_cleanup_required_before_spawn = Mock(return_value=False)
    runner._perform_cleanup_before_spawn_locked = Mock()
    runner._aggressive_windivert_cleanup = Mock()
    runner._wait_after_aggressive_windivert_cleanup = Mock()
    runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)
    return runner


def _make_winws1_runner(tmp_dir: str, winws_exe: str):
    from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

    runner = object.__new__(Winws1StrategyRunner)
    runner.winws_exe = winws_exe
    runner.work_dir = tmp_dir
    runner._state_lock = threading.RLock()
    runner.running_process = None
    runner.current_launch_label = None
    runner.current_strategy_args = None
    runner._preset_file_path = None
    runner.last_error = None
    runner._last_spawn_exit_code = None
    runner._last_spawn_stderr = ""
    runner._transition_in_progress_callback = None
    runner._runner_failure_callback = Mock()
    runner._launch_error_callback = Mock()
    runner._active_preset_content_changed_callback = None

    runner._compile_preset_artifact = Mock(
        return_value=SimpleNamespace(
            validation_ok=True,
            validation_report="",
            preset_path="preset.txt",
            cache_key=None,
            normalized_text="--wf-tcp-out=443\n",
            launch_args=("--wf-tcp-out=443",),
        )
    )
    runner._prepare_cleanup_before_spawn_locked = Mock()
    runner._ensure_windivert_ready_before_spawn = Mock(return_value=True)
    runner._run_preset_dry_run_locked = Mock(return_value=True)
    runner.is_running = Mock(return_value=False)
    return runner


class SpawnFailureClassifierTests(unittest.TestCase):
    """AC5: unified classification matches the historical predicates."""

    def test_dll_init_failure_is_transient_and_retryable(self) -> None:
        from winws_runtime.runners.spawn_failure import (
            SpawnFailureKind,
            classify_spawn_failure,
        )

        result = classify_spawn_failure(0xC0000142)
        self.assertEqual(result.kind, SpawnFailureKind.TRANSIENT_DLL_INIT)
        self.assertTrue(result.retryable)
        self.assertTrue(result.is_transient_dll_init)

    def test_conflict_exit_code_and_signatures(self) -> None:
        from winws_runtime.runners.spawn_failure import (
            SpawnFailureKind,
            classify_spawn_failure,
        )

        self.assertEqual(classify_spawn_failure(9).kind, SpawnFailureKind.WINDIVERT_CONFLICT)
        for signature in (
            "GUID or LUID already exists",
            "an object with that GUID is present",
            "A copy of winws2 is already running with the same filter",
        ):
            result = classify_spawn_failure(1, signature)
            self.assertTrue(result.is_conflict, signature)
            self.assertEqual(result.kind, SpawnFailureKind.WINDIVERT_CONFLICT, signature)
            self.assertTrue(result.retryable, signature)

    def test_system_exit_codes_and_signatures_are_not_retryable(self) -> None:
        from winws_runtime.runners.spawn_failure import (
            SpawnFailureKind,
            classify_spawn_failure,
        )

        for exit_code in (577, 1060, 1068, 1275, 654):
            result = classify_spawn_failure(exit_code)
            self.assertEqual(result.kind, SpawnFailureKind.WINDIVERT_SYSTEM, exit_code)
            self.assertFalse(result.retryable, exit_code)
        # Some signatures map to the 1058 family, whose soft/hard resolution
        # probes live system state; pin the diagnosis for determinism. A hard
        # 1058 diagnosis keeps these non-retryable, matching the historical
        # ordering (system markers win over the transient-service retry).
        with patch(
            "winws_runtime.health.process_health_check.diagnose_winws_exit",
            return_value=SimpleNamespace(win32_error=1058, cause="Включён Secure Boot"),
        ):
            for signature in (
                "the service cannot be started",
                "service is disabled",
                "invalid image hash",
                "driver blocked",
                "disable secure boot",
                "driver failed prior unload",
            ):
                result = classify_spawn_failure(1, signature)
                self.assertTrue(result.is_system, signature)
                self.assertFalse(result.retryable, signature)

    def test_soft_1058_is_service_transient_and_retryable(self) -> None:
        from winws_runtime.runners.spawn_failure import (
            SpawnFailureKind,
            classify_spawn_failure,
        )

        with patch(
            "winws_runtime.health.process_health_check.diagnose_winws_exit",
            return_value=SimpleNamespace(win32_error=1058, cause="Временная гонка службы"),
        ):
            result = classify_spawn_failure(1058, "")

        self.assertEqual(result.kind, SpawnFailureKind.WINDIVERT_SERVICE_TRANSIENT)
        self.assertTrue(result.retryable)
        self.assertTrue(result.is_system)  # 1058 stays a system code for the old predicate

    def test_hard_1058_causes_are_system_and_not_retryable(self) -> None:
        from winws_runtime.runners.spawn_failure import (
            SpawnFailureKind,
            classify_spawn_failure,
        )

        for cause in (
            "Отключена служба Base Filtering Engine",
            "Служба WinDivert отключена",
            "Отсутствуют файлы WinDivert",
            "Включён Secure Boot",
            "Неверная подпись драйвера",
            "Блокирует политика безопасности",
        ):
            with patch(
                "winws_runtime.health.process_health_check.diagnose_winws_exit",
                return_value=SimpleNamespace(win32_error=1058, cause=cause),
            ):
                result = classify_spawn_failure(1058, "")
            self.assertEqual(result.kind, SpawnFailureKind.WINDIVERT_SYSTEM, cause)
            self.assertFalse(result.retryable, cause)

    def test_unknown_failure_is_not_retryable(self) -> None:
        from winws_runtime.runners.spawn_failure import (
            SpawnFailureKind,
            classify_spawn_failure,
        )

        result = classify_spawn_failure(1, "something unexpected")
        self.assertEqual(result.kind, SpawnFailureKind.UNKNOWN)
        self.assertFalse(result.retryable)

    def test_runner_predicates_delegate_to_classifier(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        runner = object.__new__(Winws2StrategyRunner)
        self.assertTrue(runner._is_windivert_conflict_error("", 9))
        self.assertTrue(runner._is_windivert_conflict_error("guid or luid already exists", 1))
        self.assertFalse(runner._is_windivert_conflict_error("", 1))
        self.assertTrue(runner._is_windivert_system_error("", 1275))
        self.assertTrue(runner._is_windivert_system_error("driver blocked", 1))
        self.assertFalse(runner._is_windivert_system_error("", 1))
        self.assertTrue(Winws2StrategyRunner._should_retry_dry_run_exit_code(0xC0000142))
        self.assertFalse(Winws2StrategyRunner._should_retry_dry_run_exit_code(1))
        self.assertTrue(Winws2StrategyRunner._should_retry_fast_switch_spawn_exit_code(0xC0000142))
        self.assertFalse(Winws2StrategyRunner._should_retry_fast_switch_spawn_exit_code(9))


class Winws2QuietRetryPublicationTests(unittest.TestCase):
    def test_final_failure_publishes_human_message_not_raw_winws_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = _make_winws2_runner(tmp_dir)
            runner.last_error = (
                "winws2 не запустился. Найдена причина: служба WinDivert отключена "
                "(код ошибки Windows 1058; код завершения процесса 34)"
            )
            runner._last_spawn_stderr = (
                "github version v1.0.1 lua_compat_ver 6\n"
                "windivert: error opening filter"
            )

            with patch("winws_runtime.runners.runner_base.log"):
                runner._publish_final_launch_failure(
                    launch_method="zapret2_mode",
                    fallback_message="winws2 не запустился",
                )

        runner._runner_failure_callback.assert_called_once_with(
            launch_method="zapret2_mode",
            error=runner.last_error,
        )
        self.assertNotIn("github version", runner._runner_failure_callback.call_args.kwargs["error"])

    def test_transient_dll_init_retry_success_stays_quiet(self) -> None:
        """AC1: first attempt fails with 0xC0000142, retry succeeds — no user-facing noise."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "preset.txt"
            preset_path.write_text("--wf-tcp-out=443", encoding="utf-8")

            runner = _make_winws2_runner(tmp_dir)

            def spawn_dll_init_failure_then_success(*_args, **_kwargs):
                if runner._spawn_process_locked.call_count == 1:
                    runner._last_spawn_exit_code = 0xC0000142
                    runner._last_spawn_stderr = ""
                    return False
                return True

            runner._spawn_process_locked = Mock(side_effect=spawn_dll_init_failure_then_success)

            recorder = _LogRecorder()
            with (
                patch("winws_runtime.runners.zapret2_runner.log", recorder),
                patch("winws_runtime.runners.runner_base.log", recorder),
                patch(
                    "winws_runtime.runners.zapret2_runner.find_stale_windivert_delete_pending_services_runtime",
                    return_value=[],
                ),
            ):
                success = runner.start_from_preset_file(str(preset_path), "Preset")

        self.assertTrue(success)
        self.assertEqual(runner._spawn_process_locked.call_count, 2)
        self.assertNotIn("ERROR", recorder.levels())
        runner._launch_error_callback.assert_not_called()
        runner._runner_failure_callback.assert_not_called()

    def test_exhausted_retries_publish_exactly_once(self) -> None:
        """AC2: the whole operation fails — exactly one toast/notification/failure event."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "preset.txt"
            preset_path.write_text("--wf-tcp-out=443", encoding="utf-8")

            runner = _make_winws2_runner(tmp_dir)

            def spawn_always_dll_init_failure(*_args, **_kwargs):
                runner._last_spawn_exit_code = 0xC0000142
                runner._last_spawn_stderr = ""
                runner._set_last_error(
                    runner._format_windows_process_init_failure(0xC0000142),
                    notify=False,
                )
                return False

            runner._spawn_process_locked = Mock(side_effect=spawn_always_dll_init_failure)

            recorder = _LogRecorder()
            with (
                patch("winws_runtime.runners.zapret2_runner.log", recorder),
                patch("winws_runtime.runners.runner_base.log", recorder),
                patch(
                    "winws_runtime.runners.zapret2_runner.find_stale_windivert_delete_pending_services_runtime",
                    return_value=[],
                ),
            ):
                success = runner.start_from_preset_file(str(preset_path), "Preset")

        self.assertFalse(success)
        self.assertEqual(runner._spawn_process_locked.call_count, 2)
        self.assertEqual(len(recorder.error_messages()), 1)
        self.assertTrue(runner.last_error)
        self.assertIn("Windows не смогла инициализировать DLL", runner.last_error)
        runner._launch_error_callback.assert_called_once_with(runner.last_error)
        runner._runner_failure_callback.assert_called_once()
        self.assertEqual(recorder.error_messages()[0], runner.last_error)

    def test_missing_preset_file_publishes_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = _make_winws2_runner(tmp_dir)
            missing = str(Path(tmp_dir) / "missing.txt")

            recorder = _LogRecorder()
            with (
                patch("winws_runtime.runners.zapret2_runner.log", recorder),
                patch("winws_runtime.runners.runner_base.log", recorder),
            ):
                success = runner.start_from_preset_file(missing, "Preset")

        self.assertFalse(success)
        self.assertEqual(len(recorder.error_messages()), 1)
        runner._launch_error_callback.assert_called_once()
        runner._runner_failure_callback.assert_called_once()

    def test_settle_pause_applies_to_normal_start(self) -> None:
        """AC4: post-dry-run settle pause is no longer preset-switch-only."""
        from winws_runtime.runners.zapret2_runner import (
            _PRESET_SWITCH_AFTER_DRY_RUN_SETTLE_SEC,
            Winws2StrategyRunner,
        )

        runner = object.__new__(Winws2StrategyRunner)
        with patch("winws_runtime.runners.zapret2_runner.time.sleep") as sleep_mock:
            runner._wait_after_successful_dry_run_before_spawn(preset_switch=False)
        sleep_mock.assert_called_once_with(_PRESET_SWITCH_AFTER_DRY_RUN_SETTLE_SEC)

        with patch("winws_runtime.runners.zapret2_runner.time.sleep") as sleep_mock:
            runner._wait_after_successful_dry_run_before_spawn(preset_switch=True)
        sleep_mock.assert_called_once_with(_PRESET_SWITCH_AFTER_DRY_RUN_SETTLE_SEC)

    def test_fast_switch_failure_never_notifies(self) -> None:
        """AC6: fast switch failures surface via last_error only."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "preset.txt"
            preset_path.write_text("--wf-tcp-out=443", encoding="utf-8")

            runner = _make_winws2_runner(tmp_dir)

            def spawn_unretryable_failure(*_args, **_kwargs):
                runner._last_spawn_exit_code = 1
                runner._last_spawn_stderr = "some fatal winws2 output"
                runner._set_last_error("winws2 завершился сразу (код 1)", notify=False)
                return False

            runner._spawn_process_locked = Mock(side_effect=spawn_unretryable_failure)

            success = runner.switch_preset_file_fast(str(preset_path), "Selected")

        self.assertFalse(success)
        self.assertTrue(runner.last_error)
        runner._launch_error_callback.assert_not_called()
        runner._runner_failure_callback.assert_not_called()


class Winws1QuietRetryPublicationTests(unittest.TestCase):
    def test_unclassified_code_one_retry_success_stays_quiet(self) -> None:
        """AC7/AC1: winws1 retries exit code 1 without output quietly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "preset.txt"
            preset_path.write_text("--wf-tcp-out=443", encoding="utf-8")

            runner = _make_winws1_runner(tmp_dir, winws_exe=str(preset_path))

            def spawn_code_one_then_success(*_args, **_kwargs):
                if runner._spawn_process_locked.call_count == 1:
                    runner._last_spawn_exit_code = 1
                    runner._last_spawn_stderr = ""
                    return False
                return True

            runner._spawn_process_locked = Mock(side_effect=spawn_code_one_then_success)

            recorder = _LogRecorder()
            with (
                patch("winws_runtime.runners.zapret1_runner.log", recorder),
                patch("winws_runtime.runners.runner_base.log", recorder),
            ):
                success = runner.start_from_preset_file(str(preset_path), "Preset")

        self.assertTrue(success)
        self.assertEqual(runner._spawn_process_locked.call_count, 2)
        self.assertNotIn("ERROR", recorder.levels())
        runner._launch_error_callback.assert_not_called()
        runner._runner_failure_callback.assert_not_called()

    def test_exhausted_retries_publish_exactly_once(self) -> None:
        """AC7/AC2: winws1 final failure publishes exactly once."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "preset.txt"
            preset_path.write_text("--wf-tcp-out=443", encoding="utf-8")

            runner = _make_winws1_runner(tmp_dir, winws_exe=str(preset_path))

            def spawn_always_code_one(*_args, **_kwargs):
                runner._last_spawn_exit_code = 1
                runner._last_spawn_stderr = ""
                runner._set_last_error("winws завершился сразу (код 1)", notify=False)
                return False

            runner._spawn_process_locked = Mock(side_effect=spawn_always_code_one)

            recorder = _LogRecorder()
            with (
                patch("winws_runtime.runners.zapret1_runner.log", recorder),
                patch("winws_runtime.runners.runner_base.log", recorder),
                patch(
                    "winws_runtime.runners.zapret1_runner.check_common_crash_causes",
                    return_value="",
                ),
            ):
                success = runner.start_from_preset_file(str(preset_path), "Preset")

        self.assertFalse(success)
        self.assertEqual(runner._spawn_process_locked.call_count, 2)
        self.assertEqual(len(recorder.error_messages()), 1)
        self.assertTrue(runner.last_error)
        runner._launch_error_callback.assert_called_once_with(runner.last_error)
        runner._runner_failure_callback.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
