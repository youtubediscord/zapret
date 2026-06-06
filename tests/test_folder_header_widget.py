from __future__ import annotations

import unittest

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import QApplication

from ui.widgets.folder_header import (
    FOLDER_HEADER_GAP,
    FOLDER_HEADER_ICON_BOX,
    FOLDER_HEADER_LEFT_MARGIN,
    FOLDER_HEADER_RIGHT_MARGIN,
    FOLDER_HEADER_STYLE_SHEET,
    FolderGroupHeader,
    folder_header_font,
    folder_header_icon_name,
    folder_header_title,
    is_folder_toggle_click,
)


class _Event:
    def __init__(self, event_type, button):
        self._event_type = event_type
        self._button = button

    def type(self):
        return self._event_type

    def button(self):
        return self._button


class FolderHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_icon_name_matches_expanded_state(self) -> None:
        self.assertEqual(folder_header_icon_name(True), "fa5s.chevron-down")
        self.assertEqual(folder_header_icon_name(False), "fa5s.chevron-right")

    def test_title_appends_count_like_gui_folder_header(self) -> None:
        self.assertEqual(folder_header_title("YouTube", 3), "YouTube  3")
        self.assertEqual(folder_header_title("YouTube", 0), "YouTube")
        self.assertEqual(folder_header_title("YouTube", -1), "YouTube")

    def test_folder_toggles_only_on_left_mouse_release(self) -> None:
        self.assertTrue(is_folder_toggle_click(_Event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton)))
        self.assertFalse(is_folder_toggle_click(_Event(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton)))
        self.assertFalse(is_folder_toggle_click(_Event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.RightButton)))

    def test_widget_and_painted_folder_header_share_style_constants(self) -> None:
        self.assertEqual(FOLDER_HEADER_LEFT_MARGIN, 0)
        self.assertEqual(FOLDER_HEADER_RIGHT_MARGIN, 8)
        self.assertEqual(FOLDER_HEADER_ICON_BOX, 16)
        self.assertEqual(FOLDER_HEADER_GAP, 4)
        self.assertIn('QFrame[folderHeader="true"]', FOLDER_HEADER_STYLE_SHEET)

    def test_folder_header_font_uses_shared_weight(self) -> None:
        self.assertEqual(folder_header_font(QFont()).weight(), QFont.Weight.DemiBold)

    def test_folder_header_has_screen_reader_state_text(self) -> None:
        header = FolderGroupHeader("video", "Видео", count=3)

        self.assertEqual(header.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertEqual(header.accessibleName(), "Папка Видео, развернута, элементов: 3")
        self.assertEqual(header.property("screenReaderStateText"), "Папка Видео, развернута, элементов: 3")
        self.assertIn("Enter", header.accessibleDescription())

    def test_folder_header_toggles_from_keyboard_and_updates_state_text(self) -> None:
        header = FolderGroupHeader("video", "Видео", count=3)
        toggles: list[tuple[str, bool]] = []
        header.toggled.connect(lambda key, expanded: toggles.append((key, expanded)))

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(header, event)

        self.assertEqual(toggles, [("video", False)])
        self.assertEqual(header.accessibleName(), "Папка Видео, свернута, элементов: 3")
        self.assertEqual(header.property("screenReaderStateText"), "Папка Видео, свернута, элементов: 3")


if __name__ == "__main__":
    unittest.main()
