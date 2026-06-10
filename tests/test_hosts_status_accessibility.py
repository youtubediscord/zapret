from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from hosts.ui.sections_build import build_hosts_status_section
from hosts.ui.sections_build import build_hosts_adobe_section
from qfluentwidgets import SwitchButton


class HostsStatusAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_status_buttons_have_screen_reader_text(self) -> None:
        widgets = build_hosts_status_section(
            tr_fn=lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default,
            active_count=3,
            on_clear_clicked=lambda: None,
            on_open_hosts_file=lambda: None,
        )

        self.assertEqual(widgets.clear_button.accessibleName(), "Очистить hosts")
        self.assertIn("Удаляет активные домены", widgets.clear_button.accessibleDescription())
        self.assertEqual(widgets.open_hosts_button.accessibleName(), "Открыть файл hosts")
        self.assertIn("Открывает системный файл hosts", widgets.open_hosts_button.accessibleDescription())

    def test_status_state_is_text_for_screen_reader(self) -> None:
        active_widgets = build_hosts_status_section(
            tr_fn=lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default,
            active_count=3,
            on_clear_clicked=lambda: None,
            on_open_hosts_file=lambda: None,
        )
        inactive_widgets = build_hosts_status_section(
            tr_fn=lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default,
            active_count=0,
            on_clear_clicked=lambda: None,
            on_open_hosts_file=lambda: None,
        )

        self.assertEqual(active_widgets.status_label.accessibleName(), "Статус hosts: Активно 3 доменов")
        self.assertEqual(active_widgets.status_dot.accessibleName(), "Индикатор hosts: есть активные домены")
        self.assertEqual(active_widgets.card.accessibleName(), "Статус hosts: Активно 3 доменов")

        self.assertEqual(inactive_widgets.status_label.accessibleName(), "Статус hosts: Нет активных")
        self.assertEqual(inactive_widgets.status_dot.accessibleName(), "Индикатор hosts: нет активных доменов")
        self.assertEqual(inactive_widgets.card.accessibleName(), "Статус hosts: Нет активных")

    def test_adobe_switch_reads_current_state(self) -> None:
        widgets = build_hosts_adobe_section(
            tr_fn=lambda _key, default, **_kwargs: default,
            adobe_active=False,
            on_toggle_adobe=lambda _checked: None,
            switch_button_cls=SwitchButton,
        )

        self.assertEqual(widgets.switch.accessibleName(), "Блокировка Adobe, выключено")
        self.assertEqual(widgets.switch.property("screenReaderStateText"), "Блокировка Adobe, выключено")
        self.assertIn("Блокирует серверы проверки активации Adobe", widgets.switch.accessibleDescription())

        widgets.switch.setChecked(True)

        self.assertEqual(widgets.switch.accessibleName(), "Блокировка Adobe, включено")
        self.assertEqual(widgets.switch.property("screenReaderStateText"), "Блокировка Adobe, включено")


if __name__ == "__main__":
    unittest.main()
