from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_SRC = Path(__file__).resolve().parent.parent / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class SwitchDiagnosticsSafetyTests(unittest.TestCase):
    def test_page_switch_has_no_synchronous_profiler_or_widget_tree_walk(self) -> None:
        from ui import page_host

        source = inspect.getsource(page_host)

        self.assertNotIn("sys.setprofile", source)
        self.assertNotIn("_SwitchTracer", source)
        self.assertNotIn("findChildren", source)

    def test_timing_failure_does_not_cancel_completed_switch(self) -> None:
        from app.page_names import PageName
        from ui.page_host import WindowPageHost

        calls = []

        class Window:
            stackedWidget = object()

            def switchTo(self, page):  # noqa: N802
                calls.append(page)

        host = WindowPageHost(Window(), page_factory=None)
        page = object()

        with patch("ui.page_host.log_page_timing", side_effect=RuntimeError("boom")):
            self.assertTrue(
                host.set_stacked_widget_current_page(
                    page,
                    page_name=PageName.ZAPRET2_USER_PRESETS,
                )
            )
        self.assertEqual(calls, [page])


class StackedBackgroundContractTests(unittest.TestCase):
    def test_app_window_uses_stock_qfluent_background_update(self) -> None:
        from ui.fluent_app_window import ZapretFluentWindow

        self.assertNotIn("_updateStackedBackground", ZapretFluentWindow.__dict__)

    def test_page_host_sets_explicit_qfluent_background_property(self) -> None:
        from ui.page_host import WindowPageHost

        class Page:
            def __init__(self) -> None:
                self.properties = {}

            def property(self, name):
                return self.properties.get(name)

            def setProperty(self, name, value):  # noqa: N802
                self.properties[name] = value

        class Stack:
            def __init__(self) -> None:
                self.added = []

            def indexOf(self, _page):  # noqa: N802
                return -1

            def addWidget(self, page):  # noqa: N802
                self.added.append(page)

        page = Page()
        stack = Stack()
        host = WindowPageHost(type("Window", (), {"stackedWidget": stack})(), page_factory=None)

        host.ensure_page_in_stacked_widget(page)

        self.assertIs(page.property("isStackedTransparent"), False)
        self.assertEqual(stack.added, [page])


if __name__ == "__main__":
    unittest.main()
