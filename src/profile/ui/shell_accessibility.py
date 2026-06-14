"""Accessibility helpers for profile setup shell controls."""

from __future__ import annotations

from ui.accessibility import remove_line_edit_buttons_from_tab_order, set_control_accessibility, set_state_text


def apply_profile_shell_accessibility(
    *,
    add_profile_btn=None,
    request_btn=None,
    view_menu_btn=None,
    order_btn=None,
    info_btn=None,
    profile_search_input=None,
    tr_fn,
    toolbar_key,
    request_hint: str,
    engine_label: str,
) -> None:
    """Задаёт понятные имена toolbar-элементам профилей для экранного диктора."""

    def _set_shell_control(widget, *, name: str, description: str) -> None:
        set_control_accessibility(widget, name=name, description=description)
        set_state_text(widget, name)

    _set_shell_control(
        add_profile_btn,
        name=tr_fn(toolbar_key("add.accessible_name"), "Добавить пользовательский profile"),
        description=tr_fn(
            toolbar_key("add.description"),
            "Добавить новый пользовательский profile в общий список.",
        ),
    )
    _set_shell_control(
        request_btn,
        name=tr_fn(
            toolbar_key("request.accessible_name"),
            "Открыть форму добавления profile на GitHub",
        ),
        description=request_hint,
    )
    _set_shell_control(
        view_menu_btn,
        name=tr_fn(toolbar_key("view_menu.accessible_name"), "Открыть меню вида профилей"),
        description=tr_fn(
            toolbar_key("view_menu.description"),
            "Открывает меню, где можно развернуть или свернуть группы и выбрать, какие профили показывать.",
        ),
    )
    _set_shell_control(
        order_btn,
        name=tr_fn(toolbar_key("order.accessible_name"), "Открыть порядок профилей в пресете"),
        description=tr_fn(
            toolbar_key("order.description"),
            "Открыть отдельный список для изменения реального порядка профилей внутри файла пресета.",
        ),
    )
    _set_shell_control(
        info_btn,
        name=tr_fn(toolbar_key("info.accessible_name"), "Показать справку по профилям"),
        description=tr_fn(
            toolbar_key("info.description"),
            f"Показать краткое объяснение по работе режима профилей {engine_label}.",
        ),
    )
    _set_shell_control(
        profile_search_input,
        name=tr_fn(toolbar_key("search.accessible_name"), "Поиск профиля"),
        description=tr_fn(
            toolbar_key("search.description"),
            (
                "Поиск профиля по имени, портам и т.д. "
                "После ввода перейдите в список клавишей Tab или нажмите Стрелка вниз, "
                "выберите profile стрелками вверх и вниз, затем нажмите Enter или Пробел."
            ),
        ),
    )
    remove_line_edit_buttons_from_tab_order(profile_search_input)


__all__ = ["apply_profile_shell_accessibility"]
