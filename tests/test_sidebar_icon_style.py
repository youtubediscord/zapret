import unittest
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtGui import QIcon


class SidebarIconStyleSettingsTests(unittest.TestCase):
    def test_normalize_appearance_keeps_valid_sidebar_icon_style(self) -> None:
        from settings.normalize import normalize_appearance

        normalized = normalize_appearance({"sidebar_icon_style": "windows11_fluent"})

        self.assertEqual(normalized["sidebar_icon_style"], "windows11_fluent")

    def test_normalize_appearance_falls_back_to_standard_sidebar_icon_style(self) -> None:
        from settings.normalize import normalize_appearance

        normalized = normalize_appearance({"sidebar_icon_style": "unknown"})

        self.assertEqual(normalized["sidebar_icon_style"], "standard")

    def test_appearance_initial_state_includes_sidebar_icon_style(self) -> None:
        import settings.appearance as appearance_settings

        data = {
            "appearance": {
                "sidebar_icon_style": "windows11_fluent",
            },
            "window": {},
        }

        with patch("settings.store.read_settings", return_value=data):
            plan = appearance_settings.load_page_initial_state()

        self.assertEqual(plan.sidebar_icon_style, "windows11_fluent")

    def test_save_sidebar_icon_style_persists_normalized_value(self) -> None:
        import settings.appearance as appearance_settings

        with patch("settings.store.set_sidebar_icon_style") as save_style:
            plan = appearance_settings.save_sidebar_icon_style("windows11_fluent")

        save_style.assert_called_once_with("windows11_fluent")
        self.assertEqual(plan.style, "windows11_fluent")

    def test_initial_ui_state_warms_sidebar_icon_style(self) -> None:
        import settings.appearance as appearance_settings
        from app.initial_ui_state import build_initial_ui_state

        data = {
            "appearance": {
                "sidebar_icon_style": "windows11_fluent",
            },
            "window": {},
            "ui_state": {},
            "program": {
                "strategy_launch_method": "zapret2_mode",
            },
        }

        appearance_settings.clear_warmed_sidebar_icon_style_cache()
        with patch("settings.store.read_settings", return_value=data):
            build_initial_ui_state()

        self.assertEqual(appearance_settings.peek_warmed_sidebar_icon_style(), "windows11_fluent")

    def test_warmed_page_initial_state_warms_sidebar_icon_style(self) -> None:
        import settings.appearance as appearance_settings

        state = appearance_settings.AppearancePageInitialStatePlan(
            display_mode="dark",
            ui_language="ru",
            background_preset="standard",
            rkn_background=None,
            mica_enabled=False,
            window_opacity=100,
            accent_color=None,
            follow_windows_accent=True,
            tinted_background=False,
            tinted_intensity=20,
            animations_enabled=False,
            smooth_scroll_enabled=False,
            editor_smooth_scroll_enabled=False,
            sidebar_icon_style="windows11_fluent",
            garland_enabled=False,
            snowflakes_enabled=False,
        )

        appearance_settings.clear_warmed_sidebar_icon_style_cache()
        appearance_settings.store_warmed_page_initial_state(state)

        self.assertEqual(appearance_settings.peek_warmed_sidebar_icon_style(), "windows11_fluent")


class SidebarIconStyleNavigationTests(unittest.TestCase):
    def test_navigation_icon_resource_lookup_lives_outside_ui_module(self) -> None:
        import ui.navigation.icons as nav_icons

        source = inspect.getsource(nav_icons)

        self.assertIn("resolve_windows11_sidebar_icon_path", source)
        self.assertNotIn("Path(", source)
        self.assertNotIn(".exists()", source)

    def test_navigation_icon_resource_lookup_uses_canonical_ico_folder(self) -> None:
        import app.navigation_icon_resources as resources
        from config.runtime_layout import ApplicationPaths

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            icon_path = root / "ico" / "windows11_fluent" / "sidebar" / "home.svg"
            icon_path.parent.mkdir(parents=True)
            icon_path.write_text("<svg />", encoding="utf-8")

            with patch.object(resources, "APPLICATION_RESOURCE_PATHS", ApplicationPaths.from_root(root)):
                self.assertEqual(resources.resolve_windows11_sidebar_icon_path("home.svg"), str(icon_path))

    def test_navigation_icon_resource_lookup_ignores_nested_src_ico_folder(self) -> None:
        import app.navigation_icon_resources as resources
        from config.runtime_layout import ApplicationPaths

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            icon_path = root / "src" / "ico" / "windows11_fluent" / "sidebar" / "home.svg"
            icon_path.parent.mkdir(parents=True)
            icon_path.write_text("<svg />", encoding="utf-8")

            with patch.object(resources, "APPLICATION_RESOURCE_PATHS", ApplicationPaths.from_root(root)):
                self.assertEqual(resources.resolve_windows11_sidebar_icon_path("home.svg"), "")

    def test_current_sidebar_icon_style_uses_cache_without_settings_load(self) -> None:
        import settings.appearance as appearance_settings
        from ui.navigation.icons import current_sidebar_icon_style

        appearance_settings.clear_warmed_sidebar_icon_style_cache()
        with patch(
            "settings.appearance.load_sidebar_icon_style",
            side_effect=AssertionError("navigation must not read settings synchronously"),
        ):
            self.assertEqual(current_sidebar_icon_style(), "standard")

        appearance_settings.store_warmed_sidebar_icon_style("windows11_fluent")
        with patch(
            "settings.appearance.load_sidebar_icon_style",
            side_effect=AssertionError("navigation must not read settings synchronously"),
        ):
            self.assertEqual(current_sidebar_icon_style(), "windows11_fluent")

    def test_windows11_fluent_nav_icons_are_project_svg_icons(self) -> None:
        from app.page_names import PageName
        from ui.navigation.icons import build_nav_icons

        icons = build_nav_icons("windows11_fluent")

        self.assertIsInstance(icons[PageName.ZAPRET2_USER_PRESETS], QIcon)
        self.assertFalse(icons[PageName.ZAPRET2_USER_PRESETS].isNull())
        self.assertIsInstance(icons[PageName.APPEARANCE], QIcon)
        self.assertFalse(icons[PageName.APPEARANCE].isNull())

    def test_apply_sidebar_icon_style_updates_existing_items(self) -> None:
        from app.page_names import PageName
        from ui.navigation.icons import apply_sidebar_icon_style

        class _Item:
            def __init__(self) -> None:
                self.icons = []

            def setIcon(self, icon) -> None:
                self.icons.append(icon)

        preset_item = _Item()
        appearance_item = _Item()
        session = SimpleNamespace(
            nav_icons={},
            default_nav_icon=None,
            nav_items={
                PageName.ZAPRET2_USER_PRESETS: preset_item,
                PageName.APPEARANCE: appearance_item,
            },
        )
        window = SimpleNamespace(ui_session=session)

        apply_sidebar_icon_style(window, "windows11_fluent")

        self.assertEqual(len(preset_item.icons), 1)
        self.assertFalse(preset_item.icons[0].isNull())
        self.assertEqual(len(appearance_item.icons), 1)
        self.assertFalse(appearance_item.icons[0].isNull())
        self.assertIsInstance(session.default_nav_icon, QIcon)


class SidebarIconStyleAppearancePageTests(unittest.TestCase):
    def test_appearance_page_exposes_sidebar_icon_style_segment(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        source = inspect.getsource(AppearancePage._build_ui)

        self.assertIn("page.appearance.section.sidebar_icons", source)
        self.assertIn("windows11_fluent", source)
        self.assertIn("_on_sidebar_icon_style_changed", source)


if __name__ == "__main__":
    unittest.main()
