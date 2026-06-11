from __future__ import annotations

import inspect
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import log.ui.logs_build as logs_build
import log.ui.page as logs_page
import log.ui.runtime_helpers as runtime_helpers


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
        self.assertEqual(page.log_combo.accessible_description, "Доступных файлов логов: 2.")
        self.assertEqual(
            page.log_combo.property("screenReaderStateText"),
            "Выбор файла лога, выбрано: current.log",
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
        self.assertEqual(page.log_combo.accessible_description, "Доступных файлов логов: 2.")
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
