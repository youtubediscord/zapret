from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QWidget


class DnsChoiceListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_choice_list_uses_delegate_rows_for_static_dns_choices(self) -> None:
        from dns.ui.choice_list import DOH_ROLE, DnsChoiceListWidget
        from dns.ui.cards import DNSProviderCard

        view = DnsChoiceListWidget()
        auto = view.add_auto_choice("Автоматически (DHCP)")
        provider = view.add_provider(
            "Google DNS",
            {
                "desc": "Надёжный",
                "ipv4": ["8.8.8.8"],
                "ipv6": ["2001:4860:4860::8888"],
                "icon": "fa5b.google",
                "doh": "https://dns.google/dns-query",
            },
            show_ipv6=True,
        )

        self.assertEqual(len(view.findChildren(DNSProviderCard)), 0)
        self.assertEqual(auto.property("selected"), False)

        provider.set_selected(True)

        self.assertTrue(provider.property("selected"))
        self.assertEqual(provider.accessibleName(), "DNS Google DNS, выбран")
        self.assertTrue(provider.item.data(DOH_ROLE))
        self.assertGreater(view.sizeHintForRow(0), 0)

    def test_choice_list_hides_doh_badge_when_windows_does_not_support_doh(self) -> None:
        from dns.ui.choice_list import DOH_ROLE, DnsChoiceListWidget

        view = DnsChoiceListWidget()
        provider = view.add_provider(
            "Google DNS",
            {
                "desc": "Надёжный",
                "ipv4": ["8.8.8.8"],
                "doh": "https://dns.google/dns-query",
            },
            show_doh=False,
        )

        self.assertFalse(provider.item.data(DOH_ROLE))

    def test_choice_list_emits_same_selection_signals_as_old_cards(self) -> None:
        from dns.ui.choice_list import DnsChoiceListWidget

        view = DnsChoiceListWidget()
        auto_item = view.add_auto_choice("Автоматически (DHCP)").item
        provider_item = view.add_provider(
            "Cloudflare",
            {"desc": "Быстрый", "ipv4": ["1.1.1.1"], "ipv6": []},
            show_ipv6=False,
        ).item
        custom_item = view.set_custom_choice(QWidget())
        selected: list[str] = []
        view.auto_selected.connect(lambda: selected.append("auto"))
        view.provider_selected.connect(lambda name, _data: selected.append(name))
        view.custom_selected.connect(lambda: selected.append("custom"))

        view.activate_item(auto_item)
        view.activate_item(provider_item)
        view.activate_item(custom_item)

        self.assertEqual(selected, ["auto", "Cloudflare", "custom"])
        self.assertEqual(auto_item.flags() & Qt.ItemFlag.ItemIsEnabled, Qt.ItemFlag.ItemIsEnabled)

    def test_choice_list_focuses_first_choice_and_reads_keyboard_state(self) -> None:
        from dns.ui.choice_list import DnsChoiceListWidget

        view = DnsChoiceListWidget()
        auto = view.add_auto_choice("Автоматически (DHCP)")
        provider = view.add_provider(
            "Cloudflare",
            {"desc": "Быстрый", "ipv4": ["1.1.1.1"], "ipv6": []},
            show_ipv6=False,
        )
        selected: list[str] = []
        view.auto_selected.connect(lambda: selected.append("auto"))

        self.assertIsNone(view.currentItem())

        view.focusInEvent(QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))

        self.assertIs(view.currentItem(), auto.item)
        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список DNS-серверов: DNS автоматически (DHCP), не выбран. "
            "Нажмите Enter или Пробел, чтобы выбрать DNS.",
        )

        view.setCurrentItem(provider.item)

        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список DNS-серверов: DNS Cloudflare, не выбран. "
            "Нажмите Enter или Пробел, чтобы выбрать DNS.",
        )

        view.setCurrentItem(auto.item)
        event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(selected, ["auto"])

    def test_choice_focused_row_paints_keyboard_current_state(self) -> None:
        import dns.ui.choice_list as choice_list
        from dns.ui.choice_list import DnsChoiceListDelegate, DnsChoiceListWidget

        view = DnsChoiceListWidget()
        view.add_auto_choice("Автоматически (DHCP)")
        index = view.model().index(0, 0)
        option = QStyleOptionViewItem()
        option.rect = view.visualRect(index)
        if not option.rect.isValid():
            option.rect.setRect(0, 0, 360, 38)
        option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_HasFocus
        painted_states: list[dict] = []
        original_paint = choice_list.paint_profile_hover_row

        def capture_paint(_painter, _rect, *, active=False, hovered=False, selected=False):
            painted_states.append({"active": active, "hovered": hovered, "selected": selected})

        choice_list.paint_profile_hover_row = capture_paint
        try:
            pixmap = QPixmap(360, 38)
            painter = QPainter(pixmap)
            DnsChoiceListDelegate(view).paint(painter, option, index)
            painter.end()
        finally:
            choice_list.paint_profile_hover_row = original_paint

        self.assertEqual(painted_states, [{"active": False, "hovered": False, "selected": True}])

    def test_custom_dns_row_reads_selection_state_for_keyboard_navigation(self) -> None:
        from dns.ui.choice_list import DnsChoiceListWidget

        view = DnsChoiceListWidget()
        custom_item = view.set_custom_choice(QWidget())

        view.setCurrentItem(custom_item)

        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список DNS-серверов: Свой DNS, не выбран. Нажмите Enter или Пробел, чтобы выбрать DNS.",
        )

        view.set_item_selected(custom_item, True)

        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список DNS-серверов: Свой DNS, выбран. Нажмите Enter или Пробел, чтобы выбрать DNS.",
        )

    def test_choice_list_context_menu_is_only_for_custom_dns_rows(self) -> None:
        from dns.ui.choice_list import DnsChoiceListWidget

        view = DnsChoiceListWidget()
        regular = view.add_provider(
            "Cloudflare",
            {"desc": "Быстрый", "ipv4": ["1.1.1.1"], "ipv6": []},
            show_ipv6=False,
        )
        custom = view.add_provider(
            "Мой DNS",
            {
                "desc": "Пользовательский",
                "ipv4": ["8.8.8.8"],
                "ipv6": [],
                "custom_id": "custom-1",
            },
            show_ipv6=False,
        )
        requested: list[tuple[str, dict]] = []
        view.custom_provider_context_requested.connect(
            lambda name, data, _pos: requested.append((name, data))
        )

        self.assertFalse(view._emit_custom_provider_context(regular.item, view.visualItemRect(regular.item).center()))
        self.assertTrue(view._emit_custom_provider_context(custom.item, view.visualItemRect(custom.item).center()))
        self.assertEqual(requested[0][0], "Мой DNS")
        self.assertEqual(requested[0][1]["custom_id"], "custom-1")

    def test_choice_list_right_click_on_custom_dns_row_requests_context_menu(self) -> None:
        from dns.ui.choice_list import DnsChoiceListWidget

        view = DnsChoiceListWidget()
        custom = view.add_provider(
            "Мой DNS",
            {
                "desc": "Пользовательский",
                "ipv4": ["8.8.8.8"],
                "ipv6": [],
                "custom_id": "custom-1",
            },
            show_ipv6=False,
        )
        requested: list[str] = []
        view.custom_provider_context_requested.connect(lambda name, _data, _pos: requested.append(name))

        pos = view.visualItemRect(custom.item).center()
        event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(pos),
            QPointF(view.viewport().mapToGlobal(pos)),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )

        view.mouseReleaseEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, ["Мой DNS"])


if __name__ == "__main__":
    unittest.main()
