import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QSizePolicy, QWidget

from presets.ui.common.preset_subpage_base import PresetRawEditorPage, RawPresetRuntimeActions, _RenameDialog


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.enabled = True

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self.enabled = bool(enabled)


class _FakeMenuItem:
    def __init__(self) -> None:
        self._data = {}

    def setData(self, role, value) -> None:  # noqa: N802
        self._data[int(role)] = value

    def data(self, role):
        return self._data.get(int(role))


class _FakeMenuView:
    def __init__(self) -> None:
        self._items: list[_FakeMenuItem] = []

    def add_item(self) -> None:
        self._items.append(_FakeMenuItem())

    def count(self) -> int:
        return len(self._items)

    def item(self, row: int):
        return self._items[row] if 0 <= row < len(self._items) else None


class _FakeMenu:
    def __init__(self, *, parent=None) -> None:
        self.parent = parent
        self.actions: list[_FakeAction] = []
        self.view = _FakeMenuView()

    def addAction(self, action: _FakeAction) -> None:  # noqa: N802
        self.actions.append(action)
        self.view.add_item()


class PresetSubpageAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        self.app.closeAllWindows()
        self.app.processEvents()

    def test_main_controls_are_named_for_screen_reader(self) -> None:
        page = PresetRawEditorPage(
            create_raw_preset_load_worker=lambda *_args, **_kwargs: None,
            create_raw_preset_save_worker=lambda *_args, **_kwargs: None,
            create_raw_preset_activate_worker=lambda *_args, **_kwargs: None,
            create_raw_preset_action_worker=lambda *_args, **_kwargs: None,
            launch_method="zapret2",
            title="Пресет",
            open_back=lambda: None,
            open_root=lambda: None,
            runtime_actions=RawPresetRuntimeActions(
                start=lambda *_args, **_kwargs: None,
                stop=lambda *_args, **_kwargs: None,
                is_available=lambda: True,
            ),
            ui_state_store=None,
        )
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.menuButton.accessibleName(), "Открыть меню действий пресета")
        self.assertEqual(page.menuButton.property("screenReaderStateText"), "Открыть меню действий пресета")
        self.assertIn("переименовать", page.menuButton.accessibleDescription())
        self.assertEqual(page.activateButton.accessibleName(), "Сделать пресет активным")
        self.assertEqual(page.activateButton.property("screenReaderStateText"), "Сделать пресет активным")
        self.assertIn("выбранным для запуска", page.activateButton.accessibleDescription())
        self.assertEqual(page.openExternalButton.accessibleName(), "Открыть пресет в редакторе")
        self.assertEqual(page.openExternalButton.property("screenReaderStateText"), "Открыть пресет в редакторе")
        self.assertIn("внешнем текстовом редакторе", page.openExternalButton.accessibleDescription())
        self.assertEqual(page.runtimeToggleButton.accessibleName(), "Запустить пресет")
        self.assertEqual(page.runtimeToggleButton.property("screenReaderStateText"), "Запустить пресет")
        self.assertIn("Запускает Zapret", page.runtimeToggleButton.accessibleDescription())
        self.assertEqual(page.searchInput.accessibleName(), "Поиск по тексту пресета")
        self.assertEqual(page.searchInput.property("screenReaderStateText"), "Поиск по тексту пресета")
        self.assertIn("После ввода перейдите к тексту пресета клавишей Tab", page.searchInput.accessibleDescription())
        self.assertIn("или нажмите Стрелка вниз", page.searchInput.accessibleDescription())
        self.assertGreaterEqual(page.searchInput.minimumWidth(), 320)
        self.assertGreaterEqual(page.searchInput.maximumWidth(), 460)
        self.assertEqual(page.searchInput.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)
        self.assertEqual(page.editor.accessibleName(), "Текст открытого пресета")
        self.assertEqual(page.editor.property("screenReaderStateText"), "Текст открытого пресета")

    def test_arrow_down_from_search_moves_focus_to_preset_text(self) -> None:
        page = PresetRawEditorPage(
            create_raw_preset_load_worker=lambda *_args, **_kwargs: None,
            create_raw_preset_save_worker=lambda *_args, **_kwargs: None,
            create_raw_preset_activate_worker=lambda *_args, **_kwargs: None,
            create_raw_preset_action_worker=lambda *_args, **_kwargs: None,
            launch_method="zapret2",
            title="Пресет",
            open_back=lambda: None,
            open_root=lambda: None,
            runtime_actions=RawPresetRuntimeActions(
                start=lambda *_args, **_kwargs: None,
                stop=lambda *_args, **_kwargs: None,
                is_available=lambda: True,
            ),
            ui_state_store=None,
        )
        self.addCleanup(page.deleteLater)
        page.show()
        self.app.processEvents()
        page.searchInput.setFocus()
        self.app.processEvents()

        QTest.keyClick(page.searchInput, Qt.Key.Key_Down)
        self.app.processEvents()

        self.assertIs(self.app.focusWidget(), page.editor)

    def test_raw_preset_actions_menu_items_are_named_for_screen_reader(self) -> None:
        import presets.ui.common.preset_subpage_base as preset_subpage_base

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._preset_origin = "user"
        page._preset_file_name = "custom.txt"
        page._ui_language = "ru"
        page.menuButton = SimpleNamespace(
            rect=lambda: SimpleNamespace(bottomLeft=lambda: QPoint(0, 0)),
            mapToGlobal=lambda point: point,
        )
        page._is_current_selected_file = lambda: True
        menu_holder: dict[str, _FakeMenu] = {}

        class CapturingMenu(_FakeMenu):
            def __init__(self, *, parent=None) -> None:
                super().__init__(parent=parent)
                menu_holder["menu"] = self

        with (
            patch.object(preset_subpage_base, "RoundMenu", CapturingMenu),
            patch.object(preset_subpage_base, "Action", _FakeAction),
            patch.object(preset_subpage_base, "_make_menu_action", lambda text, **_kwargs: _FakeAction(text)),
            patch.object(preset_subpage_base, "exec_popup_menu", return_value=None),
        ):
            PresetRawEditorPage._open_menu(page)

        accessible_items = [
            menu_holder["menu"].view.item(row).data(Qt.ItemDataRole.AccessibleTextRole)
            for row in range(menu_holder["menu"].view.count())
            if menu_holder["menu"].view.item(row) is not None
            and menu_holder["menu"].view.item(row).data(Qt.ItemDataRole.AccessibleTextRole)
        ]

        self.assertIn("Действие preset: Переименовать", accessible_items)
        self.assertIn("Действие preset: Дублировать", accessible_items)
        self.assertIn("Действие preset: Экспорт", accessible_items)
        self.assertIn("Действие preset: Вернуть встроенный", accessible_items)
        self.assertIn("Действие preset: Удалить, недоступно", accessible_items)

    def test_raw_builtin_preset_menu_hides_reset_action(self) -> None:
        import presets.ui.common.preset_subpage_base as preset_subpage_base

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._preset_origin = "builtin"
        page._preset_file_name = "Default.txt"
        page._ui_language = "ru"
        page.menuButton = SimpleNamespace(
            rect=lambda: SimpleNamespace(bottomLeft=lambda: QPoint(0, 0)),
            mapToGlobal=lambda point: point,
        )
        page._is_current_selected_file = lambda: True
        menu_holder: dict[str, _FakeMenu] = {}

        class CapturingMenu(_FakeMenu):
            def __init__(self, *, parent=None) -> None:
                super().__init__(parent=parent)
                menu_holder["menu"] = self

        with (
            patch.object(preset_subpage_base, "RoundMenu", CapturingMenu),
            patch.object(preset_subpage_base, "Action", _FakeAction),
            patch.object(preset_subpage_base, "_make_menu_action", lambda text, **_kwargs: _FakeAction(text)),
            patch.object(preset_subpage_base, "exec_popup_menu", return_value=None),
        ):
            PresetRawEditorPage._open_menu(page)

        action_texts = [action.text for action in menu_holder["menu"].actions]

        self.assertNotIn("Вернуть встроенный", action_texts)

    def test_rename_dialog_is_named_for_screen_reader(self) -> None:
        parent = QWidget()
        parent.resize(640, 480)
        parent.show()
        self.addCleanup(parent.deleteLater)

        dialog = _RenameDialog("Default", [], parent)
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.nameEdit.accessibleName(), "Новое название открытого пресета")
        self.assertIn("Текущее имя: Default", dialog.nameEdit.accessibleDescription())
        self.assertEqual(dialog.yesButton.accessibleName(), "Переименовать открытый пресет")
        self.assertIn("Меняет имя открытого пресета", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить переименование открытого пресета")

        dialog.nameEdit.setText("")
        self.assertFalse(dialog.validate())

        self.assertEqual(dialog.warningLabel.accessibleName(), "Ошибка: Введите название.")
        self.assertEqual(dialog.warningLabel.property("screenReaderStateText"), "Ошибка: Введите название.")

    def test_rename_dialog_clear_button_does_not_take_tab_focus(self) -> None:
        parent = QWidget()
        parent.resize(640, 480)
        parent.show()
        self.addCleanup(parent.deleteLater)

        dialog = _RenameDialog("Default", [], parent)
        self.addCleanup(dialog.deleteLater)
        dialog.nameEdit.setText("Default")

        buttons = [
            child
            for child in dialog.nameEdit.findChildren(object)
            if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
            and hasattr(child, "setFocusPolicy")
        ]

        self.assertTrue(buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))


if __name__ == "__main__":
    unittest.main()
