from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, LineEdit, PrimaryToolButton, StrongBodyLabel

from presets.ui.common.user_presets_build import build_user_presets_page_shell
from presets.ui.common.user_presets_dialogs import CreatePresetDialog, RenamePresetDialog, ResetAllPresetsDialog
from presets.ui.common.user_presets_page_lifecycle import apply_user_presets_language
from ui.theme import get_cached_qta_pixmap, get_theme_tokens


class _PageHost(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.resize(1000, 600)
        self.layout = QVBoxLayout(self)

    def viewport(self):  # noqa: ANN201
        return self


class UserPresetsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _build_widgets(self):
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
            on_preset_list_action=lambda *_args: None,
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
            dialog._source_seg.setCurrentItem("standard")
            self.assertEqual(dialog._source_seg.accessibleName(), "Основа нового пресета, выбрано: Встроенный пресет")
            self.assertEqual(
                dialog._source_seg.property("screenReaderStateText"),
                "Основа нового пресета, выбрано: Встроенный пресет",
            )
        self.assertEqual(dialog.yesButton.accessibleName(), "Создать пресет")
        self.assertIn("Сохраняет текущие настройки", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить создание пресета")

        self.assertFalse(dialog.validate())

        self.assertEqual(dialog.warningLabel.accessibleName(), "Ошибка: Введите название.")
        self.assertEqual(dialog.warningLabel.property("screenReaderStateText"), "Ошибка: Введите название.")

    def test_rename_preset_dialog_has_screen_reader_text(self) -> None:
        dialog = RenamePresetDialog("Дом", ["Дом"], self._dialog_parent())
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.nameEdit.accessibleName(), "Новое название пресета")
        self.assertIn("Текущее имя: Дом", dialog.nameEdit.accessibleDescription())
        self.assertEqual(dialog.yesButton.accessibleName(), "Переименовать пресет")
        self.assertIn("Меняет имя пресета", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить переименование пресета")

    def test_reset_presets_dialog_has_screen_reader_text(self) -> None:
        dialog = ResetAllPresetsDialog(self._dialog_parent())
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.yesButton.accessibleName(), "Вернуть встроенные пресеты")
        self.assertIn("Изменения во встроенных пресетах будут потеряны", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить возврат встроенных пресетов")

    def _assert_accessibility(self, widgets) -> None:
        expected = {
            widgets.get_configs_btn: ("Открыть GitHub Discussions с конфигами", "Обменивайтесь пресетами"),
            widgets.create_btn: ("Создать новый пресет", "Создать новый пресет"),
            widgets.import_btn: ("Импортировать пресет из файла", "Импорт пресета из файла"),
            widgets.open_folder_btn: ("Открыть папку пресетов", "Открыть папку, где лежат ваши пресеты"),
            widgets.reset_all_btn: ("Вернуть встроенные пресеты", "изменения во встроенных пресетах будут потеряны"),
            widgets.presets_info_btn: ("Открыть вики по пресетам", "Вики по пресетам"),
            widgets.info_btn: ("Показать справку о пресетах", "Что это такое"),
            widgets.preset_search_input: ("Поиск пресетов", "Поиск пресетов по имени"),
            widgets.presets_list: (
                "Список пользовательских пресетов",
                "Стрелки выбирают пресет, Enter делает выбранный пресет активным, PageUp и PageDown перемещают пресет, клавиша меню открывает действия",
            ),
        }
        for widget, (name, description) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(widget.accessibleName(), name)
                self.assertIn(description, widget.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
