from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, TransparentToolButton

from ui.fluent_widgets import set_tooltip


class TooltipKeyboardAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_tooltip_makes_icon_only_action_keyboard_accessible(self) -> None:
        button = TransparentToolButton(FluentIcon.ADD)
        self.addCleanup(button.deleteLater)
        clicked: list[bool] = []
        button.clicked.connect(lambda: clicked.append(True))

        set_tooltip(button, "Добавить домен")
        button.show()
        self._app.processEvents()
        button.setFocus()
        self._app.processEvents()
        QTest.keyClick(button, Qt.Key.Key_Return)
        self._app.processEvents()

        self.assertEqual(button.accessibleName(), "Добавить домен")
        self.assertEqual(button.accessibleDescription(), "Добавить домен")
        self.assertEqual(button.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertEqual(clicked, [True])


if __name__ == "__main__":
    unittest.main()
