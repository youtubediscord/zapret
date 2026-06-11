from __future__ import annotations

import inspect
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, ComboBox, PushButton, StrongBodyLabel, TransparentToolButton

import log.ui.logs_build as logs_build
import log.ui.page as logs_page
import log.ui.runtime_helpers as runtime_helpers
import log.ui.send_build as send_build
from ui.fluent_widgets import QuickActionsBar, SettingsCard


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""
        self.style = ""
        self.accessible_name = ""
        self.properties = {}

    def setText(self, text: str) -> None:  # noqa: N802
        self.text = text

    def setStyleSheet(self, style: str) -> None:  # noqa: N802
        self.style = style

    def accessibleName(self) -> str:  # noqa: N802
        return self.accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self.accessible_name = text

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        self.properties[name] = value


class _FakeLogCombo:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []
        self.current_index = -1
        self.accessible_name = ""
        self.accessible_description = ""
        self.properties = {}

    def blockSignals(self, _blocked: bool) -> None:  # noqa: N802
        pass

    def clear(self) -> None:
        self.items.clear()
        self.current_index = -1

    def addItem(self, display: str, userData: str = "") -> None:  # noqa: N802
        self.items.append((display, userData))

    def count(self) -> int:
        return len(self.items)

    def itemData(self, index: int) -> str:  # noqa: N802
        return self.items[index][1]

    def itemText(self, index: int) -> str:  # noqa: N802
        return self.items[index][0]

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        self.current_index = int(index)

    def accessibleName(self) -> str:  # noqa: N802
        return self.accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self.accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self.accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self.accessible_description = str(text)

    def property(self, name: str) -> object:
        return self.properties.get(name)

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        self.properties[name] = value


class LogsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_tabs_read_current_section_for_screen_reader(self) -> None:
        page = logs_page.LogsPage(
            logs_feature=SimpleNamespace(get_current_log_file=lambda: ""),
            orchestra_feature=SimpleNamespace(),
        )
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.tabs_pivot.accessibleName(), "Вкладки страницы логов, выбрано: Логи")
        self.assertIn("Логи или Поддержка", page.tabs_pivot.accessibleDescription())

        page.tabs_pivot.setCurrentItem("send")

        self.assertEqual(page.tabs_pivot.accessibleName(), "Вкладки страницы логов, выбрано: Поддержка")
        self.assertEqual(
            page.tabs_pivot.property("screenReaderStateText"),
            "Вкладки страницы логов, выбрано: Поддержка",
        )

    def test_tabs_items_read_name_and_selection_for_screen_reader(self) -> None:
        page = logs_page.LogsPage(
            logs_feature=SimpleNamespace(get_current_log_file=lambda: ""),
            orchestra_feature=SimpleNamespace(),
        )
        self.addCleanup(page.deleteLater)

        self.assertEqual(
            page.tabs_pivot.items["logs"].accessibleName(),
            "Вкладки страницы логов: Логи, выбрано",
        )
        self.assertEqual(
            page.tabs_pivot.items["send"].accessibleName(),
            "Вкладки страницы логов: Поддержка, не выбрано",
        )

        page.tabs_pivot.setCurrentItem("send")

        self.assertEqual(
            page.tabs_pivot.items["logs"].accessibleName(),
            "Вкладки страницы логов: Логи, не выбрано",
        )
        self.assertEqual(
            page.tabs_pivot.items["send"].accessibleName(),
            "Вкладки страницы логов: Поддержка, выбрано",
        )

    def test_logs_build_assigns_screen_reader_names_to_core_controls(self) -> None:
        source = inspect.getsource(logs_build.build_logs_primary_tab_ui)
        secondary_source = inspect.getsource(logs_build.build_logs_secondary_panels_ui)

        self.assertIn("set_control_accessibility", source)
        self.assertIn("log_combo,", source)
        self.assertIn("refresh_btn,", source)
        self.assertIn("log_text,", source)
        self.assertIn("stats_label,", source)
        self.assertIn("set_control_accessibility", secondary_source)
        self.assertIn("clear_errors_btn,", secondary_source)
        self.assertIn("errors_text,", secondary_source)

    def test_log_combo_initial_description_explains_keyboard_selection(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        layout = QVBoxLayout(parent)

        widgets = logs_build.build_logs_primary_tab_ui(
            parent_layout=layout,
            content_parent=parent,
            ui_language="ru",
            tr_catalog_fn=lambda _key, language, default, **_kwargs: default,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            caption_label_cls=CaptionLabel,
            strong_body_label_cls=StrongBodyLabel,
            combo_box_cls=ComboBox,
            tool_button_cls=TransparentToolButton,
            push_button_cls=PushButton,
            text_edit_cls=QTextEdit,
            quick_actions_bar_cls=QuickActionsBar,
            qfont_cls=QFont,
            get_theme_tokens_fn=lambda: {},
            on_log_selected=lambda *_args: None,
            on_refresh=lambda: None,
            on_spin_tick=lambda: None,
            on_copy=lambda: None,
            on_clear_view=lambda: None,
            on_open_folder=lambda: None,
            refresh_timer_parent=parent,
        )

        self.assertEqual(widgets.log_combo.accessibleName(), "Выбор файла лога")
        self.assertIn("выберите файл стрелками вверх и вниз", widgets.log_combo.accessibleDescription())
        self.assertEqual(
            widgets.log_text.property("screenReaderStateText"),
            "Содержимое текущего лога: лог пока не загружен",
        )
        self.assertEqual(
            widgets.info_label.property("screenReaderStateText"),
            "Сообщение страницы логов: пока нет сообщений",
        )
        self.assertEqual(
            widgets.stats_label.property("screenReaderStateText"),
            "Статистика логов: пока нет данных",
        )

    def test_send_status_initial_state_is_text_for_screen_reader(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        layout = QVBoxLayout(parent)

        widgets = send_build.build_logs_send_tab(
            parent_layout=layout,
            ui_language="ru",
            tr_catalog_fn=lambda _key, language, default, **_kwargs: default,
            settings_card_cls=SettingsCard,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qlabel_cls=QLabel,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            strong_body_label_cls=StrongBodyLabel,
            push_button_cls=PushButton,
            quick_actions_bar_cls=QuickActionsBar,
            qta_module=None,
            get_theme_tokens_fn=lambda: {},
            on_prepare_support=lambda: None,
            on_open_folder=lambda: None,
        )

        self.assertEqual(
            widgets.send_status_label.property("screenReaderStateText"),
            "Статус подготовки обращения: пока обращение не подготовлено",
        )

    def test_errors_text_initial_state_is_text_for_screen_reader(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        layout = QVBoxLayout(parent)

        widgets = logs_build.build_logs_secondary_panels_ui(
            parent_layout=layout,
            ui_language="ru",
            tr_catalog_fn=lambda _key, language, default, **_kwargs: default,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qlabel_cls=QLabel,
            caption_label_cls=CaptionLabel,
            strong_body_label_cls=StrongBodyLabel,
            fluent_push_button_cls=PushButton,
            text_edit_cls=QTextEdit,
            qfont_cls=QFont,
            errors_text_min_height=52,
            errors_text_max_height=140,
            on_clear_errors=lambda: None,
            on_update_errors_height=lambda: None,
        )

        self.assertEqual(
            widgets.errors_text.accessibleName(),
            "Найденные ошибки и предупреждения: пока нет записей",
        )
        self.assertEqual(
            widgets.errors_text.property("screenReaderStateText"),
            "Найденные ошибки и предупреждения: пока нет записей",
        )

    def test_log_page_routes_info_text_through_screen_reader_state(self) -> None:
        source = inspect.getsource(logs_page.LogsPage)

        self.assertIn("def _set_info_text", source)
        self.assertIn("set_info_text_fn=self._set_info_text", source)
        self.assertIn("self._set_info_text(", source)

    def test_log_combo_accessible_name_includes_selected_file(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.log_combo = _FakeLogCombo()

        logs_page.LogsPage._apply_logs_list_state(
            page,
            SimpleNamespace(
                entries=[
                    {"display": "old.log", "path": "C:/Zapret/Dev/logs/old.log", "is_current": False, "index": 0},
                    {"display": "current.log", "path": "C:/Zapret/Dev/logs/current.log", "is_current": True, "index": 1},
                ],
            ),
            run_cleanup=False,
        )

        self.assertEqual(page.log_combo.accessible_name, "Выбор файла лога, выбрано: current.log")
        self.assertIn("Доступных файлов логов: 2.", page.log_combo.accessible_description)
        self.assertIn("выберите файл стрелками вверх и вниз", page.log_combo.accessible_description)
        self.assertEqual(
            page.log_combo.property("screenReaderStateText"),
            "Выбор файла лога, выбрано: current.log",
        )

    def test_log_combo_menu_items_are_named_for_screen_reader(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.log_combo = ComboBox()

        logs_page.LogsPage._apply_logs_list_state(
            page,
            SimpleNamespace(
                entries=[
                    {"display": "old.log", "path": "C:/Zapret/Dev/logs/old.log", "is_current": False, "index": 0},
                    {"display": "current.log", "path": "C:/Zapret/Dev/logs/current.log", "is_current": True, "index": 1},
                ],
            ),
            run_cleanup=False,
        )
        create_menu = getattr(page.log_combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)

        menu = create_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Выбор файла лога: old.log, не выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Выбор файла лога: current.log, выбран",
        )

    def test_log_combo_accessible_name_updates_after_keyboard_selection(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.current_log_file = "C:/Zapret/Dev/logs/old.log"
        page.log_combo = _FakeLogCombo()
        page.log_combo.addItem("old.log", "C:/Zapret/Dev/logs/old.log")
        page.log_combo.addItem("new.log", "C:/Zapret/Dev/logs/new.log")
        page._start_tail_worker = lambda: None

        logs_page.LogsPage._on_log_selected(page, 1)

        self.assertEqual(page.current_log_file, "C:/Zapret/Dev/logs/new.log")
        self.assertEqual(page.log_combo.accessible_name, "Выбор файла лога, выбрано: new.log")
        self.assertIn("Доступных файлов логов: 2.", page.log_combo.accessible_description)
        self.assertIn("выберите файл стрелками вверх и вниз", page.log_combo.accessible_description)
        self.assertEqual(
            page.log_combo.property("screenReaderStateText"),
            "Выбор файла лога, выбрано: new.log",
        )

    def test_send_status_label_updates_screen_reader_state(self) -> None:
        label = _FakeLabel()

        runtime_helpers.render_send_status_label(
            label=label,
            text="Архив поддержки готов",
            tone="neutral",
            theme_tokens=type("Tokens", (), {"accent_hex": "#0078d4", "is_light": True})(),
        )

        self.assertEqual(label.text, "Архив поддержки готов")
        self.assertEqual(label.accessible_name, "Архив поддержки готов")
        self.assertEqual(label.properties["screenReaderStateText"], "Архив поддержки готов")

    def test_error_count_updates_screen_reader_state(self) -> None:
        errors_text = type("ErrorsText", (), {"append": lambda self, text: None})()
        label = _FakeLabel()

        count = runtime_helpers.append_error(
            errors_text=errors_text,
            errors_count_label=label,
            tr_fn=lambda _key, default: default,
            current_count=0,
            text="RuntimeError: failed",
        )

        self.assertEqual(count, 1)
        self.assertEqual(label.accessible_name, "Ошибок: 1")
        self.assertEqual(label.properties["screenReaderStateText"], "Ошибок: 1")


if __name__ == "__main__":
    unittest.main()
