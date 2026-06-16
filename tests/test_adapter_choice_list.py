from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QRect, Qt
from PyQt6.QtGui import QFocusEvent, QKeyEvent, QPainter, QPixmap
from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem
from PyQt6.QtWidgets import QApplication

from dns.ui.adapters import build_adapter_cards, refresh_adapter_cards


class AdapterChoiceListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_adapter_list_uses_delegate_rows_and_keeps_checkbox_contract(self) -> None:
        from dns.ui.adapter_list import AdapterChoiceHandle
        from dns.ui.adapter_list import AdapterChoiceListWidget

        changed: list[int] = []
        view = AdapterChoiceListWidget()

        cards = build_adapter_cards(
            adapters=[("Ethernet", "Intel")],
            dns_info={"Ethernet": {"ipv4": ["8.8.8.8"], "ipv6": []}},
            adapters_layout=view,
            normalize_alias_fn=lambda value: value,
            on_state_changed=changed.append,
        )

        self.assertEqual(len(cards), 1)
        self.assertIsInstance(cards[0], AdapterChoiceHandle)
        self.assertEqual(cards[0].adapter_name, "Ethernet")
        self.assertTrue(cards[0].checkbox.isChecked())
        self.assertEqual(
            cards[0].property("screenReaderStateText"),
            "Сетевой адаптер Ethernet, выбран, DNS v4 8.8.8.8",
        )
        self.assertGreaterEqual(view.sizeHintForRow(0), 38)
        self.assertLessEqual(view.sizeHintForRow(0), 40)

        view.activate_item(cards[0].item)

        self.assertFalse(cards[0].checkbox.isChecked())
        self.assertEqual(changed, [0])
        self.assertEqual(
            cards[0].property("screenReaderStateText"),
            "Сетевой адаптер Ethernet, не выбран, DNS v4 8.8.8.8",
        )

    def test_adapter_list_updates_dns_text_and_toggles_from_keyboard(self) -> None:
        from dns.ui.adapter_list import AdapterChoiceListWidget

        view = AdapterChoiceListWidget()
        cards = build_adapter_cards(
            adapters=[("Ethernet", "Intel")],
            dns_info={"Ethernet": {"ipv4": [], "ipv6": []}},
            adapters_layout=view,
            normalize_alias_fn=lambda value: value,
            on_state_changed=lambda _state: None,
        )

        refresh_adapter_cards(
            adapter_cards=cards,
            dns_info={"Ethernet": {"ipv4": ["1.1.1.1"], "ipv6": []}},
            build_refresh_plan_fn=lambda names, info: _RefreshPlan(names, info),
        )

        self.assertEqual(cards[0].dns_label.text(), "v4 1.1.1.1")

        view.setCurrentItem(cards[0].item)
        event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertFalse(cards[0].checkbox.isChecked())

    def test_adapter_list_focuses_first_adapter_and_reads_state_for_keyboard_selection(self) -> None:
        from dns.ui.adapter_list import AdapterChoiceListWidget

        view = AdapterChoiceListWidget()
        cards = build_adapter_cards(
            adapters=[("Ethernet", "Intel")],
            dns_info={"Ethernet": {"ipv4": ["8.8.8.8"], "ipv6": []}},
            adapters_layout=view,
            normalize_alias_fn=lambda value: value,
            on_state_changed=lambda _state: None,
        )

        self.assertIsNone(view.currentItem())

        view.focusInEvent(QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))

        self.assertIs(view.currentItem(), cards[0].item)
        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список сетевых адаптеров: Сетевой адаптер Ethernet, выбран, DNS v4 8.8.8.8. "
            "Нажмите Enter или Пробел, чтобы включить или исключить этот адаптер.",
        )

        event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertFalse(cards[0].checkbox.isChecked())
        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список сетевых адаптеров: Сетевой адаптер Ethernet, не выбран, DNS v4 8.8.8.8. "
            "Нажмите Enter или Пробел, чтобы включить или исключить этот адаптер.",
        )

    def test_adapter_checked_row_does_not_paint_active_background(self) -> None:
        import dns.ui.adapter_list as adapter_list
        from dns.ui.adapter_list import CHECKED_ROLE, AdapterChoiceListDelegate, AdapterChoiceListWidget

        view = AdapterChoiceListWidget()
        cards = build_adapter_cards(
            adapters=[("Ethernet", "Intel")],
            dns_info={"Ethernet": {"ipv4": ["8.8.8.8"], "ipv6": []}},
            adapters_layout=view,
            normalize_alias_fn=lambda value: value,
            on_state_changed=lambda _state: None,
        )
        cards[0].item.setData(CHECKED_ROLE, True)
        index = view.model().index(0, 0)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 360, 38)
        option.state = QStyle.StateFlag.State_Enabled
        painted_states: list[dict] = []
        original_paint = adapter_list.paint_profile_hover_row

        def capture_paint(_painter, _rect, *, active=False, hovered=False, selected=False):
            painted_states.append({"active": active, "hovered": hovered, "selected": selected})

        adapter_list.paint_profile_hover_row = capture_paint
        try:
            pixmap = QPixmap(360, 38)
            painter = QPainter(pixmap)
            AdapterChoiceListDelegate(view).paint(painter, option, index)
            painter.end()
        finally:
            adapter_list.paint_profile_hover_row = original_paint

        self.assertEqual(painted_states, [{"active": False, "hovered": False, "selected": False}])

    def test_adapter_focused_row_paints_keyboard_current_state(self) -> None:
        import dns.ui.adapter_list as adapter_list
        from dns.ui.adapter_list import AdapterChoiceListDelegate, AdapterChoiceListWidget

        view = AdapterChoiceListWidget()
        build_adapter_cards(
            adapters=[("Ethernet", "Intel")],
            dns_info={"Ethernet": {"ipv4": ["8.8.8.8"], "ipv6": []}},
            adapters_layout=view,
            normalize_alias_fn=lambda value: value,
            on_state_changed=lambda _state: None,
        )
        index = view.model().index(0, 0)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 360, 38)
        option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_HasFocus
        painted_states: list[dict] = []
        original_paint = adapter_list.paint_profile_hover_row

        def capture_paint(_painter, _rect, *, active=False, hovered=False, selected=False):
            painted_states.append({"active": active, "hovered": hovered, "selected": selected})

        adapter_list.paint_profile_hover_row = capture_paint
        try:
            pixmap = QPixmap(360, 38)
            painter = QPainter(pixmap)
            AdapterChoiceListDelegate(view).paint(painter, option, index)
            painter.end()
        finally:
            adapter_list.paint_profile_hover_row = original_paint

        self.assertEqual(painted_states, [{"active": False, "hovered": False, "selected": True}])

    def test_adapter_card_widget_is_removed_from_dns_cards_module(self) -> None:
        import dns.ui.cards as cards_module

        self.assertFalse(hasattr(cards_module, "AdapterCard"))


class _RefreshPlan:
    def __init__(self, names, info):
        self.entries = [
            _RefreshEntry(
                adapter_name=name,
                adapter_data=info[name],
                ipv4=info[name].get("ipv4", []),
                ipv6=info[name].get("ipv6", []),
            )
            for name in names
        ]


class _RefreshEntry:
    def __init__(self, *, adapter_name, adapter_data, ipv4, ipv6):
        self.adapter_name = adapter_name
        self.adapter_data = adapter_data
        self.ipv4 = ipv4
        self.ipv6 = ipv6


if __name__ == "__main__":
    unittest.main()
