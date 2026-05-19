from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import Action, RoundMenu

from ui.popup_menu import exec_popup_menu
from presets.folders import get_preset_item_meta, set_preset_rating


def show_preset_rating_menu(
    parent: QWidget,
    *,
    preset_file_name: str,
    display_name: str,
    folder_scope: str,
    refresh_callback: Callable[[], None],
    clear_label: str,
    global_pos: QPoint | None = None,
) -> None:
    """Show shared preset rating menu and persist the selected rating."""

    menu = RoundMenu(parent=parent)
    current_rating = int(
        get_preset_item_meta(folder_scope, preset_file_name).get("rating", 0) or 0
    )

    clear_action = Action(str(clear_label or "Сбросить рейтинг"), menu)
    menu.addAction(clear_action)
    clear_action.setCheckable(True)
    clear_action.setChecked(current_rating == 0)
    menu.addSeparator()

    actions = {}
    for value in range(1, 11):
        action = Action(f"{value}/10", menu)
        menu.addAction(action)
        action.setCheckable(True)
        action.setChecked(current_rating == value)
        actions[action] = value

    chosen = exec_popup_menu(
        menu,
        global_pos or QCursor.pos(),
        owner=parent,
        capture_action=True,
    )
    if chosen == clear_action:
        set_preset_rating(folder_scope, preset_file_name, 0, display_name=display_name)
        refresh_callback()
        return

    if chosen in actions:
        set_preset_rating(folder_scope, preset_file_name, actions[chosen], display_name=display_name)
        refresh_callback()
