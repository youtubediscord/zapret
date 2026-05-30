from __future__ import annotations

import unittest


class SidebarStartupDelayTests(unittest.TestCase):
    def test_sidebar_secondary_groups_are_not_delayed_for_multiple_seconds(self) -> None:
        import ui.navigation.sidebar_builder as sidebar_builder

        self.assertLessEqual(sidebar_builder.SIDEBAR_SECONDARY_GROUPS_AFTER_INTERACTIVE_MS, 1_000)
        self.assertLessEqual(sidebar_builder.SIDEBAR_SECONDARY_GROUP_STEP_MS, 10)

    def test_sidebar_search_and_hidden_mode_items_stay_after_initial_paint_but_not_late(self) -> None:
        import ui.navigation.sidebar_builder as sidebar_builder

        self.assertGreaterEqual(sidebar_builder.SIDEBAR_SEARCH_AFTER_INTERACTIVE_MS, 500)
        self.assertLessEqual(sidebar_builder.SIDEBAR_SEARCH_AFTER_INTERACTIVE_MS, 1_500)
        self.assertGreaterEqual(sidebar_builder.SIDEBAR_HIDDEN_MODE_ITEMS_AFTER_INTERACTIVE_MS, 1_000)
        self.assertLessEqual(sidebar_builder.SIDEBAR_HIDDEN_MODE_ITEMS_AFTER_INTERACTIVE_MS, 2_500)


if __name__ == "__main__":
    unittest.main()
