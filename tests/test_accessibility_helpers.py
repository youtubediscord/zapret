from __future__ import annotations

import unittest


class _Widget:
    def __init__(self, text: str = "") -> None:
        self._text = str(text)
        self.accessible_name = ""
        self.accessible_description = ""
        self.tooltip = ""
        self.properties: dict[str, object] = {}

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = str(text)

    def accessibleName(self) -> str:  # noqa: N802
        return self.accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self.accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self.accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self.accessible_description = str(text)

    def toolTip(self) -> str:  # noqa: N802
        return self.tooltip

    def setToolTip(self, text: str) -> None:  # noqa: N802
        self.tooltip = str(text)

    def property(self, name: str):  # noqa: A003
        return self.properties.get(str(name))

    def setProperty(self, name: str, value) -> None:  # noqa: N802
        self.properties[str(name)] = value


class AccessibilityHelpersTests(unittest.TestCase):
    def test_set_accessible_name_uses_widget_text_by_default(self) -> None:
        from ui.accessibility import set_accessible_name

        widget = _Widget("Запустить")

        changed = set_accessible_name(widget)

        self.assertTrue(changed)
        self.assertEqual(widget.accessible_name, "Запустить")

    def test_set_accessible_description_skips_duplicate_value(self) -> None:
        from ui.accessibility import set_accessible_description

        widget = _Widget()
        widget.accessible_description = "Открывает папку с логами"

        changed = set_accessible_description(widget, "Открывает папку с логами")

        self.assertFalse(changed)
        self.assertEqual(widget.accessible_description, "Открывает папку с логами")

    def test_set_control_accessibility_sets_name_and_description(self) -> None:
        from ui.accessibility import set_control_accessibility

        widget = _Widget("Остановить")

        set_control_accessibility(
            widget,
            name="Остановить Zapret",
            description="Останавливает запущенный процесс обхода блокировок.",
        )

        self.assertEqual(widget.accessible_name, "Остановить Zapret")
        self.assertEqual(widget.accessible_description, "Останавливает запущенный процесс обхода блокировок.")

    def test_set_state_text_marks_text_status_for_screen_reader(self) -> None:
        from ui.accessibility import set_state_text

        widget = _Widget()

        set_state_text(widget, "Запущено")

        self.assertEqual(widget.accessible_name, "Запущено")
        self.assertEqual(widget.properties["screenReaderStateText"], "Запущено")

    def test_set_tooltip_also_sets_accessible_description(self) -> None:
        from unittest.mock import patch

        from ui.fluent_widgets import set_tooltip

        widget = _Widget()
        widget.installEventFilter = lambda _filter: None

        with patch("ui.fluent_widgets.ToolTipFilter", return_value=object()):
            set_tooltip(widget, "Открывает папку с логами.")

        self.assertEqual(widget.tooltip, "Открывает папку с логами.")
        self.assertEqual(widget.accessible_description, "Открывает папку с логами.")

    def test_set_tooltip_sets_accessible_name_for_icon_only_controls(self) -> None:
        from unittest.mock import patch

        from ui.fluent_widgets import set_tooltip

        widget = _Widget("")
        widget.installEventFilter = lambda _filter: None

        with patch("ui.fluent_widgets.ToolTipFilter", return_value=object()):
            set_tooltip(widget, "Создать новый preset")

        self.assertEqual(widget.accessible_name, "Создать новый preset")


if __name__ == "__main__":
    unittest.main()
