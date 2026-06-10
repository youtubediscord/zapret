from __future__ import annotations

import unittest

from dns.page_plans import build_force_dns_status_plan, build_force_dns_toggle_plan, build_reset_dhcp_result_plan
from dns.ui.force_dns_ui import update_force_dns_status_label


class _StatusParent:
    def __init__(self) -> None:
        self.refreshed = False
        self.geometry_updated = False

    def _refresh_minimum_height(self) -> None:
        self.refreshed = True

    def updateGeometry(self) -> None:  # noqa: N802
        self.geometry_updated = True


class _StatusLabel:
    def __init__(self) -> None:
        self.text = ""
        self.visible = False
        self.accessible_name = ""
        self.properties: dict[str, object] = {}
        self.parent = _StatusParent()

    def setText(self, text: str) -> None:  # noqa: N802
        self.text = str(text)

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        self.visible = bool(visible)

    def parentWidget(self):
        return self.parent

    def accessibleName(self) -> str:  # noqa: N802
        return self.accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self.accessible_name = str(text)

    def property(self, name: str):  # noqa: A003
        return self.properties.get(str(name))

    def setProperty(self, name: str, value) -> None:  # noqa: N802
        self.properties[str(name)] = value


class ForceDnsStatusTextTests(unittest.TestCase):
    def test_plain_toggle_state_does_not_repeat_status_text(self) -> None:
        enabled_plan = build_force_dns_status_plan(enabled=True)
        disabled_plan = build_force_dns_status_plan(enabled=False)

        self.assertEqual(enabled_plan.text, "")
        self.assertEqual(disabled_plan.text, "")

    def test_action_details_are_shown_without_repeating_toggle_state(self) -> None:
        plan = build_force_dns_status_plan(
            enabled=True,
            details_key="page.network.force_dns.action.enable.description",
            details_fallback="Программа пропишет DNS-серверы для обхода блокировок.",
        )

        self.assertEqual(
            plan.text,
            "Программа пропишет DNS-серверы для обхода блокировок. Это поможет, если провайдер подменяет DNS.",
        )

    def test_toggle_success_uses_human_action_descriptions(self) -> None:
        enable_plan = build_force_dns_toggle_plan(requested_enabled=True, success=True)
        disable_plan = build_force_dns_toggle_plan(requested_enabled=False, success=True)

        self.assertEqual(enable_plan.details_key, "page.network.force_dns.action.enable.description")
        self.assertEqual(disable_plan.details_key, "page.network.force_dns.action.disable.description")

    def test_reset_success_uses_automatic_dns_description(self) -> None:
        plan = build_reset_dhcp_result_plan(success=True, message="", force_dns_active=False)

        self.assertEqual(plan.status_details_key, "page.network.force_dns.action.reset.description")

    def test_status_label_exposes_screen_reader_state_text(self) -> None:
        label = _StatusLabel()

        update_force_dns_status_label(
            label=label,
            enabled=True,
            details_key=None,
            details_kwargs=None,
            details_fallback="Принудительный DNS включён",
            language="ru",
            build_status_plan_fn=build_force_dns_status_plan,
        )

        self.assertEqual(label.text, "Принудительный DNS включён")
        self.assertEqual(
            label.properties.get("screenReaderStateText"),
            "Статус принудительного DNS: Принудительный DNS включён",
        )


if __name__ == "__main__":
    unittest.main()
