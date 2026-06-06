from __future__ import annotations

import inspect
import unittest

from profile.ui.profile_setup_page import ProfileStrategyListWidget


class StrategyListAccessibilityTests(unittest.TestCase):
    def test_strategy_list_is_keyboard_focusable_and_named(self) -> None:
        source = inspect.getsource(ProfileStrategyListWidget.__init__)

        self.assertIn("Qt.FocusPolicy.StrongFocus", source)
        self.assertNotIn("Qt.FocusPolicy.NoFocus", source)
        self.assertIn('set_control_accessibility(self._search, name="Поиск готовых стратегий"', source)
        self.assertIn("set_control_accessibility(", source)
        self.assertIn('name="Список готовых стратегий"', source)
        self.assertIn("стрелками вверх и вниз", source)


if __name__ == "__main__":
    unittest.main()
