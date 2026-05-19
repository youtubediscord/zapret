from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class PresetSidebarNavigationTests(unittest.TestCase):
    def test_winws2_preset_pages_are_visible_in_root_sidebar(self) -> None:
        from app.page_names import PageName
        from settings.mode import ZAPRET2_MODE
        from ui.navigation.schema import get_page_spec, get_sidebar_pages_for_method

        root_pages = get_sidebar_pages_for_method(ZAPRET2_MODE, sidebar_group="root")

        self.assertEqual(
            root_pages[:3],
            (
                PageName.ZAPRET2_MODE_CONTROL,
                PageName.ZAPRET2_USER_PRESETS,
                PageName.ZAPRET2_PRESET_SETUP,
            ),
        )
        for page_name in (
            PageName.ZAPRET2_USER_PRESETS,
            PageName.ZAPRET2_PRESET_SETUP,
        ):
            spec = get_page_spec(page_name)
            self.assertTrue(spec.is_top_level)
            self.assertFalse(spec.is_hidden)
            self.assertEqual(spec.sidebar_group, "root")

    def test_winws1_preset_pages_are_visible_in_root_sidebar(self) -> None:
        from app.page_names import PageName
        from settings.mode import ZAPRET1_MODE
        from ui.navigation.schema import get_page_spec, get_sidebar_pages_for_method

        root_pages = get_sidebar_pages_for_method(ZAPRET1_MODE, sidebar_group="root")

        self.assertEqual(
            root_pages[:3],
            (
                PageName.ZAPRET1_MODE_CONTROL,
                PageName.ZAPRET1_USER_PRESETS,
                PageName.ZAPRET1_PRESET_SETUP,
            ),
        )
        for page_name in (
            PageName.ZAPRET1_USER_PRESETS,
            PageName.ZAPRET1_PRESET_SETUP,
        ):
            spec = get_page_spec(page_name)
            self.assertTrue(spec.is_top_level)
            self.assertFalse(spec.is_hidden)
            self.assertEqual(spec.sidebar_group, "root")

    def test_only_real_nested_preset_pages_stay_internal(self) -> None:
        from app.page_names import PageName
        from ui.navigation.schema import INNER_PAGE_NAMES, get_page_spec

        self.assertEqual(
            INNER_PAGE_NAMES,
            frozenset(
                {
                    PageName.ZAPRET2_PROFILE_SETUP,
                    PageName.ZAPRET2_PRESET_RAW_EDITOR,
                    PageName.ZAPRET1_PROFILE_SETUP,
                    PageName.ZAPRET1_PRESET_RAW_EDITOR,
                }
            ),
        )
        for page_name in INNER_PAGE_NAMES:
            spec = get_page_spec(page_name)
            self.assertFalse(spec.is_top_level)
            self.assertTrue(spec.is_hidden)

    def test_control_pages_do_not_build_preset_navigation_cards(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        combined_source = "\n".join(
            (
                inspect.getsource(Zapret1ModeControlPage._build_ui),
                inspect.getsource(Zapret1ModeControlPage._build_deferred_sections),
                inspect.getsource(Zapret2ModeControlPage._build_ui),
                inspect.getsource(Zapret2ModeControlPage._build_deferred_sections),
            )
        )

        forbidden_fragments = (
            "build_winws1_presets_section",
            "build_winws2_presets_section",
            "preset_card",
            "presets_btn",
            "preset_setup_card",
            "preset_setup_open_btn",
        )
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, combined_source)

    def test_sidebar_preset_pages_do_not_build_breadcrumbs(self) -> None:
        import profile.ui.preset_setup_page as preset_setup_page
        import presets.ui.common.user_presets_page as common_user_presets_page
        import presets.ui.zapret1.user_presets_page as zapret1_user_presets_page
        import presets.ui.zapret2.user_presets_page as zapret2_user_presets_page

        combined_source = "\n".join(
            (
                inspect.getsource(preset_setup_page.PresetSetupPageBase.__init__),
                inspect.getsource(common_user_presets_page.UserPresetsPageBase.__init__),
            )
        )

        self.assertNotIn("BreadcrumbBar", combined_source)
        self.assertNotIn("_rebuild_breadcrumb", combined_source)
        self.assertTrue(
            issubclass(
                zapret1_user_presets_page.Zapret1UserPresetsPage,
                common_user_presets_page.UserPresetsPageBase,
            )
        )
        self.assertTrue(
            issubclass(
                zapret2_user_presets_page.Zapret2UserPresetsPage,
                common_user_presets_page.UserPresetsPageBase,
            )
        )

    def test_user_presets_pages_use_one_common_implementation(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase
        from presets.ui.zapret1.user_presets_page import Zapret1UserPresetsPage
        from presets.ui.zapret2.user_presets_page import Zapret2UserPresetsPage

        self.assertIs(Zapret1UserPresetsPage.__mro__[1], UserPresetsPageBase)
        self.assertIs(Zapret2UserPresetsPage.__mro__[1], UserPresetsPageBase)
        self.assertNotIn(
            "build_user_presets_page_shell",
            inspect.getsource(Zapret1UserPresetsPage),
        )
        self.assertNotIn(
            "build_user_presets_page_shell",
            inspect.getsource(Zapret2UserPresetsPage),
        )

    def test_mode_switch_keeps_equivalent_preset_sidebar_page(self) -> None:
        from app.page_names import PageName
        from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
        from ui.workflows.mode import resolve_mode_context_page_for_method

        self.assertEqual(
            resolve_mode_context_page_for_method(PageName.ZAPRET2_USER_PRESETS, ZAPRET1_MODE),
            PageName.ZAPRET1_USER_PRESETS,
        )
        self.assertEqual(
            resolve_mode_context_page_for_method(PageName.ZAPRET1_USER_PRESETS, ZAPRET2_MODE),
            PageName.ZAPRET2_USER_PRESETS,
        )
        self.assertEqual(
            resolve_mode_context_page_for_method(PageName.ZAPRET2_PRESET_SETUP, ZAPRET1_MODE),
            PageName.ZAPRET1_PRESET_SETUP,
        )
        self.assertEqual(
            resolve_mode_context_page_for_method(PageName.ZAPRET1_MODE_CONTROL, ZAPRET2_MODE),
            PageName.ZAPRET2_MODE_CONTROL,
        )


if __name__ == "__main__":
    unittest.main()
