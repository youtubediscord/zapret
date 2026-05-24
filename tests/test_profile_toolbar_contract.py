from __future__ import annotations

import inspect
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from profile.ui import shell as profile_shell
from presets.ui.common import user_presets_build
from presets.ui.common import user_presets_page


class ProfileToolbarContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

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

    def test_user_presets_status_bar_is_in_toolbar_not_under_list(self) -> None:
        source = inspect.getsource(user_presets_page.UserPresetsPageBase._build_ui)

        self.assertIn("set_inline_widget(self._preset_status_bar", source)
        self.assertNotIn("self.add_widget(self._preset_status_bar)", source)

    def test_toolbar_can_place_inline_status_before_search(self) -> None:
        from PyQt6.QtWidgets import QLabel, QWidget

        from ui.presets_menu.toolbar import PresetsToolbarLayout

        parent = QWidget()
        toolbar = PresetsToolbarLayout(parent)
        first = toolbar.create_action_button("Импорт", None)
        second = toolbar.create_action_button("Что это такое?", None)
        status = QLabel("Пресет применён")
        search = QLabel("Поиск")

        toolbar.set_buttons([first, second])
        toolbar.set_inline_widget(status, minimum_width=120)
        toolbar.set_trailing_widget(search, minimum_width=160)
        toolbar.refresh_layout(600)

        row_layout = toolbar._rows[0][1]
        widgets = [row_layout.itemAt(index).widget() for index in range(row_layout.count())]

        self.assertLess(widgets.index(second), widgets.index(status))
        self.assertLess(widgets.index(status), widgets.index(search))

    def test_toolbar_restores_inline_status_after_narrow_layout(self) -> None:
        from PyQt6.QtWidgets import QLabel, QWidget

        from ui.presets_menu.toolbar import PresetsToolbarLayout

        parent = QWidget()
        toolbar = PresetsToolbarLayout(parent)
        first = toolbar.create_action_button("Импорт", None)
        second = toolbar.create_action_button("Что это такое?", None)
        status = QLabel("Пресет применён")
        search = QLabel("Поиск")

        toolbar.set_buttons([first, second])
        toolbar.set_inline_widget(status, minimum_width=180)
        toolbar.set_trailing_widget(search, minimum_width=260)

        toolbar.refresh_layout(420)
        self.assertTrue(status.isHidden())

        toolbar.refresh_layout(800)
        self.assertFalse(status.isHidden())


if __name__ == "__main__":
    unittest.main()
