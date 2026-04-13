from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from filters.ui.strategy_detail.shared import build_detail_subtitle_widgets, build_strategies_tree_widget
from filters.ui.strategy_detail.zapret2.common import (
    STRATEGY_TECHNIQUE_FILTERS,
    TCP_PHASE_TAB_ORDER,
    ElidedLabel,
    build_strategy_block_shell,
    build_strategy_header_widgets,
    build_strategy_toolbar_widgets,
    build_tcp_phase_bar_widgets,
)


@dataclass(slots=True)
class StrategyDetailHeaderSection:
    header_widget: QWidget
    breadcrumb: object | None
    parent_link: object | None
    title_label: object
    spinner: object
    success_icon: object
    subtitle_label: object
    subtitle_strategy_label: object


@dataclass(slots=True)
class StrategyDetailStrategiesSection:
    block_widget: QWidget
    card_widget: object
    header_widget: object
    title_label: object
    summary_label: object
    toolbar_widget: object
    search_input: object
    filter_combo: object
    sort_combo: object
    edit_args_btn: object
    phases_bar_widget: object
    phase_tabbar: object
    phase_tab_index_by_key: dict[str, int]
    phase_tab_key_by_index: dict[int, str]
    strategies_tree: object


def build_detail_header_section(
    *,
    page,
    tokens,
    detail_text_color: str,
    title_label_cls,
    body_label_cls,
    spinner_cls,
    pixmap_label_cls,
    transparent_push_button_cls,
    on_breadcrumb_changed,
    on_back_clicked,
    get_themed_qta_icon_fn,
) -> StrategyDetailHeaderSection:
    header = QFrame()
    header.setFrameShape(QFrame.Shape.NoFrame)
    header.setStyleSheet("background: transparent; border: none;")
    header_layout = QVBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 16)
    header_layout.setSpacing(4)

    breadcrumb = None
    parent_link = None
    try:
        from qfluentwidgets import BreadcrumbBar as _BreadcrumbBar

        breadcrumb = _BreadcrumbBar(page)
        breadcrumb.blockSignals(True)
        breadcrumb.addItem("control", page._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"))
        breadcrumb.addItem("strategies", page._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"))
        breadcrumb.addItem("detail", page._tr("page.z2_strategy_detail.header.category_fallback", "Target"))
        breadcrumb.blockSignals(False)
        breadcrumb.currentItemChanged.connect(on_breadcrumb_changed)
        header_layout.addWidget(breadcrumb)
    except Exception:
        back_row = QHBoxLayout()
        back_row.setContentsMargins(0, 0, 0, 0)
        back_row.setSpacing(4)
        parent_link = transparent_push_button_cls(parent=page)
        parent_link.setText(page._tr("page.z2_strategy_detail.back.strategies", "Стратегии DPI"))
        parent_link.setIcon(get_themed_qta_icon_fn("fa5s.chevron-left", color=tokens.fg_muted))
        parent_link.setIconSize(QSize(12, 12))
        parent_link.clicked.connect(on_back_clicked)
        back_row.addWidget(parent_link)
        back_row.addStretch()
        header_layout.addLayout(back_row)

    title_label = title_label_cls(page._tr("page.z2_strategy_detail.header.select_category", "Выберите target"))
    header_layout.addWidget(title_label)

    subtitle_widgets = build_detail_subtitle_widgets(
        parent=page,
        body_label_cls=body_label_cls,
        spinner_cls=spinner_cls,
        pixmap_label_cls=pixmap_label_cls,
        subtitle_strategy_label_cls=ElidedLabel,
        detail_text_color=detail_text_color,
    )
    header_layout.addWidget(subtitle_widgets.container_widget)

    return StrategyDetailHeaderSection(
        header_widget=header,
        breadcrumb=breadcrumb,
        parent_link=parent_link,
        title_label=title_label,
        spinner=subtitle_widgets.spinner,
        success_icon=subtitle_widgets.success_icon,
        subtitle_label=subtitle_widgets.subtitle_label,
        subtitle_strategy_label=subtitle_widgets.subtitle_strategy_label,
    )


def build_strategies_section(
    *,
    page,
    tokens,
    settings_card_cls,
    strong_label_cls,
    caption_label_cls,
    search_line_edit_cls,
    combo_cls,
    transparent_tool_button_cls,
    segmented_widget_cls,
    tree_cls,
    set_tooltip_fn,
) -> StrategyDetailStrategiesSection:
    strategy_block_widgets = build_strategy_block_shell(settings_card_cls=settings_card_cls)
    strategies_block = strategy_block_widgets.block_widget
    strategies_card = strategy_block_widgets.card_widget

    header_widgets = build_strategy_header_widgets(
        title_text=page._tr("page.z2_strategy_detail.tree.title", "Все стратегии"),
        strong_label_cls=strong_label_cls,
        caption_label_cls=caption_label_cls,
    )
    strategies_card.add_widget(header_widgets.header_widget)

    toolbar_widgets = build_strategy_toolbar_widgets(
        parent=page,
        tr=page._tr,
        tokens=tokens,
        search_line_edit_cls=search_line_edit_cls,
        combo_cls=combo_cls,
        transparent_tool_button_cls=transparent_tool_button_cls,
        set_tooltip=set_tooltip_fn,
        build_filter_combo_fn=page._build_strategy_filter_combo_for_page,
        technique_filters=STRATEGY_TECHNIQUE_FILTERS,
        on_search_changed=page._on_search_changed,
        on_filter_changed=page._on_technique_filter_changed,
        on_sort_changed=page._on_sort_combo_changed,
        on_edit_args_clicked=page._toggle_args_editor,
    )
    strategies_card.add_widget(toolbar_widgets.toolbar_widget)

    phase_widgets = build_tcp_phase_bar_widgets(
        parent=page,
        segmented_widget_cls=segmented_widget_cls,
        on_click=page._on_phase_pivot_item_clicked,
        on_changed=page._on_phase_tab_changed,
        phase_tabs=TCP_PHASE_TAB_ORDER,
    )
    strategies_card.add_widget(phase_widgets.container_widget)

    strategies_tree = build_strategies_tree_widget(
        parent=page,
        tree_cls=tree_cls,
        on_row_clicked=page._on_row_clicked,
        on_favorite_toggled=page._on_favorite_toggled,
        on_working_mark_requested=page._on_tree_working_mark_requested,
        on_preview_requested=page._on_tree_preview_requested,
        on_preview_pinned_requested=page._on_tree_preview_pinned_requested,
        on_preview_hide_requested=page._on_tree_preview_hide_requested,
    )
    strategies_card.add_widget(strategies_tree)

    return StrategyDetailStrategiesSection(
        block_widget=strategies_block,
        card_widget=strategies_card,
        header_widget=header_widgets.header_widget,
        title_label=header_widgets.title_label,
        summary_label=header_widgets.summary_label,
        toolbar_widget=toolbar_widgets.toolbar_widget,
        search_input=toolbar_widgets.search_input,
        filter_combo=toolbar_widgets.filter_combo,
        sort_combo=toolbar_widgets.sort_combo,
        edit_args_btn=toolbar_widgets.edit_args_btn,
        phases_bar_widget=phase_widgets.container_widget,
        phase_tabbar=phase_widgets.tabbar,
        phase_tab_index_by_key=phase_widgets.index_by_key,
        phase_tab_key_by_index=phase_widgets.key_by_index,
        strategies_tree=strategies_tree,
    )
