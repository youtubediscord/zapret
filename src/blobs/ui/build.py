"""Build-helper верхней части страницы BlobsPage."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy

from ui.fluent_widgets import (
    SettingsCard,
    ActionButton,
    PrimaryActionButton,
    QuickActionsBar,
    RefreshButton,
    insert_widget_into_setting_card_group,
)
from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class BlobsPageHeaderWidgets:
    back_btn: object | None
    desc_label: object
    actions_group: object | None
    actions_meta_card: object | None
    actions_bar: object | None
    add_btn: object
    reload_btn: object
    open_folder_btn: object
    open_json_btn: object
    count_label: object
    filter_icon_label: object
    filter_edit: object
    blobs_container: object
    blobs_layout: object


def build_blobs_page_header(
    *,
    page,
    has_fluent_inputs: bool,
    setting_card_group_cls,
    line_edit_cls,
    action_button_cls,
    primary_action_button_cls,
    quick_actions_bar_cls,
    refresh_button_cls,
    add_widget,
    tr_fn,
    on_back,
    on_add_blob,
    on_reload_blobs,
    on_open_bin_folder,
    on_open_json,
    on_filter_blobs,
) -> BlobsPageHeaderWidgets:
    back_btn = None
    if has_fluent_inputs:
        from PyQt6.QtCore import QSize
        from qfluentwidgets import TransparentPushButton

        back_btn = TransparentPushButton(parent=page)
        back_btn.setText(tr_fn("page.blobs.button.back", "Управление"))
        back_btn.setIcon(get_themed_qta_icon("fa5s.chevron-left", color="#888"))
        back_btn.setIconSize(QSize(12, 12))
        back_btn.clicked.connect(on_back)
        back_row = QHBoxLayout()
        back_row.setContentsMargins(0, 0, 0, 0)
        back_row.addWidget(back_btn)
        back_row.addStretch()
        back_row_widget = QWidget()
        back_row_widget.setLayout(back_row)
        back_row_widget.setStyleSheet("background: transparent;")
        page.vBoxLayout.insertWidget(0, back_row_widget)

    desc_card = SettingsCard()
    desc_label = QLabel(
        tr_fn(
            "page.blobs.description",
            "Блобы — это бинарные данные (файлы .bin или hex-значения), используемые в стратегиях для имитации TLS/QUIC пакетов.\nВы можете добавлять свои блобы для кастомных стратегий.",
        )
    )
    desc_label.setWordWrap(True)
    desc_card.add_widget(desc_label)
    add_widget(desc_card)

    actions_group = None
    actions_meta_card = None
    actions_bar = None

    if setting_card_group_cls is not None and has_fluent_inputs:
        actions_group = setting_card_group_cls(
            tr_fn("page.blobs.section.actions", "Действия"),
            page.content,
        )
        actions_bar = quick_actions_bar_cls(page.content)

        add_btn = primary_action_button_cls(
            tr_fn("page.blobs.button.add", "Добавить блоб"),
            "fa5s.plus",
        )
        add_btn.clicked.connect(on_add_blob)

        reload_btn = refresh_button_cls()
        reload_btn.clicked.connect(on_reload_blobs)

        open_folder_btn = action_button_cls(
            tr_fn("page.blobs.button.bin_folder", "Папка bin"),
            "fa5s.folder-open",
        )
        open_folder_btn.clicked.connect(on_open_bin_folder)

        open_json_btn = action_button_cls(
            tr_fn("page.blobs.button.open_json", "Открыть JSON"),
            "fa5s.file-code",
        )
        open_json_btn.clicked.connect(on_open_json)

        actions_bar.add_buttons([add_btn, reload_btn, open_folder_btn, open_json_btn])
        insert_widget_into_setting_card_group(actions_group, 1, actions_bar)

        actions_meta_card = SettingsCard()
        count_label = QLabel("")
        actions_meta_card.add_widget(count_label)
        actions_group.addSettingCard(actions_meta_card)
        add_widget(actions_group)
    else:
        actions_card = SettingsCard()
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        add_btn = action_button_cls(tr_fn("page.blobs.button.add", "Добавить блоб"), "fa5s.plus")
        add_btn.clicked.connect(on_add_blob)
        actions_layout.addWidget(add_btn)

        reload_btn = refresh_button_cls()
        reload_btn.clicked.connect(on_reload_blobs)
        actions_layout.addWidget(reload_btn)

        open_folder_btn = action_button_cls(tr_fn("page.blobs.button.bin_folder", "Папка bin"), "fa5s.folder-open")
        open_folder_btn.clicked.connect(on_open_bin_folder)
        actions_layout.addWidget(open_folder_btn)

        open_json_btn = action_button_cls(tr_fn("page.blobs.button.open_json", "Открыть JSON"), "fa5s.file-code")
        open_json_btn.clicked.connect(on_open_json)
        actions_layout.addWidget(open_json_btn)

        actions_layout.addStretch()
        actions_card.add_layout(actions_layout)

        count_label = QLabel("")
        actions_card.add_widget(count_label)
        add_widget(actions_card)

    filter_card = SettingsCard()
    filter_layout = QHBoxLayout()
    filter_layout.setSpacing(8)

    filter_icon_label = QLabel()
    filter_layout.addWidget(filter_icon_label)

    filter_edit = line_edit_cls()
    filter_edit.setPlaceholderText(tr_fn("page.blobs.filter.placeholder", "Фильтр по имени..."))
    filter_edit.textChanged.connect(on_filter_blobs)
    filter_layout.addWidget(filter_edit, 1)

    filter_card.add_layout(filter_layout)
    add_widget(filter_card)

    blobs_container = QWidget()
    blobs_container.setStyleSheet("background: transparent;")
    blobs_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    from PyQt6.QtWidgets import QVBoxLayout

    blobs_layout = QVBoxLayout(blobs_container)
    blobs_layout.setContentsMargins(0, 0, 0, 0)
    blobs_layout.setSpacing(6)
    add_widget(blobs_container)

    return BlobsPageHeaderWidgets(
        back_btn=back_btn,
        desc_label=desc_label,
        actions_group=actions_group,
        actions_meta_card=actions_meta_card,
        actions_bar=actions_bar,
        add_btn=add_btn,
        reload_btn=reload_btn,
        open_folder_btn=open_folder_btn,
        open_json_btn=open_json_btn,
        count_label=count_label,
        filter_icon_label=filter_icon_label,
        filter_edit=filter_edit,
        blobs_container=blobs_container,
        blobs_layout=blobs_layout,
    )
