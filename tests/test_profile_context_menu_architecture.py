from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from profile.ui import profile_context_menu


class _Menu:
    def __init__(self, parent=None) -> None:
        self.parent = parent
        self._actions = []

    def addAction(self, action) -> None:  # noqa: N802
        self._actions.append(action)

    def addSeparator(self) -> None:  # noqa: N802
        self._actions.append(None)


class _Action:
    def __init__(self, text: str) -> None:
        self.text = text


class ProfileContextMenuArchitectureTests(unittest.TestCase):
    def test_profile_context_menu_returns_action_before_dispatch(self) -> None:
        source = inspect.getsource(profile_context_menu.show_profile_context_menu)

        self.assertIn("exec_popup_menu", source)
        self.assertIn("capture_action=True", source)
        self.assertIn("action_map", source)
        self.assertNotIn("menu.exec(", source)
        self.assertNotIn("triggered.connect", source)

    def test_profile_context_menu_dispatches_chosen_action_after_menu_closes(self) -> None:
        item = SimpleNamespace(key="profile-1", in_preset=True, enabled=True, user_profile_id="")
        actions = profile_context_menu.ProfileContextMenuActions(
            open_profile=Mock(),
            set_enabled=Mock(),
            duplicate_profile=Mock(),
            delete_from_preset=Mock(),
            edit_user_profile=Mock(),
            delete_user_profile=Mock(),
        )
        created_actions: dict[str, _Action] = {}

        def make_action(text: str, *, icon=None, parent=None):
            action = _Action(text)
            created_actions[text] = action
            return action

        with (
            patch("profile.ui.profile_context_menu.RoundMenu", _Menu),
            patch("profile.ui.profile_context_menu.make_menu_action", side_effect=make_action),
            patch(
                "profile.ui.profile_context_menu.exec_popup_menu",
                side_effect=lambda *_args, **_kwargs: created_actions["Выключить"],
            ) as exec_menu,
        ):
            profile_context_menu.show_profile_context_menu(
                parent=None,
                item=item,
                global_pos=None,
                actions=actions,
            )

        exec_menu.assert_called_once()
        self.assertTrue(exec_menu.call_args.kwargs.get("capture_action"))
        actions.set_enabled.assert_called_once_with("profile-1", False)
        actions.open_profile.assert_not_called()
        actions.duplicate_profile.assert_not_called()
        actions.delete_from_preset.assert_not_called()


if __name__ == "__main__":
    unittest.main()
