from __future__ import annotations

import inspect
import unittest

from profile.ui import shell as profile_shell
from presets.ui.common import user_presets_build


class ProfileToolbarContractTests(unittest.TestCase):
    def test_profile_toolbar_has_no_manual_refresh_button(self) -> None:
        source = inspect.getsource(profile_shell)

        self.assertNotIn("RefreshButton", source)
        self.assertNotIn("reload_btn", source)
        self.assertNotIn("on_reload", source)

    def test_github_buttons_use_direct_fluent_icons(self) -> None:
        profile_source = inspect.getsource(profile_shell.build_profile_shell)
        presets_source = inspect.getsource(user_presets_build.build_user_presets_page_shell)

        self.assertIn("request_btn = PrimaryPushButton(", profile_source)
        self.assertIn("icon=FluentIcon.GITHUB", profile_source)
        self.assertIn("get_configs_btn = PrimaryPushButton(", presets_source)
        self.assertIn("icon=FluentIcon.GITHUB", presets_source)

    def test_user_presets_list_reserves_space_for_visible_fluent_scrollbar(self) -> None:
        presets_source = inspect.getsource(user_presets_build.build_user_presets_page_shell)

        self.assertIn("reserve_vertical_space=True", presets_source)


if __name__ == "__main__":
    unittest.main()
