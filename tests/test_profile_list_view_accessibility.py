from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from profile.ui.profile_list_model import ProfileListModel
from profile.ui.profile_list_view import ProfileListView


class ProfileListViewAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_current_row_updates_screen_reader_state_text(self) -> None:
        model = ProfileListModel()
        model._rows = [
            {
                "kind": "profile",
                "display_name": "YouTube",
                "enabled": True,
                "in_preset": True,
                "strategy_name": "TLS fake",
            },
            {
                "kind": "group",
                "group_name": "Видео",
                "count": 2,
                "collapsed": False,
            },
        ]
        view = ProfileListView()
        self.addCleanup(view.deleteLater)
        view.set_screen_reader_list_name("Список профилей")
        view.setModel(model)

        view.setCurrentIndex(model.index(0, 0))

        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список профилей: YouTube, включён, есть в preset, стратегия: TLS fake. "
            "Нажмите Enter или Пробел, чтобы открыть profile.",
        )

        view.setCurrentIndex(model.index(1, 0))

        self.assertEqual(
            view.property("screenReaderStateText"),
            "Список профилей: Группа Видео, 2 профиля, развернута. "
            "Нажмите Enter или Пробел, чтобы свернуть или развернуть группу.",
        )

    def test_empty_current_row_keeps_list_name_for_screen_reader(self) -> None:
        view = ProfileListView()
        self.addCleanup(view.deleteLater)
        view.set_screen_reader_list_name("Порядок profile")

        self.assertEqual(view.property("screenReaderStateText"), "Порядок profile")

    def test_space_activates_selected_profile(self) -> None:
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
        view.profile_activated.connect(requested.append)

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, ["profile-youtube"])

    def test_space_toggles_selected_folder(self) -> None:
        model = ProfileListModel()
        model._rows = [
            {
                "kind": "folder",
                "group": "video",
                "group_name": "Видео",
            }
        ]
        view = ProfileListView()
        self.addCleanup(view.deleteLater)
        view.setModel(model)
        view.setCurrentIndex(model.index(0, 0))
        requested: list[str] = []
        view.folder_toggle_requested.connect(requested.append)

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, ["video"])


if __name__ == "__main__":
    unittest.main()
