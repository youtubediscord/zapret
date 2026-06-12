from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.pages.base_page import BasePage


class BasePageAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_page_scrollbar_arrow_buttons_do_not_take_tab_focus(self) -> None:
        page = BasePage("Тестовая страница")
        self.addCleanup(page.deleteLater)

        buttons = [
            child
            for child in page.findChildren(object)
            if type(child).__name__ == "ArrowButton"
            and hasattr(child, "setFocusPolicy")
        ]

        self.assertTrue(buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))


if __name__ == "__main__":
    unittest.main()
