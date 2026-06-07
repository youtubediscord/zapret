from __future__ import annotations

import inspect
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from ui.widgets import folder_context_menu


class FolderContextMenuArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialog_parent(self) -> QWidget:
        parent = QWidget()
        parent.resize(640, 480)
        parent.show()
        self.addCleanup(parent.deleteLater)
        return parent

    def test_folder_context_menu_returns_action_before_dispatch(self) -> None:
        source = inspect.getsource(folder_context_menu.show_folder_context_menu)

        self.assertIn("exec_popup_menu", source)
        self.assertIn("capture_action=True", source)
        self.assertIn("action_map", source)
        self.assertNotIn("menu.exec(", source)
        self.assertNotIn("triggered.connect(lambda: _run_folder_action", source)

    def test_folder_name_dialog_has_screen_reader_text_for_create(self) -> None:
        dialog = folder_context_menu.FolderNameDialog(
            title="Создать папку",
            subtitle="Создаёт папку для группировки пресетов.",
            button_text="Создать",
            parent=self._dialog_parent(),
        )
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.nameEdit.accessibleName(), "Название папки")
        self.assertIn("Введите имя папки", dialog.nameEdit.accessibleDescription())
        self.assertEqual(dialog.yesButton.accessibleName(), "Создать папку")
        self.assertIn("Создаёт папку", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить создание папки")

        self.assertFalse(dialog.validate())

        self.assertEqual(dialog.warningLabel.accessibleName(), "Ошибка: Введите название папки.")
        self.assertEqual(dialog.warningLabel.property("screenReaderStateText"), "Ошибка: Введите название папки.")

    def test_folder_name_dialog_has_screen_reader_text_for_rename(self) -> None:
        dialog = folder_context_menu.FolderNameDialog(
            title="Переименовать папку",
            subtitle="Меняет имя папки.",
            button_text="Переименовать",
            current_name="Видео",
            parent=self._dialog_parent(),
        )
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.nameEdit.accessibleName(), "Новое название папки")
        self.assertIn("Текущее имя: Видео", dialog.nameEdit.accessibleDescription())
        self.assertEqual(dialog.yesButton.accessibleName(), "Переименовать папку")
        self.assertIn("Меняет имя папки", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить переименование папки")


if __name__ == "__main__":
    unittest.main()
