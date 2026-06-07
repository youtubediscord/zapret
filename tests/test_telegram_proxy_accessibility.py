import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, PrimaryPushButton, PushButton

from telegram_proxy.ui.build import build_telegram_proxy_diag_panel, build_telegram_proxy_logs_panel


class TelegramProxyAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _layout(self) -> QVBoxLayout:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        return QVBoxLayout(parent)

    def test_logs_panel_controls_are_named_for_screen_reader(self) -> None:
        widgets = build_telegram_proxy_logs_panel(
            self._layout(),
            push_button_cls=PushButton,
            on_copy_all_logs=lambda: None,
            on_open_log_file=lambda: None,
            on_clear_logs=lambda: None,
        )

        self.assertEqual(widgets.btn_copy_logs.accessibleName(), "Копировать лог Telegram Proxy")
        self.assertIn("копирует весь лог", widgets.btn_copy_logs.accessibleDescription().lower())
        self.assertEqual(widgets.btn_open_log_file.accessibleName(), "Открыть файл лога Telegram Proxy")
        self.assertIn("открывает файл", widgets.btn_open_log_file.accessibleDescription().lower())
        self.assertEqual(widgets.btn_clear_logs.accessibleName(), "Очистить лог Telegram Proxy")
        self.assertIn("очищает видимый лог", widgets.btn_clear_logs.accessibleDescription().lower())
        self.assertEqual(widgets.log_edit.accessibleName(), "Лог Telegram Proxy")
        self.assertIn("события подключений", widgets.log_edit.accessibleDescription())

    def test_diagnostics_panel_controls_are_named_for_screen_reader(self) -> None:
        widgets = build_telegram_proxy_diag_panel(
            self._layout(),
            caption_label_cls=CaptionLabel,
            primary_push_button_cls=PrimaryPushButton,
            push_button_cls=PushButton,
            on_run_diagnostics=lambda: None,
            on_copy_diag=lambda: None,
        )

        self.assertEqual(widgets.diag_desc_label.accessibleName(), "Описание диагностики Telegram Proxy")
        self.assertIn("Telegram DC", widgets.diag_desc_label.accessibleDescription())
        self.assertEqual(widgets.btn_run_diag.accessibleName(), "Запустить диагностику Telegram Proxy")
        self.assertIn("проверяет соединения", widgets.btn_run_diag.accessibleDescription().lower())
        self.assertEqual(widgets.btn_copy_diag.accessibleName(), "Копировать результат диагностики Telegram Proxy")
        self.assertIn("копирует результат", widgets.btn_copy_diag.accessibleDescription().lower())
        self.assertEqual(widgets.diag_edit.accessibleName(), "Результат диагностики Telegram Proxy")
        self.assertIn("подробный результат", widgets.diag_edit.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
