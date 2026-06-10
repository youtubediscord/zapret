from __future__ import annotations

import inspect
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


class WindowUiFacadeLazyImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_window_ui_facade_keeps_qfluentwidgets_out_of_module_import(self) -> None:
        import ui.window_ui_facade as window_ui_facade

        source = inspect.getsource(window_ui_facade)
        top_level = source.split("def _get_nav_icons", 1)[0]

        self.assertNotIn("from qfluentwidgets import", top_level)
        self.assertNotIn("from PyQt6.QtWidgets import", top_level)
        self.assertIn("def _get_nav_icons", source)
        self.assertIn("def _get_sidebar_search_nav_widget_cls", source)

    def test_sidebar_search_widget_explains_keyboard_activation(self) -> None:
        import ui.window_ui_facade as window_ui_facade

        widget_cls = window_ui_facade._get_sidebar_search_nav_widget_cls()
        widget = widget_cls()
        self.addCleanup(widget.deleteLater)

        self.assertEqual(widget.accessibleName(), "Глобальный поиск по ZapretGUI")
        self.assertIn("выберите результат стрелками", widget.accessibleDescription())
        self.assertIn("Enter открывает выбранный результат", widget.accessibleDescription())
        self.assertEqual(widget._search.accessibleName(), "Глобальный поиск по ZapretGUI")
        self.assertIn("Enter открывает выбранный результат", widget._search.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
