from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from ui.dialog_action_buttons import create_dialog_action_button, create_dialog_cancel_button


class DialogActionButtonsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_action_button_has_default_screen_reader_text(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)

        button = create_dialog_action_button(parent, text="Удалить")

        self.assertEqual(button.accessibleName(), "Удалить")
        self.assertEqual(button.property("screenReaderStateText"), "Удалить")
        self.assertIn("Выполняет действие диалога", button.accessibleDescription())
        self.assertIn("Удалить", button.accessibleDescription())

    def test_cancel_button_has_default_screen_reader_text(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)

        button = create_dialog_cancel_button(parent, text="Отмена")

        self.assertEqual(button.accessibleName(), "Отмена")
        self.assertEqual(button.property("screenReaderStateText"), "Отмена")
        self.assertIn("Закрывает диалог", button.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
