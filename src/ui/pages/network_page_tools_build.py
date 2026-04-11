"""Сборка tools/actions UI-блока для страницы Network."""

from __future__ import annotations

from dataclasses import dataclass


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
    has_fluent_labels: bool,
    setting_card_group_cls,
    settings_card_cls,
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

    if setting_card_group_cls is not None and has_fluent_labels:
        section_label = None
        tools_card = setting_card_group_cls(tools_title, content_parent)
        actions_bar = quick_actions_bar_cls(content_parent)

        test_btn = action_button_cls(test_text, "fa5s.wifi")
        test_btn.clicked.connect(on_test)
        set_tooltip_fn(test_btn, test_tooltip)

        flush_btn = action_button_cls(flush_text, "fa5s.eraser")
        flush_btn.clicked.connect(on_flush_dns)
        set_tooltip_fn(flush_btn, flush_tooltip)

        actions_bar.add_buttons([test_btn, flush_btn])
        insert_widget_into_setting_card_group_fn(tools_card, 1, actions_bar)
    else:
        section_label = add_section_title_fn(text_key="page.network.section.tools")
        tools_card = settings_card_cls()
        actions_bar = None
        tools_layout = qhbox_layout_cls()
        tools_layout.setContentsMargins(10, 8, 12, 8)
        tools_layout.setSpacing(8)

        test_btn = action_button_cls(test_text, "fa5s.wifi")
        test_btn.setFixedHeight(28)
        test_btn.clicked.connect(on_test)
        set_tooltip_fn(test_btn, test_tooltip)
        tools_layout.addWidget(test_btn)

        flush_btn = action_button_cls(flush_text, "fa5s.eraser")
        flush_btn.setFixedHeight(28)
        flush_btn.clicked.connect(on_flush_dns)
        set_tooltip_fn(flush_btn, flush_tooltip)
        tools_layout.addWidget(flush_btn)

        tools_layout.addStretch()
        tools_card.add_layout(tools_layout)

    return NetworkToolsWidgets(
        card=tools_card,
        section_label=section_label,
        actions_bar=actions_bar,
        test_button=test_btn,
        flush_button=flush_btn,
    )
