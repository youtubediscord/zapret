from __future__ import annotations

import inspect
import unittest

from log.ui import logs_build
from log.ui.page import LogsPage


class LogRefreshIconContractTests(unittest.TestCase):
    def test_logs_primary_tab_refresh_button_uses_fluent_icon(self) -> None:
        source = inspect.getsource(logs_build.build_logs_primary_tab_ui)

        self.assertIn("FluentIcon.SYNC", source)
        self.assertNotIn("get_themed_qta_icon", source)

    def test_log_page_theme_refresh_button_uses_fluent_icon(self) -> None:
        source = inspect.getsource(LogsPage._apply_page_theme)

        self.assertIn("FluentIcon.SYNC", source)
        self.assertNotIn("get_themed_qta_icon", source)


if __name__ == "__main__":
    unittest.main()
