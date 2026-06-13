from __future__ import annotations

import unittest

from ui.message_box_accessibility import set_message_box_button_accessibility


class _ButtonStub:
    def __init__(self) -> None:
        self._accessible_name = ""
        self._accessible_description = ""
        self._properties = {}

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self._accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self._accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self._accessible_description = str(text)

    def property(self, name: str) -> object:
        return self._properties.get(name)

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        self._properties[name] = value


class _MessageBoxStub:
    def __init__(self) -> None:
        self.title = "Удалить пресет"
        self.body = "Пресет будет удалён из списка."
        self.yesButton = _ButtonStub()
        self.cancelButton = _ButtonStub()
        self._accessible_name = ""
        self._accessible_description = ""
        self._properties = {}

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self._accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self._accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self._accessible_description = str(text)

    def property(self, name: str) -> object:
        return self._properties.get(name)

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        self._properties[name] = value


class MessageBoxAccessibilityTests(unittest.TestCase):
    def test_message_box_buttons_expose_screen_reader_state_text(self) -> None:
        box = _MessageBoxStub()

        set_message_box_button_accessibility(
            box,
            yes_name="Удалить пользовательский пресет",
            yes_description="Удаляет пользовательский пресет.",
            cancel_name="Отменить удаление пользовательского пресета",
            cancel_description="Закрывает окно без удаления.",
        )

        self.assertEqual(box.yesButton.accessibleName(), "Удалить пользовательский пресет")
        self.assertEqual(
            box.yesButton.property("screenReaderStateText"),
            "Удалить пользовательский пресет",
        )
        self.assertIn("Удаляет", box.yesButton.accessibleDescription())
        self.assertEqual(box.cancelButton.accessibleName(), "Отменить удаление пользовательского пресета")
        self.assertEqual(
            box.cancelButton.property("screenReaderStateText"),
            "Отменить удаление пользовательского пресета",
        )
        self.assertIn("без удаления", box.cancelButton.accessibleDescription())
        self.assertEqual(box.accessibleName(), "Диалог: Удалить пресет. Пресет будет удалён из списка.")
        self.assertEqual(
            box.property("screenReaderStateText"),
            "Диалог: Удалить пресет. Пресет будет удалён из списка.",
        )
        self.assertEqual(box.accessibleDescription(), "Пресет будет удалён из списка.")


if __name__ == "__main__":
    unittest.main()
