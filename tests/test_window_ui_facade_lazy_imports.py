from __future__ import annotations

import inspect
import unittest


class WindowUiFacadeLazyImportTests(unittest.TestCase):
    def test_window_ui_facade_keeps_qfluentwidgets_out_of_module_import(self) -> None:
        import ui.window_ui_facade as window_ui_facade

        source = inspect.getsource(window_ui_facade)
        top_level = source.split("def _get_nav_icons", 1)[0]

        self.assertNotIn("from qfluentwidgets import", top_level)
        self.assertNotIn("from PyQt6.QtWidgets import", top_level)
        self.assertIn("def _get_nav_icons", source)
        self.assertIn("def _get_sidebar_search_nav_widget_cls", source)


if __name__ == "__main__":
    unittest.main()
