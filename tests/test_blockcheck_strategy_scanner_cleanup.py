from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock


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


if __name__ == "__main__":
    unittest.main()
