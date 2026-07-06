from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class FiletimeConversionTests(unittest.TestCase):
    def test_unix_epoch_converts_to_zero(self) -> None:
        from main.process_start_time import filetime_to_unix_seconds

        unix_epoch_ticks = 11_644_473_600 * 10_000_000
        self.assertEqual(filetime_to_unix_seconds(unix_epoch_ticks), 0.0)

    def test_one_second_after_unix_epoch(self) -> None:
        from main.process_start_time import filetime_to_unix_seconds

        ticks = (11_644_473_600 + 1) * 10_000_000
        self.assertEqual(filetime_to_unix_seconds(ticks), 1.0)


@unittest.skipUnless(sys.platform == "win32", "GetProcessTimes есть только на Windows")
class ProcessCreationTimeTests(unittest.TestCase):
    def test_creation_time_matches_psutil(self) -> None:
        import psutil

        from main.process_start_time import process_creation_unix_seconds

        created = process_creation_unix_seconds()
        self.assertIsNotNone(created)
        self.assertAlmostEqual(created, psutil.Process().create_time(), delta=2.0)

    def test_creation_time_is_in_the_past(self) -> None:
        from main.process_start_time import process_creation_unix_seconds

        created = process_creation_unix_seconds()
        self.assertIsNotNone(created)
        self.assertLessEqual(created, time.time())


@unittest.skipUnless(sys.platform == "win32", "GetProcessTimes есть только на Windows")
class ExeToPythonGapTests(unittest.TestCase):
    def test_gap_is_non_negative_and_plausible(self) -> None:
        from main.process_start_time import exe_to_python_ms

        gap_ms = exe_to_python_ms()
        self.assertIsNotNone(gap_ms)
        self.assertGreaterEqual(gap_ms, 0)
        # Импорт модуля в тестах происходит позже, чем в бою, но всё равно
        # в пределах жизни текущего процесса.
        one_hour_ms = 60 * 60 * 1000
        self.assertLess(gap_ms, one_hour_ms)

    def test_gap_consistent_with_entered_wall(self) -> None:
        from main.process_start_time import (
            exe_to_python_ms,
            process_creation_unix_seconds,
            python_entered_wall,
        )

        created = process_creation_unix_seconds()
        gap_ms = exe_to_python_ms()
        self.assertIsNotNone(created)
        self.assertIsNotNone(gap_ms)
        expected_ms = (python_entered_wall() - created) * 1000.0
        self.assertAlmostEqual(gap_ms, expected_ms, delta=1.0)


if __name__ == "__main__":
    unittest.main()
