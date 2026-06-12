from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import PushButton

from blockcheck.ui.domain_chip import DomainChip


class DomainChipAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_domain_chip_has_screen_reader_names(self) -> None:
        chip = DomainChip("youtube.com")
        buttons = chip.findChildren(PushButton)

        self.assertEqual(chip.accessibleName(), "Домен youtube.com")
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].accessibleName(), "Удалить домен youtube.com")
        self.assertEqual(buttons[0].property("screenReaderStateText"), "Удалить домен youtube.com")
        self.assertIn("youtube.com", buttons[0].accessibleDescription())

    def test_domain_chip_remove_button_removes_domain_from_keyboard_target(self) -> None:
        chip = DomainChip("youtube.com")
        buttons = chip.findChildren(PushButton)
        removed: list[str] = []
        chip.removed.connect(removed.append)

        buttons[0].click()

        self.assertEqual(removed, ["youtube.com"])

    def test_domain_chip_remove_button_accepts_enter_key(self) -> None:
        chip = DomainChip("youtube.com")
        self.addCleanup(chip.deleteLater)
        chip.show()
        self._app.processEvents()
        button = chip.findChildren(PushButton)[0]
        removed: list[str] = []
        chip.removed.connect(removed.append)

        button.setFocus()
        self._app.processEvents()
        QTest.keyClick(button, Qt.Key.Key_Return)
        self._app.processEvents()

        self.assertEqual(removed, ["youtube.com"])


if __name__ == "__main__":
    unittest.main()
