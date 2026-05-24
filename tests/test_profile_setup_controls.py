from __future__ import annotations

import unittest

from profile.ui.profile_setup_controls import sync_range_value_enabled


class ProfileSetupControlsTests(unittest.TestCase):
    def test_range_value_placeholder_does_not_show_fake_default_8(self) -> None:
        class Combo:
            def __init__(self, mode: str) -> None:
                self.mode = mode

            def currentIndex(self) -> int:  # noqa: N802
                return 0

            def itemData(self, _index: int):
                return self.mode

        class ValueEdit:
            def __init__(self) -> None:
                self.enabled = True
                self.text = "8"
                self.placeholder = ""

            def setEnabled(self, enabled: bool) -> None:  # noqa: N802
                self.enabled = enabled

            def clear(self) -> None:
                self.text = ""

            def setPlaceholderText(self, text: str) -> None:  # noqa: N802
                self.placeholder = text

        for mode in ("a", "x", "n", "d"):
            edit = ValueEdit()
            sync_range_value_enabled(Combo(mode), edit)
            self.assertNotEqual(edit.placeholder, "8")


if __name__ == "__main__":
    unittest.main()
