from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidget
from qfluentwidgets import ScrollBar

from ui.widgets.fluent_scrollbar import FluentScrollBars, install_fluent_scrollbars


class FluentScrollbarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_install_fluent_scrollbars_uses_qfluent_scrollbar(self) -> None:
        widget = QListWidget()

        bars = install_fluent_scrollbars(widget, vertical=True, horizontal=False)

        self.assertIsInstance(bars, FluentScrollBars)
        self.assertIsInstance(bars.vertical, ScrollBar)
        self.assertIsNone(bars.horizontal)
        self.assertIs(getattr(widget, "_zapret_fluent_scrollbars"), bars)
        self.assertEqual(widget.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def test_install_fluent_scrollbars_is_idempotent(self) -> None:
        widget = QListWidget()

        first = install_fluent_scrollbars(widget, vertical=True, horizontal=False)
        second = install_fluent_scrollbars(widget, vertical=True, horizontal=False)

        self.assertIs(first, second)

    def test_reserved_vertical_space_keeps_rows_away_from_visible_scrollbar(self) -> None:
        widget = QListWidget()
        widget.resize(180, 120)
        for row in range(40):
            widget.addItem(f"Profile {row}")

        bars = install_fluent_scrollbars(
            widget,
            vertical=True,
            horizontal=False,
            reserve_vertical_space=True,
        )
        widget.show()
        self._app.processEvents()

        self.assertIsNotNone(bars.vertical)
        self.assertGreater(widget.verticalScrollBar().maximum(), 0)
        row_rect = widget.visualItemRect(widget.item(0)).adjusted(8, 2, -8, -2)
        self.assertGreaterEqual(bars.vertical.geometry().left() - row_rect.right(), 8)

    def test_reserved_vertical_space_is_not_used_without_scroll_range(self) -> None:
        widget = QListWidget()
        widget.resize(180, 120)
        widget.addItem("Only one profile")

        install_fluent_scrollbars(
            widget,
            vertical=True,
            horizontal=False,
            reserve_vertical_space=True,
        )
        widget.show()
        self._app.processEvents()

        self.assertEqual(widget.verticalScrollBar().maximum(), 0)
        self.assertEqual(widget.viewportMargins().right(), 0)


if __name__ == "__main__":
    unittest.main()
