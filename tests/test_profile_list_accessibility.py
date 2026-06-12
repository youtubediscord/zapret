from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication


def _profile_item(name: str, *, key: str = "profile-youtube"):
    from profile.state import ProfileListItem

    return ProfileListItem(
        key=key,
        persistent_key=key,
        profile_index=0,
        display_name=name,
        enabled=True,
        in_preset=True,
        strategy_id="pass",
        strategy_name="pass",
        match_lines=("--filter-tcp=443", f"--hostlist=lists/{name.lower()}.txt"),
        list_type="hostlist",
        rating="",
        favorite=False,
        group="youtube",
        group_name="YouTube",
        order=0,
        profile_name=name,
    )


class ProfileListAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_profile_list_has_screen_reader_name_and_help(self) -> None:
        from profile.ui.profiles_list import ProfilesList

        widget = ProfilesList()
        self.addCleanup(widget.deleteLater)

        self.assertEqual(widget.accessibleName(), "Список профилей: список пока загружается")
        self.assertIn("стрелками вверх и вниз", widget.accessibleDescription())
        self.assertEqual(widget.property("screenReaderStateText"), "Список профилей: список пока загружается")
        self.assertEqual(widget._view.accessibleName(), "Список профилей: список пока загружается")
        self.assertEqual(widget._view.property("screenReaderStateText"), "Список профилей: список пока загружается")
        self.assertIn("Enter или Пробел открывает выбранный profile", widget._view.accessibleDescription())
        self.assertIn("клавиша меню открывает действия", widget._view.accessibleDescription())

    def test_profile_list_wrapper_forwards_keyboard_focus_to_view(self) -> None:
        from profile.ui.profiles_list import ProfilesList

        widget = ProfilesList()
        self.addCleanup(widget.deleteLater)

        self.assertEqual(widget.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertIs(widget.focusProxy(), widget._view)

    def test_profile_list_focuses_first_loaded_row_for_screen_reader(self) -> None:
        from profile.list_view_state import build_profile_list_view_state
        from profile.ui.profiles_list import ProfilesList

        widget = ProfilesList()
        self.addCleanup(widget.deleteLater)

        state = build_profile_list_view_state(
            (_profile_item("YouTube"),),
            active_profile_types={"all"},
            search_query="",
            group_expanded={},
        )
        widget.apply_view_state(state)

        self.assertEqual(widget._view.currentIndex().row(), 0)
        self.assertNotEqual(
            widget._view.property("screenReaderStateText"),
            "Список профилей: список пока загружается",
        )
        self.assertIn("Список профилей:", widget._view.property("screenReaderStateText"))
        self.assertIn("YouTube", widget._view.property("screenReaderStateText"))

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

    def test_profile_list_toggles_selected_folder_from_keyboard(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel
        from profile.ui.profile_list_view import ProfileListView

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

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Return), Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, ["video"])


if __name__ == "__main__":
    unittest.main()
