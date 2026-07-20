import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.feature_facades.logs import LogsFeature
from log.commands import build_tail_start_plan
from log.runtime_workflow import run_logs_runtime_init
from log.ui.page import LogsPage
from log_tail import LogTailWorker
from ui.log_limits import MAIN_LOG_VIEW_MAX_LINES


class LogPageRuntimeTests(unittest.TestCase):
    def test_logs_feature_has_no_live_winws_output_api(self) -> None:
        feature = LogsFeature()

        self.assertFalse(hasattr(feature, "start_winws_output_worker"))
        self.assertFalse(hasattr(feature, "create_winws_output_worker"))
        self.assertFalse(hasattr(feature, "build_winws_output_plan"))

    def test_tail_plan_does_not_reload_unchanged_log_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "zapret_log.txt"
            log_path.write_text("line 1\nline 2\n", encoding="utf-8")

            first_plan = build_tail_start_plan(current_log_file=str(log_path))
            second_plan = build_tail_start_plan(
                current_log_file=str(log_path),
                previous_signature=first_plan.file_signature,
            )

        self.assertTrue(first_plan.should_clear_view)
        self.assertEqual(first_plan.initial_max_bytes, 1024 * 1024)
        self.assertFalse(second_plan.should_clear_view)
        self.assertEqual(second_plan.initial_max_bytes, 0)

    def test_runtime_init_schedules_one_overview_refresh(self) -> None:
        scheduled = []
        update_stats = Mock()
        start_tail = Mock()

        initialized, started = run_logs_runtime_init(
            runtime_initialized=False,
            runtime_started=False,
            schedule_fn=lambda delay, callback: scheduled.append((delay, callback)),
            update_stats_fn=update_stats,
            start_tail_worker_fn=start_tail,
        )

        self.assertTrue(initialized)
        self.assertTrue(started)
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], 0)
        scheduled[0][1]()
        update_stats.assert_called_once_with()
        start_tail.assert_called_once_with()

    def test_log_text_cache_is_bounded_without_rebuilding_one_large_string(self) -> None:
        page = LogsPage.__new__(LogsPage)
        page._log_text_cache = ""

        LogsPage._append_log_text_cache(
            page,
            "\n".join(f"line {index}" for index in range(MAIN_LOG_VIEW_MAX_LINES + 25)),
        )

        cached_lines = page._log_text_cache.splitlines()
        self.assertEqual(len(cached_lines), MAIN_LOG_VIEW_MAX_LINES)
        self.assertEqual(cached_lines[0], "line 25")

    def test_log_tail_worker_batches_available_live_lines(self) -> None:
        worker = LogTailWorker("unused.log", initial_chunk_chars=64 * 1024)

        text = worker._read_available_text(io.StringIO("first\nsecond\nthird\n"))

        self.assertEqual(text, "first\nsecond\nthird\n")

    def test_log_file_name_is_cached_before_management_tab_exists(self) -> None:
        page = LogsPage.__new__(LogsPage)
        page._info_text_cache = ""

        LogsPage._set_info_text(page, "current.log")

        self.assertEqual(page._info_text_cache, "current.log")


if __name__ == "__main__":
    unittest.main()
