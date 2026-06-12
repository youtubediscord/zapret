from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import Qt
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

    profile_name = _profile_menu_name(item, fallback=profile_key)

    def _add_action(text: str, *, icon_name: str, command: str, payload: object = None):
        action = make_menu_action(text, icon=fluent_icon(icon_name), parent=menu)
        menu.addAction(action)
        accessible_text = _profile_menu_accessible_text(
            text=text,
            command=command,
            profile_name=profile_name,
        )
        menu_item = menu.view.item(menu.view.count() - 1)
        if menu_item is not None and accessible_text:
            menu_item.setData(Qt.ItemDataRole.AccessibleTextRole, accessible_text)
            menu_item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, accessible_text)
        action_map[action] = (str(command or ""), payload)
        return action

    _add_action("Открыть", icon_name="VIEW", command="open")

    if in_preset:
        _add_action(
            "Выключить" if enabled else "Включить",
            icon_name="CANCEL" if enabled else "ACCEPT",
            command="set_enabled",
            payload=not enabled,
        )

        _add_action("Дублировать", icon_name="COPY", command="duplicate")

        _add_action("Удалить из preset", icon_name="DELETE", command="delete_from_preset")
    else:
        _add_action("Добавить в preset", icon_name="ADD", command="set_enabled", payload=True)

    if is_user_profile:
        menu.addSeparator()
        _add_action("Изменить пользовательский profile", icon_name="EDIT", command="edit_user_profile")

        _add_action("Удалить пользовательский profile", icon_name="DELETE", command="delete_user_profile")

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


def _profile_menu_name(item, *, fallback: str) -> str:
    for attr in ("display_name", "profile_name", "name", "key"):
        value = str(getattr(item, attr, "") or "").strip()
        if value:
            return value
    return str(fallback or "").strip() or "profile"


def _profile_menu_accessible_text(*, text: str, command: str, profile_name: str) -> str:
    name = str(profile_name or "profile").strip() or "profile"
    command_value = str(command or "").strip()
    if command_value == "open":
        return f"Открыть profile {name}"
    if command_value == "set_enabled":
        action = "Выключить" if str(text or "").strip() == "Выключить" else "Включить"
        return f"{action} profile {name}"
    if command_value == "duplicate":
        return f"Дублировать profile {name}"
    if command_value == "delete_from_preset":
        return f"Удалить profile {name} из preset"
    if command_value == "edit_user_profile":
        return f"Изменить пользовательский profile {name}"
    if command_value == "delete_user_profile":
        return f"Удалить пользовательский profile {name}"
    return str(text or "").strip()
