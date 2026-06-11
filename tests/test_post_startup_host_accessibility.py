from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from main.post_startup_host import PostStartupHost


class _DialogButton:
    def __init__(self) -> None:
        self._text = ""
        self._accessible_name = ""
        self._accessible_description = ""

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = str(text)

    def text(self) -> str:
        return self._text

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


class PostStartupHostAccessibilityTests(unittest.TestCase):
    def test_update_confirm_buttons_are_named_for_screen_reader(self) -> None:
        window = SimpleNamespace()
        host = PostStartupHost(window)
        _MessageBox.instances = []

        with patch("qfluentwidgets.MessageBox", _MessageBox):
            confirmed = host.confirm_update_install("1.2.3")

        self.assertFalse(confirmed)
        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Скачать и установить обновление")
        self.assertIn("Выпущена версия 1.2.3", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отложить установку обновления")
        self.assertTrue(dialog.exec_called)


if __name__ == "__main__":
    unittest.main()
