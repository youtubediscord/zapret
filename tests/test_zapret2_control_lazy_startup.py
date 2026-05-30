from __future__ import annotations

import inspect
import unittest


class ControlPageImmediateStartupTests(unittest.TestCase):
    def test_control_pages_build_settings_sections_immediately(self) -> None:
        import presets.ui.control.zapret1.page as zapret1_page
        import presets.ui.control.zapret2.page as zapret2_page

        for page_cls in (zapret1_page.Zapret1ModeControlPage, zapret2_page.Zapret2ModeControlPage):
            with self.subTest(page_cls=page_cls.__name__):
                page_source = inspect.getsource(page_cls)
                build_ui_source = inspect.getsource(page_cls._build_ui)

                self.assertIn("_build_settings_sections", build_ui_source)
                self.assertIn("_attach_program_settings_runtime", build_ui_source)
                self.assertIn("_schedule_additional_settings_reload(force=True)", build_ui_source)
                self.assertNotIn("_build_deferred_sections", page_source)
                self.assertNotIn("_run_deferred_show_work", page_source)
                self.assertNotIn("_startup_can_run_deferred_sections", page_source)
                self.assertNotIn("STARTUP_DEFERRED_SECTIONS", page_source)

    def test_additional_settings_workers_are_imported_only_when_requested(self) -> None:
        import presets.ui.control.zapret2.page as zapret2_page

        module_source = inspect.getsource(zapret2_page)
        import_block = "\n".join(module_source.splitlines()[:90])
        reload_source = inspect.getsource(zapret2_page.Zapret2ModeControlPage._schedule_additional_settings_reload)
        save_source = inspect.getsource(zapret2_page.Zapret2ModeControlPage._request_additional_settings_save)

        self.assertNotIn("create_additional_settings_worker as create_control_additional_settings_worker", import_block)
        self.assertIn("create_additional_settings_worker as create_control_additional_settings_worker", reload_source)
        self.assertIn("_create_additional_settings_save_worker", save_source)

    def test_zapret2_page_runtime_is_not_imported_on_page_module_import(self) -> None:
        import presets.ui.control.zapret2.page as zapret2_page
        import presets.ui.control.zapret2.runtime_helpers as runtime_helpers

        page_source = inspect.getsource(zapret2_page)
        page_import_block = "\n".join(page_source.splitlines()[:90])
        helper_source = inspect.getsource(runtime_helpers)
        helper_import_block = "\n".join(helper_source.splitlines()[:30])
        after_ui_source = inspect.getsource(zapret2_page.Zapret2ModeControlPage._after_ui_built)

        self.assertNotIn("import presets.ui.control.zapret2.page_runtime", page_import_block)
        self.assertNotIn("import presets.ui.control.zapret2.page_runtime", helper_import_block)
        self.assertIn("def _zapret2_page_runtime", page_source)
        self.assertNotIn("_update_stop_winws_button_text()", after_ui_source)

    def test_zapret2_first_page_keeps_theme_refresh_imports_lazy(self) -> None:
        import presets.ui.control.shared_builders as shared_builders
        import presets.ui.control.top_summary_widget as top_summary_widget
        import presets.ui.control.zapret2.page as zapret2_page
        import ui.pages.base_page as base_page

        shared_source = inspect.getsource(shared_builders)
        shared_import_block = "\n".join(shared_source.splitlines()[:30])
        top_summary_source = inspect.getsource(top_summary_widget)
        top_summary_import_block = "\n".join(top_summary_source.splitlines()[:30])
        zapret2_page_source = inspect.getsource(zapret2_page)
        zapret2_import_block = "\n".join(zapret2_page_source.splitlines()[:45])
        item_init_source = inspect.getsource(top_summary_widget.ControlTopSummaryItem.__init__)
        activate_source = inspect.getsource(top_summary_widget.ControlTopSummaryItem._activate_theme_refresh)
        base_page_source = inspect.getsource(base_page)
        base_page_import_block = "\n".join(base_page_source.splitlines()[:35])
        zapret2_source = inspect.getsource(zapret2_page.Zapret2ModeControlPage)

        self.assertNotIn("from ui.theme import", top_summary_import_block)
        self.assertNotIn("from ui.theme_refresh import", top_summary_import_block)
        self.assertIn("_schedule_icon_refresh", item_init_source)
        self.assertIn("from ui.theme_refresh import ThemeRefreshBinding", activate_source)
        self.assertNotIn("from ui.theme_refresh import", base_page_import_block)
        self.assertIn("_create_page_theme_refresh_if_needed", base_page_source)
        self.assertNotIn("def _apply_page_theme", zapret2_source)
        self.assertNotIn("from ui.fluent_widgets import", shared_import_block)
        self.assertIn("from ui.pulsing_dot import PulsingDot", shared_import_block)

    def test_zapret2_top_summary_icons_are_delayed_past_first_paint(self) -> None:
        import inspect

        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        build_ui_source = inspect.getsource(Zapret2ModeControlPage._build_ui)

        self.assertIn("ControlTopSummaryWidget", build_ui_source)
        self.assertIn("initial_icon_delay_ms=250", build_ui_source)

    def test_zapret2_startup_does_not_build_hidden_profile_mode_card(self) -> None:
        import inspect

        import presets.ui.control.zapret2.sections_build as sections_build

        source = inspect.getsource(sections_build.build_winws2_pages_settings_sections)

        self.assertNotIn("profile_ui_mode_card = build_push_setting_card_common", source)
        self.assertNotIn("get_cached_qta_pixmap", source)
        self.assertIn("profile_ui_mode_btn=None", source)

    def test_zapret2_program_settings_auto_height_is_not_applied_twice(self) -> None:
        import inspect

        import presets.ui.control.zapret2.sections_build as sections_build
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        page_source = inspect.getsource(Zapret2ModeControlPage._build_settings_sections)
        builder_source = inspect.getsource(sections_build.build_winws2_pages_settings_sections)

        self.assertIn("enable_setting_card_group_auto_height(program_settings_card)", builder_source)
        self.assertNotIn("enable_setting_card_group_auto_height(self.program_settings_card)", page_source)


if __name__ == "__main__":
    unittest.main()
