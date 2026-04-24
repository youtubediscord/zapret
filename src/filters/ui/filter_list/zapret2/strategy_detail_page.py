# filters/ui/filter_list/zapret2/strategy_detail_page.py
"""
Страница детального просмотра стратегий для выбранного target'а.
Открывается при клике на target в Zapret2StrategiesPageNew.
"""

import json
import time as _time

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QEvent
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QFrame, QMenu,
)

from ui.page_dependencies import require_page_app_context
try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel, SubtitleLabel,
        ComboBox, SpinBox, LineEdit, TextEdit,
        ToolButton, TransparentToolButton, SwitchButton, SegmentedWidget, TogglePushButton,
        PixmapLabel,
        TitleLabel, TransparentPushButton, IndeterminateProgressRing, RoundMenu, Action,
        InfoBar, FluentIcon, SettingCardGroup, MessageBox,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import (
        QComboBox as ComboBox, QSpinBox as SpinBox,
        QLineEdit as LineEdit, QTextEdit as TextEdit, QPushButton, QCheckBox,
    )
    BodyLabel = QLabel
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    SubtitleLabel = QLabel
    TitleLabel = QLabel
    ToolButton = QPushButton
    TransparentToolButton = QPushButton
    SwitchButton = QCheckBox
    TransparentPushButton = QPushButton
    SegmentedWidget = QWidget
    TogglePushButton = QPushButton
    TextEdit = QWidget
    PixmapLabel = QLabel
    IndeterminateProgressRing = QWidget
    RoundMenu = QMenu
    Action = lambda *a, **kw: None
    InfoBar = None
    FluentIcon = None
    SettingCardGroup = None
    MessageBox = None
    _HAS_FLUENT = False

try:
    from qfluentwidgets import SearchLineEdit
except ImportError:
    SearchLineEdit = LineEdit

from ui.pages.base_page import BasePage
from app_state.main_window_state import AppUiState, MainWindowStateStore
from ui.compat_widgets import ActionButton, SettingsRow, set_tooltip, SettingsCard
from ui.widgets.win11_controls import Win11ToggleRow, Win11ComboRow, Win11NumberRow
from filters.ui.strategy_tree import StrategyTree, StrategyTreeRow
from ui.popup_menu import exec_popup_menu
from filters.ui.strategy_detail.args_preview_dialog import ArgsPreviewDialog
from blobs.service import get_blobs_info
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon
from log.log import log

from filters.strategy_detail.zapret2.controller import StrategyDetailPageController
from filters.strategy_detail.zapret2.payload_logic import (
    build_apply_feedback_timeout_plan,
    build_row_click_plan,
    build_status_icon_plan,
)
from filters.strategy_detail.zapret2.runtime_state import (
    create_preset_refresh_runtime,
    create_strategies_load_runtime,
    create_target_payload_runtime,
)
from filters.ui.strategy_detail.zapret2.apply import (
    apply_selected_strategy_header_state,
    apply_target_payload_header_state,
)
from filters.ui.strategy_detail.shared import (
    build_detail_subtitle_widgets,
    build_strategies_tree_widget,
    run_args_editor_dialog,
)
from filters.ui.strategy_detail.shared_detail_header import build_detail_header_text_state
from filters.ui.strategy_detail.filter_mode_ui import apply_filter_mode_selector_texts
from filters.ui.strategy_detail.zapret2.common import (
    STRATEGY_TECHNIQUE_FILTERS,
    TCP_EMBEDDED_FAKE_TECHNIQUES,
    TCP_PHASE_COMMAND_ORDER,
    TCP_PHASE_TAB_ORDER,
    ElidedLabel,
    build_strategy_block_shell,
    build_selected_strategy_header_state,
    build_strategy_header_widgets,
    build_strategy_filter_combo,
    build_strategy_toolbar_widgets,
    build_tcp_phase_bar_widgets,
    refresh_strategy_filter_combo,
    log_z2_detail_metric as _log_z2_detail_metric,
    prepare_compact_setting_group as _prepare_compact_setting_group,
    tr_text as _tr_text,
)
from filters.ui.strategy_detail.zapret2.strategy_detail_ui import (
    build_detail_header_section,
    build_settings_section,
    build_strategies_section,
)
from filters.ui.strategy_detail.zapret2.page_actions_runtime import (
    apply_args_editor_runtime,
    build_args_editor_open_plan,
    confirm_reset_settings_clicked,
    create_preset_from_current,
    hide_args_editor_runtime,
    on_args_changed_runtime,
    on_create_preset_clicked,
    on_rename_preset_clicked,
    on_reset_settings_confirmed,
    refresh_args_editor_state_runtime,
    rename_current_preset,
    toggle_args_editor_runtime,
)
from filters.ui.strategy_detail.zapret2.page_filtering_runtime import (
    apply_filters_runtime,
    apply_sort_runtime,
    on_filter_toggled,
    on_phase_pivot_item_clicked,
    on_phase_tab_changed,
    on_search_changed,
    on_sort_combo_changed,
    on_technique_filter_changed,
    populate_sort_combo_runtime,
    show_sort_menu_runtime,
    sync_tree_selection_to_active_phase_runtime,
    update_sort_button_ui_runtime,
    update_strategies_summary_runtime,
    update_technique_filter_ui_runtime,
)
from filters.ui.strategy_detail.zapret2.page_interactions_runtime import (
    close_preview_dialog_runtime,
    close_transient_overlays,
    ensure_preview_dialog_runtime,
    get_default_strategy,
    get_preview_rating,
    get_preview_strategy_data,
    on_favorite_toggled,
    on_preview_closed,
    on_tree_preview_hide_requested,
    on_tree_preview_pinned_requested,
    on_tree_preview_requested,
    on_tree_working_mark_requested,
    refresh_working_marks_for_target,
    show_preview_dialog_runtime,
    toggle_preview_rating,
)
from filters.ui.strategy_detail.zapret2.strategy_detail_runtime import (
    apply_preset_refresh_now,
    apply_target_payload,
    apply_page_theme,
    apply_pending_target_request_if_ready,
    after_content_built,
    close_filter_combo_popup,
    handle_hide_event,
    handle_host_window_event_filter,
    handle_page_activated,
    install_host_window_event_filter,
    on_target_payload_loaded,
    refresh_scroll_range,
    refresh_from_preset_switch,
    request_target_payload,
    restore_scroll_state,
    save_scroll_state,
    show_target,
)
from filters.ui.strategy_detail.zapret2.page_phase_runtime import (
    apply_out_range_ui_state,
    apply_tcp_phase_tabs_visibility_runtime,
    extract_desync_techniques_from_args,
    flush_syndata_settings_save,
    get_strategy_args_text_by_id,
    get_target_strategy_args_text,
    infer_strategy_id_from_args_exact,
    infer_tcp_phase_key_for_strategy_args,
    load_syndata_settings,
    load_target_last_tcp_phase_tab,
    load_tcp_phase_state_from_preset_runtime,
    on_send_toggled,
    on_syndata_toggled,
    on_tcp_phase_row_clicked,
    save_target_last_tcp_phase_tab,
    save_tcp_phase_state_to_preset,
    schedule_syndata_settings_save,
    select_default_tcp_phase_tab_runtime,
    select_out_range_kind,
    select_out_range_mode,
    set_out_range_expression,
    set_active_phase_chip_runtime,
    update_tcp_phase_chip_markers_runtime,
)
from filters.ui.strategy_detail.zapret2.page_strategies_runtime import (
    add_strategy_row,
    clear_strategies,
    is_dpi_running_now,
    load_next_strategies_batch,
    load_strategies,
)
from filters.strategy_detail.zapret2.mode_policy import StrategyDetailModePolicy
from direct_preset.ui.zapret2.preset_dialogs import PresetNameDialog
from filters.mode_runtime import resolve_direct_mode_override
from filters.ui.strategy_detail.zapret2.args_editor import (
    hide_args_editor_state,
    open_args_editor_dialog,
    refresh_args_editor_state,
)
from filters.ui.strategy_detail.zapret2.preset_workflow import (
    present_preset_action_result,
    present_preset_exception,
    prompt_preset_name,
)
from filters.ui.strategy_detail.zapret2.filtering_ui import (
    apply_filter_plan_to_tree,
    apply_sort_plan_to_tree,
    populate_sort_combo,
    update_sort_button_ui,
    update_strategies_summary,
    update_technique_filter_ui,
)
from filters.ui.strategy_detail.zapret2.tcp_phase_ui import (
    apply_tcp_phase_tabs_visibility,
    select_default_tcp_phase_tab,
    set_active_phase_chip,
    sync_tree_selection_to_active_phase,
    update_tcp_phase_chip_markers,
)
from filters.strategy_detail.zapret2.tcp_phase_workflow import (
    apply_tcp_phase_row_click_result,
    apply_tcp_phase_save_result,
    build_strategy_args_lookup,
    load_tcp_phase_state,
)
from filters.ui.strategy_detail.zapret2.sort_menu import show_sort_menu
from filters.ui.strategy_detail.zapret2.target_ui import (
    set_target_block_dimmed,
    set_target_enabled_ui,
)
from filters.ui.strategy_detail.zapret2.target_payload_apply import (
    apply_payload_reuse_plan,
    finalize_target_payload_apply_ui,
    prepare_target_payload_apply_ui,
)
from filters.ui.strategy_detail.zapret2.ttl_button_selector import TTLButtonSelector
from filters.strategy_detail.zapret2.helpers import (
    extract_desync_technique_from_arg as _extract_desync_technique_from_arg,
    map_desync_technique_to_tcp_phase as _map_desync_technique_to_tcp_phase,
    normalize_args_text as _normalize_args_text,
)

