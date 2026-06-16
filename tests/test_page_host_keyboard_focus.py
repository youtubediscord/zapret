from __future__ import annotations

import unittest
from unittest.mock import patch

from app.page_names import PageName
from ui.page_host import WindowPageHost


class PageHostKeyboardFocusTests(unittest.TestCase):
    def test_show_page_requests_keyboard_focus_when_page_is_already_current(self) -> None:
        class _Page:
            def __init__(self) -> None:
                self.focus_requests = 0

            def request_keyboard_focus(self) -> None:
                self.focus_requests += 1

        page = _Page()

        class _FakeStack:
            def currentWidget(self):  # noqa: N802
                return page

            def indexOf(self, _page):  # noqa: N802
                return 0

        class _FakeWindow:
            def __init__(self) -> None:
                self.stackedWidget = _FakeStack()

            def get_launch_method(self) -> str:
                return "zapret2_mode"

        window = _FakeWindow()
        host = WindowPageHost(window=window, page_factory=None)
        host.pages[PageName.ZAPRET2_USER_PRESETS] = page
        host._shown_pages.add(PageName.ZAPRET2_USER_PRESETS)

        with patch("ui.page_host.apply_ui_language_to_page"):
            self.assertTrue(host.show_page(PageName.ZAPRET2_USER_PRESETS, allow_internal=True))

        self.assertEqual(page.focus_requests, 1)


if __name__ == "__main__":
    unittest.main()
