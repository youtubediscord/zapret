"""Сборка UI-блока Force DNS для страницы Network."""

from __future__ import annotations

from dataclasses import dataclass

from qfluentwidgets import FluentIcon

from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import QuickActionsBar, set_tooltip


@dataclass(slots=True)
class ForceDnsCardWidgets:
    card: object
    force_button: object
    status_label: object
    reset_button: object


def build_force_dns_card_ui(
    *,
    parent,
    content_parent,
    add_section_title_fn,
    tr_fn,
    add_widget_fn,
    get_theme_tokens_fn,
    get_force_dns_status_fn,
    setting_card_group_cls,
    caption_label_cls,
    action_button_cls,
    win11_toggle_row_cls,
    qwidget_cls,
    qvbox_layout_cls,
    qhbox_layout_cls,
    qt_namespace,
    insert_widget_into_setting_card_group_fn,
    enable_setting_card_group_auto_height_fn,
    on_toggle,
    on_confirm_reset,
) -> tuple[bool, ForceDnsCardWidgets]:
    tokens = get_theme_tokens_fn()
    force_dns_active = get_force_dns_status_fn()
    _ = tokens
    _ = parent
    _ = setting_card_group_cls
    _ = win11_toggle_row_cls
    _ = qwidget_cls
    _ = qvbox_layout_cls
    _ = qhbox_layout_cls
    _ = qt_namespace
    _ = insert_widget_into_setting_card_group_fn
    _ = enable_setting_card_group_auto_height_fn

    force_dns_card = QuickActionsBar(content_parent)
    force_dns_button_text = tr_fn(
        "page.network.force_dns.action.disable.button" if force_dns_active else "page.network.force_dns.action.enable.button",
        "Выключить принудительный DNS" if force_dns_active else "Включить принудительный DNS",
    )
    force_dns_button_description = tr_fn(
        "page.network.force_dns.action.disable.description" if force_dns_active else "page.network.force_dns.action.enable.description",
        (
            "Программа уберёт принудительные DNS и вернёт обычный режим."
            if force_dns_active
            else "Программа пропишет DNS-серверы для обхода блокировок. Это поможет, если провайдер подменяет DNS."
        ),
    )
    force_dns_btn = action_button_cls(force_dns_button_text, icon=FluentIcon.POWER_BUTTON)
    force_dns_btn.clicked.connect(lambda _checked=False: on_toggle())
    set_tooltip(force_dns_btn, force_dns_button_description)
    set_state_text(force_dns_btn, force_dns_button_text)
    set_control_accessibility(
        force_dns_btn,
        name=force_dns_button_text,
        description=force_dns_button_description,
    )

    force_dns_reset_dhcp_btn = action_button_cls(
        tr_fn("page.network.force_dns.reset.button", "Вернуть DNS автоматически"),
        icon=FluentIcon.RETURN,
    )
    force_dns_reset_dhcp_btn.clicked.connect(on_confirm_reset)
    reset_description = tr_fn(
        "page.network.force_dns.action.reset.description",
        "DNS будет снова получаться автоматически от роутера или провайдера через DHCP. Это полезно, если интернет работает нестабильно после ручной настройки DNS.",
    )
    set_tooltip(force_dns_reset_dhcp_btn, reset_description)
    reset_name = tr_fn("page.network.force_dns.reset.accessible_name", "Вернуть DNS автоматически")
    set_state_text(force_dns_reset_dhcp_btn, reset_name)
    set_control_accessibility(
        force_dns_reset_dhcp_btn,
        name=reset_name,
        description=reset_description,
    )

    force_dns_status_label = caption_label_cls("")
    force_dns_status_label.setWordWrap(True)
    force_dns_status_label.setVisible(False)

    force_dns_card.add_buttons((force_dns_btn, force_dns_reset_dhcp_btn))
    force_dns_card.actions_layout.addWidget(force_dns_status_label)

    add_widget_fn(force_dns_card)

    return force_dns_active, ForceDnsCardWidgets(
        card=force_dns_card,
        force_button=force_dns_btn,
        status_label=force_dns_status_label,
        reset_button=force_dns_reset_dhcp_btn,
    )
