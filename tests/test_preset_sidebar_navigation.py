from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


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

    def test_sidebar_plan_keeps_other_mode_items_created_but_hidden(self) -> None:
        from app.page_names import PageName
        from settings.mode import ZAPRET2_MODE
        from ui.navigation.layout_plan import build_sidebar_group_plans
        from ui.navigation.schema import get_nav_visibility

        root_plan = next(
            group_plan
            for group_plan in build_sidebar_group_plans(ZAPRET2_MODE)
            if group_plan.group_name == "root"
        )
        visibility = get_nav_visibility(ZAPRET2_MODE)

        self.assertEqual(
            root_plan.page_names[:3],
            (
                PageName.ZAPRET2_MODE_CONTROL,
                PageName.ZAPRET2_USER_PRESETS,
                PageName.ZAPRET2_PRESET_SETUP,
            ),
        )
        for page_name in (
            PageName.ZAPRET1_MODE_CONTROL,
            PageName.ZAPRET1_USER_PRESETS,
            PageName.ZAPRET1_PRESET_SETUP,
        ):
            self.assertIn(page_name, root_plan.page_names)
            self.assertFalse(visibility[page_name])

    def test_mode_switch_reuses_hidden_other_mode_items(self) -> None:
        from app.page_names import PageName
        from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
        from ui.navigation.schema import get_nav_visibility
        import ui.navigation.sidebar_builder as sidebar_builder

        class FakeNavItem:
            def __init__(self, visible: bool = True) -> None:
                self.visible = visible

            def setVisible(self, visible: bool) -> None:
                self.visible = bool(visible)

        class FakeNavigationInterface:
            def __init__(self, session) -> None:
                self._session = session

            def addItem(self, *, routeKey, icon, text, onClick, selectable, position):
                _ = routeKey, icon, text, onClick, selectable, position
                return FakeNavItem(True)

            def insertItem(self, index, *, routeKey, icon, text, onClick, selectable, position):
                _ = index, routeKey, icon, text, onClick, selectable, position
                return FakeNavItem(True)

        old_pages = (
            PageName.ZAPRET2_MODE_CONTROL,
            PageName.ZAPRET2_USER_PRESETS,
            PageName.ZAPRET2_PRESET_SETUP,
        )
        new_pages = (
            PageName.ZAPRET1_MODE_CONTROL,
            PageName.ZAPRET1_USER_PRESETS,
            PageName.ZAPRET1_PRESET_SETUP,
        )
        initial_visibility = get_nav_visibility(ZAPRET2_MODE)
        session = SimpleNamespace(
            nav_items={
                page_name: FakeNavItem(visible)
                for page_name, visible in initial_visibility.items()
            },
            nav_icons={},
            nav_labels={},
            nav_headers=[],
            nav_header_by_group={},
            nav_search_query="",
            nav_mode_visibility={},
            nav_scroll_position=None,
            default_nav_icon=None,
            ui_language="ru",
            sidebar_search_model=None,
            sidebar_search_completer=None,
            page_host=SimpleNamespace(ensure_page=lambda page_name: None),
        )
        window = SimpleNamespace(
            ui_session=session,
            navigationInterface=FakeNavigationInterface(session),
            get_launch_method=lambda: ZAPRET2_MODE,
        )

        original_pump = sidebar_builder.pump_startup_ui
        try:
            sidebar_builder.pump_startup_ui = lambda current_window: self.fail("mode switch should reuse existing nav items")

            sidebar_builder.sync_nav_visibility(window, ZAPRET1_MODE)
        finally:
            sidebar_builder.pump_startup_ui = original_pump

        self.assertFalse(any(session.nav_items[page_name].visible for page_name in old_pages))
        self.assertTrue(all(session.nav_items[page_name].visible for page_name in new_pages))

    def test_sidebar_search_is_delayed_until_interactive_ready(self) -> None:
        import ui.navigation.sidebar_builder as sidebar_builder

        class Signal:
            def __init__(self) -> None:
                self._callbacks = []

            def connect(self, callback) -> None:
                self._callbacks.append(callback)

            def emit(self) -> None:
                for callback in list(self._callbacks):
                    callback("ui_ready")

        signal = Signal()
        window = SimpleNamespace(
            ui_session=SimpleNamespace(
                sidebar_search_widget_cls=object,
            ),
            startup_state=SimpleNamespace(interactive_logged=False),
            startup_interactive_ready=signal,
        )
        scheduled = []
        installed = []

        with (
            patch.object(
                sidebar_builder.QTimer,
                "singleShot",
                side_effect=lambda delay_ms, callback: scheduled.append((int(delay_ms), callback)),
            ),
            patch.object(
                sidebar_builder,
                "_install_sidebar_search",
                side_effect=lambda current_window: installed.append(current_window),
            ),
        ):
            sidebar_builder._schedule_sidebar_search_after_interactive(window)
            self.assertEqual(scheduled, [])
            self.assertEqual(installed, [])

            signal.emit()

            self.assertEqual(len(scheduled), 1)
            self.assertGreaterEqual(scheduled[0][0], 500)
            self.assertEqual(installed, [])

            scheduled[0][1]()

        self.assertEqual(installed, [window])


if __name__ == "__main__":
    unittest.main()
