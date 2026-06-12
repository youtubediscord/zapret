"""Сборка tools/actions UI-блока для страницы Network."""

from __future__ import annotations

from dataclasses import dataclass

from qfluentwidgets import FluentIcon

from ui.accessibility import set_control_accessibility, set_state_text


@dataclass(slots=True)
class NetworkToolsWidgets:
    card: object
    section_label: object | None
    actions_bar: object | None
    test_button: object
    flush_button: object


def build_tools_card_ui(
    *,
    content_parent,
    tr_fn,
    add_section_title_fn,
    setting_card_group_cls,
    quick_actions_bar_cls,
    action_button_cls,
    qhbox_layout_cls,
    insert_widget_into_setting_card_group_fn,
    on_test,
    on_flush_dns,
    set_tooltip_fn,
) -> NetworkToolsWidgets:
    tools_title = tr_fn("page.network.section.tools", "Диагностика")
    test_text = tr_fn("page.network.button.test", "Тест соединения")
    test_tooltip = tr_fn(
        "page.network.tools.test.description",
        "Проверить доступность DNS и популярных сайтов из этой системы.",
    )
    flush_text = tr_fn("page.network.button.flush_dns_cache", "Сбросить DNS кэш")
    flush_tooltip = tr_fn(
        "page.network.tools.flush_dns.description",
        "Очистить локальный кэш DNS Windows, если ответы или домены застряли в старом состоянии.",
    )

    _ = add_section_title_fn
    _ = qhbox_layout_cls
    section_label = None
    tools_card = setting_card_group_cls(tools_title, content_parent)
    actions_bar = quick_actions_bar_cls(content_parent)

    test_btn = action_button_cls(test_text, icon=FluentIcon.WIFI)
    test_btn.clicked.connect(on_test)
    set_tooltip_fn(test_btn, test_tooltip)
    test_accessible_name = tr_fn("page.network.tools.test.accessible_name", "Проверить DNS и сайты")
    set_control_accessibility(
        test_btn,
        name=test_accessible_name,
        description=test_tooltip,
    )
    set_state_text(test_btn, test_accessible_name)

    flush_btn = action_button_cls(flush_text, icon=FluentIcon.ERASE_TOOL)
    flush_btn.clicked.connect(on_flush_dns)
    set_tooltip_fn(flush_btn, flush_tooltip)
    flush_accessible_name = tr_fn("page.network.tools.flush_dns.accessible_name", "Сбросить DNS кэш Windows")
    set_control_accessibility(
        flush_btn,
        name=flush_accessible_name,
        description=flush_tooltip,
    )
    set_state_text(flush_btn, flush_accessible_name)

    actions_bar.add_buttons([test_btn, flush_btn])
    insert_widget_into_setting_card_group_fn(tools_card, 1, actions_bar)

    return NetworkToolsWidgets(
        card=tools_card,
        section_label=section_label,
        actions_bar=actions_bar,
        test_button=test_btn,
        flush_button=flush_btn,
    )
