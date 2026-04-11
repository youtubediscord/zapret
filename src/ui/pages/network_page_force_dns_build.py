"""Сборка UI-блока Force DNS для страницы Network."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ForceDnsCardWidgets:
    card: object
    toggle: object
    status_label: object
    reset_button: object
    reset_row: object | None


def build_force_dns_card_ui(
    *,
    parent,
    content_parent,
    add_section_title_fn,
    tr_fn,
    add_widget_fn,
    get_theme_tokens_fn,
    get_force_dns_status_fn,
    has_fluent_labels: bool,
    setting_card_group_cls,
    settings_card_cls,
    caption_label_cls,
    reset_action_button_cls,
    win11_toggle_row_cls,
    qwidget_cls,
    qvbox_layout_cls,
    qhbox_layout_cls,
    qt_namespace,
    insert_widget_into_setting_card_group_fn,
    enable_setting_card_group_auto_height_fn,
    on_toggle,
    on_reset,
) -> tuple[bool, ForceDnsCardWidgets]:
    tokens = get_theme_tokens_fn()
    force_dns_active = get_force_dns_status_fn()

    add_section_title_fn(text_key="page.network.section.force_dns")

    title_text = tr_fn(
        "page.network.force_dns.card.title",
        "Принудительно прописывает Google DNS + OpenDNS для обхода блокировок",
    )
    if setting_card_group_cls is not None and has_fluent_labels:
        force_dns_card = setting_card_group_cls(title_text, content_parent)
        dns_layout = None
    else:
        force_dns_card = settings_card_cls(title_text)
        dns_layout = qvbox_layout_cls()
        dns_layout.setSpacing(8)

    force_dns_toggle = win11_toggle_row_cls(
        "fa5s.shield-alt",
        tr_fn("page.network.force_dns.toggle.title", "Принудительный DNS"),
        tr_fn(
            "page.network.force_dns.toggle.description",
            "Устанавливает Google DNS + OpenDNS на активные адаптеры",
        ),
        tokens.accent_hex,
    )
    force_dns_toggle.setChecked(force_dns_active)
    force_dns_toggle.toggled.connect(on_toggle)
    if hasattr(force_dns_card, "addSettingCard"):
        force_dns_card.addSettingCard(force_dns_toggle)
    else:
        dns_layout.addWidget(force_dns_toggle)

    force_dns_status_label = caption_label_cls("")
    if dns_layout is not None:
        dns_layout.addWidget(force_dns_status_label)
    else:
        try:
            insert_widget_into_setting_card_group_fn(force_dns_card, 1, force_dns_status_label)
        except Exception:
            pass

    force_dns_reset_dhcp_btn = reset_action_button_cls(
        tr_fn("page.network.force_dns.reset.button", "Сбросить DNS на DHCP"),
        confirm_text=tr_fn(
            "page.network.force_dns.reset.confirm",
            "Отключить Force DNS и сбросить DNS на DHCP для всех адаптеров?",
        ),
    )
    force_dns_reset_dhcp_btn.setFixedHeight(30)
    force_dns_reset_dhcp_btn.reset_confirmed.connect(on_reset)
    force_dns_reset_dhcp_btn.setToolTip(
        tr_fn(
            "page.network.force_dns.reset.description",
            "Отключить Force DNS и вернуть получение DNS через DHCP для всех адаптеров.",
        )
    )

    reset_row = None
    if dns_layout is None:
        reset_row = qwidget_cls(force_dns_card)
        reset_row_layout = qhbox_layout_cls(reset_row)
        reset_row_layout.setContentsMargins(0, 4, 0, 0)
        reset_row_layout.setSpacing(8)
        reset_row_layout.addWidget(force_dns_reset_dhcp_btn, 0, qt_namespace.AlignmentFlag.AlignLeft)
        reset_row_layout.addStretch()
        insert_widget_into_setting_card_group_fn(force_dns_card, 2, reset_row)
        enable_setting_card_group_auto_height_fn(force_dns_card)
    else:
        dns_layout.addWidget(force_dns_reset_dhcp_btn, alignment=qt_namespace.AlignmentFlag.AlignLeft)
        force_dns_card.add_layout(dns_layout)

    add_widget_fn(force_dns_card)

    return force_dns_active, ForceDnsCardWidgets(
        card=force_dns_card,
        toggle=force_dns_toggle,
        status_label=force_dns_status_label,
        reset_button=force_dns_reset_dhcp_btn,
        reset_row=reset_row,
    )
