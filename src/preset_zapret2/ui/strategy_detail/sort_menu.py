"""Sort menu helper'ы для страницы деталей стратегии Z2."""

from __future__ import annotations


def show_sort_menu(
    *,
    parent,
    sort_button,
    current_mode: str,
    has_fluent: bool,
    round_menu_cls,
    action_cls,
    fluent_icon,
    build_sort_options_fn,
    tr,
    on_select,
    exec_popup_menu_fn,
) -> None:
    menu = round_menu_cls(parent=parent)

    sort_icon = fluent_icon.SCROLL if has_fluent else None
    asc_icon = fluent_icon.UP if has_fluent else None
    desc_icon = fluent_icon.DOWN if has_fluent else None

    for entry in build_sort_options_fn(tr=tr):
        mode = entry.mode
        label = entry.label
        icon = sort_icon if mode == "default" else (asc_icon if mode == "name_asc" else desc_icon)
        action = action_cls(icon, label, checkable=True) if has_fluent else action_cls(label)
        action.setChecked(current_mode == mode)
        action.triggered.connect(lambda _checked=False, selected_mode=mode: on_select(selected_mode))
        menu.addAction(action)

    try:
        pos = sort_button.mapToGlobal(sort_button.rect().bottomLeft())
    except Exception:
        return
    exec_popup_menu_fn(menu, pos, owner=parent)
