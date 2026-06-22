from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import RoundMenu

from ui.popup_menu import exec_popup_menu


def show_preset_actions_menu(
    parent: QWidget,
    *,
    global_pos: QPoint | None,
    is_builtin: bool,
    disabled_actions: set[str] | None = None,
    labels: dict[str, str],
    make_menu_action: Callable[..., object],
    icon_resolver: Callable[[str], object | None],
    round_menu_cls=RoundMenu,
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

    def _create_action(menu, key: str) -> object:
        return make_menu_action(
            labels[key],
            icon=icon_resolver(action_specs_map[key]),
            parent=menu,
        )

    action_specs_map = {key: icon_name for key, icon_name in action_specs}
    action_order = ["open", "rating", "move_up", "move_down", "duplicate", "export"]
    if not is_builtin:
        action_order.insert(4, "rename")
        action_order.append("reset")
        action_order.append("delete")

    disabled_action_keys = {str(key or "").strip() for key in (disabled_actions or set())}
    menu = round_menu_cls(parent=parent)
    action_map: dict[object, str] = {}
    for key in action_order:
        action = _create_action(menu, key)
        is_disabled = key in disabled_action_keys
        if is_disabled and hasattr(action, "setEnabled"):
            action.setEnabled(False)
        menu.addAction(action)
        _set_menu_item_accessibility(
            menu,
            text=labels[key],
            disabled=is_disabled,
        )
        action_map[action] = key
    chosen = exec_popup_menu(
        menu,
        global_pos or QCursor.pos(),
        owner=parent,
        capture_action=True,
    )
    chosen_key = action_map.get(chosen)
    if chosen_key in disabled_action_keys:
        return None
    return chosen_key


def _set_menu_item_accessibility(menu, *, text: str, disabled: bool) -> None:
    menu_view = getattr(menu, "view", None)
    if menu_view is None:
        return
    try:
        item = menu_view.item(menu_view.count() - 1)
    except Exception:
        item = None
    if item is None:
        return
    accessible_text = f"Действие preset: {str(text or '').strip()}"
    if disabled:
        accessible_text = f"{accessible_text}, недоступно"
    item.setData(Qt.ItemDataRole.AccessibleTextRole, accessible_text)
    item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, accessible_text)
