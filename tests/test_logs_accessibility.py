from __future__ import annotations

import inspect
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QSizePolicy, QTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, PushButton, StrongBodyLabel, TransparentToolButton

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

    def property(self, name: str) -> object:
        return self.properties.get(name)


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
        self.assertIn("Логи, Поддержка или Управление", page.tabs_pivot.accessibleDescription())

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
        self.assertEqual(
            page.tabs_pivot.items["manage"].accessibleName(),
            "Вкладки страницы логов: Управление, не выбрано",
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
        self.assertEqual(
            page.tabs_pivot.items["manage"].accessibleName(),
            "Вкладки страницы логов: Управление, не выбрано",
        )

    def test_logs_build_assigns_screen_reader_names_to_core_controls(self) -> None:
        source = inspect.getsource(logs_build.build_logs_primary_tab_ui)
        manage_source = inspect.getsource(logs_build.build_logs_management_tab_ui)
        secondary_source = inspect.getsource(logs_build.build_logs_secondary_panels_ui)

        self.assertIn("set_control_accessibility", source)
        self.assertIn("log_text,", source)
        self.assertIn("stats_label,", source)
        self.assertIn("set_control_accessibility", manage_source)
        self.assertIn("logs_table,", manage_source)
        self.assertIn("refresh_btn,", manage_source)
        self.assertIn("set_control_accessibility", secondary_source)
        self.assertIn("clear_errors_btn,", secondary_source)
        self.assertIn("errors_text,", secondary_source)

    def test_logs_management_tab_exposes_table_and_actions(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        layout = QVBoxLayout(parent)

        widgets = logs_build.build_logs_management_tab_ui(
            parent_layout=layout,
            content_parent=parent,
            ui_language="ru",
            tr_catalog_fn=lambda _key, language, default, **_kwargs: default,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            caption_label_cls=CaptionLabel,
            tool_button_cls=TransparentToolButton,
            push_button_cls=PushButton,
            table_widget_cls=logs_page.TableWidget,
            table_item_cls=logs_page.QTableWidgetItem,
            header_view_cls=logs_page.QHeaderView,
            quick_actions_bar_cls=QuickActionsBar,
            get_theme_tokens_fn=lambda: {},
            on_log_selected=lambda *_args: None,
            on_refresh=lambda: None,
            on_spin_tick=lambda: None,
            on_copy=lambda: None,
            on_clear_view=lambda: None,
            on_open_folder=lambda: None,
            refresh_timer_parent=parent,
        )

        self.assertEqual(widgets.logs_table.accessibleName(), "Таблица файлов логов: строки пока не загружены")
        self.assertIn("Выберите строку", widgets.logs_table.accessibleDescription())
        self.assertEqual(widgets.refresh_btn.accessibleName(), "Обновить список логов")
        self.assertEqual(widgets.refresh_btn.property("screenReaderStateText"), "Обновить список логов")
        self.assertIn("список файлов логов", widgets.refresh_btn.accessibleDescription())
        self.assertEqual(widgets.copy_btn.accessibleName(), "Копировать текущий лог")
        self.assertEqual(widgets.copy_btn.property("screenReaderStateText"), "Копировать текущий лог")
        self.assertEqual(widgets.clear_btn.accessibleName(), "Очистить окно просмотра лога")
        self.assertEqual(
            widgets.clear_btn.property("screenReaderStateText"),
            "Очистить окно просмотра лога",
        )
        self.assertEqual(widgets.folder_btn.accessibleName(), "Открыть папку логов")
        self.assertEqual(widgets.folder_btn.property("screenReaderStateText"), "Открыть папку логов")
        self.assertEqual(
            widgets.info_label.property("screenReaderStateText"),
            "Сообщение страницы логов: пока нет сообщений",
        )

    def test_logs_content_area_has_no_extra_header_and_more_room(self) -> None:
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
            text_edit_cls=QTextEdit,
            qfont_cls=QFont,
            get_theme_tokens_fn=lambda: {},
        )

        self.assertIsNone(getattr(widgets.log_card, "_title_label", None))
        self.assertGreaterEqual(widgets.log_text.minimumHeight(), 360)
        log_layout_item = widgets.log_card.main_layout.itemAt(0)
        self.assertIsNotNone(log_layout_item)
        log_layout = log_layout_item.layout()
        self.assertIsNotNone(log_layout)
        margins = log_layout.contentsMargins()
        self.assertEqual((margins.left(), margins.top(), margins.right(), margins.bottom()), (0, 0, 0, 0))
        self.assertEqual(widgets.log_card.sizePolicy().verticalPolicy(), QSizePolicy.Policy.Expanding)
        self.assertEqual(widgets.log_text.sizePolicy().verticalPolicy(), QSizePolicy.Policy.Expanding)
        self.assertEqual(layout.stretch(layout.indexOf(widgets.log_card)), 1)

        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.log_card = widgets.log_card
        page._controls_actions_title = None
        page._logs_secondary_initialized = False

        logs_page.LogsPage._retranslate_logs_tab(page)

        self.assertIsNone(getattr(widgets.log_card, "_title_label", None))

    def test_logs_action_buttons_keep_screen_reader_state_after_language_refresh(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.controls_card = None
        page.log_card = None
        page._controls_actions_title = None
        page.refresh_btn = TransparentToolButton()
        page.copy_btn = PushButton()
        page.clear_btn = PushButton()
        page.folder_btn = PushButton()
        page._logs_secondary_initialized = False

        self.addCleanup(page.refresh_btn.deleteLater)
        self.addCleanup(page.copy_btn.deleteLater)
        self.addCleanup(page.clear_btn.deleteLater)
        self.addCleanup(page.folder_btn.deleteLater)

        logs_page.LogsPage._retranslate_logs_tab(page)

        self.assertEqual(page.refresh_btn.accessibleName(), "Обновить список логов")
        self.assertEqual(page.refresh_btn.property("screenReaderStateText"), "Обновить список логов")
        self.assertEqual(page.copy_btn.accessibleName(), "Копировать текущий лог")
        self.assertEqual(page.copy_btn.property("screenReaderStateText"), "Копировать текущий лог")
        self.assertEqual(page.clear_btn.accessibleName(), "Очистить окно просмотра лога")
        self.assertEqual(page.clear_btn.property("screenReaderStateText"), "Очистить окно просмотра лога")
        self.assertEqual(page.folder_btn.accessibleName(), "Открыть папку логов")
        self.assertEqual(page.folder_btn.property("screenReaderStateText"), "Открыть папку логов")

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
        self.assertEqual(
            widgets.send_desc_label.property("screenReaderStateText"),
            (
                "Описание подготовки обращения: Нажмите кнопку, чтобы собрать ZIP из свежих логов, "
                "скопировать шаблон обращения и открыть GitHub Discussions."
            ),
        )
        self.assertEqual(
            widgets.send_info_label.property("screenReaderStateText"),
            (
                "Что будет подготовлено: Будет создан архив в папке logs/support_bundles. "
                "Шаблон обращения автоматически попадёт в буфер обмена."
            ),
        )
        self.assertEqual(
            widgets.orchestra_icon_label.accessibleName(),
            "Индикатор режима оркестратора: проверьте основной лог и файл orchestra",
        )
        self.assertEqual(
            widgets.orchestra_icon_label.property("screenReaderStateText"),
            "Индикатор режима оркестратора: проверьте основной лог и файл orchestra",
        )
        self.assertEqual(
            widgets.info_icon_label.accessibleName(),
            "Индикатор подготовки обращения: будет создан архив и скопирован шаблон",
        )
        self.assertEqual(
            widgets.info_icon_label.property("screenReaderStateText"),
            "Индикатор подготовки обращения: будет создан архив и скопирован шаблон",
        )
        self.assertEqual(widgets.send_log_btn.accessibleName(), "Подготовить обращение в поддержку")
        self.assertEqual(
            widgets.send_log_btn.property("screenReaderStateText"),
            "Подготовить обращение в поддержку",
        )
        self.assertIn("Собрать ZIP", widgets.send_log_btn.accessibleDescription())
        self.assertEqual(widgets.open_logs_folder_btn.accessibleName(), "Открыть папку логов и обращений")
        self.assertEqual(
            widgets.open_logs_folder_btn.property("screenReaderStateText"),
            "Открыть папку логов и обращений",
        )
        self.assertIn("support bundles", widgets.open_logs_folder_btn.accessibleDescription())

    def test_send_action_buttons_keep_screen_reader_state_after_language_refresh(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.send_card = None
        page._send_actions_title = None
        page._orchestra_text_label = QLabel()
        page.send_desc_label = QLabel()
        page.send_info_label = QLabel()
        page.send_log_btn = PushButton()
        page.open_logs_folder_btn = PushButton()

        self.addCleanup(page._orchestra_text_label.deleteLater)
        self.addCleanup(page.send_desc_label.deleteLater)
        self.addCleanup(page.send_info_label.deleteLater)
        self.addCleanup(page.send_log_btn.deleteLater)
        self.addCleanup(page.open_logs_folder_btn.deleteLater)

        logs_page.LogsPage._retranslate_send_tab(page)

        self.assertEqual(page.send_log_btn.accessibleName(), "Подготовить обращение в поддержку")
        self.assertEqual(
            page.send_log_btn.property("screenReaderStateText"),
            "Подготовить обращение в поддержку",
        )
        self.assertEqual(page.open_logs_folder_btn.accessibleName(), "Открыть папку логов и обращений")
        self.assertEqual(
            page.open_logs_folder_btn.property("screenReaderStateText"),
            "Открыть папку логов и обращений",
        )
        self.assertEqual(
            page.send_desc_label.property("screenReaderStateText"),
            (
                "Описание подготовки обращения: Нажмите кнопку, чтобы собрать ZIP из свежих логов, "
                "скопировать шаблон обращения и открыть GitHub Discussions."
            ),
        )
        self.assertEqual(
            page.send_info_label.property("screenReaderStateText"),
            (
                "Что будет подготовлено: Будет создан архив в папке logs/support_bundles. "
                "Шаблон обращения автоматически попадёт в буфер обмена."
            ),
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

    def test_log_page_info_text_updates_screen_reader_context(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.info_label = _FakeLabel()

        logs_page.LogsPage._set_info_text(page, "Лог скопирован")

        self.assertEqual(page.info_label.text, "Лог скопирован")
        self.assertEqual(page.info_label.accessible_name, "Сообщение страницы логов: Лог скопирован")
        self.assertEqual(
            page.info_label.property("screenReaderStateText"),
            "Сообщение страницы логов: Лог скопирован",
        )

    def test_log_page_stats_text_updates_screen_reader_context(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.stats_label = _FakeLabel()

        logs_page.LogsPage._set_stats_text(page, "Ошибок: 2")

        self.assertEqual(page.stats_label.text, "Ошибок: 2")
        self.assertEqual(page.stats_label.accessible_name, "Статистика логов: Ошибок: 2")
        self.assertEqual(
            page.stats_label.property("screenReaderStateText"),
            "Статистика логов: Ошибок: 2",
        )

    def test_logs_list_state_populates_management_table(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.logs_table = logs_page.TableWidget()
        page.info_label = _FakeLabel()
        page.current_log_file = ""
        self.addCleanup(page.logs_table.deleteLater)

        logs_page.LogsPage._apply_logs_list_state(
            page,
            SimpleNamespace(
                entries=[
                    {"display": "old.log", "path": "C:/Zapret/Dev/logs/old.log", "is_current": False, "index": 0},
                    {"display": "current.log", "path": "C:/Zapret/Dev/logs/current.log", "is_current": True, "index": 1},
                ],
                cleanup_deleted=0,
                cleanup_total=0,
                cleanup_errors=[],
            ),
            run_cleanup=False,
        )

        self.assertEqual(page.logs_table.rowCount(), 2)
        self.assertEqual(page.logs_table.item(0, 0).text(), "old.log")
        self.assertEqual(page.logs_table.item(0, 1).text(), "Старый")
        self.assertEqual(page.logs_table.item(1, 1).text(), "Текущий")
        self.assertEqual(page.logs_table.item(1, 0).data(Qt.ItemDataRole.UserRole), "C:/Zapret/Dev/logs/current.log")
        self.assertEqual(page.logs_table.currentRow(), 1)
        self.assertEqual(page.logs_table.accessibleName(), "Таблица файлов логов, выбрано: current.log")
        self.assertIn("Доступных файлов логов: 2.", page.logs_table.accessibleDescription())
        self.assertIn("Выберите строку", page.logs_table.accessibleDescription())
        self.assertEqual(
            page.logs_table.property("screenReaderStateText"),
            "Таблица файлов логов, выбрано: current.log",
        )

    def test_log_table_items_are_named_for_screen_reader(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.logs_table = logs_page.TableWidget()
        page.info_label = _FakeLabel()
        self.addCleanup(page.logs_table.deleteLater)

        logs_page.LogsPage._apply_logs_list_state(
            page,
            SimpleNamespace(
                entries=[
                    {"display": "old.log", "path": "C:/Zapret/Dev/logs/old.log", "is_current": False, "index": 0},
                    {"display": "current.log", "path": "C:/Zapret/Dev/logs/current.log", "is_current": True, "index": 1},
                ],
                cleanup_deleted=0,
                cleanup_total=0,
                cleanup_errors=[],
            ),
            run_cleanup=False,
        )

        self.assertEqual(
            page.logs_table.item(0, 0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Файл лога: old.log, Старый",
        )
        self.assertEqual(
            page.logs_table.item(1, 0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Файл лога: current.log, Текущий",
        )

    def test_log_table_selection_updates_current_file(self) -> None:
        page = logs_page.LogsPage.__new__(logs_page.LogsPage)
        page._ui_language = "ru"
        page.current_log_file = "C:/Zapret/Dev/logs/old.log"
        page.logs_table = logs_page.TableWidget()
        page.info_label = _FakeLabel()
        page._start_log_source = lambda: None
        self.addCleanup(page.logs_table.deleteLater)

        logs_page.LogsPage._apply_logs_list_state(
            page,
            SimpleNamespace(
                entries=[
                    {"display": "old.log", "path": "C:/Zapret/Dev/logs/old.log", "is_current": True, "index": 0},
                    {"display": "new.log", "path": "C:/Zapret/Dev/logs/new.log", "is_current": False, "index": 1},
                ],
                cleanup_deleted=0,
                cleanup_total=0,
                cleanup_errors=[],
            ),
            run_cleanup=False,
        )

        logs_page.LogsPage._on_log_table_cell_clicked(page, 1, 0)

        self.assertEqual(page.current_log_file, "C:/Zapret/Dev/logs/new.log")
        self.assertEqual(page.logs_table.accessibleName(), "Таблица файлов логов, выбрано: new.log")
        self.assertIn("Доступных файлов логов: 2.", page.logs_table.accessibleDescription())
        self.assertIn("Выберите строку", page.logs_table.accessibleDescription())
        self.assertEqual(
            page.logs_table.property("screenReaderStateText"),
            "Таблица файлов логов, выбрано: new.log",
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
