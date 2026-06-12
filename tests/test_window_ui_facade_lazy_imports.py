from __future__ import annotations

import inspect
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
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

        search_buttons = [
            child
            for child in widget._search.findChildren(object)
            if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
            and hasattr(child, "setFocusPolicy")
        ]
        self.assertTrue(search_buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in search_buttons))

    def test_sidebar_search_widget_emits_keyboard_result_actions(self) -> None:
        import ui.window_ui_facade as window_ui_facade

        widget_cls = window_ui_facade._get_sidebar_search_nav_widget_cls()
        widget = widget_cls()
        self.addCleanup(widget.deleteLater)
        navigation_steps: list[int] = []
        activations: list[bool] = []
        widget.completionNavigationRequested.connect(navigation_steps.append)
        widget.completionActivationRequested.connect(lambda: activations.append(True))
        widget.show()
        self._app.processEvents()
        widget._search.setFocus()
        self._app.processEvents()

        QTest.keyClick(widget._search, Qt.Key.Key_Down)
        QTest.keyClick(widget._search, Qt.Key.Key_Up)
        QTest.keyClick(widget._search, Qt.Key.Key_Return)

        self.assertEqual(navigation_steps, [1, -1])
        self.assertEqual(activations, [True])


if __name__ == "__main__":
    unittest.main()
