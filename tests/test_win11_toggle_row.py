from __future__ import annotations

import unittest


class _TextLabel:
    def __init__(self, text: str) -> None:
        self._text = str(text)
        self.set_calls: list[str] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.set_calls.append(value)
        self._text = value


class _SwitchButton:
    def __init__(self, checked: bool) -> None:
        self.checked = bool(checked)
        self.set_calls: list[bool] = []
        self.block_calls: list[bool] = []

    def isChecked(self) -> bool:  # noqa: N802
        return self.checked

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        self.set_calls.append(bool(checked))
        self.checked = bool(checked)

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        self.block_calls.append(bool(blocked))


class Win11ToggleRowTests(unittest.TestCase):
    def test_set_checked_skips_duplicate_state(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow.__new__(Win11ToggleRow)
        switch = _SwitchButton(True)
        row._switch_button = switch

        Win11ToggleRow.setChecked(row, True, block_signals=True)

        self.assertEqual(switch.set_calls, [])
        self.assertEqual(switch.block_calls, [])

    def test_set_checked_applies_changed_state_with_blocked_signals(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow.__new__(Win11ToggleRow)
        switch = _SwitchButton(False)
        row._switch_button = switch

        Win11ToggleRow.setChecked(row, True, block_signals=True)

        self.assertEqual(switch.set_calls, [True])
        self.assertEqual(switch.block_calls, [True, False])
        self.assertTrue(switch.checked)

    def test_set_texts_skips_duplicate_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow.__new__(Win11ToggleRow)
        row._title_label = _TextLabel("Title")
        row._desc_label = _TextLabel("Description")
        title_calls: list[str] = []
        content_calls: list[str] = []

        def set_title(text: str) -> None:
            title_calls.append(str(text))

        def set_content(text: str) -> None:
            content_calls.append(str(text))

        row.setTitle = set_title
        row.setContent = set_content

        Win11ToggleRow.set_texts(row, "Title", "Description")

        self.assertEqual(title_calls, [])
        self.assertEqual(content_calls, [])

    def test_set_texts_applies_changed_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow.__new__(Win11ToggleRow)
        row._title_label = _TextLabel("Old title")
        row._desc_label = _TextLabel("Old description")
        title_calls: list[str] = []
        content_calls: list[str] = []

        def set_title(text: str) -> None:
            title_calls.append(str(text))

        def set_content(text: str) -> None:
            content_calls.append(str(text))

        row.setTitle = set_title
        row.setContent = set_content

        Win11ToggleRow.set_texts(row, "Title", "Description")

        self.assertEqual(title_calls, ["Title"])
        self.assertEqual(content_calls, ["Description"])

    def test_radio_option_set_texts_skips_duplicate_text(self) -> None:
        from ui.widgets.win11_controls import Win11RadioOption

        row = Win11RadioOption.__new__(Win11RadioOption)
        title_label = _TextLabel("Zapret 2")
        desc_label = _TextLabel("Preset mode")
        badge_label = _TextLabel("recommended")
        row._title_label = title_label
        row._desc_label = desc_label
        row._badge_label = badge_label

        Win11RadioOption.set_texts(row, "Zapret 2", "Preset mode", "recommended")

        self.assertEqual(title_label.set_calls, [])
        self.assertEqual(desc_label.set_calls, [])
        self.assertEqual(badge_label.set_calls, [])

    def test_radio_option_set_texts_applies_changed_text(self) -> None:
        from ui.widgets.win11_controls import Win11RadioOption

        row = Win11RadioOption.__new__(Win11RadioOption)
        title_label = _TextLabel("Old")
        desc_label = _TextLabel("Old description")
        badge_label = _TextLabel("old")
        row._title_label = title_label
        row._desc_label = desc_label
        row._badge_label = badge_label

        Win11RadioOption.set_texts(row, "Zapret 2", "Preset mode", "recommended")

        self.assertEqual(title_label.set_calls, ["Zapret 2"])
        self.assertEqual(desc_label.set_calls, ["Preset mode"])
        self.assertEqual(badge_label.set_calls, ["recommended"])


if __name__ == "__main__":
    unittest.main()
