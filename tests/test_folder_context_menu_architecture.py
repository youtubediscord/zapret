from __future__ import annotations

import inspect
import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from ui.widgets import folder_context_menu


class _DialogButton:
    def __init__(self) -> None:
        self._text = ""
        self._accessible_name = ""
        self._accessible_description = ""

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = str(text)

    def text(self) -> str:
        return self._text

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self._accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self._accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self._accessible_description = str(text)


class _MessageBox:
    instances: list["_MessageBox"] = []

    def __init__(self, title: str, body: str, parent=None) -> None:
        self.title = title
        self.body = body
        self.parent = parent
        self.yesButton = _DialogButton()
        self.cancelButton = _DialogButton()
        self.exec_called = False
        _MessageBox.instances.append(self)

    def exec(self) -> bool:
        self.exec_called = True
        return False


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

    def test_delete_folder_dialog_buttons_are_named_for_screen_reader(self) -> None:
        labels = folder_context_menu.FolderMenuLabels(
            reset_title="Сбросить папки",
            reset_body="Папки будут возвращены к стандартному виду.",
            create_subtitle="",
            rename_subtitle="",
            delete_body="Папка будет удалена, элементы останутся в общем списке.",
            action_error_suffix="preset-ов",
        )
        actions = folder_context_menu.FolderMenuActions(run_action=Mock())
        _MessageBox.instances = []

        with patch("ui.widgets.folder_context_menu.MessageBox", _MessageBox):
            folder_context_menu._delete_folder(
                self._dialog_parent(),
                actions,
                labels,
                "folder-1",
                refresh_fn=Mock(),
                log_fn=None,
            )

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Удалить папку")
        self.assertIn("Папка будет удалена", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить удаление папки")
        self.assertTrue(dialog.exec_called)
        actions.run_action.assert_not_called()

    def test_reset_folders_dialog_buttons_are_named_for_screen_reader(self) -> None:
        labels = folder_context_menu.FolderMenuLabels(
            reset_title="Сбросить папки",
            reset_body="Папки будут возвращены к стандартному виду.",
            create_subtitle="",
            rename_subtitle="",
            delete_body="",
            action_error_suffix="preset-ов",
        )
        actions = folder_context_menu.FolderMenuActions(run_action=Mock())
        _MessageBox.instances = []

        with patch("ui.widgets.folder_context_menu.MessageBox", _MessageBox):
            folder_context_menu._reset_folders(
                self._dialog_parent(),
                actions,
                labels,
                refresh_fn=Mock(),
                log_fn=None,
            )

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Сбросить папки")
        self.assertIn("Папки будут возвращены", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить сброс папок")
        self.assertTrue(dialog.exec_called)
        actions.run_action.assert_not_called()


if __name__ == "__main__":
    unittest.main()
