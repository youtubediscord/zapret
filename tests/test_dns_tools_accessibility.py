from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets import PushButton

from dns.ui.tools_build import build_tools_card_ui
from ui.fluent_widgets import set_tooltip


class DnsToolsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_dns_tools_buttons_have_screen_reader_text(self) -> None:
        parent = QWidget()

        widgets = build_tools_card_ui(
            content_parent=parent,
            tr_fn=lambda _key, default: default,
            add_section_title_fn=lambda *_args, **_kwargs: None,
            setting_card_group_cls=_Group,
            quick_actions_bar_cls=_ActionsBar,
            action_button_cls=PushButton,
            qhbox_layout_cls=object,
            insert_widget_into_setting_card_group_fn=lambda group, _index, widget: group.layout.addWidget(widget),
            on_test=lambda: None,
            on_flush_dns=lambda: None,
            set_tooltip_fn=set_tooltip,
        )

        self.assertEqual(widgets.test_button.accessibleName(), "Проверить DNS и сайты")
        self.assertEqual(
            widgets.test_button.property("screenReaderStateText"),
            "Проверить DNS и сайты",
        )
        self.assertIn("популярных сайтов", widgets.test_button.accessibleDescription())
        self.assertEqual(widgets.flush_button.accessibleName(), "Сбросить DNS кэш Windows")
        self.assertEqual(
            widgets.flush_button.property("screenReaderStateText"),
            "Сбросить DNS кэш Windows",
        )
        self.assertIn("Очистить локальный кэш DNS Windows", widgets.flush_button.accessibleDescription())


class _Group(QWidget):
    def __init__(self, _title: str, parent=None) -> None:
        super().__init__(parent)
        self.layout = QVBoxLayout(self)


class _ActionsBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

    def add_buttons(self, buttons) -> None:
        for button in buttons:
            self.layout.addWidget(button)


if __name__ == "__main__":
    unittest.main()
