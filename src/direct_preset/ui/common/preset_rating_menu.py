from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget, QMenu

from ui.popup_menu import exec_popup_menu


def show_preset_rating_menu(
    parent: QWidget,
    *,
    preset_file_name: str,
    display_name: str,
    hierarchy_store,
    refresh_callback: Callable[[], None],
    clear_label: str,
    global_pos: QPoint | None = None,
) -> None:
    """Show shared preset rating menu and persist the selected rating."""

    menu = QMenu(parent)
    current_rating = int(
        hierarchy_store.get_preset_meta(
            preset_file_name,
            display_name=display_name,
        ).get("rating", 0) or 0
    )

    clear_action = menu.addAction(str(clear_label or "Сбросить рейтинг"))
    clear_action.setCheckable(True)
    clear_action.setChecked(current_rating == 0)
    menu.addSeparator()

    actions = {}
    for value in range(1, 11):
        action = menu.addAction(f"{value}/10")
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
        hierarchy_store.set_preset_rating(
            preset_file_name,
            0,
            display_name=display_name,
        )
        refresh_callback()
        return

    if chosen in actions:
        hierarchy_store.set_preset_rating(
            preset_file_name,
            actions[chosen],
            display_name=display_name,
        )
        refresh_callback()
