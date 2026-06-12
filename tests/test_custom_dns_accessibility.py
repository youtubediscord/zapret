from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QWidget
from qfluentwidgets import BodyLabel, LineEdit, PushButton

from dns.ui.dns_build import build_custom_dns_ui


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


class _Card(QWidget):
    def add_layout(self, layout) -> None:
        self.setLayout(layout)


if __name__ == "__main__":
    unittest.main()
