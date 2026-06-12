from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from hosts.ui.page import HostsPage
from hosts.ui.sections_build import build_hosts_status_section
from hosts.ui.sections_build import build_hosts_adobe_section
from qfluentwidgets import SwitchButton


class _DialogButton:
    def __init__(self) -> None:
        self._text = ""
        self._accessible_name = ""
        self._accessible_description = ""
        self._properties = {}

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

    def property(self, name: str) -> object:  # noqa: A003
        return self._properties.get(name)

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        self._properties[name] = value


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
        self.assertEqual(
            widgets.clear_button.property("screenReaderStateText"),
            "Очистить hosts",
        )
        self.assertIn("Удаляет активные домены", widgets.clear_button.accessibleDescription())
        self.assertEqual(widgets.open_hosts_button.accessibleName(), "Открыть файл hosts")
        self.assertEqual(
            widgets.open_hosts_button.property("screenReaderStateText"),
            "Открыть файл hosts",
        )
        self.assertIn("Открывает системный файл hosts", widgets.open_hosts_button.accessibleDescription())

    def test_language_refresh_updates_status_button_screen_reader_state(self) -> None:
        from hosts.ui.page_lifecycle_helpers import apply_hosts_page_language

        clear_btn = _DialogButton()
        open_btn = _DialogButton()

        apply_hosts_page_language(
            tr_fn=lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default,
            clear_btn=clear_btn,
            open_hosts_button=open_btn,
            info_text_label=None,
            browser_warning_label=None,
            adobe_desc_label=None,
            adobe_title_label=None,
            startup_initialized=False,
            applying=False,
            rebuild_services_selectors_fn=lambda: None,
            check_hosts_access_fn=lambda: None,
            update_ui_fn=lambda: None,
        )

        self.assertEqual(clear_btn.accessibleName(), "Очистить hosts")
        self.assertEqual(clear_btn.property("screenReaderStateText"), "Очистить hosts")
        self.assertIn("Удаляет активные домены", clear_btn.accessibleDescription())
        self.assertEqual(open_btn.accessibleName(), "Открыть файл hosts")
        self.assertEqual(open_btn.property("screenReaderStateText"), "Открыть файл hosts")
        self.assertIn("Открывает системный файл hosts", open_btn.accessibleDescription())

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
        self.assertEqual(active_widgets.card.property("screenReaderStateText"), "Статус hosts: Активно 3 доменов")

        self.assertEqual(inactive_widgets.status_label.accessibleName(), "Статус hosts: Нет активных")
        self.assertEqual(inactive_widgets.status_dot.accessibleName(), "Индикатор hosts: нет активных доменов")
        self.assertEqual(inactive_widgets.card.accessibleName(), "Статус hosts: Нет активных")
        self.assertEqual(inactive_widgets.card.property("screenReaderStateText"), "Статус hosts: Нет активных")

    def test_runtime_status_update_refreshes_screen_reader_state(self) -> None:
        page = HostsPage.__new__(HostsPage)
        page.status_dot = QLabel("●")
        page.status_label = QLabel("Нет активных")
        page.status_card = QWidget()
        page.service_combos = {}
        page.adobe_switch = SwitchButton()
        page._adobe_active = False
        page._update_profile_row_visual = Mock()
        page._log_ui_timing = Mock()
        page._tr = lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default

        HostsPage._apply_hosts_runtime_state_to_ui(
            page,
            SimpleNamespace(active_domains={"one.example", "two.example"}, adobe_active=True),
        )

        self.assertEqual(page.status_label.text(), "Активно 2 доменов")
        self.assertEqual(page.status_label.accessibleName(), "Статус hosts: Активно 2 доменов")
        self.assertEqual(
            page.status_label.property("screenReaderStateText"),
            "Статус hosts: Активно 2 доменов",
        )
        self.assertEqual(page.status_dot.accessibleName(), "Индикатор hosts: есть активные домены")
        self.assertEqual(page.status_card.accessibleName(), "Статус hosts: Активно 2 доменов")
        self.assertEqual(page.status_card.property("screenReaderStateText"), "Статус hosts: Активно 2 доменов")

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

    def test_adobe_switch_works_from_keyboard(self) -> None:
        events: list[bool] = []
        widgets = build_hosts_adobe_section(
            tr_fn=lambda _key, default, **_kwargs: default,
            adobe_active=False,
            on_toggle_adobe=events.append,
            switch_button_cls=SwitchButton,
        )

        self.assertEqual(widgets.switch.focusPolicy(), Qt.FocusPolicy.StrongFocus)

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widgets.switch, event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(events, [True])
        self.assertEqual(widgets.switch.accessibleName(), "Блокировка Adobe, включено")

    def test_clear_hosts_confirmation_buttons_are_named_for_screen_reader(self) -> None:
        page = HostsPage.__new__(HostsPage)
        page._applying = False
        page._clear_hosts = Mock()
        page._tr = lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default
        page.window = lambda: None
        _MessageBox.instances = []

        with patch("hosts.ui.page.MessageBox", _MessageBox):
            HostsPage._on_clear_clicked(page)

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Очистить записи ZapretGUI из hosts")
        self.assertIn("Будет удалён только блок записей ZapretGUI", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить очистку hosts")
        self.assertTrue(dialog.exec_called)
        page._clear_hosts.assert_not_called()


if __name__ == "__main__":
    unittest.main()
