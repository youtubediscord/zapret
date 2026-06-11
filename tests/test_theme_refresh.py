from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget


class ThemeRefreshBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_hidden_pending_refresh_flushes_when_widget_is_shown(self) -> None:
        import ui.theme_refresh as theme_refresh

        widget = QWidget()
        self.addCleanup(widget.deleteLater)
        calls: list[tuple[object, bool]] = []

        binding = theme_refresh.ThemeRefreshBinding(
            widget,
            lambda tokens=None, force=False: calls.append((tokens, bool(force))),
        )

        binding.request_refresh(force=True)

        self.assertEqual(calls, [])

        with patch.object(
            theme_refresh.QTimer,
            "singleShot",
            side_effect=lambda _delay_ms, callback: callback(),
        ):
            widget.show()
            self._app.processEvents()

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1])

    def test_flush_pending_theme_refreshes_walks_window_children(self) -> None:
        import ui.theme_refresh as theme_refresh

        window = QWidget()
        child = QWidget(window)
        self.addCleanup(window.deleteLater)
        calls: list[tuple[object, bool]] = []

        binding = theme_refresh.ThemeRefreshBinding(
            child,
            lambda tokens=None, force=False: calls.append((tokens, bool(force))),
        )

        binding.request_refresh(force=True)
        self.assertEqual(calls, [])

        with patch.object(
            theme_refresh.QTimer,
            "singleShot",
            side_effect=lambda _delay_ms, callback: callback(),
        ):
            window.show()
            child.show()
            self._app.processEvents()
            flushed = theme_refresh.flush_pending_theme_refreshes(window)

        self.assertEqual(flushed, 1)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1])


if __name__ == "__main__":
    unittest.main()
