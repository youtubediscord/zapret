from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QWidget


class ClickableCardAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _press_key(self, widget, key: Qt.Key) -> None:
        event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        widget.keyPressEvent(event)

    def test_control_summary_clickable_item_works_from_keyboard(self) -> None:
        from presets.ui.control.top_summary_widget import ControlTopSummaryItem

        item = ControlTopSummaryItem(icon_name="fa5s.folder-open", clickable=True)
        clicks: list[bool] = []
        item.clicked.connect(lambda: clicks.append(True))
        item.set_texts(caption="Текущий preset", value="Default", details="")

        self.assertEqual(item.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertEqual(item.accessibleName(), "Текущий preset: Default")

        self._press_key(item, Qt.Key.Key_Return)

        self.assertEqual(clicks, [True])

    def test_dns_provider_card_works_from_keyboard(self) -> None:
        from dns.ui.cards import DNSProviderCard

        card = DNSProviderCard(
            "Cloudflare",
            {"desc": "быстрый DNS", "ipv4": ["1.1.1.1"], "ipv6": []},
        )
        selected: list[str] = []
        card.selected.connect(lambda name, _data: selected.append(name))

        self.assertEqual(card.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertIn("DNS Cloudflare", card.accessibleName())
        self.assertEqual(
            card.property("screenReaderStateText"),
            "DNS Cloudflare, не выбран, быстрый DNS, 1.1.1.1",
        )

        card.set_selected(True)

        self.assertEqual(
            card.property("screenReaderStateText"),
            "DNS Cloudflare, выбран, быстрый DNS, 1.1.1.1",
        )

        self._press_key(card, Qt.Key.Key_Space)

        self.assertEqual(selected, ["Cloudflare"])

    def test_dns_provider_card_uses_card_accent_without_indicator_widget(self) -> None:
        from dns.ui.cards import DNSProviderCard

        card = DNSProviderCard(
            "Google DNS",
            {
                "desc": "надёжный",
                "ipv4": ["8.8.8.8"],
                "ipv6": ["2001:4860:4860::8888"],
                "doh": "https://dns.google/dns-query",
            },
            show_ipv6=True,
        )

        self.assertFalse(hasattr(card, "indicator"))
        self.assertLessEqual(len(card.findChildren(QWidget)), 5)

        off_style = card.styleSheet()
        card.set_selected(True)

        self.assertTrue(card.property("selected"))
        self.assertNotEqual(card.styleSheet(), off_style)
        self.assertIn("background-color", card.styleSheet())
        self.assertIn("border", card.styleSheet())
        self.assertIn("rgba", card.styleSheet())

    def test_adapter_card_checkbox_works_from_keyboard(self) -> None:
        from dns.ui.cards import AdapterCard

        card = AdapterCard("Ethernet", {"ipv4": ["8.8.8.8"], "ipv6": []})

        self.assertEqual(card.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertIn("Сетевой адаптер Ethernet", card.accessibleName())
        self.assertEqual(
            card.property("screenReaderStateText"),
            "Сетевой адаптер Ethernet, выбран, DNS v4 8.8.8.8",
        )
        self.assertTrue(card.checkbox.isChecked())

        self._press_key(card, Qt.Key.Key_Return)

        self.assertFalse(card.checkbox.isChecked())
        self.assertEqual(
            card.property("screenReaderStateText"),
            "Сетевой адаптер Ethernet, не выбран, DNS v4 8.8.8.8",
        )


if __name__ == "__main__":
    unittest.main()
