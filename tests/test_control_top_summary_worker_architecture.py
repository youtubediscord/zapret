from __future__ import annotations

import inspect
import unittest

import presets.ui.control.control_page_shared as control_page_shared
from presets.ui.control.zapret1.page import Zapret1ModeControlPage
from presets.ui.control.zapret2.page import Zapret2ModeControlPage
import ui.page_deps.presets as preset_page_deps


class ControlTopSummaryWorkerArchitectureTests(unittest.TestCase):
    def test_control_pages_receive_summary_worker_factory_not_raw_summary_readers(self) -> None:
        for page_cls in (Zapret1ModeControlPage, Zapret2ModeControlPage):
            init_source = inspect.getsource(page_cls.__init__)
            request_source = inspect.getsource(page_cls._request_top_summary_worker)

            self.assertIn("create_top_summary_worker", init_source)
            self.assertNotIn("get_selected_source_preset_display", init_source)
            self.assertNotIn("get_enabled_profile_count_snapshot", init_source)
            self.assertIn("self._create_top_summary_worker", request_source)
            self.assertNotIn("_get_selected_source_preset_display", request_source)
            self.assertNotIn("_get_enabled_profile_count_snapshot", request_source)

        import presets.ui.control.zapret2.page as zapret2_page

        self.assertFalse(hasattr(zapret2_page, "create_control_top_summary_worker"))

    def test_page_deps_wraps_summary_readers_inside_worker_factory(self) -> None:
        source = inspect.getsource(preset_page_deps.build_control_page_kwargs)

        self.assertIn("create_top_summary_worker", source)
        self.assertIn("get_selected_source_preset_display", source)
        self.assertIn("get_enabled_profile_count_snapshot", source)

    def test_control_pages_receive_additional_settings_save_worker_factory(self) -> None:
        for page_cls in (Zapret1ModeControlPage, Zapret2ModeControlPage):
            init_source = inspect.getsource(page_cls.__init__)
            request_source = inspect.getsource(page_cls._request_additional_settings_save)
            start_source = inspect.getsource(page_cls._start_additional_settings_save_worker)

            self.assertIn("create_additional_settings_save_worker", init_source)
            self.assertNotIn("set_wssize_enabled", init_source)
            self.assertNotIn("set_debug_log_enabled", init_source)
            self.assertNotIn("set_discord_restart_setting", request_source)
            self.assertIn("_start_additional_settings_save_worker", request_source)
            self.assertIn("self._create_additional_settings_save_worker", start_source)
            self.assertNotIn("_set_wssize_enabled", request_source)
            self.assertNotIn("_set_debug_log_enabled", request_source)

    def test_control_pages_start_refresh_workers_through_runtime(self) -> None:
        for page_cls in (Zapret1ModeControlPage, Zapret2ModeControlPage):
            top_summary_source = inspect.getsource(page_cls._request_top_summary_worker)
            top_summary_finished_source = inspect.getsource(page_cls._on_top_summary_worker_finished)
            load_source = inspect.getsource(page_cls._schedule_additional_settings_reload)
            save_source = inspect.getsource(page_cls._start_additional_settings_save_worker)
            page_source = inspect.getsource(page_cls)

            for source in (top_summary_source, load_source, save_source):
                self.assertIn("start_qthread_worker", source)
                self.assertNotIn("worker.start()", source)

            self.assertIn("schedule_pending_after_finish", top_summary_finished_source)
            self.assertIn("_run_scheduled_top_summary_worker_start", top_summary_finished_source)
            self.assertNotIn("self._request_top_summary_worker()", top_summary_finished_source)
            self.assertNotIn("runtime.top_summary_worker", page_source)
            self.assertNotIn("runtime.additional_settings_worker", page_source)
            self.assertNotIn("runtime.additional_settings_save_worker", page_source)

        cleanup_source = inspect.getsource(control_page_shared.cleanup_control_page_subscriptions)
        self.assertIn("top_summary_runtime.stop", cleanup_source)
        self.assertNotIn("top_summary_worker", cleanup_source)

    def test_page_deps_wraps_additional_settings_setters_inside_worker_factory(self) -> None:
        source = inspect.getsource(preset_page_deps.build_control_page_kwargs)

        self.assertIn("create_additional_settings_save_worker", source)
        self.assertIn("set_discord_restart_setting", source)
        self.assertIn("set_wssize_enabled", source)
        self.assertIn("set_debug_log_enabled", source)


if __name__ == "__main__":
    unittest.main()
