from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtWidgets import QMenu, QWidget

from ui.popup_menu import exec_popup_menu


def show_preset_actions_menu(
    parent: QWidget,
    *,
    global_pos: QPoint | None,
    is_builtin: bool,
    labels: dict[str, str],
    make_menu_action: Callable[..., QAction],
    icon_resolver: Callable[[str], object | None],
    round_menu_cls=None,
) -> str | None:
    """Show shared preset actions menu and return chosen action key."""

    action_specs = [
        ("open", "VIEW"),
        ("rating", "FAVORITE"),
        ("move_up", "UP"),
        ("move_down", "DOWN"),
        ("rename", "RENAME"),
        ("duplicate", "COPY"),
        ("export", "SHARE"),
        ("reset", "SYNC"),
        ("delete", "DELETE"),
    ]

    def _create_action(menu, key: str) -> QAction:
        return make_menu_action(
            labels[key],
            icon=icon_resolver(action_specs_map[key]),
            parent=menu,
        )

    action_specs_map = {key: icon_name for key, icon_name in action_specs}
    action_order = ["open", "rating", "move_up", "move_down", "duplicate", "export", "reset"]
    if not is_builtin:
        action_order.insert(4, "rename")
        action_order.append("delete")

    if round_menu_cls is not None:
        menu = round_menu_cls(parent=parent)
        action_map: dict[QAction, str] = {}
        for key in action_order:
            action = _create_action(menu, key)
            menu.addAction(action)
            action_map[action] = key
        chosen = exec_popup_menu(
            menu,
            global_pos or QCursor.pos(),
            owner=parent,
            capture_action=True,
        )
        return action_map.get(chosen)

    menu = QMenu(parent)
    action_map = {menu.addAction(labels[key]): key for key in action_order}
    chosen = exec_popup_menu(
        menu,
        global_pos or QCursor.pos(),
        owner=parent,
        capture_action=True,
    )
    return action_map.get(chosen)
