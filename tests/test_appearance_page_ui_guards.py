from __future__ import annotations

import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.state_store import AppUiState


class AppearancePageUiGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_opacity_state_change_skips_premium_and_holiday_repaint(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page.set_opacity_value = Mock()
        page.set_premium_status = Mock(
            side_effect=AssertionError("opacity-only change must not repaint premium controls")
        )
        page.set_garland_state = Mock(
            side_effect=AssertionError("opacity-only change must not repaint garland checkbox")
        )
        page.set_snowflakes_state = Mock(
            side_effect=AssertionError("opacity-only change must not repaint snowflakes checkbox")
        )
        page._current_bg_preset_from_ui = Mock(
            side_effect=AssertionError("opacity-only change must not read background preset UI")
        )

        AppearancePage._on_ui_state_changed(
            page,
            AppUiState(
                subscription_is_premium=True,
                garland_enabled=True,
                snowflakes_enabled=True,
                window_opacity=72,
            ),
            frozenset({"window_opacity"}),
        )

        page.set_opacity_value.assert_called_once_with(72)
        page.set_premium_status.assert_not_called()
        page.set_garland_state.assert_not_called()
        page.set_snowflakes_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
