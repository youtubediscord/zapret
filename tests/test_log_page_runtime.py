import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.feature_facades.logs import LogsFeature
from log.commands import build_file_read_plan
from log.file_reader_worker import LogFileReaderWorker
from log.runtime_workflow import run_logs_runtime_init, start_live_log_source
from log.ui.page import LogsPage
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

            first_plan = build_file_read_plan(current_log_file=str(log_path))
            second_plan = build_file_read_plan(
                current_log_file=str(log_path),
                previous_signature=first_plan.file_signature,
            )

        self.assertTrue(first_plan.should_clear_view)
        self.assertEqual(first_plan.max_bytes, 1024 * 1024)
        self.assertFalse(second_plan.should_clear_view)
        self.assertEqual(second_plan.max_bytes, 0)

    def test_runtime_init_schedules_one_overview_refresh(self) -> None:
        scheduled = []
        update_stats = Mock()
        start_tail = Mock()

        initialized, started = run_logs_runtime_init(
            runtime_initialized=False,
            runtime_started=False,
            schedule_fn=lambda delay, callback: scheduled.append((delay, callback)),
            update_stats_fn=update_stats,
            start_log_source_fn=start_tail,
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

    def test_old_log_reader_finishes_at_eof_without_polling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "old.log"
            log_path.write_text("first\nsecond\nthird\n", encoding="utf-8")
            worker = LogFileReaderWorker(str(log_path), chunk_chars=64 * 1024)
            chunks = []
            worker.new_lines.connect(chunks.append)

            worker.run()

        self.assertEqual("".join(chunks).splitlines(), ["first", "second", "third"])

    def test_live_source_applies_memory_snapshot_without_file_reader(self) -> None:
        bridge = SimpleNamespace(
            snapshot=SimpleNamespace(
                text="history\n",
                last_sequence=12,
                reset_required=True,
            )
        )
        clear_view = Mock()
        append_text = Mock()
        set_cursor = Mock()
        set_bridge = Mock()

        result = start_live_log_source(
            active_log_file="C:/Zapret/Dev/logs/current.log",
            after_sequence=7,
            should_reset_view=False,
            create_bridge_fn=Mock(return_value=bridge),
            on_new_text=Mock(),
            set_bridge_fn=set_bridge,
            set_cursor_fn=set_cursor,
            set_displayed_file_fn=Mock(),
            set_info_text_fn=Mock(),
            clear_log_view_fn=clear_view,
            append_text_fn=append_text,
            log_fn=Mock(),
        )

        self.assertIs(result, bridge)
        set_bridge.assert_called_once_with(bridge)
        clear_view.assert_called_once_with()
        append_text.assert_called_once_with("history\n")
        set_cursor.assert_called_once_with(12)

    def test_log_file_name_is_cached_before_management_tab_exists(self) -> None:
        page = LogsPage.__new__(LogsPage)
        page._info_text_cache = ""

        LogsPage._set_info_text(page, "current.log")

        self.assertEqual(page._info_text_cache, "current.log")


if __name__ == "__main__":
    unittest.main()
