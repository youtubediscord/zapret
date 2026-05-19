from __future__ import annotations

import unittest

from PyQt6.QtCore import QEvent, Qt

from ui.widgets.folder_header import folder_header_icon_name, folder_header_title, is_folder_toggle_click


class _Event:
    def __init__(self, event_type, button):
        self._event_type = event_type
        self._button = button

    def type(self):
        return self._event_type

    def button(self):
        return self._button


class FolderHeaderTests(unittest.TestCase):
    def test_icon_name_matches_expanded_state(self) -> None:
        self.assertEqual(folder_header_icon_name(True), "fa5s.chevron-down")
        self.assertEqual(folder_header_icon_name(False), "fa5s.chevron-right")

    def test_title_appends_count_like_gui_folder_header(self) -> None:
        self.assertEqual(folder_header_title("YouTube", 3), "YouTube  3")
        self.assertEqual(folder_header_title("YouTube", 0), "YouTube")

    def test_folder_toggles_only_on_left_mouse_release(self) -> None:
        self.assertTrue(is_folder_toggle_click(_Event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton)))
        self.assertFalse(is_folder_toggle_click(_Event(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton)))
        self.assertFalse(is_folder_toggle_click(_Event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.RightButton)))


if __name__ == "__main__":
    unittest.main()
