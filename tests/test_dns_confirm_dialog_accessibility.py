from __future__ import annotations

import unittest
from unittest.mock import patch

from dns.ui.page import NetworkPage


class _DialogButton:
    def __init__(self) -> None:
        self._accessible_name = ""
        self._accessible_description = ""

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self._accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self._accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self._accessible_description = str(text)


class _MessageBox:
    instances: list["_MessageBox"] = []

    def __init__(self, title: str, body: str, parent=None) -> None:
        self.title = title
        self.body = body
        self.parent = parent
        self.yesButton = _DialogButton()
        self.cancelButton = _DialogButton()
        self.exec_called = False
        _MessageBox.instances.append(self)

    def exec(self) -> bool:
        self.exec_called = True
        return False


class DnsConfirmDialogAccessibilityTests(unittest.TestCase):
    def test_dns_confirmation_buttons_are_named_for_screen_reader(self) -> None:
        page = NetworkPage.__new__(NetworkPage)
        page._tr = lambda _key, default: default
        page.window = lambda: None
        _MessageBox.instances = []

        with patch("dns.ui.page.MessageBox", _MessageBox):
            confirmed = NetworkPage._confirm_action(
                page,
                "page.network.force_dns.action.enable.button",
                "Включить принудительный DNS",
                "page.network.force_dns.action.enable.confirm",
                "Программа пропишет DNS-серверы на выбранные адаптеры.",
            )

        self.assertFalse(confirmed)
        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Включить принудительный DNS")
        self.assertIn("Программа пропишет DNS-серверы", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить действие: Включить принудительный DNS")
        self.assertTrue(dialog.exec_called)


if __name__ == "__main__":
    unittest.main()
