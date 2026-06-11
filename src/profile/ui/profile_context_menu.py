from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from qfluentwidgets import RoundMenu

from ui.popup_menu import exec_popup_menu
from ui.presets_menu.common import fluent_icon, make_menu_action


@dataclass(frozen=True)
class ProfileContextMenuActions:
    open_profile: Callable[[str], object]
    set_enabled: Callable[[str, bool], object]
    duplicate_profile: Callable[[str], object]
    delete_from_preset: Callable[[str], object]
    edit_user_profile: Callable[[str], object]
    delete_user_profile: Callable[[str], object]


def show_profile_context_menu(
    *,
    parent,
    item,
    global_pos,
    actions: ProfileContextMenuActions,
) -> None:
    profile_key = str(getattr(item, "key", "") or "").strip()
    if not profile_key:
        return

    in_preset = bool(getattr(item, "in_preset", False))
    enabled = bool(getattr(item, "enabled", False))
    user_profile_id = str(getattr(item, "user_profile_id", "") or "").strip()
    is_user_profile = bool(user_profile_id or profile_key.startswith("template:user:"))

    menu = RoundMenu(parent=parent)
    action_map: dict[object, tuple[str, object]] = {}

    open_action = make_menu_action("Открыть", icon=fluent_icon("VIEW"), parent=menu)
    menu.addAction(open_action)
    action_map[open_action] = ("open", None)

    if in_preset:
        toggle_action = make_menu_action(
            "Выключить" if enabled else "Включить",
            icon=fluent_icon("CANCEL") if enabled else fluent_icon("ACCEPT"),
            parent=menu,
        )
        menu.addAction(toggle_action)
        action_map[toggle_action] = ("set_enabled", not enabled)

        duplicate_action = make_menu_action("Дублировать", icon=fluent_icon("COPY"), parent=menu)
        menu.addAction(duplicate_action)
        action_map[duplicate_action] = ("duplicate", None)

        delete_action = make_menu_action("Удалить из preset", icon=fluent_icon("DELETE"), parent=menu)
        menu.addAction(delete_action)
        action_map[delete_action] = ("delete_from_preset", None)
    else:
        add_action = make_menu_action("Добавить в preset", icon=fluent_icon("ADD"), parent=menu)
        menu.addAction(add_action)
        action_map[add_action] = ("set_enabled", True)

    if is_user_profile:
        menu.addSeparator()
        edit_action = make_menu_action("Изменить пользовательский profile", icon=fluent_icon("EDIT"), parent=menu)
        menu.addAction(edit_action)
        action_map[edit_action] = ("edit_user_profile", None)

        delete_user_action = make_menu_action("Удалить пользовательский profile", icon=fluent_icon("DELETE"), parent=menu)
        menu.addAction(delete_user_action)
        action_map[delete_user_action] = ("delete_user_profile", None)

    chosen = exec_popup_menu(menu, global_pos, owner=parent, capture_action=True)
    command, payload = action_map.get(chosen, ("", None))
    if command == "open":
        actions.open_profile(profile_key)
    elif command == "set_enabled":
        actions.set_enabled(profile_key, bool(payload))
    elif command == "duplicate":
        actions.duplicate_profile(profile_key)
    elif command == "delete_from_preset":
        actions.delete_from_preset(profile_key)
    elif command == "edit_user_profile":
        actions.edit_user_profile(profile_key)
    elif command == "delete_user_profile":
        actions.delete_user_profile(profile_key)
