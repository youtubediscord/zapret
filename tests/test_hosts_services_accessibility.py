from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import BodyLabel, ComboBox, PushButton, StrongBodyLabel, SwitchButton

from hosts.page_plans import HostsServiceGroupPlan, HostsServiceRowPlan
from hosts.ui.services_build import build_hosts_services_group
from hosts.ui.services_build import build_hosts_service_row


class HostsServicesAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_direct_toggle_reads_service_state(self) -> None:
        widgets = build_hosts_service_row(
            HostsServiceRowPlan(
                service_name="Adobe",
                icon_name="",
                icon_color=None,
                direct_only=True,
                available_profiles=[],
                profile_items=[],
                selected_profile=None,
                toggle_enabled=True,
                toggle_checked=False,
            ),
            body_label_cls=BodyLabel,
            combo_cls=ComboBox,
            toggle_cls=SwitchButton,
            off_label="Отключено",
            on_direct_toggle=lambda *_args: None,
            on_profile_changed=lambda *_args: None,
        )

        self.assertEqual(widgets.control.accessibleName(), "Adobe, выключено")
        self.assertEqual(widgets.control.property("screenReaderStateText"), "Adobe, выключено")
        self.assertIn("Включает или отключает hosts-запись", widgets.control.accessibleDescription())

        widgets.control.setChecked(True)

        self.assertEqual(widgets.control.accessibleName(), "Adobe, включено")
        self.assertEqual(widgets.control.property("screenReaderStateText"), "Adobe, включено")

    def test_direct_toggle_works_from_keyboard(self) -> None:
        events: list[tuple[str, bool]] = []
        widgets = build_hosts_service_row(
            HostsServiceRowPlan(
                service_name="Adobe",
                icon_name="",
                icon_color=None,
                direct_only=True,
                available_profiles=[],
                profile_items=[],
                selected_profile=None,
                toggle_enabled=True,
                toggle_checked=False,
            ),
            body_label_cls=BodyLabel,
            combo_cls=ComboBox,
            toggle_cls=SwitchButton,
            off_label="Отключено",
            on_direct_toggle=lambda service, checked: events.append((service, checked)),
            on_profile_changed=lambda *_args: None,
        )

        self.assertEqual(widgets.control.focusPolicy(), Qt.FocusPolicy.StrongFocus)

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widgets.control, event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(events, [("Adobe", True)])
        self.assertEqual(widgets.control.accessibleName(), "Adobe, включено")

    def test_profile_combo_reads_selected_profile(self) -> None:
        widgets = build_hosts_service_row(
            HostsServiceRowPlan(
                service_name="YouTube",
                icon_name="",
                icon_color=None,
                direct_only=False,
                available_profiles=["zapret_dns"],
                profile_items=[("zapret_dns", "Zapret DNS")],
                selected_profile="zapret_dns",
                toggle_enabled=True,
                toggle_checked=False,
            ),
            body_label_cls=BodyLabel,
            combo_cls=ComboBox,
            toggle_cls=SwitchButton,
            off_label="Отключено",
            on_direct_toggle=lambda *_args: None,
            on_profile_changed=lambda *_args: None,
        )

        self.assertEqual(widgets.control.accessibleName(), "YouTube, выбран профиль Zapret DNS")
        self.assertEqual(widgets.control.property("screenReaderStateText"), "YouTube, выбран профиль Zapret DNS")
        self.assertIn("Выберите профиль hosts", widgets.control.accessibleDescription())
        self.assertIn("стрелками вверх и вниз", widgets.control.accessibleDescription())

        widgets.control.setCurrentIndex(0)

        self.assertEqual(widgets.control.accessibleName(), "YouTube, отключено")
        self.assertEqual(widgets.control.property("screenReaderStateText"), "YouTube, отключено")

    def test_profile_combo_menu_items_are_named_for_screen_reader(self) -> None:
        widgets = build_hosts_service_row(
            HostsServiceRowPlan(
                service_name="YouTube",
                icon_name="",
                icon_color=None,
                direct_only=False,
                available_profiles=["zapret_dns"],
                profile_items=[("zapret_dns", "Zapret DNS")],
                selected_profile="zapret_dns",
                toggle_enabled=True,
                toggle_checked=False,
            ),
            body_label_cls=BodyLabel,
            combo_cls=ComboBox,
            toggle_cls=SwitchButton,
            off_label="Отключено",
            on_direct_toggle=lambda *_args: None,
            on_profile_changed=lambda *_args: None,
        )
        create_menu = getattr(widgets.control, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)

        menu = create_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "YouTube: Отключено, не выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "YouTube: Zapret DNS, выбран",
        )

    def test_group_chips_read_bulk_action(self) -> None:
        widgets = build_hosts_services_group(
            HostsServiceGroupPlan(
                title="Видео",
                direct_only=False,
                service_names=["YouTube", "Twitch"],
                common_profiles=[("zapret_dns", "Zapret DNS")],
                rows=[],
            ),
            off_label="Отключено",
            strong_body_label_cls=StrongBodyLabel,
            make_chip=lambda label: PushButton(label),
            on_bulk_apply=lambda *_args: None,
        )

        self.assertEqual(widgets.chip_buttons[0].accessibleName(), "Отключить группу Видео")
        self.assertEqual(widgets.chip_buttons[0].property("screenReaderStateText"), "Отключить группу Видео")
        self.assertIn("YouTube, Twitch", widgets.chip_buttons[0].accessibleDescription())
        self.assertEqual(widgets.chip_buttons[1].accessibleName(), "Применить Zapret DNS к группе Видео")
        self.assertEqual(
            widgets.chip_buttons[1].property("screenReaderStateText"),
            "Применить Zapret DNS к группе Видео",
        )
        self.assertIn("YouTube, Twitch", widgets.chip_buttons[1].accessibleDescription())


if __name__ == "__main__":
    unittest.main()
