from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication


class ProfileListAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_profile_list_has_screen_reader_name_and_help(self) -> None:
        from profile.ui.profiles_list import ProfilesList

        widget = ProfilesList()
        self.addCleanup(widget.deleteLater)

        self.assertEqual(widget.accessibleName(), "Список профилей")
        self.assertIn("стрелками вверх и вниз", widget.accessibleDescription())
        self.assertEqual(widget._view.accessibleName(), "Список профилей")
        self.assertIn("Enter открывает выбранный profile", widget._view.accessibleDescription())
        self.assertIn("клавиша меню открывает действия", widget._view.accessibleDescription())

    def test_profile_list_opens_selected_profile_menu_from_keyboard(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel
        from profile.ui.profile_list_view import ProfileListView

        model = ProfileListModel()
        model._rows = [
            {
                "kind": "profile",
                "key": "profile-youtube",
                "display_name": "YouTube",
            }
        ]
        view = ProfileListView()
        self.addCleanup(view.deleteLater)
        view.setModel(model)
        view.setCurrentIndex(model.index(0, 0))
        requested: list[str] = []
        view.profile_context_requested.connect(lambda key, _point: requested.append(key))

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Menu), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, ["profile-youtube"])


if __name__ == "__main__":
    unittest.main()
