from __future__ import annotations

import inspect
import unittest

from ui.pages.base_page import BasePage


class BasePageLayoutContractTests(unittest.TestCase):
    def test_base_page_clamps_content_width_to_viewport(self) -> None:
        init = inspect.getsource(BasePage.__init__)
        sync = inspect.getsource(BasePage._sync_content_width_to_viewport)
        resize = inspect.getsource(BasePage.resizeEvent)
        show = inspect.getsource(BasePage.showEvent)

        self.assertIn("ScrollBarAlwaysOff", init)
        self.assertIn("self.content.setMinimumWidth(0)", init)
        self.assertIn("self.viewport().width()", sync)
        self.assertIn("self.content.setMaximumWidth(width)", sync)
        self.assertIn("_sync_content_width_to_viewport", resize)
        self.assertIn("_sync_content_width_to_viewport", show)

    def test_base_page_show_event_logs_internal_timing_steps(self) -> None:
        show = inspect.getsource(BasePage.showEvent)
        schedule_theme = inspect.getsource(BasePage._schedule_page_theme_refresh_flush)
        flush_theme = inspect.getsource(BasePage._flush_page_theme_refresh)

        self.assertIn("_log_show_step_timing", show)
        self.assertIn("show.event.sync_width", show)
        self.assertIn("show.event.ready_callbacks", show)
        self.assertIn("show.event.schedule_activation", show)
        self.assertIn("show.event.schedule_theme_flush", show)
        self.assertIn("_schedule_page_theme_refresh_flush", show)
        self.assertNotIn("_flush_page_theme_refresh()", show)
        self.assertIn("QTimer.singleShot(0, self._flush_page_theme_refresh)", schedule_theme)
        self.assertIn("show.event.theme_flush", flush_theme)


if __name__ == "__main__":
    unittest.main()
