"""Сборка auto/custom DNS UI-блоков для страницы Network."""

from __future__ import annotations

from dataclasses import dataclass
from PyQt6.QtCore import Qt

from ui.theme import get_cached_qta_pixmap


@dataclass(slots=True)
class AutoDnsWidgets:
    card: object
    indicator: object
    icon_label: object
    title_label: object


@dataclass(slots=True)
class CustomDnsWidgets:
    card: object
    indicator: object
    title_label: object
    primary_input: object
    secondary_input: object
    apply_button: object


def build_custom_dns_ui(
    *,
    tr_fn,
    has_fluent_labels: bool,
    settings_card_cls,
    qhbox_layout_cls,
    qframe_cls,
    body_label_cls,
    qlabel_cls,
    line_edit_cls,
    action_button_cls,
    on_apply,
    indicator_off_qss: str,
) -> CustomDnsWidgets:
    custom_card = settings_card_cls()
    custom_card.setObjectName("dnsCard")
    custom_card.setProperty("selected", False)
    custom_layout = qhbox_layout_cls()
    custom_layout.setContentsMargins(10, 6, 12, 6)
    custom_layout.setSpacing(8)

    custom_indicator = qframe_cls()
    custom_indicator.setFixedSize(16, 16)
    custom_indicator.setStyleSheet(indicator_off_qss)
    custom_layout.addWidget(custom_indicator)

    if has_fluent_labels:
        custom_label = body_label_cls(tr_fn("page.network.custom.label", "Свой:"))
    else:
        custom_label = qlabel_cls(tr_fn("page.network.custom.label", "Свой:"))
    custom_layout.addWidget(custom_label)

    custom_primary = line_edit_cls()
    custom_primary.setPlaceholderText("8.8.8.8")
    custom_primary.setFixedWidth(110)
    custom_primary.returnPressed.connect(on_apply)
    custom_layout.addWidget(custom_primary)

    custom_secondary = line_edit_cls()
    custom_secondary.setPlaceholderText("208.67.222.222")
    custom_secondary.setFixedWidth(110)
    custom_secondary.returnPressed.connect(on_apply)
    custom_layout.addWidget(custom_secondary)

    custom_apply_btn = action_button_cls(tr_fn("page.network.custom.apply", "OK"), "fa5s.check")
    custom_apply_btn.setFixedSize(70, 26)
    custom_apply_btn.clicked.connect(on_apply)
    custom_layout.addWidget(custom_apply_btn)

    custom_layout.addStretch()

    custom_card.add_layout(custom_layout)
    custom_card.hide()

    return CustomDnsWidgets(
        card=custom_card,
        indicator=custom_indicator,
        title_label=custom_label,
        primary_input=custom_primary,
        secondary_input=custom_secondary,
        apply_button=custom_apply_btn,
    )


def build_auto_dns_ui(
    *,
    tr_fn,
    has_fluent_labels: bool,
    settings_card_cls,
    qhbox_layout_cls,
    qframe_cls,
    strong_body_label_cls,
    qlabel_cls,
    qta_module,
    icon_color: str,
    indicator_off_qss: str,
    on_select,
) -> AutoDnsWidgets:
    auto_card = settings_card_cls()
    auto_card.setObjectName("dnsCard")
    auto_card.setCursor(Qt.CursorShape.PointingHandCursor)
    auto_card.setProperty("selected", False)
    auto_layout = qhbox_layout_cls()
    auto_layout.setContentsMargins(10, 6, 12, 6)
    auto_layout.setSpacing(10)

    auto_indicator = qframe_cls()
    auto_indicator.setFixedSize(16, 16)
    auto_indicator.setStyleSheet(indicator_off_qss)
    auto_layout.addWidget(auto_indicator)

    auto_icon = qlabel_cls()
    auto_icon.setPixmap(get_cached_qta_pixmap("fa5s.sync", color=icon_color, size=16))
    auto_layout.addWidget(auto_icon)

    if has_fluent_labels:
        auto_label = strong_body_label_cls(tr_fn("page.network.dns.auto", "Автоматически (DHCP)"))
    else:
        auto_label = qlabel_cls(tr_fn("page.network.dns.auto", "Автоматически (DHCP)"))
    auto_layout.addWidget(auto_label)

    auto_layout.addStretch()
    auto_card.add_layout(auto_layout)
    auto_card.mousePressEvent = on_select

    return AutoDnsWidgets(
        card=auto_card,
        indicator=auto_indicator,
        icon_label=auto_icon,
        title_label=auto_label,
    )
