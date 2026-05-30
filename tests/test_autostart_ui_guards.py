from __future__ import annotations

import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.state_store import AppUiState
from PyQt6.QtWidgets import QApplication


class _Label:
    def __init__(self, text: str = "") -> None:
        self._text = str(text)
        self.text_calls: list[str] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.text_calls.append(value)
        self._text = value


class AutostartUiGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_strategy_summary_change_skips_mode_worker_reload(self) -> None:
        from autostart.ui.page import AutostartPage

        page = AutostartPage.__new__(AutostartPage)
        page._cleanup_in_progress = False
        page.strategy_name = "Old"
        page.current_strategy_label = _Label("Old")
        page._update_mode = Mock(
            side_effect=AssertionError("strategy summary change must not reload launch mode")
        )
        page.update_status = AutostartPage.update_status.__get__(page, AutostartPage)
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)
        page.status_label = _Label()
        page.status_desc = _Label()
        page.status_icon = Mock()
        page.disable_btn = Mock()
        page.gui_option = Mock()

        AutostartPage._on_ui_state_changed(
            page,
            AppUiState(autostart_enabled=False, current_strategy_summary="New"),
            frozenset({"current_strategy_summary"}),
        )

        page._update_mode.assert_not_called()
        self.assertEqual(page.current_strategy_label.text(), "New")


if __name__ == "__main__":
    unittest.main()
