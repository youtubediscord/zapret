from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from presets.ui.common.preset_status_bar import (
    PresetStatusBar,
    PresetStatusIcon,
    build_preset_status_plan,
)


class PresetStatusBarAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_status_bar_exposes_screen_reader_state_text(self) -> None:
        bar = PresetStatusBar()
        self.addCleanup(bar.deleteLater)

        bar.set_plan(build_preset_status_plan("applied", launch_method="zapret2"))

        expected = "Статус пресета: Пресет применён"
        self.assertEqual(bar.accessibleName(), expected)
        self.assertEqual(bar.property("screenReaderStateText"), expected)
        self.assertEqual(bar.text_label.accessibleName(), expected)
        self.assertEqual(bar.text_label.property("screenReaderStateText"), expected)

    def test_status_icon_exposes_screen_reader_state_text(self) -> None:
        icon = PresetStatusIcon(size=24)
        self.addCleanup(icon.deleteLater)

        icon.set_plan(build_preset_status_plan("applying", launch_method="zapret2"))

        expected = "Статус пресета: Применяем пресет..."
        self.assertEqual(icon.accessibleName(), expected)
        self.assertEqual(icon.property("screenReaderStateText"), expected)


if __name__ == "__main__":
    unittest.main()
