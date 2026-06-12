from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QWidget
from qfluentwidgets import BodyLabel, LineEdit, PushButton, StrongBodyLabel

from dns.ui.dns_build import build_auto_dns_ui, build_custom_dns_ui
from dns.ui.selection import set_dns_card_selected


class CustomDnsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_custom_dns_controls_have_screen_reader_text(self) -> None:
        widgets = build_custom_dns_ui(
            tr_fn=lambda _key, default: default,
            settings_card_cls=_Card,
            qhbox_layout_cls=QHBoxLayout,
            qframe_cls=QFrame,
            body_label_cls=BodyLabel,
            line_edit_cls=LineEdit,
            action_button_cls=PushButton,
            on_apply=lambda: None,
            indicator_off_qss="",
        )

        self.assertEqual(widgets.primary_input.accessibleName(), "Основной DNS сервер")
        self.assertIn("первый DNS сервер", widgets.primary_input.accessibleDescription())
        self.assertEqual(widgets.secondary_input.accessibleName(), "Дополнительный DNS сервер")
        self.assertIn("второй DNS сервер", widgets.secondary_input.accessibleDescription())
        self.assertEqual(widgets.apply_button.accessibleName(), "Применить свой DNS")
        self.assertEqual(
            widgets.apply_button.property("screenReaderStateText"),
            "Применить свой DNS",
        )
        self.assertIn("указанные DNS серверы", widgets.apply_button.accessibleDescription())

    def test_auto_dns_card_has_keyboard_selection_and_screen_reader_state(self) -> None:
        selected: list[str] = []

        widgets = build_auto_dns_ui(
            tr_fn=lambda _key, default: default,
            settings_card_cls=_Card,
            qhbox_layout_cls=QHBoxLayout,
            qframe_cls=QFrame,
            strong_body_label_cls=StrongBodyLabel,
            qlabel_cls=QLabel,
            qta_module=None,
            icon_color="#777777",
            indicator_off_qss="",
            on_select=lambda _event=None: selected.append("auto"),
        )

        self.assertEqual(widgets.card.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertEqual(widgets.card.accessibleName(), "DNS автоматически (DHCP), не выбран")
        self.assertEqual(
            widgets.card.property("screenReaderStateText"),
            "DNS автоматически (DHCP), не выбран",
        )
        self.assertIn("Enter или пробел", widgets.card.accessibleDescription())

        event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier)
        widgets.card.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(selected, ["auto"])

        set_dns_card_selected(widgets.card, True)

        self.assertEqual(
            widgets.card.property("screenReaderStateText"),
            "DNS автоматически (DHCP), выбран",
        )


class _Card(QWidget):
    def add_layout(self, layout) -> None:
        self.setLayout(layout)


if __name__ == "__main__":
    unittest.main()
