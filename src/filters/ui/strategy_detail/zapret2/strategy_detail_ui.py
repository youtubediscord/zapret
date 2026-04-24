from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from blobs.service import get_blobs_info
from filters.ui.strategy_detail.filter_mode_ui import apply_filter_mode_selector_texts
from filters.ui.strategy_detail.shared import build_detail_subtitle_widgets, build_strategies_tree_widget
from filters.ui.strategy_detail.zapret2.common import (
    STRATEGY_TECHNIQUE_FILTERS,
    TCP_PHASE_TAB_ORDER,
    ElidedLabel,
    build_strategy_block_shell,
    build_strategy_header_widgets,
    build_strategy_toolbar_widgets,
    build_tcp_phase_bar_widgets,
    prepare_compact_setting_group as _prepare_compact_setting_group,
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


@dataclass(slots=True)
class StrategyDetailSettingsSection:
    settings_host: object
    toolbar_frame: object
    general_card: object
    filter_mode_frame: object
    filter_mode_selector: object
    out_range_frame: object
    out_range_kind_label: object
    out_range_kind_seg: object
    out_range_mode_label: object
    out_range_seg: object
    out_range_mode: str
    out_range_value_label: object
    out_range_spin: object
    out_range_expression_label: object
    out_range_expression_input: object
    out_range_complex_label: object
    send_frame: object
    send_toggle_row: object
    send_toggle: object
    send_settings: object
    send_repeats_row: object
    send_repeats_spin: object
    send_ip_ttl_frame: object
    send_ip_ttl_selector: object
    send_ip6_ttl_frame: object
    send_ip6_ttl_selector: object
    send_ip_id_row: object
    send_ip_id_combo: object
    send_badsum_frame: object
    send_badsum_check: object
    syndata_frame: object
    syndata_toggle_row: object
    syndata_toggle: object
    syndata_settings: object
    blob_row: object
    blob_combo: object
    tls_mod_row: object
    tls_mod_combo: object
    autottl_delta_frame: object
    autottl_delta_selector: object
    autottl_min_frame: object
    autottl_min_selector: object
    autottl_max_frame: object
    autottl_max_selector: object
    tcp_flags_row: object
    tcp_flags_combo: object
    reset_row_widget: object
    create_preset_btn: object
    rename_preset_btn: object
    reset_settings_btn: object


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

    title_label = title_label_cls("")
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


def _connect_boolean_changed(widget, callback) -> None:
    signal = getattr(widget, "checkedChanged", None)
    if signal is None:
        signal = getattr(widget, "toggled", None)
    if signal is not None:
        signal.connect(callback)


def build_settings_section(
    *,
    page,
    content_parent,
    tr,
    has_fluent: bool,
    setting_card_group_cls,
    settings_card_cls,
    settings_row_cls,
    body_label_cls,
    switch_button_cls,
    segmented_widget_cls,
    spin_box_cls,
    line_edit_cls,
    win11_toggle_row_cls,
    win11_number_row_cls,
    win11_combo_row_cls,
    ttl_button_selector_cls,
    action_button_cls,
    set_tooltip_fn,
    on_filter_mode_changed,
    on_select_out_range_kind_simple,
    on_select_out_range_kind_expression,
    on_select_out_range_mode_a,
    on_select_out_range_mode_x,
    on_select_out_range_mode_n,
    on_select_out_range_mode_d,
    on_out_range_expression_changed,
    on_schedule_syndata_settings_save,
    on_send_toggled,
    on_syndata_toggled,
    on_create_preset_clicked,
    on_rename_preset_clicked,
    on_reset_settings_clicked,
) -> StrategyDetailSettingsSection:
    settings_host = QWidget()
    settings_host.setVisible(False)
    settings_host_layout = QVBoxLayout(settings_host)
    settings_host_layout.setContentsMargins(0, 0, 0, 0)
    settings_host_layout.setSpacing(6)

    toolbar_frame = QWidget()
    toolbar_frame.setVisible(False)
    toolbar_layout = QVBoxLayout(toolbar_frame)
    toolbar_layout.setContentsMargins(0, 4, 0, 4)
    toolbar_layout.setSpacing(12)

    general_card = settings_card_cls()

    filter_mode_frame = settings_row_cls(
        "fa5s.filter",
        tr("page.z2_strategy_detail.filter_mode.title", "Режим фильтрации"),
        tr("page.z2_strategy_detail.filter_mode.description", "Hostlist - по доменам, IPset - по IP"),
    )
    filter_mode_selector = switch_button_cls(parent=page)
    apply_filter_mode_selector_texts(
        filter_mode_selector,
        ipset_text=tr("page.z2_strategy_detail.filter.ipset", "IPset"),
        hostlist_text=tr("page.z2_strategy_detail.filter.hostlist", "Hostlist"),
    )
    _connect_boolean_changed(
        filter_mode_selector,
        lambda checked: on_filter_mode_changed("ipset" if checked else "hostlist")
    )
    filter_mode_frame.set_control(filter_mode_selector)
    general_card.add_widget(filter_mode_frame)
    filter_mode_frame.setVisible(False)

    out_range_frame = settings_row_cls(
        "fa5s.sliders-h",
        tr("page.z2_strategy_detail.out_range.title", "Out Range"),
        tr("page.z2_strategy_detail.out_range.description", "Ограничение исходящих пакетов"),
    )
    out_range_controls = QWidget()
    out_range_controls_layout = QVBoxLayout(out_range_controls)
    out_range_controls_layout.setContentsMargins(0, 0, 0, 0)
    out_range_controls_layout.setSpacing(6)

    out_range_kind_row = QWidget()
    out_range_kind_row_layout = QHBoxLayout(out_range_kind_row)
    out_range_kind_row_layout.setContentsMargins(0, 0, 0, 0)
    out_range_kind_row_layout.setSpacing(8)
    out_range_kind_label = body_label_cls(tr("page.z2_strategy_detail.out_range.kind", "Тип:"))
    out_range_kind_row_layout.addWidget(out_range_kind_label)

    out_range_kind_seg = segmented_widget_cls()
    out_range_kind_seg.addItem(
        "simple",
        tr("page.z2_strategy_detail.out_range.kind.simple", "Простой"),
        on_select_out_range_kind_simple,
    )
    out_range_kind_seg.addItem(
        "expression",
        tr("page.z2_strategy_detail.out_range.kind.expression", "Выражение"),
        on_select_out_range_kind_expression,
    )
    set_tooltip_fn(
        out_range_kind_seg,
        tr(
            "page.z2_strategy_detail.out_range.kind.tooltip",
            "Простой режим для a, x, n и d. Выражение нужно для форм вроде s1<d1, b1000- или <s34228.",
        ),
    )
    out_range_kind_seg.setCurrentItem("simple")
    out_range_kind_row_layout.addWidget(out_range_kind_seg)
    out_range_kind_row_layout.addStretch()
    out_range_controls_layout.addWidget(out_range_kind_row)

    out_range_mode_row = QWidget()
    out_range_mode_row_layout = QHBoxLayout(out_range_mode_row)
    out_range_mode_row_layout.setContentsMargins(0, 0, 0, 0)
    out_range_mode_row_layout.setSpacing(8)
    out_range_mode_label = body_label_cls(tr("page.z2_strategy_detail.out_range.mode", "Режим:"))
    out_range_mode_row_layout.addWidget(out_range_mode_label)

    out_range_seg = segmented_widget_cls()
    out_range_seg.addItem("a", "a", on_select_out_range_mode_a)
    out_range_seg.addItem("x", "x", on_select_out_range_mode_x)
    out_range_seg.addItem("n", "n", on_select_out_range_mode_n)
    out_range_seg.addItem("d", "d", on_select_out_range_mode_d)
    set_tooltip_fn(
        out_range_seg,
        tr(
            "page.z2_strategy_detail.out_range.mode.tooltip",
            "a = всегда, x = никогда, n = номер пакета, d = номер пакета с данными",
        ),
    )
    out_range_mode = "d"
    out_range_seg.setCurrentItem("d")
    out_range_mode_row_layout.addWidget(out_range_seg)
    out_range_mode_row_layout.addStretch()
    out_range_controls_layout.addWidget(out_range_mode_row)

    out_range_value_row = QWidget()
    out_range_value_row_layout = QHBoxLayout(out_range_value_row)
    out_range_value_row_layout.setContentsMargins(0, 0, 0, 0)
    out_range_value_row_layout.setSpacing(8)
    out_range_value_label = body_label_cls(tr("page.z2_strategy_detail.out_range.value", "Значение:"))
    out_range_value_row_layout.addWidget(out_range_value_label)

    out_range_spin = spin_box_cls()
    out_range_spin.setRange(1, 999)
    out_range_spin.setValue(8)
    out_range_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
    set_tooltip_fn(
        out_range_spin,
        tr(
            "page.z2_strategy_detail.out_range.value.tooltip",
            "Для режимов n и d укажите число. Для a и x значение не используется.",
        ),
    )
    out_range_spin.valueChanged.connect(on_schedule_syndata_settings_save)
    out_range_value_row_layout.addWidget(out_range_spin)
    out_range_value_row_layout.addStretch()
    out_range_controls_layout.addWidget(out_range_value_row)

    out_range_expression_row = QWidget()
    out_range_expression_row_layout = QHBoxLayout(out_range_expression_row)
    out_range_expression_row_layout.setContentsMargins(0, 0, 0, 0)
    out_range_expression_row_layout.setSpacing(8)
    out_range_expression_label = body_label_cls(tr("page.z2_strategy_detail.out_range.expression", "Выражение:"))
    out_range_expression_label.setVisible(False)
    out_range_expression_row_layout.addWidget(out_range_expression_label)

    out_range_expression_input = line_edit_cls()
    try:
        out_range_expression_input.setClearButtonEnabled(True)
    except Exception:
        pass
    out_range_expression_input.setPlaceholderText(
        tr(
            "page.z2_strategy_detail.out_range.expression.placeholder",
            "Например: s1<d1, b1000-, <s34228",
        )
    )
    set_tooltip_fn(
        out_range_expression_input,
        tr(
            "page.z2_strategy_detail.out_range.expression.tooltip",
            "Введите только значение после --out-range=. Например: x, -d10, s1<d1, b1000- или <s34228.",
        ),
    )
    out_range_expression_input.setVisible(False)
    out_range_expression_input.textChanged.connect(on_out_range_expression_changed)
    out_range_expression_row_layout.addWidget(out_range_expression_input, 1)
    out_range_controls_layout.addWidget(out_range_expression_row)

    out_range_complex_label = body_label_cls("")
    try:
        out_range_complex_label.setWordWrap(True)
    except Exception:
        pass
    out_range_complex_label.setVisible(False)
    out_range_controls_layout.addWidget(out_range_complex_label)

    out_range_frame.set_control(out_range_controls)

    general_card.add_widget(out_range_frame)
    toolbar_layout.addWidget(general_card)

    if setting_card_group_cls is not None and has_fluent:
        send_frame = setting_card_group_cls(
            tr("page.z2_strategy_detail.send.toggle.title", "Send параметры"),
            content_parent,
        )
        _prepare_compact_setting_group(send_frame)
    else:
        send_frame = settings_card_cls()
    send_frame.setVisible(False)

    send_toggle_row = win11_toggle_row_cls(
        "fa5s.paper-plane",
        tr("page.z2_strategy_detail.send.toggle.title", "Send параметры"),
        tr("page.z2_strategy_detail.send.toggle.description", "Отправка копий пакетов"),
    )
    send_toggle = send_toggle_row.toggle
    send_toggle_row.toggled.connect(on_send_toggled)
    if hasattr(send_frame, "addSettingCard"):
        send_frame.addSettingCard(send_toggle_row)
    else:
        send_frame.add_widget(send_toggle_row)

    send_settings = QWidget()
    send_settings.setVisible(False)
    send_settings_layout = QVBoxLayout(send_settings)
    send_settings_layout.setContentsMargins(12, 0, 0, 0)
    send_settings_layout.setSpacing(0)

    send_repeats_row = win11_number_row_cls(
        "fa5s.redo",
        tr("page.z2_strategy_detail.send.repeats.title", "repeats"),
        tr("page.z2_strategy_detail.send.repeats.description", "Количество повторных отправок"),
        min_val=0,
        max_val=10,
        default_val=2,
    )
    send_repeats_spin = send_repeats_row.spinbox
    send_repeats_row.valueChanged.connect(on_schedule_syndata_settings_save)
    send_settings_layout.addWidget(send_repeats_row)

    send_ip_ttl_frame = settings_row_cls(
        "fa5s.stopwatch",
        tr("page.z2_strategy_detail.send.ip_ttl.title", "ip_ttl"),
        tr("page.z2_strategy_detail.send.ip_ttl.description", "TTL для IPv4 отправляемых пакетов"),
    )
    send_ip_ttl_selector = ttl_button_selector_cls(
        values=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        labels=["off", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
    )
    send_ip_ttl_selector.value_changed.connect(on_schedule_syndata_settings_save)
    send_ip_ttl_frame.set_control(send_ip_ttl_selector)
    send_settings_layout.addWidget(send_ip_ttl_frame)

    send_ip6_ttl_frame = settings_row_cls(
        "fa5s.stopwatch",
        tr("page.z2_strategy_detail.send.ip6_ttl.title", "ip6_ttl"),
        tr("page.z2_strategy_detail.send.ip6_ttl.description", "TTL для IPv6 отправляемых пакетов"),
    )
    send_ip6_ttl_selector = ttl_button_selector_cls(
        values=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        labels=["off", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
    )
    send_ip6_ttl_selector.value_changed.connect(on_schedule_syndata_settings_save)
    send_ip6_ttl_frame.set_control(send_ip6_ttl_selector)
    send_settings_layout.addWidget(send_ip6_ttl_frame)

    send_ip_id_row = win11_combo_row_cls(
        "fa5s.fingerprint",
        tr("page.z2_strategy_detail.send.ip_id.title", "ip_id"),
        tr("page.z2_strategy_detail.send.ip_id.description", "Режим IP ID для отправляемых пакетов"),
        items=[("none", None), ("seq", None), ("rnd", None), ("zero", None)],
    )
    send_ip_id_combo = send_ip_id_row.combo
    send_ip_id_row.currentTextChanged.connect(on_schedule_syndata_settings_save)
    send_settings_layout.addWidget(send_ip_id_row)

    send_badsum_frame = settings_row_cls(
        "fa5s.exclamation-triangle",
        tr("page.z2_strategy_detail.send.badsum.title", "badsum"),
        tr(
            "page.z2_strategy_detail.send.badsum.description",
            "Отправлять пакеты с неправильной контрольной суммой",
        ),
    )
    send_badsum_check = switch_button_cls()
    _connect_boolean_changed(send_badsum_check, on_schedule_syndata_settings_save)
    send_badsum_frame.set_control(send_badsum_check)
    send_settings_layout.addWidget(send_badsum_frame)

    if hasattr(send_frame, "addSettingCard"):
        send_frame.addSettingCard(send_settings)
    else:
        send_frame.add_widget(send_settings)
    toolbar_layout.addWidget(send_frame)

    if setting_card_group_cls is not None and has_fluent:
        syndata_frame = setting_card_group_cls(
            tr("page.z2_strategy_detail.syndata.toggle.title", "Syndata параметры"),
            content_parent,
        )
        _prepare_compact_setting_group(syndata_frame)
    else:
        syndata_frame = settings_card_cls()
    syndata_frame.setVisible(False)

    syndata_toggle_row = win11_toggle_row_cls(
        "fa5s.cog",
        tr("page.z2_strategy_detail.syndata.toggle.title", "Syndata параметры"),
        tr(
            "page.z2_strategy_detail.syndata.toggle.description",
            "Дополнительные параметры обхода DPI",
        ),
    )
    syndata_toggle = syndata_toggle_row.toggle
    syndata_toggle_row.toggled.connect(on_syndata_toggled)
    if hasattr(syndata_frame, "addSettingCard"):
        syndata_frame.addSettingCard(syndata_toggle_row)
    else:
        syndata_frame.add_widget(syndata_toggle_row)

    syndata_settings = QWidget()
    syndata_settings.setVisible(False)
    settings_layout = QVBoxLayout(syndata_settings)
    settings_layout.setContentsMargins(12, 0, 0, 0)
    settings_layout.setSpacing(0)

    blob_names = ["none"]
    try:
        all_blobs = get_blobs_info()
        blob_names = ["none"] + sorted(all_blobs.keys())
    except Exception:
        blob_names = ["none", "tls_google", "tls7"]
    blob_items = [(name, None) for name in blob_names]

    blob_row = win11_combo_row_cls(
        "fa5s.file-code",
        tr("page.z2_strategy_detail.syndata.blob.title", "blob"),
        tr("page.z2_strategy_detail.syndata.blob.description", "Полезная нагрузка пакета"),
        items=blob_items,
    )
    blob_combo = blob_row.combo
    blob_row.currentTextChanged.connect(on_schedule_syndata_settings_save)
    settings_layout.addWidget(blob_row)

    tls_mod_row = win11_combo_row_cls(
        "fa5s.shield-alt",
        tr("page.z2_strategy_detail.syndata.tls_mod.title", "tls_mod"),
        tr("page.z2_strategy_detail.syndata.tls_mod.description", "Модификация полезной нагрузки TLS"),
        items=[("none", None), ("rnd", None), ("rndsni", None), ("sni=google.com", None)],
    )
    tls_mod_combo = tls_mod_row.combo
    tls_mod_row.currentTextChanged.connect(on_schedule_syndata_settings_save)
    settings_layout.addWidget(tls_mod_row)

    autottl_delta_frame = settings_row_cls(
        "fa5s.clock",
        tr("page.z2_strategy_detail.syndata.autottl_delta.title", "AutoTTL Delta"),
        tr(
            "page.z2_strategy_detail.syndata.autottl_delta.description",
            "Смещение от измеренного TTL (OFF = убрать ip_autottl)",
        ),
    )
    autottl_delta_selector = ttl_button_selector_cls(
        values=[0, -1, -2, -3, -4, -5, -6, -7, -8, -9],
        labels=["OFF", "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9"],
    )
    autottl_delta_selector.value_changed.connect(on_schedule_syndata_settings_save)
    autottl_delta_frame.set_control(autottl_delta_selector)
    settings_layout.addWidget(autottl_delta_frame)

    autottl_min_frame = settings_row_cls(
        "fa5s.angle-down",
        tr("page.z2_strategy_detail.syndata.autottl_min.title", "AutoTTL Min"),
        tr("page.z2_strategy_detail.syndata.autottl_min.description", "Минимальный TTL"),
    )
    autottl_min_selector = ttl_button_selector_cls(
        values=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        labels=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
    )
    autottl_min_selector.value_changed.connect(on_schedule_syndata_settings_save)
    autottl_min_frame.set_control(autottl_min_selector)
    settings_layout.addWidget(autottl_min_frame)

    autottl_max_frame = settings_row_cls(
        "fa5s.angle-up",
        tr("page.z2_strategy_detail.syndata.autottl_max.title", "AutoTTL Max"),
        tr("page.z2_strategy_detail.syndata.autottl_max.description", "Максимальный TTL"),
    )
    autottl_max_selector = ttl_button_selector_cls(
        values=[15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25],
        labels=["15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25"],
    )
    autottl_max_selector.value_changed.connect(on_schedule_syndata_settings_save)
    autottl_max_frame.set_control(autottl_max_selector)
    settings_layout.addWidget(autottl_max_frame)

    tcp_flags_row = win11_combo_row_cls(
        "fa5s.flag",
        tr("page.z2_strategy_detail.syndata.tcp_flags.title", "tcp_flags_unset"),
        tr("page.z2_strategy_detail.syndata.tcp_flags.description", "Сбросить TCP флаги"),
        items=[("none", None), ("ack", None), ("psh", None), ("ack,psh", None)],
    )
    tcp_flags_combo = tcp_flags_row.combo
    tcp_flags_row.currentTextChanged.connect(on_schedule_syndata_settings_save)
    settings_layout.addWidget(tcp_flags_row)

    if hasattr(syndata_frame, "addSettingCard"):
        syndata_frame.addSettingCard(syndata_settings)
    else:
        syndata_frame.add_widget(syndata_settings)
    toolbar_layout.addWidget(syndata_frame)

    reset_row_widget = QWidget()
    reset_row = QHBoxLayout(reset_row_widget)
    reset_row.setContentsMargins(0, 8, 0, 0)
    reset_row.setSpacing(8)

    create_preset_btn = action_button_cls(
        tr("page.z2_strategy_detail.button.create_preset", "Создать пресет"),
        "fa5s.plus",
    )
    set_tooltip_fn(
        create_preset_btn,
        tr(
            "page.z2_strategy_detail.button.create_preset.tooltip",
            "Создать новый пресет на основе текущих настроек",
        ),
    )
    create_preset_btn.clicked.connect(on_create_preset_clicked)
    reset_row.addWidget(create_preset_btn)

    rename_preset_btn = action_button_cls(
        tr("page.z2_strategy_detail.button.rename_preset", "Переименовать"),
        "fa5s.pen",
    )
    set_tooltip_fn(
        rename_preset_btn,
        tr(
            "page.z2_strategy_detail.button.rename_preset.tooltip",
            "Переименовать текущий активный пресет",
        ),
    )
    rename_preset_btn.clicked.connect(on_rename_preset_clicked)
    reset_row.addWidget(rename_preset_btn)

    reset_row.addStretch()

    reset_settings_btn = action_button_cls(
        tr("page.z2_strategy_detail.button.reset_settings", "Сбросить настройки"),
        "fa5s.undo",
    )
    reset_settings_btn.clicked.connect(on_reset_settings_clicked)
    reset_row.addWidget(reset_settings_btn)
    reset_row_widget.setVisible(False)

    toolbar_layout.addWidget(reset_row_widget)
    settings_host_layout.addWidget(toolbar_frame)

    return StrategyDetailSettingsSection(
        settings_host=settings_host,
        toolbar_frame=toolbar_frame,
        general_card=general_card,
        filter_mode_frame=filter_mode_frame,
        filter_mode_selector=filter_mode_selector,
        out_range_frame=out_range_frame,
        out_range_kind_label=out_range_kind_label,
        out_range_kind_seg=out_range_kind_seg,
        out_range_mode_label=out_range_mode_label,
        out_range_seg=out_range_seg,
        out_range_mode=out_range_mode,
        out_range_value_label=out_range_value_label,
        out_range_spin=out_range_spin,
        out_range_expression_label=out_range_expression_label,
        out_range_expression_input=out_range_expression_input,
        out_range_complex_label=out_range_complex_label,
        send_frame=send_frame,
        send_toggle_row=send_toggle_row,
        send_toggle=send_toggle,
        send_settings=send_settings,
        send_repeats_row=send_repeats_row,
        send_repeats_spin=send_repeats_spin,
        send_ip_ttl_frame=send_ip_ttl_frame,
        send_ip_ttl_selector=send_ip_ttl_selector,
        send_ip6_ttl_frame=send_ip6_ttl_frame,
        send_ip6_ttl_selector=send_ip6_ttl_selector,
        send_ip_id_row=send_ip_id_row,
        send_ip_id_combo=send_ip_id_combo,
        send_badsum_frame=send_badsum_frame,
        send_badsum_check=send_badsum_check,
        syndata_frame=syndata_frame,
        syndata_toggle_row=syndata_toggle_row,
        syndata_toggle=syndata_toggle,
        syndata_settings=syndata_settings,
        blob_row=blob_row,
        blob_combo=blob_combo,
        tls_mod_row=tls_mod_row,
        tls_mod_combo=tls_mod_combo,
        autottl_delta_frame=autottl_delta_frame,
        autottl_delta_selector=autottl_delta_selector,
        autottl_min_frame=autottl_min_frame,
        autottl_min_selector=autottl_min_selector,
        autottl_max_frame=autottl_max_frame,
        autottl_max_selector=autottl_max_selector,
        tcp_flags_row=tcp_flags_row,
        tcp_flags_combo=tcp_flags_combo,
        reset_row_widget=reset_row_widget,
        create_preset_btn=create_preset_btn,
        rename_preset_btn=rename_preset_btn,
        reset_settings_btn=reset_settings_btn,
    )
