"""Build-helper'ы обзорных панелей hostlist/ipset."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HostlistOverviewPanelWidgets:
    panel: object
    desc_label: object
    manage_group: object
    actions_bar: object
    info_card: object
    info_label: object
    open_button: object
    rebuild_button: object | None


def build_overview_panel(
    *,
    content_parent,
    tr_fn,
    get_theme_tokens_fn,
    qwidget_cls,
    qvbox_layout_cls,
    settings_card_cls,
    body_label_cls,
    caption_label_cls,
    setting_card_group_cls,
    quick_actions_bar_cls,
    action_button_cls,
    insert_widget_into_setting_card_group_fn,
    set_tooltip_fn,
    desc_key: str,
    desc_default: str,
    open_tooltip_key: str,
    open_tooltip_default: str,
    on_open,
    on_rebuild=None,
    rebuild_tooltip_key: str | None = None,
    rebuild_tooltip_default: str = "",
) -> HostlistOverviewPanelWidgets:
    tokens = get_theme_tokens_fn()
    panel = qwidget_cls()
    layout = qvbox_layout_cls(panel)
    layout.setContentsMargins(0, 8, 0, 0)
    layout.setSpacing(12)

    desc_card = settings_card_cls()
    desc_label = body_label_cls(tr_fn(desc_key, desc_default))
    desc_label.setWordWrap(True)
    desc_card.add_widget(desc_label)
    layout.addWidget(desc_card)

    manage_group = setting_card_group_cls(tr_fn("page.hostlist.section.manage", "Управление"), content_parent)
    actions_bar = quick_actions_bar_cls(content_parent)

    open_button = action_button_cls(
        tr_fn("page.hostlist.button.open", "Открыть"),
        "fa5s.folder-open",
    )
    open_button.clicked.connect(on_open)
    set_tooltip_fn(
        open_button,
        tr_fn(open_tooltip_key, open_tooltip_default),
    )

    rebuild_button = None
    if on_rebuild is not None:
        rebuild_button = action_button_cls(
            tr_fn("page.hostlist.button.rebuild", "Перестроить"),
            "fa5s.sync-alt",
        )
        rebuild_button.clicked.connect(on_rebuild)
        if rebuild_tooltip_key:
            set_tooltip_fn(
                rebuild_button,
                tr_fn(rebuild_tooltip_key, rebuild_tooltip_default),
            )
        actions_bar.add_buttons([open_button, rebuild_button])
    else:
        actions_bar.add_button(open_button)

    insert_widget_into_setting_card_group_fn(manage_group, 1, actions_bar)

    info_card = settings_card_cls()
    info_label = caption_label_cls(
        tr_fn("page.hostlist.info.loading", "Загрузка информации...")
    )
    info_label.setStyleSheet(f"color: {tokens.fg_muted};")
    info_label.setWordWrap(True)
    info_card.add_widget(info_label)
    manage_group.addSettingCard(info_card)
    layout.addWidget(manage_group)

    layout.addStretch()

    return HostlistOverviewPanelWidgets(
        panel=panel,
        desc_label=desc_label,
        manage_group=manage_group,
        actions_bar=actions_bar,
        info_card=info_card,
        info_label=info_label,
        open_button=open_button,
        rebuild_button=rebuild_button,
    )
