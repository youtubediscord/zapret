from __future__ import annotations

import inspect
import unittest


class Zapret2ControlLazyStartupTests(unittest.TestCase):
    def test_deferred_build_helpers_are_not_imported_on_page_module_import(self) -> None:
        import presets.ui.control.zapret2.page as zapret2_page

        module_source = inspect.getsource(zapret2_page)
        import_block = "\n".join(module_source.splitlines()[:80])
        deferred_source = inspect.getsource(zapret2_page.Zapret2ModeControlPage._build_deferred_sections)

        self.assertNotIn("from presets.ui.control.zapret2.deferred_build import", import_block)
        self.assertNotIn("MessageBoxBase", import_block)
        self.assertNotIn("SegmentedWidget", import_block)
        self.assertIn("from presets.ui.control.zapret2.deferred_build import", deferred_source)

    def test_additional_settings_workers_are_imported_only_when_requested(self) -> None:
        import presets.ui.control.zapret2.page as zapret2_page

        module_source = inspect.getsource(zapret2_page)
        import_block = "\n".join(module_source.splitlines()[:90])
        reload_source = inspect.getsource(zapret2_page.Zapret2ModeControlPage._schedule_additional_settings_reload)
        save_source = inspect.getsource(zapret2_page.Zapret2ModeControlPage._request_additional_settings_save)

        self.assertNotIn("create_additional_settings_worker as create_control_additional_settings_worker", import_block)
        self.assertIn("create_additional_settings_worker as create_control_additional_settings_worker", reload_source)
        self.assertIn("create_additional_settings_save_worker as create_control_additional_settings_save_worker", save_source)

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


if __name__ == "__main__":
    unittest.main()
