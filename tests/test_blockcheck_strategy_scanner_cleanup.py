from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class BlockcheckStrategyScannerCleanupTests(unittest.TestCase):
    def test_post_scan_cleanup_uses_runtime_windivert_cleanup(self) -> None:
        from blockcheck.strategy_scanner import StrategyScanner

        scanner = object.__new__(StrategyScanner)
        scanner._runtime_feature = SimpleNamespace(
            shutdown_sync=Mock(return_value=SimpleNamespace(still_running=False))
        )
        scanner._kill_current_process = Mock()
        scanner._cleanup_temp_files = Mock()
        scanner._cb = SimpleNamespace(on_log=Mock())

        scanner._post_scan_cleanup()

        scanner._kill_current_process.assert_called_once_with()
        scanner._runtime_feature.shutdown_sync.assert_called_once_with(
            reason="blockcheck_post_scan",
            include_cleanup=True,
        )
        scanner._cleanup_temp_files.assert_called_once_with()

    def test_strategy_process_kill_waits_for_windivert_settle(self) -> None:
        from blockcheck.strategy_scanner import StrategyScanner
        import blockcheck.strategy_scanner as strategy_scanner

        proc = SimpleNamespace(
            pid=123,
            poll=Mock(return_value=None),
            terminate=Mock(),
            wait=Mock(return_value=0),
        )
        scanner = object.__new__(StrategyScanner)
        scanner._process = proc
        scanner._process_lock = nullcontext()
        scanner._runtime_feature = SimpleNamespace(
            shutdown_sync=Mock(return_value=SimpleNamespace(still_running=False))
        )

        with patch.object(strategy_scanner, "standard_windivert_cleanup_runtime") as standard_cleanup:
            scanner._kill_current_process()

        proc.terminate.assert_called_once_with()
        standard_cleanup.assert_called_once_with()

    def test_launch_checks_windivert_readiness_before_popen(self) -> None:
        from blockcheck.strategy_scanner import StrategyScanner
        import blockcheck.strategy_scanner as strategy_scanner

        scanner = object.__new__(StrategyScanner)
        scanner._winws2_exe = r"C:\Zapret\Dev\exe\winws2.exe"
        scanner._work_dir = r"C:\Zapret\Dev"
        scanner._cb = SimpleNamespace(on_log=Mock())

        ready_probe = SimpleNamespace(ready=True)
        with (
            patch.object(strategy_scanner, "wait_for_windivert_spawn_ready_runtime", return_value=ready_probe)
            as wait_ready,
            patch.object(
                strategy_scanner.subprocess,
                "STARTUPINFO",
                return_value=SimpleNamespace(dwFlags=0, wShowWindow=0),
                create=True,
            ),
            patch.object(strategy_scanner.subprocess, "Popen") as popen,
        ):
            scanner._launch_winws2(r"C:\Zapret\Dev\tmp\strategy.txt")

        wait_ready.assert_called_once()
        popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