TCP_FAKE_DISABLED_STRATEGY_ID = "__phase_fake_disabled__"
CUSTOM_STRATEGY_ID = "custom"

class StrategyDetailPage(BasePage):
    """
    Страница детального выбора стратегии для target'а.

    Signals:
        strategy_selected(str, str): Эмитится при выборе стратегии (target_key, strategy_id)
        args_changed(str, str, list): Эмитится при изменении аргументов (target_key, strategy_id, new_args)
        strategy_marked(str, str, object): Эмитится при пометке стратегии (target_key, strategy_id, is_working)
        back_clicked(): Эмитится при нажатии кнопки "Назад"
    """

    strategy_selected = pyqtSignal(str, str)  # target_key, strategy_id
    filter_mode_changed = pyqtSignal(str, str)  # target_key, "hostlist"|"ipset"
    args_changed = pyqtSignal(str, str, list)  # target_key, strategy_id, new_args
    strategy_marked = pyqtSignal(str, str, object)  # target_key, strategy_id, is_working (bool|None)
    back_clicked = pyqtSignal()
    navigate_to_root = pyqtSignal()  # → PageName.ZAPRET2_DIRECT_CONTROL (skip strategies list)
    CUSTOM_STRATEGY_ID = CUSTOM_STRATEGY_ID
    TCP_FAKE_DISABLED_STRATEGY_ID = TCP_FAKE_DISABLED_STRATEGY_ID
    StrategyTreeRow = StrategyTreeRow
    direct_mode_override: str | None = None

    def __init__(self, parent=None):
        super().__init__(
            title="",  # Заголовок будет установлен динамически
            subtitle="",
            title_key="page.z2_strategy_detail.title",
            subtitle_key="page.z2_strategy_detail.subtitle",
            parent=parent,
        )
        # BasePage uses `SetMaximumSize` to clamp the content widget to its layout's
        # sizeHint. With dynamic/lazy-loaded content (like strategies list), this can
        # leave the scroll range "stuck" and cut off the bottom. For this page, keep
        # the default constraint so height can grow freely.
        try:
            self.layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)
        except Exception:
            pass
        # Reset the content widget maximum size too: `SetMaximumSize` may have already
        # applied a maxHeight during BasePage init, and switching the layout constraint
        # afterwards does not always clear that clamp.
        try:
            if hasattr(self, "content") and self.content is not None:
                self.content.setMaximumSize(16777215, 16777215)
        except Exception:
            pass
        self.parent_app = parent
        self._target_key = None
        self._target_info = None
        self._target_payload = None
        self._target_payload_runtime = create_target_payload_runtime()
        self._current_strategy_id = "none"
        self._selected_strategy_id = "none"
        self._strategies_tree = None
        self._sort_mode = "default"  # default, name_asc, name_desc
        self._active_filters = set()  # Активные фильтры по технике
        # TCP multi-phase UI state (direct_zapret2, tcp.txt + tcp_fake.txt)
        self._tcp_phase_mode = False
        self._phase_tabbar: SegmentedWidget | None = None
        self._phase_tab_index_by_key: dict[str, int] = {}
        self._phase_tab_key_by_index: dict[int, str] = {}
        self._active_phase_key = None
        self._last_active_phase_key_by_target: dict[str, str] = {}
        self._tcp_phase_selected_ids: dict[str, str] = {}  # phase_key -> strategy_id
        self._tcp_phase_custom_args: dict[str, str] = {}  # phase_key -> raw args chunk (if no matching strategy)
        self._tcp_hide_fake_phase = False
        self._tcp_last_enabled_args_by_target: dict[str, str] = {}
        self._waiting_for_process_start = False  # Флаг ожидания запуска DPI
        self._apply_feedback_timer = None  # Быстрый таймер: убрать спиннер после apply
        self._strategies_load_runtime = create_strategies_load_runtime()
        self._loaded_strategy_type = None
        self._loaded_direct_mode = None
        self._loaded_tcp_phase_mode = False
        self._detail_mode_policy: StrategyDetailModePolicy | None = None
        self._default_strategy_order = []
        self._strategies_loaded_fully = False
        self._page_scroll_by_target: dict[str, int] = {}
        self._tree_scroll_by_target: dict[str, int] = {}
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._cleanup_in_progress = False

        app_context = require_page_app_context(
            self,
            parent=parent,
            error_message="AppContext is required for Zapret2 strategy detail page",
        )

        # Direct preset facade for target settings storage
        from direct_preset.facade import DirectPresetFacade

        self._direct_facade = DirectPresetFacade.from_launch_method(
            "direct_zapret2",
            app_context=app_context,
            direct_mode_override=self._current_direct_mode(),
            on_dpi_reload_needed=self._on_dpi_reload_needed,
        )
        self._feedback_store = app_context.strategy_feedback_store
        self._favorite_strategy_ids = set()
        self._preview_dialog = None
        self._preview_pinned = False
        self._host_window = None
        self._args_preview_dialog_cls = ArgsPreviewDialog
        self._run_args_editor_dialog_fn = run_args_editor_dialog
        self._get_theme_tokens_fn = get_theme_tokens
        self._set_tooltip_fn = set_tooltip
        self._exec_popup_menu_fn = exec_popup_menu
        self._show_sort_menu_impl = show_sort_menu
        self._round_menu_cls = RoundMenu
        self._action_cls = Action
        self._fluent_icon_cls = FluentIcon
        self._strategies_data_by_id = {}
        self._content_built = False
        self._last_theme_overrides_key = None
        self._last_parent_link_icon_color = None
        self._last_edit_args_icon_color = None
        self._preset_refresh_runtime = create_preset_refresh_runtime()
        self._last_sort_icon_color = None
        self._last_strategies_summary_text = None
        self._pending_syndata_target_key: str | None = None
        self._syndata_save_timer = QTimer(self)
        self._syndata_save_timer.setSingleShot(True)
        self._syndata_save_timer.timeout.connect(self._flush_syndata_settings_save)
        self._build_content()
        self._after_content_built()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        return _tr_text(self._ui_language, key, default, **kwargs)

    def _build_strategy_filter_combo_for_page(self, combo, tr, *, technique_filters=None) -> None:
        build_strategy_filter_combo(combo, tr, technique_filters=technique_filters)

    def _after_content_built(self) -> None:
        after_content_built(self)

    def _install_host_window_event_filter(self) -> None:
        install_host_window_event_filter(self)

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        super_handler = super(StrategyDetailPage, self).eventFilter
        return handle_host_window_event_filter(
            self,
            obj,
            event,
            super_handler=lambda: super_handler(obj, event),
        )

    def _close_filter_combo_popup(self) -> None:
        close_filter_combo_popup(self)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        self._HAS_FLUENT = _HAS_FLUENT
        apply_page_theme(self, tokens=tokens, force=force)

    def hideEvent(self, event):  # noqa: N802 (Qt override)
        super_handler = super(StrategyDetailPage, self).hideEvent
        return handle_hide_event(self, event, super_handler=lambda: super_handler(event))

    def on_page_activated(self) -> None:
        handle_page_activated(self)

    def _refresh_scroll_range(self) -> None:
        refresh_scroll_range(self)

    def _apply_pending_target_request_if_ready(self) -> None:
        apply_pending_target_request_if_ready(self)

    def _save_scroll_state(self, target_key: str | None = None) -> None:
        save_scroll_state(self, target_key=target_key)

    def _restore_scroll_state(self, target_key: str | None = None, defer: bool = False) -> None:
        restore_scroll_state(self, target_key=target_key, defer=defer)

    def _on_dpi_reload_needed(self):
        """Callback for direct preset facade when DPI reload is needed."""
        # Any preset sync may restart / hot-reload winws2 via the config watcher.
        # Flip the header indicator to spinner so UI matches the real behavior.
        try:
            self.show_loading()
        except Exception:
            pass
        from winws_runtime.flow.apply_policy import request_direct_runtime_content_apply
        if self.parent_app:
            request_direct_runtime_content_apply(
                self.parent_app,
                launch_method="direct_zapret2",
                reason="preset_settings_changed",
                target_key=self._target_key
            )

    def _on_breadcrumb_item_changed(self, route_key: str) -> None:
        """Breadcrumb click handler: navigate up the hierarchy."""
        # BreadcrumbBar physically deletes trailing items on click —
        # restore the full path immediately so the widget is correct when we return.
        if self._breadcrumb is not None and self._target_key:
            target_title = ""
            try:
                target_title = self._target_info.full_name if self._target_info else ""
            except Exception:
                pass
            self._breadcrumb.blockSignals(True)
            try:
                self._breadcrumb.clear()
                self._breadcrumb.addItem("control", self._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"))
                self._breadcrumb.addItem("strategies", self._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"))
                self._breadcrumb.addItem(
                    "detail",
                    target_title or self._tr("page.z2_strategy_detail.header.category_fallback", "Target"),
                )
            finally:
                self._breadcrumb.blockSignals(False)

        if route_key == "control":
            self.navigate_to_root.emit()
        elif route_key == "strategies":
            self.back_clicked.emit()
        # "detail" = current page, nothing to do

    def _build_content(self):
        """Строит содержимое страницы"""
        _t_total = _time.perf_counter()
        tokens = get_theme_tokens()
        detail_text_color = tokens.fg_muted if tokens.is_light else tokens.fg
        _t_header = _time.perf_counter()

        # Скрываем стандартный заголовок BasePage
        if self.title_label is not None:
            self.title_label.hide()
        if self.subtitle_label is not None:
            self.subtitle_label.hide()

        header_section = build_detail_header_section(
            page=self,
            tokens=tokens,
            detail_text_color=detail_text_color,
            title_label_cls=TitleLabel,
            body_label_cls=BodyLabel,
            spinner_cls=IndeterminateProgressRing,
            pixmap_label_cls=PixmapLabel,
            transparent_push_button_cls=TransparentPushButton,
            on_breadcrumb_changed=self._on_breadcrumb_item_changed,
            on_back_clicked=self.back_clicked.emit,
            get_themed_qta_icon_fn=get_themed_qta_icon,
        )
        self._breadcrumb = header_section.breadcrumb
        self._parent_link = header_section.parent_link
        self._title = header_section.title_label
        self._spinner = header_section.spinner
        self._success_icon = header_section.success_icon
        self._subtitle = header_section.subtitle_label
        self._subtitle_strategy = header_section.subtitle_strategy_label

        self.layout.addWidget(header_section.header_widget)
        _log_z2_detail_metric("_build_content.header", (_time.perf_counter() - _t_header) * 1000)

        # ═══════════════════════════════════════════════════════════════
        # ВКЛЮЧЕНИЕ КАТЕГОРИИ + НАСТРОЙКИ
        # ═══════════════════════════════════════════════════════════════
        _t_settings = _time.perf_counter()
        settings_section = build_settings_section(
            page=self,
            content_parent=self.content,
            tr=self._tr,
            has_fluent=_HAS_FLUENT,
            setting_card_group_cls=SettingCardGroup,
            settings_card_cls=SettingsCard,
            settings_row_cls=SettingsRow,
            body_label_cls=BodyLabel,
            switch_button_cls=SwitchButton,
            segmented_widget_cls=SegmentedWidget,
            spin_box_cls=SpinBox,
            line_edit_cls=LineEdit,
            win11_toggle_row_cls=Win11ToggleRow,
            win11_number_row_cls=Win11NumberRow,
            win11_combo_row_cls=Win11ComboRow,
            ttl_button_selector_cls=TTLButtonSelector,
            action_button_cls=ActionButton,
            set_tooltip_fn=set_tooltip,
            on_filter_mode_changed=self._on_filter_mode_changed,
            on_select_out_range_kind_simple=lambda: self._select_out_range_kind("simple"),
            on_select_out_range_kind_expression=lambda: self._select_out_range_kind("expression"),
            on_select_out_range_mode_a=lambda: self._select_out_range_mode("a"),
            on_select_out_range_mode_x=lambda: self._select_out_range_mode("x"),
            on_select_out_range_mode_n=lambda: self._select_out_range_mode("n"),
            on_select_out_range_mode_d=lambda: self._select_out_range_mode("d"),
            on_out_range_expression_changed=self._on_out_range_expression_changed,
            on_schedule_syndata_settings_save=self._schedule_syndata_settings_save,
            on_send_toggled=self._on_send_toggled,
            on_syndata_toggled=self._on_syndata_toggled,
            on_create_preset_clicked=self._on_create_preset_clicked,
            on_rename_preset_clicked=self._on_rename_preset_clicked,
            on_reset_settings_clicked=self._confirm_reset_settings_clicked,
        )
        self._settings_host = settings_section.settings_host
        self._toolbar_frame = settings_section.toolbar_frame
        self._general_card = settings_section.general_card
        self._filter_mode_frame = settings_section.filter_mode_frame
        self._filter_mode_selector = settings_section.filter_mode_selector
        self._out_range_frame = settings_section.out_range_frame
        self._out_range_kind_label = settings_section.out_range_kind_label
        self._out_range_kind_seg = settings_section.out_range_kind_seg
        self._out_range_mode_label = settings_section.out_range_mode_label
        self._out_range_seg = settings_section.out_range_seg
        self._out_range_mode = settings_section.out_range_mode
        self._out_range_value_label = settings_section.out_range_value_label
        self._out_range_spin = settings_section.out_range_spin
        self._out_range_expression_label = settings_section.out_range_expression_label
        self._out_range_expression_input = settings_section.out_range_expression_input
        self._out_range_complex_label = settings_section.out_range_complex_label
        self._send_frame = settings_section.send_frame
        self._send_toggle_row = settings_section.send_toggle_row
        self._send_toggle = settings_section.send_toggle
        self._send_settings = settings_section.send_settings
        self._send_repeats_row = settings_section.send_repeats_row
        self._send_repeats_spin = settings_section.send_repeats_spin
        self._send_ip_ttl_frame = settings_section.send_ip_ttl_frame
        self._send_ip_ttl_selector = settings_section.send_ip_ttl_selector
        self._send_ip6_ttl_frame = settings_section.send_ip6_ttl_frame
        self._send_ip6_ttl_selector = settings_section.send_ip6_ttl_selector
        self._send_ip_id_row = settings_section.send_ip_id_row
        self._send_ip_id_combo = settings_section.send_ip_id_combo
        self._send_badsum_frame = settings_section.send_badsum_frame
        self._send_badsum_check = settings_section.send_badsum_check
        self._syndata_frame = settings_section.syndata_frame
        self._syndata_toggle_row = settings_section.syndata_toggle_row
        self._syndata_toggle = settings_section.syndata_toggle
        self._syndata_settings = settings_section.syndata_settings
        self._blob_row = settings_section.blob_row
        self._blob_combo = settings_section.blob_combo
        self._tls_mod_row = settings_section.tls_mod_row
        self._tls_mod_combo = settings_section.tls_mod_combo
        self._autottl_delta_frame = settings_section.autottl_delta_frame
        self._autottl_delta_selector = settings_section.autottl_delta_selector
        self._autottl_min_frame = settings_section.autottl_min_frame
        self._autottl_min_selector = settings_section.autottl_min_selector
        self._autottl_max_frame = settings_section.autottl_max_frame
        self._autottl_max_selector = settings_section.autottl_max_selector
        self._tcp_flags_row = settings_section.tcp_flags_row
        self._tcp_flags_combo = settings_section.tcp_flags_combo
        self._reset_row_widget = settings_section.reset_row_widget
        self._create_preset_btn = settings_section.create_preset_btn
        self._rename_preset_btn = settings_section.rename_preset_btn
        self._reset_settings_btn = settings_section.reset_settings_btn

        self.layout.addWidget(self._settings_host)
        _log_z2_detail_metric("_build_content.settings_block", (_time.perf_counter() - _t_settings) * 1000)

        # Strategy controls stay visible even for disabled targets.
        _t_strategies = _time.perf_counter()
        strategies_section = build_strategies_section(
            page=self,
            tokens=tokens,
            settings_card_cls=SettingsCard,
            strong_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            search_line_edit_cls=SearchLineEdit,
            combo_cls=ComboBox,
            transparent_tool_button_cls=TransparentToolButton,
            segmented_widget_cls=SegmentedWidget,
            tree_cls=StrategyTree,
            set_tooltip_fn=set_tooltip,
        )
        self._strategies_block = strategies_section.block_widget
        self._strategies_card = strategies_section.card_widget
        self._strategies_header_widget = strategies_section.header_widget
        self._strategies_title_label = strategies_section.title_label
        self._strategies_summary_label = strategies_section.summary_label
        self._search_bar_widget = strategies_section.toolbar_widget
        self._search_input = strategies_section.search_input
        self._filter_combo = strategies_section.filter_combo
        self._sort_combo = strategies_section.sort_combo
        self._edit_args_btn = strategies_section.edit_args_btn
        self._phases_bar_widget = strategies_section.phases_bar_widget
        self._phase_tabbar = strategies_section.phase_tabbar
        self._phase_tab_index_by_key = strategies_section.phase_tab_index_by_key
        self._phase_tab_key_by_index = strategies_section.phase_tab_key_by_index
        self._strategies_tree = strategies_section.strategies_tree

        # Initialize dynamic visuals/tooltips (sort/filter buttons).
        self._apply_page_theme(force=True)
        self._update_technique_filter_ui()
        self._populate_sort_combo()

        self._args_editor_dirty = False
        self._update_strategies_summary()

        self.layout.addWidget(self._strategies_block, 1)
        _log_z2_detail_metric("_build_content.strategies_block", (_time.perf_counter() - _t_strategies) * 1000)
        _log_z2_detail_metric("_build_content.total", (_time.perf_counter() - _t_total) * 1000)

    def _update_selected_strategy_header(self, strategy_id: str) -> None:
        """Обновляет подзаголовок: показывает выбранную стратегию рядом с портами."""
        state = build_selected_strategy_header_state(
            strategy_id=strategy_id,
            tcp_phase_mode=bool(self._tcp_phase_mode),
            tcp_hide_fake_phase=bool(self._tcp_hide_fake_phase),
            tcp_phase_selected_ids=self._tcp_phase_selected_ids,
            strategies_data_by_id=self._strategies_data_by_id,
            custom_strategy_id=CUSTOM_STRATEGY_ID,
            fake_disabled_strategy_id=TCP_FAKE_DISABLED_STRATEGY_ID,
            phase_command_order=TCP_PHASE_COMMAND_ORDER,
        )

        apply_selected_strategy_header_state(
            self._subtitle_strategy,
            state,
            set_tooltip_fn=set_tooltip,
        )

    def _set_tree_selected_strategy(self, strategy_id: str) -> None:
        tree = self._strategies_tree
        if tree is None:
            return
        normalized_strategy_id = str(strategy_id or "none").strip() or "none"
        if normalized_strategy_id != "none":
            try:
                tree.set_selected_strategy(normalized_strategy_id)
                return
            except Exception:
                pass
        try:
            if tree.has_strategy("none"):
                tree.set_selected_strategy("none")
            else:
                tree.clearSelection()
        except Exception:
            pass

    def _set_tree_current_strategy(self, strategy_id: str) -> None:
        tree = self._strategies_tree
        if tree is None:
            return
        normalized_strategy_id = str(strategy_id or "none").strip() or "none"
        try:
            if normalized_strategy_id != "none" and tree.has_strategy(normalized_strategy_id):
                tree.set_selected_strategy(normalized_strategy_id)
                return
            if tree.has_strategy("none"):
                tree.set_selected_strategy("none")
            else:
                tree.clearSelection()
        except Exception:
            pass

    def _apply_phase_mode_policy(self, policy: StrategyDetailModePolicy) -> None:
        self._tcp_phase_mode = bool(policy.tcp_phase_mode)
        self._detail_mode_policy = policy
        try:
            if hasattr(self, "_filter_btn") and self._filter_btn is not None:
                self._filter_btn.setVisible(policy.show_filter_button)
        except Exception:
            pass
        try:
            if hasattr(self, "_phases_bar_widget") and self._phases_bar_widget is not None:
                self._phases_bar_widget.setVisible(policy.show_phases_bar)
        except Exception:
            pass

    def _force_toggle_off(self, toggle, details_widget) -> None:
        try:
            toggle.blockSignals(True)
            toggle.setChecked(False)
        except Exception:
            pass
        finally:
            try:
                toggle.blockSignals(False)
            except Exception:
                pass

        try:
            if details_widget is not None:
                details_widget.setVisible(False)
        except Exception:
            pass

    def _apply_target_mode_visibility(self, policy: StrategyDetailModePolicy) -> None:
        try:
            if getattr(self, "_filter_mode_frame", None) is not None:
                self._filter_mode_frame.setVisible(policy.show_filter_mode_frame)
        except Exception:
            pass

        try:
            if getattr(self, "_send_frame", None) is not None:
                self._send_frame.setVisible(policy.show_send_frame)
        except Exception:
            pass

        try:
            if getattr(self, "_syndata_frame", None) is not None:
                self._syndata_frame.setVisible(policy.show_syndata_frame)
        except Exception:
            pass

        try:
            if getattr(self, "_reset_row_widget", None) is not None:
                self._reset_row_widget.setVisible(policy.show_reset_row)
        except Exception:
            pass

        if policy.force_disable_send:
            self._force_toggle_off(getattr(self, "_send_toggle", None), getattr(self, "_send_settings", None))
        if policy.force_disable_syndata:
            self._force_toggle_off(getattr(self, "_syndata_toggle", None), getattr(self, "_syndata_settings", None))

    def _load_target_payload_sync(self, target_key: str | None = None, *, refresh: bool = False):
        key = str(target_key or self._target_key or "").strip().lower()
        if not key:
            return None
        try:
            payload = self._require_app_context().direct_ui_snapshot_service.load_target_detail_payload(
                "direct_zapret2",
                key,
                direct_mode_override=self._current_direct_mode(),
                refresh=refresh,
            )
        except Exception:
            return None
        if payload is not None and str(getattr(payload, "target_key", "") or "").strip().lower() == key:
            self._target_payload = payload
        return payload

    def _require_app_context(self):
        return require_page_app_context(
            self,
            parent=self.parent(),
            error_message="AppContext is required for Zapret2 strategy detail page",
        )

    def _get_direct_ui_snapshot_service(self):
        return self._require_app_context().direct_ui_snapshot_service

    def _current_direct_mode(self) -> str | None:
        return resolve_direct_mode_override(getattr(self, "direct_mode_override", None))

    def _get_direct_flow_coordinator(self):
        return self._require_app_context().direct_flow_coordinator

    def _read_target_raw_args_text(self, target_key: str) -> str:
        try:
            return self._direct_facade.get_target_raw_args_text(target_key) or ""
        except Exception:
            return ""

    def _write_target_raw_args_text(self, target_key: str, raw_text: str, *, save_and_sync: bool = True) -> bool:
        try:
            return bool(
                self._direct_facade.update_target_raw_args_text(
                    target_key,
                    raw_text,
                    save_and_sync=save_and_sync,
                )
            )
        except Exception:
            return False

    def _write_target_details_settings(self, target_key: str, payload: dict, *, save_and_sync: bool = True) -> None:
        self._direct_facade.update_target_details_settings(
            target_key,
            payload,
            save_and_sync=save_and_sync,
        )

    def _reset_target_settings(self, target_key: str) -> bool:
        try:
            return bool(self._direct_facade.reset_target_settings(target_key))
        except Exception:
            return False

    def _build_args_editor_open_plan(self):
        return build_args_editor_open_plan(self)

    def _create_preset_from_current(self, name: str):
        return create_preset_from_current(self, name)

    def _rename_current_preset(self, *, old_file_name: str, old_name: str, new_name: str):
        return rename_current_preset(self, old_file_name=old_file_name, old_name=old_name, new_name=new_name)

    def _request_target_payload(self, target_key: str, *, refresh: bool, reason: str) -> None:
        request_target_payload(self, target_key, refresh=refresh, reason=reason)

    def _on_target_payload_loaded(self, request_id: int, snapshot, token: int, *, reason: str) -> None:
        on_target_payload_loaded(self, request_id, snapshot, token, reason=reason)

    def _apply_target_payload(
        self,
        normalized_key: str,
        payload,
        *,
        reason: str,
        started_at: float | None = None,
    ) -> None:
        apply_target_payload(self, normalized_key, payload, reason=reason, started_at=started_at)

    def show_target(self, target_key: str):
        show_target(self, target_key)

    def refresh_from_preset_switch(self):
        refresh_from_preset_switch(self)

    def bind_ui_state_store(self, store: MainWindowStateStore) -> None:
        if self._ui_state_store is store:
            return

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass

        self._ui_state_store = store
        self._ui_state_unsubscribe = store.subscribe(
            self._on_ui_state_changed,
            fields={
                "active_preset_revision",
                "preset_content_revision",
                "preset_structure_revision",
                "mode_revision",
                "launch_running",
                "launch_phase",
            },
            emit_initial=False,
        )

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        if (
            ("launch_running" in changed_fields or "launch_phase" in changed_fields)
            and self._waiting_for_process_start
            and bool(state.launch_running)
            and str(state.launch_phase or "").strip().lower() == "running"
        ):
            log("StrategyDetailPage: launch state перешёл в running, показываем галочку", "DEBUG")
            self.show_success()
            return
        if "mode_revision" in changed_fields:
            self.reload_for_mode_change()
            return
        if "preset_structure_revision" in changed_fields:
            self.refresh_from_preset_switch()
            return
        if "active_preset_revision" in changed_fields:
            self.refresh_from_preset_switch()
            return
        if "preset_content_revision" in changed_fields:
            if self._preset_refresh_runtime.consume_suppressed():
                return
            self.refresh_from_preset_switch()

    def _apply_preset_refresh(self):
        apply_preset_refresh_now(self)

    def reload_for_mode_change(self) -> None:
        if not self.isVisible():
            self._preset_refresh_runtime.mark_pending()
            return
        self.refresh_from_preset_switch()

    def _scroll_to_current_strategy(self) -> None:
        """Прокручивает страницу к текущей стратегии (не меняя порядок списка)."""
        if not self._strategies_tree:
            return

        sid = self._current_strategy_id or "none"
        if sid == "none":
            try:
                bar = self.verticalScrollBar()
                bar.setValue(bar.minimum())
            except Exception:
                pass
            return

        rect = self._strategies_tree.get_strategy_item_rect(sid)
        if rect is None:
            return

        try:
            vp = self._strategies_tree.viewport()
            center = vp.mapTo(self.content, rect.center())
            # ymargin: немного контекста вокруг строки
            self.ensureVisible(center.x(), center.y(), 0, 64)
        except Exception:
            pass

    def _notify_preset_structure_changed(self) -> None:
        store = self._ui_state_store
        if store is None:
            return
        try:
            store.bump_preset_structure_revision()
        except Exception:
            pass

    def _clear_strategies(self):
        clear_strategies(self)

    def _is_dpi_running_now(self) -> bool:
        return is_dpi_running_now(self)

    def _load_strategies(self, policy: StrategyDetailModePolicy | None = None):
        load_strategies(self, policy=policy, info_bar_cls=InfoBar)

    def _add_strategy_row(self, strategy_id: str, name: str, args: list[str] | None = None) -> None:
        add_strategy_row(self, strategy_id, name, args)

    def _load_next_strategies_batch(self) -> None:
        load_next_strategies_batch(self)

    def _refresh_working_marks_for_target(self) -> None:
        refresh_working_marks_for_target(self)

    def _get_preview_strategy_data(self, strategy_id: str) -> dict:
        return get_preview_strategy_data(self, strategy_id)

    def _get_preview_rating(self, strategy_id: str, target_key: str):
        return get_preview_rating(self, strategy_id, target_key)

    def _toggle_preview_rating(self, strategy_id: str, rating: str, target_key: str):
        return toggle_preview_rating(self, strategy_id, rating, target_key)

    def _close_preview_dialog(self, force: bool = False):
        close_preview_dialog_runtime(self, force=force)

    def close_transient_overlays(self) -> None:
        close_transient_overlays(self)

    def _on_preview_closed(self) -> None:
        on_preview_closed(self)

    def _ensure_preview_dialog(self):
        return ensure_preview_dialog_runtime(self)

    def _show_preview_dialog(self, strategy_id: str, global_pos) -> None:
        show_preview_dialog_runtime(self, strategy_id, global_pos)

    def _on_tree_preview_requested(self, strategy_id: str, global_pos):
        on_tree_preview_requested(self, strategy_id, global_pos)

    def _on_tree_preview_pinned_requested(self, strategy_id: str, global_pos):
        on_tree_preview_pinned_requested(self, strategy_id, global_pos)

    def _on_tree_preview_hide_requested(self) -> None:
        on_tree_preview_hide_requested(self)

    def _on_tree_working_mark_requested(self, strategy_id: str, is_working):
        on_tree_working_mark_requested(self, strategy_id, is_working)

    def _apply_syndata_settings(self, settings: dict):
        """Applies persisted syndata settings to controls without re-saving."""
        data = dict(settings or {})
        try:
            self._syndata_toggle.blockSignals(True)
            self._blob_combo.blockSignals(True)
            self._tls_mod_combo.blockSignals(True)
            self._out_range_spin.blockSignals(True)
            self._out_range_expression_input.blockSignals(True)
            self._tcp_flags_combo.blockSignals(True)
            self._send_toggle.blockSignals(True)
            self._send_repeats_spin.blockSignals(True)
            self._send_ip_id_combo.blockSignals(True)
            self._send_badsum_check.blockSignals(True)

            self._syndata_toggle.setChecked(bool(data.get("enabled", False)))
            self._syndata_settings.setVisible(bool(data.get("enabled", False)))

            blob_value = str(data.get("blob", "none") or "none")
            blob_index = self._blob_combo.findText(blob_value)
            if blob_index >= 0:
                self._blob_combo.setCurrentIndex(blob_index)

            tls_mod_value = str(data.get("tls_mod", "none") or "none")
            tls_mod_index = self._tls_mod_combo.findText(tls_mod_value)
            if tls_mod_index >= 0:
                self._tls_mod_combo.setCurrentIndex(tls_mod_index)

            self._autottl_delta_selector.setValue(int(data.get("autottl_delta", -2)), block_signals=True)
            self._autottl_min_selector.setValue(int(data.get("autottl_min", 3)), block_signals=True)
            self._autottl_max_selector.setValue(int(data.get("autottl_max", 20)), block_signals=True)
            self._out_range_is_simple = bool(data.get("out_range_is_simple", True))
            self._out_range_expression = str(data.get("out_range_expression", "") or "").strip()
            self._out_range_spin.setValue(max(1, int(data.get("out_range", 8) or 8)))
            self._out_range_expression_input.setText(self._out_range_expression)

            self._out_range_mode = str(data.get("out_range_mode", "d") or "d").strip().lower() or "d"
            apply_out_range_ui_state(self)

            tcp_flags_value = str(data.get("tcp_flags_unset", "none") or "none")
            tcp_flags_index = self._tcp_flags_combo.findText(tcp_flags_value)
            if tcp_flags_index >= 0:
                self._tcp_flags_combo.setCurrentIndex(tcp_flags_index)

            self._send_toggle.setChecked(bool(data.get("send_enabled", False)))
            self._send_settings.setVisible(bool(data.get("send_enabled", False)))
            self._send_repeats_spin.setValue(int(data.get("send_repeats", 2)))
            self._send_ip_ttl_selector.setValue(int(data.get("send_ip_ttl", 0)), block_signals=True)
            self._send_ip6_ttl_selector.setValue(int(data.get("send_ip6_ttl", 0)), block_signals=True)

            send_ip_id = str(data.get("send_ip_id", "none") or "none")
            send_ip_id_index = self._send_ip_id_combo.findText(send_ip_id)
            if send_ip_id_index >= 0:
                self._send_ip_id_combo.setCurrentIndex(send_ip_id_index)

            self._send_badsum_check.setChecked(bool(data.get("send_badsum", False)))
        finally:
            try:
                self._syndata_toggle.blockSignals(False)
                self._blob_combo.blockSignals(False)
                self._tls_mod_combo.blockSignals(False)
                self._out_range_spin.blockSignals(False)
                self._out_range_expression_input.blockSignals(False)
                self._tcp_flags_combo.blockSignals(False)
                self._send_toggle.blockSignals(False)
                self._send_repeats_spin.blockSignals(False)
                self._send_ip_id_combo.blockSignals(False)
                self._send_badsum_check.blockSignals(False)
            except Exception:
                pass

    def _schedule_full_repopulate(self) -> None:
        """Compatibility helper for old sort modes; keep list state consistent."""
        if self._cleanup_in_progress:
            return
        try:
            QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._apply_sort())
            QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._apply_filters())
        except Exception:
            pass


    def get_syndata_settings(self) -> dict:
        """Возвращает текущие syndata настройки для использования в командной строке"""
        return {
            "enabled": self._syndata_toggle.isChecked(),
            "blob": self._blob_combo.currentText(),
            "tls_mod": self._tls_mod_combo.currentText(),
        }

    # ======================================================================
    # PRESET CREATE / RENAME
    # ======================================================================

    def _on_create_preset_clicked(self):
        on_create_preset_clicked(self, info_bar_cls=InfoBar, dialog_cls=PresetNameDialog)

    def _on_rename_preset_clicked(self):
        on_rename_preset_clicked(self, info_bar_cls=InfoBar, dialog_cls=PresetNameDialog)

    def _on_reset_settings_confirmed(self):
        on_reset_settings_confirmed(self)

    def _confirm_reset_settings_clicked(self) -> None:
        confirm_reset_settings_clicked(self, message_box_cls=MessageBox)

    def _on_row_clicked(self, strategy_id: str):
        """Обработчик клика по строке стратегии - выбор активной"""
        if self._tcp_phase_mode:
            self._on_tcp_phase_row_clicked(strategy_id)
            return

        plan = build_row_click_plan(
            strategy_id=strategy_id,
            prev_strategy_id=self._selected_strategy_id,
            has_target_key=bool(self._target_key),
        )

        if plan.remembered_last_enabled_strategy_id:
            self._last_enabled_strategy_id = plan.remembered_last_enabled_strategy_id

        self._selected_strategy_id = plan.selected_strategy_id
        self._set_tree_selected_strategy(plan.selected_strategy_id)
        self._update_selected_strategy_header(self._selected_strategy_id)

        if plan.should_hide_args_editor:
            self._hide_args_editor(clear_text=False)

        self._apply_loading_plan_action(plan.loading_state)

        self._refresh_args_editor_state()
        self._set_target_enabled_ui(plan.target_enabled)

        if plan.should_emit_strategy_selected and self._target_key:
            self._preset_refresh_runtime.set_suppressed(plan.suppress_next_preset_refresh)
            self.strategy_selected.emit(self._target_key, plan.selected_strategy_id)

    def _update_status_icon(self, active: bool):
        """Обновляет галочку статуса в заголовке"""
        plan = build_status_icon_plan(active=active)
        self._apply_loading_plan_action(plan.action)

    def _set_loading_indicator(self, *, loading: bool = False, success: bool = False, success_pixmap=None) -> None:
        if loading:
            try:
                self._success_icon.hide()
            except Exception:
                pass
            try:
                self._spinner.show()
            except Exception:
                pass
            try:
                self._spinner.start()
            except Exception:
                pass
            return

        try:
            self._spinner.stop()
        except Exception:
            pass
        try:
            self._spinner.hide()
        except Exception:
            pass

        if success:
            try:
                if success_pixmap is not None:
                    self._success_icon.setPixmap(success_pixmap)
            except Exception:
                pass
            try:
                self._success_icon.show()
            except Exception:
                pass
            return

        try:
            self._success_icon.hide()
        except Exception:
            pass

    def _apply_loading_plan_action(self, action: str) -> None:
        normalized_action = str(action or "").strip().lower()
        if normalized_action == "show":
            self.show_loading()
            return
        if normalized_action == "success":
            self.show_success()
            return
        if normalized_action in {"stop", "hide"}:
            self._stop_loading()
            try:
                self._success_icon.hide()
            except Exception:
                pass

    def show_loading(self):
        """Показывает анимированный спиннер загрузки"""
        self._set_loading_indicator(loading=True)
        self._waiting_for_process_start = True  # Ждём запуска DPI
        # В direct_zapret2 режимах "apply" часто не меняет состояние процесса (hot-reload),
        # поэтому даём быстрый таймаут, чтобы UI не зависал на спиннере.
        self._start_apply_feedback_timer()
    def _stop_loading(self):
        """Останавливает анимацию загрузки"""
        self._set_loading_indicator(loading=False, success=False)
        self._waiting_for_process_start = False  # Больше не ждём
        self._stop_apply_feedback_timer()

    def _start_apply_feedback_timer(self, timeout_ms: int = 1500):
        """Быстрый таймер, который завершает спиннер после apply/hot-reload."""
        if self._cleanup_in_progress:
            return
        self._stop_apply_feedback_timer()
        self._apply_feedback_timer = QTimer(self)
        self._apply_feedback_timer.setSingleShot(True)
        self._apply_feedback_timer.timeout.connect(self._on_apply_feedback_timeout)
        self._apply_feedback_timer.start(timeout_ms)

    def _stop_apply_feedback_timer(self):
        if self._apply_feedback_timer:
            self._apply_feedback_timer.stop()
            self._apply_feedback_timer = None

    def _on_apply_feedback_timeout(self):
        """
        В direct_zapret2 изменения часто применяются без смены процесса (winws2 остаётся запущен),
        поэтому ориентируемся на включенность target'а, а не на processStatusChanged.
        """
        if self._cleanup_in_progress:
            return
        plan = build_apply_feedback_timeout_plan(
            waiting_for_process_start=self._waiting_for_process_start,
            selected_strategy_id=self._selected_strategy_id,
        )
        self._apply_loading_plan_action(plan.action)

    def show_success(self):
        """Показывает зелёную галочку успеха"""
        self._stop_loading()
        self._set_loading_indicator(
            success=True,
            success_pixmap=get_cached_qta_pixmap('fa5s.check-circle', color='#4ade80', size=16),
        )

    def _on_args_changed(self, strategy_id: str, args: list):
        on_args_changed_runtime(self, strategy_id, args)

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._preset_refresh_runtime.mark_pending()
        self._target_payload_runtime.clear_pending_target()

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_unsubscribe = None
        self._ui_state_store = None

        self._stop_apply_feedback_timer()
        try:
            self._syndata_save_timer.stop()
        except Exception:
            pass

        try:
            self._strategies_load_runtime.reset(delete_later=True)
        except Exception:
            pass

        try:
            self._close_preview_dialog(force=True)
        except Exception:
            pass
        try:
            self._close_filter_combo_popup()
        except Exception:
            pass

        try:
            if self._host_window is not None:
                self._host_window.removeEventFilter(self)
        except Exception:
            pass
        self._host_window = None

    def _get_target_details(self, target_key: str | None = None):
        key = str(target_key or self._target_key or "").strip().lower()
        if not key:
            return None
        payload = getattr(self, "_target_payload", None)
        if payload is not None and str(getattr(payload, "target_key", "") or "") == key:
            return payload.details
        payload = self._load_target_payload_sync(key, refresh=False)
        if payload is None:
            return None
        return getattr(payload, "details", None)

    def _reload_current_target_payload(self):
        """Перечитывает payload только для текущего target, без полного списка."""
        key = str(self._target_key or "").strip().lower()
        return self._load_target_payload_sync(key, refresh=True)

    # ======================================================================
    # TCP MULTI-PHASE (direct_zapret2)
    # ======================================================================

    def _get_target_strategy_args_text(self) -> str:
        return get_target_strategy_args_text(self)

    def _get_strategy_args_text_by_id(self, strategy_id: str) -> str:
        return get_strategy_args_text_by_id(self, strategy_id)

    def _infer_strategy_id_from_args_exact(self, args_text: str) -> str:
        """
        Best-effort exact match against loaded strategies.

        Returns:
            - matching strategy_id if found
            - "custom" if args are non-empty but don't match a single known strategy
            - "none" if args are empty
        """
        return infer_strategy_id_from_args_exact(self, args_text)

    def _extract_desync_techniques_from_args(self, args_text: str) -> list[str]:
        return extract_desync_techniques_from_args(self, args_text)

    def _infer_tcp_phase_key_for_strategy_args(self, args_text: str) -> str | None:
        """
        Returns a single phase key if all desync lines belong to the same phase.
        Otherwise returns None (multi-phase/unknown).
        """
        return infer_tcp_phase_key_for_strategy_args(self, args_text)

    def _update_tcp_phase_chip_markers(self) -> None:
        update_tcp_phase_chip_markers_runtime(self)

    def _load_tcp_phase_state_from_preset(self) -> None:
        load_tcp_phase_state_from_preset_runtime(self)

    def _apply_tcp_phase_tabs_visibility(self) -> None:
        apply_tcp_phase_tabs_visibility_runtime(self)

    def _set_active_phase_chip(self, phase_key: str) -> None:
        set_active_phase_chip_runtime(self, phase_key)

    def _select_default_tcp_phase_tab(self) -> None:
        select_default_tcp_phase_tab_runtime(self)

    def _save_tcp_phase_state_to_preset(self, *, show_loading: bool = True) -> None:
        save_tcp_phase_state_to_preset(self, show_loading=show_loading)

    def _on_tcp_phase_row_clicked(self, strategy_id: str) -> None:
        on_tcp_phase_row_clicked(self, strategy_id)

    def _set_target_block_dimmed(self, widget: QWidget | None, dimmed: bool) -> None:
        set_target_block_dimmed(widget, dimmed=dimmed)

    def _set_target_enabled_ui(self, enabled: bool) -> None:
        """Keeps controls visible and dims blocks for disabled targets."""
        set_target_enabled_ui(
            enabled=enabled,
            toolbar_frame=getattr(self, "_toolbar_frame", None),
            strategies_block=getattr(self, "_strategies_block", None),
            layout=getattr(self, "layout", None),
            set_block_dimmed_fn=self._set_target_block_dimmed,
            refresh_scroll_range_fn=self._refresh_scroll_range,
        )

    def _on_favorite_toggled(self, strategy_id: str, is_favorite: bool) -> None:
        on_favorite_toggled(self, strategy_id, is_favorite)

    def _get_default_strategy(self) -> str:
        return get_default_strategy(self)

    def _on_filter_mode_changed(self, new_mode: str):
        """╨Ю╨▒╤А╨░╨▒╨╛╤В╤З╨╕╨║ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤А╨╡╨╢╨╕╨╝╨░ ╤Д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕"""
        if not self._target_key:
            return

        # Save via the direct facade (triggers DPI reload automatically)
        self._save_target_filter_mode(self._target_key, new_mode)
        self.filter_mode_changed.emit(self._target_key, new_mode)
        log(f"╨а╨╡╨╢╨╕╨╝ ╤Д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╨╕ ╨┤╨╗╤П {self._target_key}: {new_mode}", "INFO")

    def _save_target_filter_mode(self, target_key: str, mode: str):
        """╨б╨╛╤Е╤А╨░╨╜╤П╨╡╤В ╤А╨╡╨╢╨╕╨╝ ╤Д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╤З╨╡╤А╨╡╨╖ PresetManager"""
        self._preset_refresh_runtime.mark_suppressed()
        StrategyDetailPageController.save_target_filter_mode(self._direct_facade, target_key=target_key, mode=mode)

    def _load_target_filter_mode(self, target_key: str) -> str:
        """╨Ч╨░╨│╤А╤Г╨╢╨░╨╡╤В ╤А╨╡╨╢╨╕╨╝ ╤Д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╨╕╨╖ PresetManager"""
        payload = getattr(self, "_target_payload", None)
        return StrategyDetailPageController.load_target_filter_mode(self._direct_facade, payload=payload, target_key=target_key)

    def _save_target_sort(self, target_key: str, sort_order: str):
        """╨б╨╛╤Е╤А╨░╨╜╤П╨╡╤В ╨┐╨╛╤А╤П╨┤╨╛╨║ ╤Б╨╛╤А╤В╨╕╤А╨╛╨▓╨║╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╤З╨╡╤А╨╡╨╖ PresetManager"""
        # Sort order is UI-only parameter, doesn't affect DPI
        # But save_and_sync=True is needed to persist changes to disk
        # (hot-reload may trigger but sort_order has no effect on winws2)
        StrategyDetailPageController.save_target_sort(self._direct_facade, target_key=target_key, sort_order=sort_order)

    def _load_target_sort(self, target_key: str) -> str:
        """╨Ч╨░╨│╤А╤Г╨╢╨░╨╡╤В ╨┐╨╛╤А╤П╨┤╨╛╨║ ╤Б╨╛╤А╤В╨╕╤А╨╛╨▓╨║╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╨╕╨╖ PresetManager"""
        return StrategyDetailPageController.load_target_sort(self._direct_facade, target_key=target_key)

    # ======================================================================
    # TCP PHASE TAB PERSISTENCE (UI-only)
    # ======================================================================

    _REG_TCP_PHASE_TABS_BY_TARGET = "TcpPhaseTabByTarget"

    def _load_target_last_tcp_phase_tab(self, target_key: str) -> str | None:
        return load_target_last_tcp_phase_tab(self, target_key)

    def _save_target_last_tcp_phase_tab(self, target_key: str, phase_key: str) -> None:
        save_target_last_tcp_phase_tab(self, target_key, phase_key)

    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
    # OUT RANGE METHODS
    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР

    def _select_out_range_mode(self, mode: str):
        select_out_range_mode(self, mode)

    def _select_out_range_kind(self, kind: str):
        select_out_range_kind(self, kind)

    def _on_out_range_expression_changed(self, text: str):
        set_out_range_expression(self, text)

    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
    # SYNDATA SETTINGS METHODS
    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР

    def _on_send_toggled(self, checked: bool):
        on_send_toggled(self, checked)

    def _on_syndata_toggled(self, checked: bool):
        on_syndata_toggled(self, checked)

    def _schedule_syndata_settings_save(self, delay_ms: int = 180):
        schedule_syndata_settings_save(self, delay_ms=delay_ms)

    def _flush_syndata_settings_save(self):
        flush_syndata_settings_save(self)

    def _load_syndata_settings(self, target_key: str) -> dict:
        return load_syndata_settings(self, target_key)


    def _refresh_args_editor_state(self):
        refresh_args_editor_state_runtime(self)

    def _toggle_args_editor(self):
        toggle_args_editor_runtime(self)

    def _hide_args_editor(self, clear_text: bool = False):
        hide_args_editor_runtime(self, clear_text=clear_text)

    def _load_args_into_editor(self):
        """Стаб для обратной совместимости."""
        pass

    def _on_args_editor_changed(self):
        """Стаб для обратной совместимости."""
        pass

    def _apply_args_editor(self, raw: str = ""):
        apply_args_editor_runtime(self, raw=raw)

    def _on_search_changed(self, text: str):
        on_search_changed(self, text)

    def _on_filter_toggled(self, technique: str, active: bool):
        on_filter_toggled(self, technique, active)

    def _populate_sort_combo(self) -> None:
        populate_sort_combo_runtime(self)

    def _update_sort_button_ui(self) -> None:
        update_sort_button_ui_runtime(self)

    def _on_sort_combo_changed(self, index: int) -> None:
        on_sort_combo_changed(self, index)

    def _on_technique_filter_changed(self, index: int) -> None:
        on_technique_filter_changed(self, index)

    def _update_technique_filter_ui(self) -> None:
        update_technique_filter_ui_runtime(self)

    def _update_strategies_summary(self) -> None:
        update_strategies_summary_runtime(self)

    def _on_phase_tab_changed(self, route_key: str) -> None:
        on_phase_tab_changed(self, route_key)

    def _on_phase_pivot_item_clicked(self, key: str) -> None:
        on_phase_pivot_item_clicked(self, key)

    def _apply_filters(self):
        apply_filters_runtime(self)

    def _sync_tree_selection_to_active_phase(self) -> None:
        sync_tree_selection_to_active_phase_runtime(self)

    def _show_sort_menu(self):
        show_sort_menu_runtime(self)

    def _build_sort_icon(self, icon_color: str):
        return get_themed_qta_icon("fa5s.sort", color=icon_color)

    def _apply_sort(self):
        apply_sort_runtime(self)

    def _apply_language_to_page_widgets(self) -> None:
        if not getattr(self, "_content_built", False):
            return

        if getattr(self, "_parent_link", None) is not None:
            self._parent_link.setText(self._tr("page.z2_strategy_detail.back.strategies", "Стратегии DPI"))

        if getattr(self, "_title", None) is not None:
            current_title = ""
            try:
                current_title = self._title.text()
            except Exception:
                current_title = ""
            header_state = build_detail_header_text_state(
                target_info=getattr(self, "_target_info", None),
                target_key=str(getattr(self, "_target_key", "") or ""),
                tr=self._tr,
                ports_text_key="page.z2_strategy_detail.subtitle.ports",
                ports_text_default="порты: {ports}",
                empty_title=current_title,
                empty_detail=self._tr("page.z2_strategy_detail.header.category_fallback", "Target"),
            )
            apply_target_payload_header_state(
                self._title,
                getattr(self, "_subtitle", None),
                getattr(self, "_breadcrumb", None),
                title_text=header_state.title_text,
                subtitle_text=header_state.subtitle_text,
                detail_text=header_state.detail_text,
                control_text=self._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"),
                strategies_text=self._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"),
            )

        if getattr(self, "_filter_mode_frame", None) is not None:
            self._filter_mode_frame.set_title(
                self._tr("page.z2_strategy_detail.filter_mode.title", "Режим фильтрации")
            )
            self._filter_mode_frame.set_description(
                self._tr("page.z2_strategy_detail.filter_mode.description", "Hostlist - по доменам, IPset - по IP")
            )
        if getattr(self, "_filter_mode_selector", None) is not None:
            apply_filter_mode_selector_texts(
                self._filter_mode_selector,
                ipset_text=self._tr("page.z2_strategy_detail.filter.ipset", "IPset"),
                hostlist_text=self._tr("page.z2_strategy_detail.filter.hostlist", "Hostlist"),
            )

        if getattr(self, "_out_range_kind_label", None) is not None:
            self._out_range_kind_label.setText(self._tr("page.z2_strategy_detail.out_range.kind", "Тип:"))
        if getattr(self, "_out_range_kind_seg", None) is not None:
            try:
                self._out_range_kind_seg.setItemText(
                    "simple",
                    self._tr("page.z2_strategy_detail.out_range.kind.simple", "Простой"),
                )
                self._out_range_kind_seg.setItemText(
                    "expression",
                    self._tr("page.z2_strategy_detail.out_range.kind.expression", "Выражение"),
                )
            except Exception:
                pass
            set_tooltip(
                self._out_range_kind_seg,
                self._tr(
                    "page.z2_strategy_detail.out_range.kind.tooltip",
                    "Простой режим для a, x, n и d. Выражение нужно для форм вроде s1<d1, b1000- или <s34228.",
                ),
            )
        if getattr(self, "_out_range_mode_label", None) is not None:
            self._out_range_mode_label.setText(self._tr("page.z2_strategy_detail.out_range.mode", "Режим:"))
        if getattr(self, "_out_range_value_label", None) is not None:
            self._out_range_value_label.setText(self._tr("page.z2_strategy_detail.out_range.value", "Значение:"))
        if getattr(self, "_out_range_expression_label", None) is not None:
            self._out_range_expression_label.setText(self._tr("page.z2_strategy_detail.out_range.expression", "Выражение:"))
        if getattr(self, "_out_range_expression_input", None) is not None:
            self._out_range_expression_input.setPlaceholderText(
                self._tr(
                    "page.z2_strategy_detail.out_range.expression.placeholder",
                    "Например: s1<d1, b1000-, <s34228",
                )
            )
            set_tooltip(
                self._out_range_expression_input,
                self._tr(
                    "page.z2_strategy_detail.out_range.expression.tooltip",
                    "Введите только значение после --out-range=. Например: x, -d10, s1<d1, b1000- или <s34228.",
                ),
            )
        if getattr(self, "_out_range_frame", None) is not None:
            self._out_range_frame.set_title(self._tr("page.z2_strategy_detail.out_range.title", "Out Range"))
            self._out_range_frame.set_description(
                self._tr("page.z2_strategy_detail.out_range.description", "Ограничение исходящих пакетов")
            )
        if getattr(self, "_out_range_seg", None) is not None:
            set_tooltip(
                self._out_range_seg,
                self._tr(
                    "page.z2_strategy_detail.out_range.mode.tooltip",
                    "a = всегда, x = никогда, n = номер пакета, d = номер пакета с данными",
                ),
            )
        if getattr(self, "_out_range_spin", None) is not None:
            set_tooltip(
                self._out_range_spin,
                self._tr(
                    "page.z2_strategy_detail.out_range.value.tooltip",
                    "Для режимов n и d укажите число. Для a и x значение не используется.",
                ),
            )
        apply_out_range_ui_state(self)

        if getattr(self, "_search_input", None) is not None:
            self._search_input.setPlaceholderText(
                self._tr("page.z2_strategy_detail.search.placeholder", "Поиск по имени или args...")
            )

        if getattr(self, "_strategies_title_label", None) is not None:
            self._strategies_title_label.setText(
                self._tr("page.z2_strategy_detail.tree.title", "Все стратегии")
            )

        if getattr(self, "_sort_btn", None) is not None:
            self._update_sort_button_ui()

        if getattr(self, "_sort_combo", None) is not None:
            self._populate_sort_combo()

        if getattr(self, "_filter_combo", None) is not None:
            idx = self._filter_combo.currentIndex()
            refresh_strategy_filter_combo(
                self._filter_combo,
                self._tr,
                current_index=idx,
                technique_filters=STRATEGY_TECHNIQUE_FILTERS,
            )

        if getattr(self, "_edit_args_btn", None) is not None:
            set_tooltip(
                self._edit_args_btn,
                self._tr(
                    "page.z2_strategy_detail.args.tooltip",
                    "Аргументы стратегии для выбранного target'а",
                ),
            )
        self._update_strategies_summary()

        if getattr(self, "_send_toggle_row", None) is not None:
            self._send_toggle_row.set_texts(
                self._tr("page.z2_strategy_detail.send.toggle.title", "Send параметры"),
                self._tr("page.z2_strategy_detail.send.toggle.description", "Отправка копий пакетов"),
            )
        if getattr(self, "_send_repeats_row", None) is not None:
            self._send_repeats_row.set_texts(
                self._tr("page.z2_strategy_detail.send.repeats.title", "repeats"),
                self._tr("page.z2_strategy_detail.send.repeats.description", "Количество повторных отправок"),
            )
        if getattr(self, "_send_ip_ttl_frame", None) is not None:
            self._send_ip_ttl_frame.set_title(self._tr("page.z2_strategy_detail.send.ip_ttl.title", "ip_ttl"))
            self._send_ip_ttl_frame.set_description(
                self._tr("page.z2_strategy_detail.send.ip_ttl.description", "TTL для IPv4 отправляемых пакетов")
            )
        if getattr(self, "_send_ip6_ttl_frame", None) is not None:
            self._send_ip6_ttl_frame.set_title(self._tr("page.z2_strategy_detail.send.ip6_ttl.title", "ip6_ttl"))
            self._send_ip6_ttl_frame.set_description(
                self._tr("page.z2_strategy_detail.send.ip6_ttl.description", "TTL для IPv6 отправляемых пакетов")
            )
        if getattr(self, "_send_ip_id_row", None) is not None:
            self._send_ip_id_row.set_texts(
                self._tr("page.z2_strategy_detail.send.ip_id.title", "ip_id"),
                self._tr("page.z2_strategy_detail.send.ip_id.description", "Режим IP ID для отправляемых пакетов"),
            )
        if getattr(self, "_send_badsum_frame", None) is not None:
            self._send_badsum_frame.set_title(self._tr("page.z2_strategy_detail.send.badsum.title", "badsum"))
            self._send_badsum_frame.set_description(
                self._tr(
                    "page.z2_strategy_detail.send.badsum.description",
                    "Отправлять пакеты с неправильной контрольной суммой",
                )
            )

        if getattr(self, "_syndata_toggle_row", None) is not None:
            self._syndata_toggle_row.set_texts(
                self._tr("page.z2_strategy_detail.syndata.toggle.title", "Syndata параметры"),
                self._tr(
                    "page.z2_strategy_detail.syndata.toggle.description",
                    "Дополнительные параметры обхода DPI",
                ),
            )
        if getattr(self, "_blob_row", None) is not None:
            self._blob_row.set_texts(
                self._tr("page.z2_strategy_detail.syndata.blob.title", "blob"),
                self._tr("page.z2_strategy_detail.syndata.blob.description", "Полезная нагрузка пакета"),
            )
        if getattr(self, "_tls_mod_row", None) is not None:
            self._tls_mod_row.set_texts(
                self._tr("page.z2_strategy_detail.syndata.tls_mod.title", "tls_mod"),
                self._tr("page.z2_strategy_detail.syndata.tls_mod.description", "Модификация полезной нагрузки TLS"),
            )
        if getattr(self, "_autottl_delta_frame", None) is not None:
            self._autottl_delta_frame.set_title(
                self._tr("page.z2_strategy_detail.syndata.autottl_delta.title", "AutoTTL Delta")
            )
            self._autottl_delta_frame.set_description(
                self._tr(
                    "page.z2_strategy_detail.syndata.autottl_delta.description",
                    "Смещение от измеренного TTL (OFF = убрать ip_autottl)",
                )
            )
        if getattr(self, "_autottl_min_frame", None) is not None:
            self._autottl_min_frame.set_title(
                self._tr("page.z2_strategy_detail.syndata.autottl_min.title", "AutoTTL Min")
            )
            self._autottl_min_frame.set_description(
                self._tr("page.z2_strategy_detail.syndata.autottl_min.description", "Минимальный TTL")
            )
        if getattr(self, "_autottl_max_frame", None) is not None:
            self._autottl_max_frame.set_title(
                self._tr("page.z2_strategy_detail.syndata.autottl_max.title", "AutoTTL Max")
            )
            self._autottl_max_frame.set_description(
                self._tr("page.z2_strategy_detail.syndata.autottl_max.description", "Максимальный TTL")
            )
        if getattr(self, "_tcp_flags_row", None) is not None:
            self._tcp_flags_row.set_texts(
                self._tr("page.z2_strategy_detail.syndata.tcp_flags.title", "tcp_flags_unset"),
                self._tr("page.z2_strategy_detail.syndata.tcp_flags.description", "Сбросить TCP флаги"),
            )

        if getattr(self, "_create_preset_btn", None) is not None:
            self._create_preset_btn.setText(
                self._tr("page.z2_strategy_detail.button.create_preset", "Создать пресет")
            )
            set_tooltip(
                self._create_preset_btn,
                self._tr(
                    "page.z2_strategy_detail.button.create_preset.tooltip",
                    "Создать новый пресет на основе текущих настроек",
                ),
            )
        if getattr(self, "_rename_preset_btn", None) is not None:
            self._rename_preset_btn.setText(
                self._tr("page.z2_strategy_detail.button.rename_preset", "Переименовать")
            )
            set_tooltip(
                self._rename_preset_btn,
                self._tr(
                    "page.z2_strategy_detail.button.rename_preset.tooltip",
                    "Переименовать текущий активный пресет",
                ),
            )
        if getattr(self, "_reset_settings_btn", None) is not None:
            self._reset_settings_btn.setText(
                self._tr("page.z2_strategy_detail.button.reset_settings", "Сбросить настройки")
            )

        updater = getattr(self, "_update_header_labels", None)
        if callable(updater):
            try:
                updater()
            except Exception:
                pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        self._apply_language_to_page_widgets()
        self._update_selected_strategy_header(self._selected_strategy_id)
