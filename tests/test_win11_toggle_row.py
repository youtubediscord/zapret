from __future__ import annotations

import unittest


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


if __name__ == "__main__":
    unittest.main()
