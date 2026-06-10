from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from orchestra.ui.settings_page import OrchestraSettingsPage


class OrchestraSettingsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_tabs_read_current_section_for_screen_reader(self) -> None:
        page = OrchestraSettingsPage(orchestra_feature=SimpleNamespace())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.pivot.accessibleName(), "Настройки Оркестратора, выбрано: Залоченные")
        self.assertIn("Залоченные, Заблокированные, Белый список или Рейтинги", page.pivot.accessibleDescription())

        page.pivot.setCurrentItem("blocked")

        self.assertEqual(page.pivot.accessibleName(), "Настройки Оркестратора, выбрано: Заблокированные")
        self.assertEqual(
            page.pivot.property("screenReaderStateText"),
            "Настройки Оркестратора, выбрано: Заблокированные",
        )


if __name__ == "__main__":
    unittest.main()
