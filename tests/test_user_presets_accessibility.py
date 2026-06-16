from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QAbstractItemView, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, LineEdit, PrimaryToolButton, StrongBodyLabel

from app.ui_texts import tr
from presets.ui.common.user_presets_build import build_user_presets_page_shell
from presets.ui.common.user_presets_dialogs import CreatePresetDialog, RenamePresetDialog, ResetAllPresetsDialog
from presets.ui.common.user_presets_page import UserPresetsPageBase
from presets.ui.common.user_presets_page_lifecycle import apply_user_presets_language
from ui.theme import get_cached_qta_pixmap, get_theme_tokens


class _PageHost(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.resize(1000, 600)
        self.layout = QVBoxLayout(self)

    def viewport(self):  # noqa: ANN201
        return self


class _DialogButton:
    def __init__(self) -> None:
        self._accessible_name = ""
        self._accessible_description = ""
        self.hidden = False

    def hide(self) -> None:
        self.hidden = True

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
        return True


class UserPresetsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _build_widgets(self, *, on_preset_list_action=None):
        parent = _PageHost()
        widgets = build_user_presets_page_shell(
            parent=parent,
            tr_fn=lambda _key, default: default,
            tokens=get_theme_tokens(),
            strong_body_label_cls=StrongBodyLabel,
            line_edit_cls=LineEdit,
            primary_tool_button_cls=PrimaryToolButton,
            tr_prefix="page.user_presets",
            delegate_language_scope="user_presets",
            delegate_help_name_role="helpName",
            fluent_icon=FluentIcon,
            get_cached_qta_pixmap_fn=get_cached_qta_pixmap,
            on_open_new_configs_post=lambda: None,
            on_create_clicked=lambda: None,
            on_import_clicked=lambda: None,
            on_open_folder_clicked=lambda: None,
            on_reset_all_presets_clicked=lambda: None,
            on_open_presets_info=lambda: None,
            on_info_clicked=lambda: None,
            on_preset_search_text_changed=lambda _text: None,
            on_activate_preset=lambda _index: None,
            on_move_preset_by_step=lambda *_args: None,
            on_item_dropped=lambda *_args: None,
            on_preset_context_requested=lambda *_args: None,
            on_folder_context_requested=lambda *_args: None,
            on_background_context_requested=lambda *_args: None,
            on_preset_list_action=on_preset_list_action or (lambda *_args: None),
            ui_language="ru",
        )
        return parent, widgets

    def _dialog_parent(self) -> QWidget:
        parent = QWidget()
        parent.resize(640, 480)
        parent.show()
        self.addCleanup(parent.deleteLater)
        return parent

    def test_toolbar_controls_have_screen_reader_text(self) -> None:
        _parent, widgets = self._build_widgets()

        self._assert_accessibility(widgets)

    def test_language_refresh_keeps_screen_reader_text(self) -> None:
        parent, widgets = self._build_widgets()

        apply_user_presets_language(
            tr_fn=lambda _key, default: default,
            configs_title_label=widgets.configs_title_label,
            get_configs_btn=widgets.get_configs_btn,
            create_btn=widgets.create_btn,
            import_btn=widgets.import_btn,
            open_folder_btn=widgets.open_folder_btn,
            reset_all_btn=widgets.reset_all_btn,
            presets_info_btn=widgets.presets_info_btn,
            info_btn=widgets.info_btn,
            preset_search_input=widgets.preset_search_input,
            presets_list=widgets.presets_list,
            presets_delegate=widgets.presets_delegate,
            ui_language="ru",
            viewport=parent.viewport(),
            layout=parent.layout,
            toolbar_layout=widgets.toolbar_layout,
            refresh_presets_view_from_cache_fn=lambda: None,
            apply_mode_labels_fn=lambda: None,
            tr_prefix="page.user_presets",
        )

        self._assert_accessibility(widgets)

    def test_preset_list_opens_selected_preset_menu_from_keyboard(self) -> None:
        from ui.presets_menu.model import PresetListModel
        from ui.presets_menu.view import LinkedWheelListView

        model = PresetListModel()
        model.set_rows(
            [
                {
                    "kind": "preset",
                    "name": "Default",
                    "file_name": "Default.txt",
                    "folder_key": "common",
                }
            ]
        )
        view = LinkedWheelListView()
        self.addCleanup(view.deleteLater)
        view.setModel(model)
        view.setCurrentIndex(model.index(0, 0))
        requested: list[str] = []
        view.preset_context_requested.connect(lambda name, _point: requested.append(name))

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Menu), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, ["Default.txt"])

    def test_preset_list_toggles_selected_folder_from_keyboard(self) -> None:
        from ui.presets_menu.model import PresetListModel
        from ui.presets_menu.view import LinkedWheelListView

        model = PresetListModel()
        model.set_rows(
            [
                {
                    "kind": "folder",
                    "name": "Игры",
                    "folder_key": "games",
                    "count": 2,
                    "is_collapsed": True,
                }
            ]
        )
        view = LinkedWheelListView()
        self.addCleanup(view.deleteLater)
        view.setModel(model)
        view.setCurrentIndex(model.index(0, 0))
        requested: list[str] = []
        view.folder_toggle_requested.connect(requested.append)

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Return), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, ["games"])

    def test_preset_list_activates_selected_preset_with_space(self) -> None:
        from ui.presets_menu.model import PresetListModel
        from ui.presets_menu.view import LinkedWheelListView

        model = PresetListModel()
        model.set_rows(
            [
                {
                    "kind": "preset",
                    "name": "Default",
                    "file_name": "Default.txt",
                }
            ]
        )
        view = LinkedWheelListView()
        self.addCleanup(view.deleteLater)
        view.setModel(model)
        view.setCurrentIndex(model.index(0, 0))
        requested: list[str] = []
        view.preset_activated.connect(requested.append)

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, ["Default.txt"])

    def test_preset_search_enter_activates_current_preset(self) -> None:
        parent, widgets = self._build_widgets()
        self.addCleanup(parent.deleteLater)
        widgets.presets_model.set_rows(
            [
                {
                    "kind": "preset",
                    "name": "Default",
                    "file_name": "Default.txt",
                }
            ]
        )
        widgets.presets_list.setCurrentIndex(widgets.presets_model.index(0, 0))
        requested: list[str] = []
        widgets.presets_list.preset_activated.connect(requested.append)
        parent.show()
        self._app.processEvents()
        widgets.preset_search_input.setFocus()
        self._app.processEvents()

        QTest.keyClick(widgets.preset_search_input, Qt.Key.Key_Return)
        self._app.processEvents()

        self.assertIs(self._app.focusWidget(), widgets.presets_list)
        self.assertEqual(requested, ["Default.txt"])

    def test_preset_search_arrow_down_moves_focus_to_preset_list(self) -> None:
        parent, widgets = self._build_widgets()
        self.addCleanup(parent.deleteLater)
        widgets.presets_model.set_rows(
            [
                {
                    "kind": "preset",
                    "name": "Default",
                    "file_name": "Default.txt",
                },
                {
                    "kind": "preset",
                    "name": "Gaming",
                    "file_name": "Gaming.txt",
                },
            ]
        )
        widgets.presets_list.setCurrentIndex(widgets.presets_model.index(0, 0))
        parent.show()
        self._app.processEvents()
        widgets.preset_search_input.setFocus()
        self._app.processEvents()

        QTest.keyClick(widgets.preset_search_input, Qt.Key.Key_Down)
        self._app.processEvents()

        self.assertIs(self._app.focusWidget(), widgets.presets_list)
        self.assertEqual(widgets.presets_list.currentIndex().row(), 1)

    def test_preset_list_navigation_does_not_use_native_selection_state(self) -> None:
        parent, widgets = self._build_widgets()
        self.addCleanup(parent.deleteLater)
        widgets.presets_model.set_rows(
            [
                {
                    "kind": "preset",
                    "name": "Default",
                    "file_name": "Default.txt",
                },
                {
                    "kind": "preset",
                    "name": "Gaming",
                    "file_name": "Gaming.txt",
                },
            ]
        )
        widgets.presets_list.setCurrentIndex(widgets.presets_model.index(0, 0))

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Down), Qt.KeyboardModifier.NoModifier)
        widgets.presets_list.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(widgets.presets_list.selectionMode(), QAbstractItemView.SelectionMode.NoSelection)
        self.assertEqual(widgets.presets_list.currentIndex().row(), 1)
        self.assertEqual(widgets.presets_list.selectedIndexes(), [])
        self.assertIn(
            "Список пользовательских пресетов: Gaming",
            widgets.presets_list.property("screenReaderStateText"),
        )

    def test_preset_list_toggles_selected_folder_with_space(self) -> None:
        from ui.presets_menu.model import PresetListModel
        from ui.presets_menu.view import LinkedWheelListView

        model = PresetListModel()
        model.set_rows(
            [
                {
                    "kind": "folder",
                    "name": "Игры",
                    "folder_key": "games",
                    "count": 2,
                    "is_collapsed": True,
                }
            ]
        )
        view = LinkedWheelListView()
        self.addCleanup(view.deleteLater)
        view.setModel(model)
        view.setCurrentIndex(model.index(0, 0))
        requested: list[str] = []
        view.folder_toggle_requested.connect(requested.append)

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, ["games"])

    def test_preset_list_updates_screen_reader_text_when_current_row_changes(self) -> None:
        from ui.presets_menu.model import PresetListModel
        from ui.presets_menu.view import LinkedWheelListView

        model = PresetListModel()
        model.set_rows(
            [
                {
                    "kind": "preset",
                    "name": "Default",
                    "file_name": "Default.txt",
                    "is_active": True,
                    "is_builtin": True,
                    "folder_name": "Общие",
                    "is_pinned": True,
                    "rating": 9,
                },
                {
                    "kind": "folder",
                    "name": "Игры",
                    "folder_key": "games",
                    "count": 2,
                    "is_collapsed": True,
                },
            ]
        )
        view = LinkedWheelListView()
        self.addCleanup(view.deleteLater)
        view.set_screen_reader_list_name("Список пользовательских пресетов")
        view.setModel(model)

        view.setCurrentIndex(model.index(0, 0))

        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список пользовательских пресетов: Default, активный пресет, встроенный, "
            "папка: Общие, закреплённый, оценка 9. Нажмите Enter или Пробел, чтобы открыть preset.",
        )

        view.setCurrentIndex(model.index(1, 0))

        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список пользовательских пресетов: Папка Игры, 2 пресета, свернута. "
            "Нажмите Enter или Пробел, чтобы свернуть или развернуть папку.",
        )

    def test_preset_page_wires_keyboard_folder_toggle_to_action_handler(self) -> None:
        requested: list[tuple[str, str]] = []
        _parent, widgets = self._build_widgets(on_preset_list_action=lambda action, name: requested.append((action, name)))
        widgets.presets_model.set_rows(
            [
                {
                    "kind": "folder",
                    "name": "Игры",
                    "folder_key": "games",
                    "count": 2,
                    "is_collapsed": True,
                }
            ]
        )
        widgets.presets_list.setCurrentIndex(widgets.presets_model.index(0, 0))

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Return), Qt.KeyboardModifier.NoModifier)
        widgets.presets_list.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, [("toggle_folder", "games")])

    def test_info_dialog_close_button_has_screen_reader_text(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._config = SimpleNamespace(tr_prefix="page.user_presets")
        page._tr = lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default
        page.window = lambda: None
        _MessageBox.instances = []

        with patch("presets.ui.common.user_presets_page.MessageBox", _MessageBox):
            UserPresetsPageBase._on_info_clicked(page)

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Закрыть справку о пресетах")
        self.assertIn("Закрывает окно справки", dialog.yesButton.accessibleDescription())
        self.assertTrue(dialog.cancelButton.hidden)
        self.assertTrue(dialog.exec_called)

    def test_create_preset_dialog_has_screen_reader_text(self) -> None:
        dialog = CreatePresetDialog([], self._dialog_parent())
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.nameEdit.accessibleName(), "Название нового пресета")
        self.assertIn("Например Игры", dialog.nameEdit.accessibleDescription())
        if hasattr(dialog, "_source_seg"):
            self.assertEqual(dialog._source_seg.accessibleName(), "Основа нового пресета, выбрано: Текущий пресет")
            self.assertEqual(
                dialog._source_seg.property("screenReaderStateText"),
                "Основа нового пресета, выбрано: Текущий пресет",
            )
            self.assertIn("Выберите", dialog._source_seg.accessibleDescription())
            current_item = dialog._source_seg.items["current"]
            standard_item = dialog._source_seg.items["standard"]
            self.assertEqual(
                current_item.accessibleName(),
                "Основа нового пресета: Текущий пресет, выбрано",
            )
            self.assertEqual(
                standard_item.accessibleName(),
                "Основа нового пресета: Встроенный пресет, не выбрано",
            )
            dialog._source_seg.setCurrentItem("standard")
            self.assertEqual(dialog._source_seg.accessibleName(), "Основа нового пресета, выбрано: Встроенный пресет")
            self.assertEqual(
                dialog._source_seg.property("screenReaderStateText"),
                "Основа нового пресета, выбрано: Встроенный пресет",
            )
            self.assertEqual(
                current_item.accessibleName(),
                "Основа нового пресета: Текущий пресет, не выбрано",
            )
            self.assertEqual(
                standard_item.accessibleName(),
                "Основа нового пресета: Встроенный пресет, выбрано",
            )
        self.assertEqual(dialog.yesButton.accessibleName(), "Создать пресет")
        self.assertEqual(dialog.yesButton.property("screenReaderStateText"), "Создать пресет")
        self.assertIn("Сохраняет текущие настройки", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить создание пресета")
        self.assertEqual(dialog.cancelButton.property("screenReaderStateText"), "Отменить создание пресета")

        self.assertFalse(dialog.validate())

        self.assertEqual(dialog.warningLabel.accessibleName(), "Ошибка: Введите название.")
        self.assertEqual(dialog.warningLabel.property("screenReaderStateText"), "Ошибка: Введите название.")

    def test_rename_preset_dialog_has_screen_reader_text(self) -> None:
        dialog = RenamePresetDialog("Дом", ["Дом"], self._dialog_parent())
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.nameEdit.accessibleName(), "Новое название пресета")
        self.assertIn("Текущее имя: Дом", dialog.nameEdit.accessibleDescription())
        self.assertEqual(dialog.yesButton.accessibleName(), "Переименовать пресет")
        self.assertEqual(dialog.yesButton.property("screenReaderStateText"), "Переименовать пресет")
        self.assertIn("Меняет имя пресета", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить переименование пресета")
        self.assertEqual(dialog.cancelButton.property("screenReaderStateText"), "Отменить переименование пресета")

    def test_preset_name_dialog_clear_buttons_do_not_take_tab_focus(self) -> None:
        dialogs = [
            CreatePresetDialog([], self._dialog_parent()),
            RenamePresetDialog("Дом", ["Дом"], self._dialog_parent()),
        ]
        for dialog in dialogs:
            self.addCleanup(dialog.deleteLater)
            dialog.nameEdit.setText("Дом")
            dialog.show()
        self._app.processEvents()

        for dialog in dialogs:
            with self.subTest(name=dialog.nameEdit.accessibleName()):
                buttons = [
                    child
                    for child in dialog.nameEdit.findChildren(object)
                    if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
                    and hasattr(child, "setFocusPolicy")
                ]
                self.assertTrue(buttons)
                self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_reset_presets_dialog_has_screen_reader_text(self) -> None:
        dialog = ResetAllPresetsDialog(self._dialog_parent())
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.yesButton.accessibleName(), "Вернуть встроенные пресеты")
        self.assertEqual(dialog.yesButton.property("screenReaderStateText"), "Вернуть встроенные пресеты")
        self.assertIn("Изменения во встроенных пресетах будут потеряны", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить возврат встроенных пресетов")
        self.assertEqual(
            dialog.cancelButton.property("screenReaderStateText"),
            "Отменить возврат встроенных пресетов",
        )

    def test_user_preset_help_text_explains_preset_file_and_wiki(self) -> None:
        for prefix in ("page.winws1_user_presets", "page.winws2_user_presets"):
            with self.subTest(prefix=prefix):
                body = tr(f"{prefix}.info.body", language="ru")

                self.assertIn(".txt", body)
                self.assertIn("@<config_file>", body)
                self.assertIn("%AppData%\\ZapretTwoDev\\preset-zapret2.txt", body)
                self.assertIn("https://publish.obsidian.md/zapret/Privacy/Zapret2/preset", body)
                self.assertIn("прямой запуск", body)

    def _assert_accessibility(self, widgets) -> None:
        expected = {
            widgets.get_configs_btn: ("Открыть GitHub Discussions с конфигами", "Обменивайтесь пресетами"),
            widgets.create_btn: ("Создать новый пресет", "Создать новый пресет"),
            widgets.import_btn: ("Импортировать пресет из файла", "Импорт пресета из файла"),
            widgets.open_folder_btn: ("Открыть папку пресетов", "Открыть папку, где лежат ваши пресеты"),
            widgets.reset_all_btn: ("Вернуть встроенные пресеты", "изменения во встроенных пресетах будут потеряны"),
            widgets.info_btn: ("Показать справку о пресетах", "Что это такое"),
            widgets.preset_search_input: ("Поиск пресетов", "Поиск пресетов по имени"),
            widgets.presets_list: (
                "Список пользовательских пресетов: список пока загружается",
                "Стрелки выбирают пресет или папку, Enter или Пробел активирует пресет или сворачивает и разворачивает папку, PageUp и PageDown перемещают пресет, клавиша меню открывает действия",
            ),
        }
        self.assertTrue(widgets.presets_info_btn.isHidden())
        for widget, (name, description) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(widget.accessibleName(), name)
                self.assertIn(description, widget.accessibleDescription())
                self.assertEqual(widget.property("screenReaderStateText"), name)

        search_description = widgets.preset_search_input.accessibleDescription()
        self.assertIn("После ввода перейдите в список клавишей Tab", search_description)
        self.assertIn("или нажмите Стрелка вниз", search_description)
        self.assertIn("выберите пресет стрелками вверх и вниз", search_description)
        self.assertIn("нажмите Enter или Пробел", search_description)
        search_buttons = [
            child
            for child in widgets.preset_search_input.findChildren(object)
            if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
            and hasattr(child, "setFocusPolicy")
        ]
        self.assertTrue(search_buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in search_buttons))
        self.assertEqual(
            widgets.presets_list.property("screenReaderStateText"),
            "Список пользовательских пресетов: список пока загружается",
        )


if __name__ == "__main__":
    unittest.main()
