from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import BodyLabel, ComboBox, SwitchButton

from hosts.page_plans import HostsServiceRowPlan
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
        self.assertIn("Включает или отключает hosts-запись", widgets.control.accessibleDescription())

        widgets.control.setChecked(True)

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
        self.assertIn("Выберите профиль hosts", widgets.control.accessibleDescription())

        widgets.control.setCurrentIndex(0)

        self.assertEqual(widgets.control.accessibleName(), "YouTube, отключено")


if __name__ == "__main__":
    unittest.main()
