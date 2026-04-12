"""Build-helper'ы для канонической DNS страницы."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout


@dataclass(slots=True)
class NetworkPageShellWidgets:
    loading_card: object
    loading_label: object
    loading_bar: object
    dns_cards_container: object
    dns_cards_layout: object
    custom_card: object
    custom_indicator: object
    custom_label: object
    custom_primary: object
    custom_secondary: object
    custom_apply_btn: object
    ipv6_label: object = None
    custom_primary_v6: object = None
    custom_secondary_v6: object = None
    adapters_container: object
    adapters_layout: object
    tools_section_label: object
    tools_card: object
    tools_actions_bar: object
    test_btn: object
    dns_flush_btn: object


def build_network_page_shell(
    *,
    parent,
    content_parent,
    tr_fn,
    add_section_title_fn,
    has_fluent_labels: bool,
    body_label_cls,
    qlabel_cls,
    settings_card_cls,
    qvbox_layout_cls,
    qhbox_layout_cls,
    qframe_cls,
    line_edit_cls,
    action_button_cls,
    indeterminate_progress_bar_cls,
    setting_card_group_cls,
    quick_actions_bar_cls,
    insert_widget_into_setting_card_group_fn,
    build_custom_dns_ui_fn,
    build_tools_card_ui_fn,
    on_apply_custom_dns,
    on_test_connection,
    on_flush_dns_cache,
    set_tooltip_fn,
    dns_provider_card_cls,
    show_ipv6: bool = False,
):
    loading_card = settings_card_cls()
    loading_layout = qvbox_layout_cls()
    loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    loading_label = (
        body_label_cls(tr_fn("page.network.loading", "⏳ Загрузка..."))
        if has_fluent_labels
        else qlabel_cls(tr_fn("page.network.loading", "⏳ Загрузка..."))
    )
    loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    loading_layout.addWidget(loading_label)

    loading_bar = indeterminate_progress_bar_cls(parent)
    loading_bar.setFixedHeight(4)
    loading_bar.setMaximumWidth(150)
    if has_fluent_labels:
        loading_bar.start()
    else:
        loading_bar.setRange(0, 0)
        loading_bar.setTextVisible(False)
    loading_layout.addWidget(loading_bar, alignment=Qt.AlignmentFlag.AlignCenter)
    loading_card.add_layout(loading_layout)

    dns_cards_container = QWidget()
    dns_cards_layout = qvbox_layout_cls(dns_cards_container)
    dns_cards_layout.setContentsMargins(0, 0, 0, 0)
    dns_cards_layout.setSpacing(4)
    dns_cards_container.hide()

    custom_widgets = build_custom_dns_ui_fn(
        tr_fn=tr_fn,
        has_fluent_labels=has_fluent_labels,
        settings_card_cls=settings_card_cls,
        qhbox_layout_cls=qhbox_layout_cls,
        qframe_cls=qframe_cls,
        body_label_cls=body_label_cls if has_fluent_labels else qlabel_cls,
        qlabel_cls=qlabel_cls,
        line_edit_cls=line_edit_cls,
        action_button_cls=action_button_cls,
        on_apply=on_apply_custom_dns,
        indicator_off_qss=dns_provider_card_cls.indicator_off(),
        show_ipv6=show_ipv6,
    )

    adapters_container = QWidget()
    adapters_layout = qvbox_layout_cls(adapters_container)
    adapters_layout.setContentsMargins(0, 0, 0, 0)
    adapters_layout.setSpacing(4)
    adapters_container.hide()

    tools_widgets = build_tools_card_ui_fn(
        content_parent=content_parent,
        tr_fn=tr_fn,
        add_section_title_fn=add_section_title_fn,
        has_fluent_labels=has_fluent_labels,
        setting_card_group_cls=setting_card_group_cls,
        settings_card_cls=settings_card_cls,
        quick_actions_bar_cls=quick_actions_bar_cls,
        action_button_cls=action_button_cls,
        qhbox_layout_cls=qhbox_layout_cls,
        insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group_fn,
        on_test=on_test_connection,
        on_flush_dns=on_flush_dns_cache,
        set_tooltip_fn=set_tooltip_fn,
    )

    return NetworkPageShellWidgets(
        loading_card=loading_card,
        loading_label=loading_label,
        loading_bar=loading_bar,
        dns_cards_container=dns_cards_container,
        dns_cards_layout=dns_cards_layout,
        custom_card=custom_widgets.card,
        custom_indicator=custom_widgets.indicator,
        custom_label=custom_widgets.title_label,
        custom_primary=custom_widgets.primary_input,
        custom_secondary=custom_widgets.secondary_input,
        custom_apply_btn=custom_widgets.apply_button,
        ipv6_label=custom_widgets.ipv6_label,
        custom_primary_v6=custom_widgets.primary_v6_input,
        custom_secondary_v6=custom_widgets.secondary_v6_input,
        adapters_container=adapters_container,
        adapters_layout=adapters_layout,
        tools_section_label=tools_widgets.section_label,
        tools_card=tools_widgets.card,
        tools_actions_bar=tools_widgets.actions_bar,
        test_btn=tools_widgets.test_button,
        dns_flush_btn=tools_widgets.flush_button,
    )
