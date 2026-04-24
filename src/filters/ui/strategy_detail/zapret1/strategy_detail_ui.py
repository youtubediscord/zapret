"""UI/build helper'ы для страницы деталей стратегии Zapret 1."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from filters.ui.strategy_detail.filter_mode_ui import apply_filter_mode_selector_texts


@dataclass(slots=True)
class StrategyDetailV1HeaderWidgets:
    header_widget: object
    spinner: object
    success_icon: object
    title_label: object
    subtitle_label: object
    selected_label: object
    desc_label: object


@dataclass(slots=True)
class StrategyDetailV1MainWidgets:
    toolbar_card: object
    state_label: object
    enable_toggle: object
    filter_mode_frame: object
    filter_label: object
    filter_mode_selector: object
    refresh_btn: object
    search_edit: object
    sort_combo: object
    edit_args_btn: object
    args_preview_label: object
    list_card: object
    tree: object
    empty_label: object


def build_strategy_detail_v1_header(
    *,
    parent,
    tr_fn,
    body_label_cls,
    title_label_cls,
    caption_label_cls,
    spinner_cls,
    pixmap_label_cls,
    build_detail_subtitle_widgets_fn,
    breadcrumb=None,
):
    header = QFrame()
    header.setFrameShape(QFrame.Shape.NoFrame)
    header.setStyleSheet("background: transparent; border: none;")
    header_layout = QVBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 10)
    header_layout.setSpacing(4)

    if breadcrumb is not None:
        header_layout.addWidget(breadcrumb)

    title_label = title_label_cls(
        tr_fn("page.z1_strategy_detail.header.category_fallback", "Target")
    )
    header_layout.addWidget(title_label)

    subtitle_widgets = build_detail_subtitle_widgets_fn(
        parent=parent,
        body_label_cls=body_label_cls,
        spinner_cls=spinner_cls,
        pixmap_label_cls=pixmap_label_cls,
        subtitle_strategy_label_cls=caption_label_cls,
        detail_text_color="#9aa2af",
    )
    selected_label = subtitle_widgets.subtitle_strategy_label
    selected_label.setFont(QFont("Segoe UI", 10))
    header_layout.addWidget(subtitle_widgets.container_widget)

    desc_label = body_label_cls("")
    desc_label.setWordWrap(True)
    header_layout.addWidget(desc_label)

    return StrategyDetailV1HeaderWidgets(
        header_widget=header,
        spinner=subtitle_widgets.spinner,
        success_icon=subtitle_widgets.success_icon,
        title_label=title_label,
        subtitle_label=subtitle_widgets.subtitle_label,
        selected_label=selected_label,
        desc_label=desc_label,
    )


def build_strategy_detail_v1_main_sections(
    *,
    parent,
    tr_fn,
    action_button_cls,
    refresh_button_cls,
    settings_card_cls,
    body_label_cls,
    caption_label_cls,
    line_edit_cls,
    combo_box_cls,
    switch_button_cls,
    build_tree_widget_fn,
    direct_tree_cls,
    on_enable_toggled,
    on_filter_mode_changed,
    on_reload_target,
    on_search_text_changed,
    on_sort_combo_changed,
    on_open_args_editor,
    on_strategy_selected,
    on_favorite_toggled,
    on_working_mark_requested,
    on_preview_requested,
    on_preview_pinned_requested,
    on_preview_hide_requested,
):
    toolbar_card = settings_card_cls()
    toolbar_layout = QVBoxLayout()
    toolbar_layout.setSpacing(8)

    state_row = QHBoxLayout()
    state_row.setSpacing(8)

    state_label = body_label_cls(
        tr_fn("page.z1_strategy_detail.state.category_bypass", "Обход для target'а")
    )
    state_row.addWidget(state_label)

    enable_toggle = switch_button_cls(parent=parent)
    if hasattr(enable_toggle, "setOnText"):
        enable_toggle.setOnText(tr_fn("page.z1_strategy_detail.toggle.on", "Включено"))
    if hasattr(enable_toggle, "setOffText"):
        enable_toggle.setOffText(tr_fn("page.z1_strategy_detail.toggle.off", "Выключено"))
    if hasattr(enable_toggle, "checkedChanged"):
        enable_toggle.checkedChanged.connect(on_enable_toggled)
    else:
        enable_toggle.toggled.connect(on_enable_toggled)
    state_row.addWidget(enable_toggle)

    filter_mode_frame = QWidget()
    filter_row = QHBoxLayout(filter_mode_frame)
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(6)
    filter_label = caption_label_cls(tr_fn("page.z1_strategy_detail.filter.label", "Фильтр:"))
    filter_row.addWidget(filter_label)

    filter_mode_selector = switch_button_cls(parent=parent)
    apply_filter_mode_selector_texts(
        filter_mode_selector,
        ipset_text=tr_fn("page.z1_strategy_detail.filter.ipset", "IPset"),
        hostlist_text=tr_fn("page.z1_strategy_detail.filter.hostlist", "Hostlist"),
    )
    if hasattr(filter_mode_selector, "checkedChanged"):
        filter_mode_selector.checkedChanged.connect(
            lambda checked: on_filter_mode_changed("ipset" if checked else "hostlist")
        )
    else:
        filter_mode_selector.toggled.connect(
            lambda checked: on_filter_mode_changed("ipset" if checked else "hostlist")
        )
    filter_row.addWidget(filter_mode_selector)
    filter_mode_frame.hide()
    state_row.addWidget(filter_mode_frame)
    state_row.addStretch(1)

    toolbar_layout.addLayout(state_row)

    controls_row = QHBoxLayout()
    controls_row.setSpacing(8)

    refresh_btn = refresh_button_cls()
    refresh_btn.clicked.connect(on_reload_target)
    controls_row.addWidget(refresh_btn)

    search_edit = line_edit_cls()
    search_edit.setPlaceholderText(
        tr_fn(
            "page.z1_strategy_detail.search.placeholder",
            "Поиск стратегии по названию или аргументам",
        )
    )
    search_edit.textChanged.connect(on_search_text_changed)
    controls_row.addWidget(search_edit, 1)

    sort_combo = combo_box_cls()
    sort_combo.addItem(
        tr_fn("page.z1_strategy_detail.sort.recommended", "По рекомендации"),
        userData="recommended",
    )
    sort_combo.addItem(
        tr_fn("page.z1_strategy_detail.sort.alpha_asc", "По алфавиту A-Z"),
        userData="alpha_asc",
    )
    sort_combo.addItem(
        tr_fn("page.z1_strategy_detail.sort.alpha_desc", "По алфавиту Z-A"),
        userData="alpha_desc",
    )
    sort_combo.currentIndexChanged.connect(on_sort_combo_changed)
    controls_row.addWidget(sort_combo)

    edit_args_btn = action_button_cls(
        tr_fn("page.z1_strategy_detail.button.edit_args", "Редактировать аргументы"),
        "fa5s.edit",
    )
    edit_args_btn.clicked.connect(on_open_args_editor)
    controls_row.addWidget(edit_args_btn)

    toolbar_layout.addLayout(controls_row)

    args_preview_label = caption_label_cls(tr_fn("page.z1_strategy_detail.args.none", "(нет аргументов)"))
    args_preview_label.setWordWrap(True)
    args_preview_label.setFont(QFont("Consolas", 9))
    toolbar_layout.addWidget(args_preview_label)

    toolbar_card.add_layout(toolbar_layout)

    list_card = settings_card_cls(tr_fn("page.z1_strategy_detail.card.strategies", "Стратегии"))
    list_layout = QVBoxLayout()
    list_layout.setContentsMargins(0, 0, 0, 0)
    list_layout.setSpacing(8)

    tree = build_tree_widget_fn(
        parent=parent,
        tree_cls=direct_tree_cls,
        on_row_clicked=on_strategy_selected,
        on_favorite_toggled=on_favorite_toggled,
        on_working_mark_requested=on_working_mark_requested,
        on_preview_requested=on_preview_requested,
        on_preview_pinned_requested=on_preview_pinned_requested,
        on_preview_hide_requested=on_preview_hide_requested,
    )
    list_layout.addWidget(tree, 1)

    empty_label = caption_label_cls(
        tr_fn(
            "page.z1_strategy_detail.empty.no_strategies",
            "Нет доступных стратегий. Проверьте папку presets рядом с программой.",
        )
    )
    empty_label.setWordWrap(True)
    empty_label.hide()
    list_layout.addWidget(empty_label)

    list_card.add_layout(list_layout)

    return StrategyDetailV1MainWidgets(
        toolbar_card=toolbar_card,
        state_label=state_label,
        enable_toggle=enable_toggle,
        filter_mode_frame=filter_mode_frame,
        filter_label=filter_label,
        filter_mode_selector=filter_mode_selector,
        refresh_btn=refresh_btn,
        search_edit=search_edit,
        sort_combo=sort_combo,
        edit_args_btn=edit_args_btn,
        args_preview_label=args_preview_label,
        list_card=list_card,
        tree=tree,
        empty_label=empty_label,
    )
