from __future__ import annotations

import os
import inspect
import unittest
from types import SimpleNamespace


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.fluent_app_window import ZapretFluentWindow
from ui.navigation.search import attach_sidebar_search_to_titlebar, update_titlebar_search_width
from ui.window_ui_facade import _SidebarSearchNavWidget


class FluentAppWindowChromeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_window_uses_qfluentwidgets_content_margins_without_resize_compensation(self) -> None:
        window = ZapretFluentWindow()
        margins = window.widgetLayout.contentsMargins()

        self.assertEqual(margins.top(), 48)
        self.assertEqual(margins.right(), 0)
        self.assertEqual(margins.bottom(), 0)

    def test_window_chrome_has_no_legacy_border_radius_or_handle_hooks(self) -> None:
        source = inspect.getsource(ZapretFluentWindow)

        self.assertNotIn("WINDOW_RESIZE_SAFE_MARGIN", source)
        self.assertNotIn("_apply_window_content_margins", source)
        self.assertNotIn("_update_border_radius", source)
        self.assertNotIn("_set_handles_visible", source)
        self.assertFalse(hasattr(ZapretFluentWindow, "set_zoom_chrome_compact"))

    def test_titlebar_search_is_centered_in_the_whole_window(self) -> None:
        window = ZapretFluentWindow()
        search_widget = _SidebarSearchNavWidget()
        window.ui_session = SimpleNamespace(
            sidebar_search_nav_widget=search_widget,
            sidebar_search_titlebar_attached=False,
        )
        window.resize(1571, 1070)
        window.show()
        self._app.processEvents()

        attach_sidebar_search_to_titlebar(window)
        update_titlebar_search_width(window)
        window.titleBar.hBoxLayout.activate()
        self._app.processEvents()

        search_center = window.titleBar.x() + search_widget.x() + search_widget.width() / 2
        window_center = window.width() / 2

        self.assertAlmostEqual(search_center, window_center, delta=4)


if __name__ == "__main__":
    unittest.main()
