"""Accessibility helpers for profile setup shell controls."""

from __future__ import annotations

from ui.accessibility import set_control_accessibility


def apply_profile_shell_accessibility(
    *,
    add_profile_btn=None,
    request_btn=None,
    expand_btn=None,
    collapse_btn=None,
    order_btn=None,
    info_btn=None,
    profile_search_input=None,
    tr_fn,
    toolbar_key,
    request_hint: str,
    engine_label: str,
) -> None:
    """Задаёт понятные имена toolbar-элементам профилей для экранного диктора."""

    set_control_accessibility(
        add_profile_btn,
        name=tr_fn(toolbar_key("add.accessible_name"), "Добавить пользовательский profile"),
        description=tr_fn(
            toolbar_key("add.description"),
            "Добавить новый пользовательский profile в общий список.",
        ),
    )
    set_control_accessibility(
        request_btn,
        name=tr_fn(
            toolbar_key("request.accessible_name"),
            "Открыть форму добавления profile на GitHub",
        ),
        description=request_hint,
    )
    set_control_accessibility(
        expand_btn,
        name=tr_fn(toolbar_key("expand.accessible_name"), "Развернуть все группы профилей"),
        description=tr_fn(
            toolbar_key("expand.description"),
            "Развернуть все группы профилей в списке.",
        ),
    )
    set_control_accessibility(
        collapse_btn,
        name=tr_fn(toolbar_key("collapse.accessible_name"), "Свернуть все группы профилей"),
        description=tr_fn(
            toolbar_key("collapse.description"),
            "Свернуть все группы профилей в списке.",
        ),
    )
    set_control_accessibility(
        order_btn,
        name=tr_fn(toolbar_key("order.accessible_name"), "Открыть порядок профилей в пресете"),
        description=tr_fn(
            toolbar_key("order.description"),
            "Открыть отдельный список для изменения реального порядка профилей внутри файла пресета.",
        ),
    )
    set_control_accessibility(
        info_btn,
        name=tr_fn(toolbar_key("info.accessible_name"), "Показать справку по профилям"),
        description=tr_fn(
            toolbar_key("info.description"),
            f"Показать краткое объяснение по работе режима профилей {engine_label}.",
        ),
    )
    set_control_accessibility(
        profile_search_input,
        name=tr_fn(toolbar_key("search.accessible_name"), "Поиск профиля"),
        description=tr_fn(
            toolbar_key("search.description"),
            (
                "Поиск профиля по имени, портам и т.д. "
                "После ввода перейдите в список клавишей Tab, "
                "выберите profile стрелками вверх и вниз, затем нажмите Enter."
            ),
        ),
    )


__all__ = ["apply_profile_shell_accessibility"]
