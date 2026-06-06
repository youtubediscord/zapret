from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import TransparentToolButton

from ui.widgets.notification_banner import NotificationBanner


class NotificationBannerAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_notification_banner_has_screen_reader_text(self) -> None:
        banner = NotificationBanner()

        banner.show_error("Не удалось запустить Zapret", auto_hide_ms=0)

        self.assertEqual(banner.accessibleName(), "Ошибка: Не удалось запустить Zapret")
        self.assertIn("уведомление", banner.accessibleDescription().lower())

    def test_close_button_has_screen_reader_name_and_description(self) -> None:
        banner = NotificationBanner()
        close_buttons = banner.findChildren(TransparentToolButton)

        self.assertEqual(len(close_buttons), 1)
        self.assertEqual(close_buttons[0].accessibleName(), "Закрыть уведомление")
        self.assertIn("скрывает", close_buttons[0].accessibleDescription().lower())


if __name__ == "__main__":
    unittest.main()
