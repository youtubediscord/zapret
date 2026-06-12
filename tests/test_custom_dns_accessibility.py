from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QWidget
from qfluentwidgets import BodyLabel, LineEdit, PushButton, StrongBodyLabel

from dns.ui.dns_build import build_auto_dns_ui, build_custom_dns_ui
from dns.ui.custom_dns_dialog import CustomDnsDialog
from dns.ui.selection import set_dns_card_selected


class CustomDnsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_custom_dns_row_has_no_inline_inputs_or_apply_button(self) -> None:
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

        self.assertEqual(widgets.primary_input.text(), "")
        self.assertEqual(widgets.secondary_input.text(), "")
        self.assertIsNone(widgets.apply_button)
        self.assertIsNone(widgets.indicator)
        self.assertTrue(hasattr(widgets.card, "set_selected"))
        self.assertEqual(len(widgets.card.findChildren(LineEdit)), 0)
        self.assertEqual(len(widgets.card.findChildren(PushButton)), 0)
        self.assertIn("кнопку", widgets.card.accessibleDescription())

        set_dns_card_selected(widgets.card, True)

        self.assertTrue(widgets.card.property("selected"))
        self.assertIn("border-left", widgets.card.styleSheet())
        self.assertIn("background-color", widgets.card.styleSheet())

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

        self.assertIsNone(widgets.indicator)
        self.assertTrue(hasattr(widgets.card, "set_selected"))
        self.assertTrue(widgets.card.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
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

    def test_custom_dns_dialog_input_clear_buttons_do_not_take_tab_focus(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        dialog = CustomDnsDialog(parent, servers=[])
        self.addCleanup(dialog.deleteLater)
        dialog.nameEdit.setText("Мой DNS")
        dialog.primaryEdit.setText("8.8.8.8")
        dialog.secondaryEdit.setText("1.1.1.1")
        dialog.show()
        self._app.processEvents()

        for line_edit in (dialog.nameEdit, dialog.primaryEdit, dialog.secondaryEdit):
            with self.subTest(name=line_edit.accessibleName()):
                buttons = [
                    child
                    for child in line_edit.findChildren(object)
                    if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
                    and hasattr(child, "setFocusPolicy")
                ]
                self.assertTrue(buttons)
                self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))


class _Card(QWidget):
    def add_layout(self, layout) -> None:
        self.setLayout(layout)


if __name__ == "__main__":
    unittest.main()
