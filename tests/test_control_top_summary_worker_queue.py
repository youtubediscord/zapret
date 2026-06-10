from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from presets.ui.control.additional_settings_runtime import ModeControlRefreshRuntime, create_refresh_runtime
from presets.ui.control.zapret1.page import Zapret1ModeControlPage
from presets.ui.control.zapret2.page import Zapret2ModeControlPage


class ControlTopSummaryWorkerQueueTests(unittest.TestCase):
    def test_top_summary_queue_uses_shared_latest_worker_state(self) -> None:
        runtime_source = inspect.getsource(ModeControlRefreshRuntime)
        init_source = inspect.getsource(ModeControlRefreshRuntime.__init__)

        self.assertIn("LatestValueWorkerState", runtime_source)
        self.assertIn("top_summary_state", runtime_source)
        self.assertNotIn("self.top_summary_pending = False", init_source)
        self.assertNotIn("self.top_summary_start_scheduled = False", init_source)

    def test_preset_switch_delayed_reloads_use_shared_latest_worker_state(self) -> None:
        from ui.latest_value_worker_state import LatestValueWorkerState

        runtime = create_refresh_runtime()
        runtime_source = inspect.getsource(ModeControlRefreshRuntime.__init__)
        cleanup_source = inspect.getsource(ModeControlRefreshRuntime.stop_workers)

        self.assertIsInstance(runtime.top_summary_preset_switch_reload_state, LatestValueWorkerState)
        self.assertIsInstance(runtime.additional_settings_preset_switch_reload_state, LatestValueWorkerState)
        self.assertIn("top_summary_preset_switch_reload_state = LatestValueWorkerState", runtime_source)
        self.assertIn("additional_settings_preset_switch_reload_state = LatestValueWorkerState", runtime_source)
        self.assertIn("top_summary_preset_switch_reload_state.reset()", cleanup_source)
        self.assertIn("additional_settings_preset_switch_reload_state.reset()", cleanup_source)

        for page_cls in (Zapret1ModeControlPage, Zapret2ModeControlPage):
            with self.subTest(page=page_cls.__name__):
                top_summary_source = inspect.getsource(page_cls._schedule_top_summary_reload_after_preset_switch)
                additional_source = inspect.getsource(page_cls._schedule_additional_settings_reload_after_preset_switch)

                self.assertIn("top_summary_preset_switch_reload_state", top_summary_source)
                self.assertIn("schedule_start", top_summary_source)
                self.assertNotIn("top_summary_reload_after_preset_switch_scheduled = True", top_summary_source)
                self.assertIn("additional_settings_preset_switch_reload_state", additional_source)
                self.assertIn("schedule_start", additional_source)
                self.assertNotIn("additional_settings_reload_after_preset_switch_scheduled = True", additional_source)

    def test_pending_top_summary_replay_is_scheduled_after_worker_finish(self) -> None:
        for page_cls in (Zapret1ModeControlPage, Zapret2ModeControlPage):
            with self.subTest(page=page_cls.__name__):
                page = page_cls.__new__(page_cls)
                page._cleanup_in_progress = False
                page._refresh_runtime = create_refresh_runtime()
                page._refresh_runtime.top_summary_pending = True
                page._request_top_summary_worker = Mock(
                    side_effect=AssertionError("queued top summary must not restart inline")
                )
                scheduled: list[tuple[int, object]] = []

                with patch(
                    f"{page_cls.__module__}.QTimer.singleShot",
                    side_effect=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
                ):
                    page_cls._on_top_summary_worker_finished(page, object())

                self.assertEqual(1, len(scheduled))
                self.assertEqual(0, scheduled[0][0])
                self.assertTrue(page._refresh_runtime.top_summary_pending)
                self.assertTrue(page._refresh_runtime.top_summary_start_scheduled)
                page._request_top_summary_worker.assert_not_called()

    def test_stale_top_summary_worker_finish_does_not_schedule_pending_replay(self) -> None:
        for page_cls in (Zapret1ModeControlPage, Zapret2ModeControlPage):
            with self.subTest(page=page_cls.__name__):
                old_worker = object()
                current_worker = object()
                page = page_cls.__new__(page_cls)
                page._cleanup_in_progress = False
                page._refresh_runtime = create_refresh_runtime()
                page._refresh_runtime.top_summary_runtime.worker = current_worker
                page._refresh_runtime.top_summary_pending = True
                page._schedule_top_summary_worker_start = Mock(
                    side_effect=AssertionError("stale top summary worker must not schedule replay")
                )

                page_cls._on_top_summary_worker_finished(page, old_worker)

                self.assertIs(page._refresh_runtime.top_summary_runtime.worker, current_worker)
                self.assertTrue(page._refresh_runtime.top_summary_pending)
                page._schedule_top_summary_worker_start.assert_not_called()

    def test_pending_top_summary_result_does_not_apply_stale_widget_state(self) -> None:
        for page_cls in (Zapret1ModeControlPage, Zapret2ModeControlPage):
            with self.subTest(page=page_cls.__name__):
                page = page_cls.__new__(page_cls)
                page._cleanup_in_progress = False
                page._ui_language = "ru"
                page._refresh_runtime = create_refresh_runtime()
                page._refresh_runtime.top_summary_request_id = 4
                page._refresh_runtime.top_summary_pending = True
                page.top_summary = Mock()
                page._schedule_top_summary_profile_retry = Mock()

                page_cls._on_top_summary_loaded(
                    page,
                    4,
                    SimpleNamespace(preset_text="Old preset", profile_count=3),
                )

                page.top_summary.set_preset.assert_not_called()
                page.top_summary.set_profile_count.assert_not_called()
                page._schedule_top_summary_profile_retry.assert_not_called()

    def test_scheduled_top_summary_start_replays_latest_pending_request(self) -> None:
        for page_cls in (Zapret1ModeControlPage, Zapret2ModeControlPage):
            with self.subTest(page=page_cls.__name__):
                page = page_cls.__new__(page_cls)
                page._cleanup_in_progress = False
                page._refresh_runtime = create_refresh_runtime()
                page._refresh_runtime.top_summary_pending = True
                page._refresh_runtime.top_summary_start_scheduled = True
                page._request_top_summary_worker = Mock()

                page_cls._run_scheduled_top_summary_worker_start(page)

                self.assertFalse(page._refresh_runtime.top_summary_pending)
                self.assertFalse(page._refresh_runtime.top_summary_start_scheduled)
                page._request_top_summary_worker.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
