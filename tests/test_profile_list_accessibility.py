from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget


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

    def test_profile_list_wrapper_forwards_arrow_and_enter_keys_to_view(self) -> None:
        from profile.ui.profiles_list import ProfilesList

        widget = ProfilesList()
        self.addCleanup(widget.deleteLater)
        widget._model._rows = [
            {
                "kind": "profile",
                "key": "profile-a",
                "display_name": "A",
            },
            {
                "kind": "profile",
                "key": "profile-b",
                "display_name": "B",
            },
        ]
        widget._view.setCurrentIndex(widget._model.index(0, 0))
        opened: list[str] = []
        widget.profile_selected.connect(opened.append)

        down_event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Down), Qt.KeyboardModifier.NoModifier)
        widget.keyPressEvent(down_event)

        self.assertTrue(down_event.isAccepted())
        self.assertEqual(widget._view.currentIndex().row(), 1)

        enter_event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_Return), Qt.KeyboardModifier.NoModifier)
        widget.keyPressEvent(enter_event)

        self.assertTrue(enter_event.isAccepted())
        self.assertEqual(opened, ["profile-b"])

    def test_profile_search_enter_activates_current_profile(self) -> None:
        from qfluentwidgets import SearchLineEdit

        from profile.ui.shell import build_profile_shell, wire_profile_search_keyboard_activation
        from profile.ui.profiles_list import ProfilesList

        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        parent.resize(900, 600)
        layout = QVBoxLayout(parent)
        opened: list[str] = []
        shell = build_profile_shell(
            content_parent=parent,
            content_layout=layout,
            add_section_title=lambda *_args, **_kwargs: None,
            tr_fn=lambda _key, default, **_kwargs: default,
            engine_label="Zapret 2",
            toolbar_title_key="page.profile.toolbar.title",
            request_button_key="page.profile.request",
            request_hint_key="page.profile.request.hint",
            loading_key="page.profile.loading",
            on_open_profile_request_form=lambda: None,
            on_add_user_profile=lambda: None,
            on_expand_all=lambda: None,
            on_collapse_all=lambda: None,
            on_open_profile_order=lambda: None,
            on_show_info_popup=lambda: None,
            on_profile_search_text_changed=lambda _text: None,
        )
        profiles_list = ProfilesList(parent)
        shell.content_host_layout.addWidget(profiles_list)
        profiles_list._model._rows = [
            {
                "kind": "profile",
                "key": "profile-youtube",
                "display_name": "YouTube",
            }
        ]
        profiles_list._view.setCurrentIndex(profiles_list._model.index(0, 0))
        profiles_list.profile_selected.connect(opened.append)
        wire_profile_search_keyboard_activation(shell.profile_search_input, profiles_list)
        parent.show()
        self._app.processEvents()
        shell.profile_search_input.setFocus()
        self._app.processEvents()

        self.assertIsInstance(shell.profile_search_input, SearchLineEdit)

        QTest.keyClick(shell.profile_search_input, Qt.Key.Key_Return)
        self._app.processEvents()

        self.assertIs(self._app.focusWidget(), profiles_list._view)
        self.assertEqual(opened, ["profile-youtube"])

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
