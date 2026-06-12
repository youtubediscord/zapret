from __future__ import annotations

import unittest
from unittest.mock import patch

from PyQt6.QtCore import QPoint, Qt


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.enabled = True

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)


class _FakeMenu:
    def __init__(self, *, parent=None) -> None:
        self.parent = parent
        self.actions: list[_FakeAction] = []
        self.view = _FakeMenuView()

    def addAction(self, action: _FakeAction) -> None:
        self.actions.append(action)
        self.view.add_item()


class _FakeMenuItem:
    def __init__(self) -> None:
        self._data = {}

    def setData(self, role, value) -> None:  # noqa: N802
        self._data[int(role)] = value

    def data(self, role):
        return self._data.get(int(role))


class _FakeMenuView:
    def __init__(self) -> None:
        self._items: list[_FakeMenuItem] = []

    def add_item(self) -> None:
        self._items.append(_FakeMenuItem())

    def count(self) -> int:
        return len(self._items)

    def item(self, row: int):
        return self._items[row] if 0 <= row < len(self._items) else None


class PresetActionsMenuTests(unittest.TestCase):
    def test_selected_user_preset_delete_action_is_disabled(self) -> None:
        from presets.ui.common import preset_actions_menu

        menu_holder: dict[str, _FakeMenu] = {}

        class CapturingMenu(_FakeMenu):
            def __init__(self, *, parent=None) -> None:
                super().__init__(parent=parent)
                menu_holder["menu"] = self

        def make_action(text: str, *, icon=None, parent=None) -> _FakeAction:
            return _FakeAction(text)

        labels = {
            "open": "Открыть",
            "rating": "Рейтинг",
            "move_up": "Переместить выше",
            "move_down": "Переместить ниже",
            "rename": "Переименовать",
            "duplicate": "Дублировать",
            "export": "Экспорт",
            "reset": "Вернуть встроенный",
            "delete": "Удалить",
        }

        with patch.object(preset_actions_menu, "exec_popup_menu", return_value=None):
            preset_actions_menu.show_preset_actions_menu(
                object(),
                global_pos=QPoint(0, 0),
                is_builtin=False,
                disabled_actions={"delete"},
                labels=labels,
                make_menu_action=make_action,
                icon_resolver=lambda _name: None,
                round_menu_cls=CapturingMenu,
            )

        delete_actions = [action for action in menu_holder["menu"].actions if action.text == "Удалить"]

        self.assertEqual(len(delete_actions), 1)
        self.assertFalse(delete_actions[0].enabled)
        accessible_items = [
            menu_holder["menu"].view.item(row).data(Qt.ItemDataRole.AccessibleTextRole)
            for row in range(menu_holder["menu"].view.count())
            if menu_holder["menu"].view.item(row) is not None
            and menu_holder["menu"].view.item(row).data(Qt.ItemDataRole.AccessibleTextRole)
        ]

        self.assertIn("Действие preset: Открыть", accessible_items)
        self.assertIn("Действие preset: Переименовать", accessible_items)
        self.assertIn("Действие preset: Удалить, недоступно", accessible_items)

    def test_list_menu_disables_delete_for_selected_user_preset(self) -> None:
        from presets.ui.common.user_presets_item_actions_workflow import open_edit_preset_menu_action

        captured: dict[str, object] = {}

        def show_menu(_page, **kwargs):
            captured.update(kwargs)
            return None

        open_edit_preset_menu_action(
            page=object(),
            name="custom.txt",
            global_pos=QPoint(0, 0),
            is_builtin_preset_file_fn=lambda _name: False,
            is_selected_preset_file_fn=lambda name: name == "custom.txt",
            tr_fn=lambda _key, fallback, **_kwargs: fallback,
            make_menu_action=lambda text, **_kwargs: _FakeAction(text),
            fluent_icon=lambda _name: None,
            round_menu_cls=_FakeMenu,
            on_preset_list_action_fn=lambda _action, _name: None,
            show_preset_actions_menu_fn=show_menu,
            tr_prefix="page.presets",
        )

        self.assertEqual(captured.get("disabled_actions"), {"delete"})


if __name__ == "__main__":
    unittest.main()
