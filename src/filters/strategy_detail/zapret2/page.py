# direct_preset/ui/zapret2/strategy_detail/page.py
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

from direct_preset.runtime import DirectTargetDetailSnapshotWorker
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
        QLineEdit as LineEdit, QTextEdit as TextEdit, QPushButton,
    )
    BodyLabel = QLabel
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    SubtitleLabel = QLabel
    TitleLabel = QLabel
    ToolButton = QPushButton
    TransparentToolButton = QPushButton
    SwitchButton = QPushButton
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
from filters.strategy_detail.args_preview_dialog import ArgsPreviewDialog
from blobs.service import get_blobs_info
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon
from log.log import log

from filters.strategy_detail.zapret2.controller import StrategyDetailPageController
from filters.strategy_detail.zapret2.apply import (
    apply_args_editor_state,
    apply_current_strategy_tree_state,
    apply_filter_mode_selector_state,
    apply_loading_plan_action,
    apply_loading_indicator_state,
    apply_tree_working_state,
    apply_working_mark_updates,
    apply_selected_strategy_header_state,
    apply_sort_button_state,
    apply_sort_combo_state,
    apply_strategies_summary_label,
    apply_technique_filter_combo_state,
    apply_target_payload_filter_reset,
    apply_target_payload_header_state,
    apply_target_payload_shell_state,
    apply_tree_selected_strategy_state,
)
from filters.strategy_detail.shared import (
    build_detail_subtitle_widgets,
    build_strategies_tree_widget,
    run_args_editor_dialog,
)
from filters.strategy_detail.shared_filter_mode import apply_filter_mode_selector_texts
from filters.strategy_detail.zapret2.common import (
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
from filters.strategy_detail.zapret2.mode_policy import StrategyDetailModePolicy
from direct_preset.ui.zapret2.preset_dialogs import PresetNameDialog
from filters.strategy_detail.zapret2.args_editor import (
    hide_args_editor_state,
    open_args_editor_dialog,
    refresh_args_editor_state,
)
from filters.strategy_detail.zapret2.preset_workflow import (
    present_preset_action_result,
    present_preset_exception,
    prompt_preset_name,
)
from filters.strategy_detail.zapret2.filtering_ui import (
    apply_filter_plan_to_tree,
    apply_sort_plan_to_tree,
    populate_sort_combo,
    update_sort_button_ui,
    update_strategies_summary,
    update_technique_filter_ui,
)
from filters.strategy_detail.zapret2.tcp_phase_ui import (
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
from filters.strategy_detail.zapret2.sort_menu import show_sort_menu
from filters.strategy_detail.zapret2.target_ui import (
    set_target_block_dimmed,
    set_target_enabled_ui,
)
from filters.strategy_detail.zapret2.target_payload_workflow import (
    apply_preset_refresh,
    handle_loaded_payload,
    start_target_payload_request,
)
from filters.strategy_detail.zapret2.target_payload_apply import (
    apply_payload_reuse_plan,
    finalize_target_payload_apply_ui,
    prepare_target_payload_apply_ui,
)
from filters.strategy_detail.zapret2.preview import (
    close_preview_dialog,
    ensure_preview_dialog_instance,
    show_preview_dialog_for_strategy,
)
from filters.strategy_detail.zapret2.helpers import (
    TTLButtonSelector,
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
        self._target_payload_runtime = StrategyDetailPageController.create_target_payload_runtime()
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
        self._strategies_load_runtime = StrategyDetailPageController.create_strategies_load_runtime()
        self._loaded_strategy_type = None
        self._loaded_strategy_set = None
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
            on_dpi_reload_needed=self._on_dpi_reload_needed,
        )
        self._feedback_store = app_context.strategy_feedback_store
        self._favorite_strategy_ids = set()
        self._preview_dialog = None
        self._preview_pinned = False
        self._host_window = None
        self._strategies_data_by_id = {}
        self._content_built = False
        self._last_theme_overrides_key = None
        self._last_parent_link_icon_color = None
        self._last_edit_args_icon_color = None
        self._preset_refresh_runtime = StrategyDetailPageController.create_preset_refresh_runtime()
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

    def _after_content_built(self) -> None:
        self._content_built = True

        # Close hover/pinned preview when the main window hides/deactivates (e.g. tray).
        QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._install_host_window_event_filter())

        self._apply_pending_target_request_if_ready()

    def _install_host_window_event_filter(self) -> None:
        if self._cleanup_in_progress:
            return
        try:
            w = self.window()
        except Exception:
            w = None
        if not w or w is self._host_window:
            return
        self._host_window = w
        try:
            w.installEventFilter(self)
        except Exception:
            pass

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        try:
            if obj is self._host_window and event is not None:
                et = event.type()
                if et in (
                    QEvent.Type.Hide,
                    QEvent.Type.Close,
                    QEvent.Type.WindowDeactivate,
                    QEvent.Type.WindowStateChange,
                ):
                    # Don't close if focus went to the preview dialog itself.
                    if et == QEvent.Type.WindowDeactivate and self._preview_dialog is not None:
                        try:
                            from PyQt6.QtWidgets import QApplication as _QApp
                            active = _QApp.activeWindow()
                            if active is not None and active is self._preview_dialog:
                                return super().eventFilter(obj, event)
                        except Exception:
                            pass
                    self._close_preview_dialog(force=True)
                    self._close_filter_combo_popup()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _close_filter_combo_popup(self) -> None:
        """Close the technique filter ComboBox dropdown if it is open."""
        try:
            combo = getattr(self, "_filter_combo", None)
            if combo is not None and hasattr(combo, "_closeComboMenu"):
                combo._closeComboMenu()
        except Exception:
            pass

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        try:
            tokens = tokens or get_theme_tokens()
        except Exception:
            return

        key = (
            str(tokens.theme_name),
            str(tokens.fg),
            str(tokens.fg_muted),
            str(tokens.fg_faint),
            str(tokens.accent_hex),
        )
        if not force and key == self._last_theme_overrides_key:
            return
        self._last_theme_overrides_key = key

        try:
            detail_text_color = tokens.fg_muted if tokens.is_light else tokens.fg
            if getattr(self, "_subtitle_strategy", None) is not None:
                subtitle_style = f"background: transparent; padding-left: 10px; color: {detail_text_color};"
                if self._subtitle_strategy.styleSheet() != subtitle_style:
                    self._subtitle_strategy.setStyleSheet(subtitle_style)
        except Exception:
            pass

        try:
            if getattr(self, "_parent_link", None) is not None:
                parent_color = str(tokens.fg_muted)
                if parent_color != self._last_parent_link_icon_color:
                    self._parent_link.setIcon(get_themed_qta_icon('fa5s.chevron-left', color=parent_color))
                    self._last_parent_link_icon_color = parent_color
        except Exception:
            pass

        try:
            if not _HAS_FLUENT and getattr(self, "_edit_args_btn", None) is not None:
                edit_color = str(tokens.fg_faint)
                if edit_color != self._last_edit_args_icon_color:
                    self._edit_args_btn.setIcon(get_themed_qta_icon('fa5s.edit', color=edit_color))
                    self._last_edit_args_icon_color = edit_color
        except Exception:
            pass

        try:
            self._update_sort_button_ui()
        except Exception:
            pass

    def hideEvent(self, event):  # noqa: N802 (Qt override)
        # Ensure floating preview/tool windows do not keep intercepting mouse events
        # after navigation away from this page.
        try:
            self._save_scroll_state()
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
            self._stop_loading()
        except Exception:
            pass
        self._preset_refresh_runtime.mark_pending()
        try:
            self._strategies_load_runtime.reset(delete_later=False)
        except Exception:
            pass
        return super().hideEvent(event)

    def on_page_activated(self) -> None:
        self._apply_pending_target_request_if_ready()
        if self._preset_refresh_runtime.consume_pending():
            self.refresh_from_preset_switch()

    def _refresh_scroll_range(self) -> None:
        # Ensure QScrollArea recomputes range after dynamic content growth.
        try:
            if self.layout is not None:
                self.layout.invalidate()
                self.layout.activate()
        except Exception:
            pass

    def _apply_pending_target_request_if_ready(self) -> None:
        if self._cleanup_in_progress:
            return
        pending_target_key = self._target_payload_runtime.take_pending_target_if_ready(
            is_visible=self.isVisible(),
            content_built=bool(getattr(self, "_content_built", False)),
        )
        if not pending_target_key:
            return

        try:
            self._request_target_payload(pending_target_key, refresh=False, reason="show_target")
        except Exception:
            self._target_payload_runtime.restore_pending_target(pending_target_key)
        try:
            if hasattr(self, "content") and self.content is not None:
                self.content.updateGeometry()
                self.content.adjustSize()
        except Exception:
            pass
        try:
            self.updateGeometry()
            self.viewport().update()
        except Exception:
            pass

    def _save_scroll_state(self, target_key: str | None = None) -> None:
        key = str(target_key or self._target_key or "").strip()
        if not key:
            return

        try:
            bar = self.verticalScrollBar()
            self._page_scroll_by_target[key] = int(bar.value())
        except Exception:
            pass

        try:
            if self._strategies_tree:
                tree_bar = self._strategies_tree.verticalScrollBar()
                self._tree_scroll_by_target[key] = int(tree_bar.value())
        except Exception:
            pass

    def _restore_scroll_state(self, target_key: str | None = None, defer: bool = False) -> None:
        key = str(target_key or self._target_key or "").strip()
        if not key:
            return

        def _apply() -> None:
            if self._cleanup_in_progress:
                return
            try:
                page_bar = self.verticalScrollBar()
                saved_page = self._page_scroll_by_target.get(key)
                if saved_page is None:
                    page_bar.setValue(page_bar.minimum())
                else:
                    page_bar.setValue(max(page_bar.minimum(), min(int(saved_page), page_bar.maximum())))
            except Exception:
                pass

            try:
                if not self._strategies_tree:
                    return
                tree_bar = self._strategies_tree.verticalScrollBar()
                saved_tree = self._tree_scroll_by_target.get(key)
                if saved_tree is None:
                    return
                tree_bar.setValue(max(tree_bar.minimum(), min(int(saved_tree), tree_bar.maximum())))
            except Exception:
                pass

        if defer:
            QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and _apply())
            QTimer.singleShot(40, lambda: (not self._cleanup_in_progress) and _apply())
        else:
            _apply()

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

        # Хедер с breadcrumb-навигацией в стиле Windows 11 Settings
        header = QFrame()
        header.setFrameShape(QFrame.Shape.NoFrame)
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 16)
        header_layout.setSpacing(4)

        # Breadcrumb navigation: Управление › Стратегии DPI › [Target]
        self._breadcrumb = None
        try:
            from qfluentwidgets import BreadcrumbBar as _BreadcrumbBar
            self._breadcrumb = _BreadcrumbBar(self)
            self._breadcrumb.blockSignals(True)
            self._breadcrumb.addItem("control", self._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"))
            self._breadcrumb.addItem("strategies", self._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"))
            self._breadcrumb.addItem("detail", self._tr("page.z2_strategy_detail.header.category_fallback", "Target"))
            self._breadcrumb.blockSignals(False)
            self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
            header_layout.addWidget(self._breadcrumb)
        except Exception:
            # Fallback: original back button
            back_row = QHBoxLayout()
            back_row.setContentsMargins(0, 0, 0, 0)
            back_row.setSpacing(4)
            self._parent_link = TransparentPushButton(parent=self)
            self._parent_link.setText(self._tr("page.z2_strategy_detail.back.strategies", "Стратегии DPI"))
            self._parent_link.setIcon(get_themed_qta_icon('fa5s.chevron-left', color=tokens.fg_muted))
            self._parent_link.setIconSize(QSize(12, 12))
            self._parent_link.clicked.connect(self.back_clicked.emit)
            back_row.addWidget(self._parent_link)
            back_row.addStretch()
            header_layout.addLayout(back_row)

        # Current page title
        self._title = TitleLabel(self._tr("page.z2_strategy_detail.header.select_category", "Выберите target"))
        header_layout.addWidget(self._title)

        subtitle_widgets = build_detail_subtitle_widgets(
            parent=self,
            body_label_cls=BodyLabel,
            spinner_cls=IndeterminateProgressRing,
            pixmap_label_cls=PixmapLabel,
            subtitle_strategy_label_cls=ElidedLabel,
            detail_text_color=detail_text_color,
        )
        self._spinner = subtitle_widgets.spinner
        self._success_icon = subtitle_widgets.success_icon
        self._subtitle = subtitle_widgets.subtitle_label
        self._subtitle_strategy = subtitle_widgets.subtitle_strategy_label
        header_layout.addWidget(subtitle_widgets.container_widget)

        self.layout.addWidget(header)
        _log_z2_detail_metric("_build_content.header", (_time.perf_counter() - _t_header) * 1000)

        # ═══════════════════════════════════════════════════════════════
        # ВКЛЮЧЕНИЕ КАТЕГОРИИ + НАСТРОЙКИ
        # ═══════════════════════════════════════════════════════════════
        _t_settings = _time.perf_counter()
        self._settings_host = QWidget()
        self._settings_host.setVisible(False)
        settings_host_layout = QVBoxLayout(self._settings_host)
        settings_host_layout.setContentsMargins(0, 0, 0, 0)
        settings_host_layout.setSpacing(6)

        # ═══════════════════════════════════════════════════════════════
        # ТУЛБАР НАСТРОЕК КАТЕГОРИИ (фоновой блок)
        # ═══════════════════════════════════════════════════════════════
        self._toolbar_frame = QFrame()
        self._toolbar_frame.setVisible(False)
        # Убираем background: transparent; border: none; чтобы фон был как у карточек,
        # или оставляем его контейнером, а внутри будут SettingsCard
        toolbar_layout = QVBoxLayout(self._toolbar_frame)
        toolbar_layout.setContentsMargins(0, 4, 0, 4)
        toolbar_layout.setSpacing(12)

        # ═══════════════════════════════════════════════════════════════
        # REGULAR SETTINGS
        # ═══════════════════════════════════════════════════════════════
        self._general_card = SettingsCard()

        # Режим фильтрации row
        self._filter_mode_frame = SettingsRow(
            "fa5s.filter",
            self._tr("page.z2_strategy_detail.filter_mode.title", "Режим фильтрации"),
            self._tr("page.z2_strategy_detail.filter_mode.description", "Hostlist - по доменам, IPset - по IP"),
        )
        self._filter_mode_selector = SwitchButton(parent=self)
        apply_filter_mode_selector_texts(
            self._filter_mode_selector,
            ipset_text=self._tr("page.z2_strategy_detail.filter.ipset", "IPset"),
            hostlist_text=self._tr("page.z2_strategy_detail.filter.hostlist", "Hostlist"),
        )
        self._filter_mode_selector.checkedChanged.connect(
            lambda checked: self._on_filter_mode_changed("ipset" if checked else "hostlist")
        )
        self._filter_mode_frame.set_control(self._filter_mode_selector)
        self._general_card.add_widget(self._filter_mode_frame)
        self._filter_mode_frame.setVisible(False)

        # OUT RANGE
        self._out_range_frame = SettingsRow(
            "fa5s.sliders-h",
            self._tr("page.z2_strategy_detail.out_range.title", "Out Range"),
            self._tr("page.z2_strategy_detail.out_range.description", "Ограничение исходящих пакетов"),
        )
        self._out_range_mode_label = BodyLabel(self._tr("page.z2_strategy_detail.out_range.mode", "Режим:"))
        self._out_range_frame.control_container.addWidget(self._out_range_mode_label)

        self._out_range_seg = SegmentedWidget()
        self._out_range_seg.addItem("n", "n", lambda: self._select_out_range_mode("n"))
        self._out_range_seg.addItem("d", "d", lambda: self._select_out_range_mode("d"))
        set_tooltip(
            self._out_range_seg,
            self._tr(
                "page.z2_strategy_detail.out_range.mode.tooltip",
                "n = количество пакетов с самого первого, d = отсчитывать ТОЛЬКО количество пакетов с данными",
            ),
        )
        self._out_range_mode = "d"
        self._out_range_seg.setCurrentItem("d")
        self._out_range_frame.control_container.addWidget(self._out_range_seg)

        self._out_range_value_label = BodyLabel(self._tr("page.z2_strategy_detail.out_range.value", "Значение:"))
        self._out_range_frame.control_container.addWidget(self._out_range_value_label)

        self._out_range_spin = SpinBox()
        self._out_range_spin.setRange(1, 999)
        self._out_range_spin.setValue(8)
        self._out_range_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_tooltip(
            self._out_range_spin,
            self._tr(
                "page.z2_strategy_detail.out_range.value.tooltip",
                "--out-range: ограничение количества исходящих пакетов (n) или задержки (d)",
            ),
        )
        self._out_range_spin.valueChanged.connect(self._schedule_syndata_settings_save)
        self._out_range_frame.control_container.addWidget(self._out_range_spin)

        self._general_card.add_widget(self._out_range_frame)
        toolbar_layout.addWidget(self._general_card)

        # ═══════════════════════════════════════════════════════════════
        # SEND SETTINGS (collapsible)
        # ═══════════════════════════════════════════════════════════════
        if SettingCardGroup is not None and _HAS_FLUENT:
            self._send_frame = SettingCardGroup(
                self._tr("page.z2_strategy_detail.send.toggle.title", "Send параметры"),
                self.content,
            )
            _prepare_compact_setting_group(self._send_frame)
        else:
            self._send_frame = SettingsCard()
        self._send_frame.setVisible(False)

        self._send_toggle_row = Win11ToggleRow(
            "fa5s.paper-plane",
            self._tr("page.z2_strategy_detail.send.toggle.title", "Send параметры"),
            self._tr("page.z2_strategy_detail.send.toggle.description", "Отправка копий пакетов"),
        )
        self._send_toggle = self._send_toggle_row.toggle
        self._send_toggle_row.toggled.connect(self._on_send_toggled)
        if hasattr(self._send_frame, "addSettingCard"):
            self._send_frame.addSettingCard(self._send_toggle_row)
        else:
            self._send_frame.add_widget(self._send_toggle_row)

        # Settings panel (shown when enabled)
        self._send_settings = QWidget()
        self._send_settings.setVisible(False)
        send_settings_layout = QVBoxLayout(self._send_settings)
        send_settings_layout.setContentsMargins(12, 0, 0, 0)
        send_settings_layout.setSpacing(0)

        # send_repeats row
        self._send_repeats_row = Win11NumberRow(
            "fa5s.redo",
            self._tr("page.z2_strategy_detail.send.repeats.title", "repeats"),
            self._tr("page.z2_strategy_detail.send.repeats.description", "Количество повторных отправок"),
            min_val=0,
            max_val=10,
            default_val=2,
        )
        self._send_repeats_spin = self._send_repeats_row.spinbox
        self._send_repeats_row.valueChanged.connect(self._schedule_syndata_settings_save)
        send_settings_layout.addWidget(self._send_repeats_row)

        # send_ip_ttl row
        self._send_ip_ttl_frame = SettingsRow(
            "fa5s.stopwatch",
            self._tr("page.z2_strategy_detail.send.ip_ttl.title", "ip_ttl"),
            self._tr("page.z2_strategy_detail.send.ip_ttl.description", "TTL для IPv4 отправляемых пакетов"),
        )
        self._send_ip_ttl_selector = TTLButtonSelector(
            values=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            labels=["off", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
        )
        self._send_ip_ttl_selector.value_changed.connect(self._schedule_syndata_settings_save)
        self._send_ip_ttl_frame.set_control(self._send_ip_ttl_selector)
        send_settings_layout.addWidget(self._send_ip_ttl_frame)

        # send_ip6_ttl row
        self._send_ip6_ttl_frame = SettingsRow(
            "fa5s.stopwatch",
            self._tr("page.z2_strategy_detail.send.ip6_ttl.title", "ip6_ttl"),
            self._tr("page.z2_strategy_detail.send.ip6_ttl.description", "TTL для IPv6 отправляемых пакетов"),
        )
        self._send_ip6_ttl_selector = TTLButtonSelector(
            values=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            labels=["off", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
        )
        self._send_ip6_ttl_selector.value_changed.connect(self._schedule_syndata_settings_save)
        self._send_ip6_ttl_frame.set_control(self._send_ip6_ttl_selector)
        send_settings_layout.addWidget(self._send_ip6_ttl_frame)

        # send_ip_id row
        self._send_ip_id_row = Win11ComboRow(
            "fa5s.fingerprint",
            self._tr("page.z2_strategy_detail.send.ip_id.title", "ip_id"),
            self._tr("page.z2_strategy_detail.send.ip_id.description", "Режим IP ID для отправляемых пакетов"),
            items=[("none", None), ("seq", None), ("rnd", None), ("zero", None)],
        )
        self._send_ip_id_combo = self._send_ip_id_row.combo
        self._send_ip_id_row.currentTextChanged.connect(self._schedule_syndata_settings_save)
        send_settings_layout.addWidget(self._send_ip_id_row)

        # send_badsum row
        self._send_badsum_frame = SettingsRow(
            "fa5s.exclamation-triangle",
            self._tr("page.z2_strategy_detail.send.badsum.title", "badsum"),
            self._tr(
                "page.z2_strategy_detail.send.badsum.description",
                "Отправлять пакеты с неправильной контрольной суммой",
            ),
        )
        self._send_badsum_check = SwitchButton()
        self._send_badsum_check.checkedChanged.connect(self._schedule_syndata_settings_save)
        self._send_badsum_frame.set_control(self._send_badsum_check)
        send_settings_layout.addWidget(self._send_badsum_frame)

        if hasattr(self._send_frame, "addSettingCard"):
            self._send_frame.addSettingCard(self._send_settings)
        else:
            self._send_frame.add_widget(self._send_settings)
        toolbar_layout.addWidget(self._send_frame)

        # ═══════════════════════════════════════════════════════════════
        # SYNDATA SETTINGS (collapsible)
        # ═══════════════════════════════════════════════════════════════
        if SettingCardGroup is not None and _HAS_FLUENT:
            self._syndata_frame = SettingCardGroup(
                self._tr("page.z2_strategy_detail.syndata.toggle.title", "Syndata параметры"),
                self.content,
            )
            _prepare_compact_setting_group(self._syndata_frame)
        else:
            self._syndata_frame = SettingsCard()
        self._syndata_frame.setVisible(False)

        self._syndata_toggle_row = Win11ToggleRow(
            "fa5s.cog",
            self._tr("page.z2_strategy_detail.syndata.toggle.title", "Syndata параметры"),
            self._tr(
                "page.z2_strategy_detail.syndata.toggle.description",
                "Дополнительные параметры обхода DPI",
            ),
        )
        self._syndata_toggle = self._syndata_toggle_row.toggle
        self._syndata_toggle_row.toggled.connect(self._on_syndata_toggled)
        if hasattr(self._syndata_frame, "addSettingCard"):
            self._syndata_frame.addSettingCard(self._syndata_toggle_row)
        else:
            self._syndata_frame.add_widget(self._syndata_toggle_row)

        # Settings panel (shown when enabled)
        self._syndata_settings = QWidget()
        self._syndata_settings.setVisible(False)
        settings_layout = QVBoxLayout(self._syndata_settings)
        settings_layout.setContentsMargins(12, 0, 0, 0)
        settings_layout.setSpacing(0)

        # Blob selector row
        blob_names = ["none"]
        try:
            all_blobs = get_blobs_info()
            blob_names = ["none"] + sorted(all_blobs.keys())
        except Exception:
            blob_names = ["none", "tls_google", "tls7"]
        blob_items = [(n, None) for n in blob_names]

        self._blob_row = Win11ComboRow(
            "fa5s.file-code",
            self._tr("page.z2_strategy_detail.syndata.blob.title", "blob"),
            self._tr("page.z2_strategy_detail.syndata.blob.description", "Полезная нагрузка пакета"),
            items=blob_items,
        )
        self._blob_combo = self._blob_row.combo
        self._blob_row.currentTextChanged.connect(self._schedule_syndata_settings_save)
        settings_layout.addWidget(self._blob_row)

        # tls_mod selector row
        self._tls_mod_row = Win11ComboRow(
            "fa5s.shield-alt",
            self._tr("page.z2_strategy_detail.syndata.tls_mod.title", "tls_mod"),
            self._tr("page.z2_strategy_detail.syndata.tls_mod.description", "Модификация полезной нагрузки TLS"),
            items=[("none", None), ("rnd", None), ("rndsni", None), ("sni=google.com", None)],
        )
        self._tls_mod_combo = self._tls_mod_row.combo
        self._tls_mod_row.currentTextChanged.connect(self._schedule_syndata_settings_save)
        settings_layout.addWidget(self._tls_mod_row)

        # ═══════════════════════════════════════════════════════════════
        # AUTOTTL SETTINGS (три строки с кнопками)
        # ═══════════════════════════════════════════════════════════════
        # --- Delta row ---
        self._autottl_delta_frame = SettingsRow(
            "fa5s.clock",
            self._tr("page.z2_strategy_detail.syndata.autottl_delta.title", "AutoTTL Delta"),
            self._tr(
                "page.z2_strategy_detail.syndata.autottl_delta.description",
                "Смещение от измеренного TTL (OFF = убрать ip_autottl)",
            ),
        )
        self._autottl_delta_selector = TTLButtonSelector(
            values=[0, -1, -2, -3, -4, -5, -6, -7, -8, -9],
            labels=["OFF", "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9"]
        )
        self._autottl_delta_selector.value_changed.connect(self._schedule_syndata_settings_save)
        self._autottl_delta_frame.set_control(self._autottl_delta_selector)
        settings_layout.addWidget(self._autottl_delta_frame)

        # --- Min row ---
        self._autottl_min_frame = SettingsRow(
            "fa5s.angle-down",
            self._tr("page.z2_strategy_detail.syndata.autottl_min.title", "AutoTTL Min"),
            self._tr("page.z2_strategy_detail.syndata.autottl_min.description", "Минимальный TTL"),
        )
        self._autottl_min_selector = TTLButtonSelector(
            values=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            labels=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        )
        self._autottl_min_selector.value_changed.connect(self._schedule_syndata_settings_save)
        self._autottl_min_frame.set_control(self._autottl_min_selector)
        settings_layout.addWidget(self._autottl_min_frame)

        # --- Max row ---
        self._autottl_max_frame = SettingsRow(
            "fa5s.angle-up",
            self._tr("page.z2_strategy_detail.syndata.autottl_max.title", "AutoTTL Max"),
            self._tr("page.z2_strategy_detail.syndata.autottl_max.description", "Максимальный TTL"),
        )
        self._autottl_max_selector = TTLButtonSelector(
            values=[15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25],
            labels=["15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25"]
        )
        self._autottl_max_selector.value_changed.connect(self._schedule_syndata_settings_save)
        self._autottl_max_frame.set_control(self._autottl_max_selector)
        settings_layout.addWidget(self._autottl_max_frame)

        # TCP flags row
        self._tcp_flags_row = Win11ComboRow(
            "fa5s.flag",
            self._tr("page.z2_strategy_detail.syndata.tcp_flags.title", "tcp_flags_unset"),
            self._tr("page.z2_strategy_detail.syndata.tcp_flags.description", "Сбросить TCP флаги"),
            items=[("none", None), ("ack", None), ("psh", None), ("ack,psh", None)],
        )
        self._tcp_flags_combo = self._tcp_flags_row.combo
        self._tcp_flags_row.currentTextChanged.connect(self._schedule_syndata_settings_save)
        settings_layout.addWidget(self._tcp_flags_row)

        if hasattr(self._syndata_frame, "addSettingCard"):
            self._syndata_frame.addSettingCard(self._syndata_settings)
        else:
            self._syndata_frame.add_widget(self._syndata_settings)
        toolbar_layout.addWidget(self._syndata_frame)

        # ═══════════════════════════════════════════════════════════════
        # PRESET ACTIONS + RESET SETTINGS BUTTON
        # ═══════════════════════════════════════════════════════════════
        self._reset_row_widget = QWidget()
        reset_row = QHBoxLayout(self._reset_row_widget)
        reset_row.setContentsMargins(0, 8, 0, 0)
        reset_row.setSpacing(8)

        self._create_preset_btn = ActionButton(
            self._tr("page.z2_strategy_detail.button.create_preset", "Создать пресет"),
            "fa5s.plus",
        )
        set_tooltip(
            self._create_preset_btn,
            self._tr(
                "page.z2_strategy_detail.button.create_preset.tooltip",
                "Создать новый пресет на основе текущих настроек",
            ),
        )
        self._create_preset_btn.clicked.connect(self._on_create_preset_clicked)
        reset_row.addWidget(self._create_preset_btn)

        self._rename_preset_btn = ActionButton(
            self._tr("page.z2_strategy_detail.button.rename_preset", "Переименовать"),
            "fa5s.pen",
        )
        set_tooltip(
            self._rename_preset_btn,
            self._tr(
                "page.z2_strategy_detail.button.rename_preset.tooltip",
                "Переименовать текущий активный пресет",
            ),
        )
        self._rename_preset_btn.clicked.connect(self._on_rename_preset_clicked)
        reset_row.addWidget(self._rename_preset_btn)

        reset_row.addStretch()

        self._reset_settings_btn = ActionButton(
            self._tr("page.z2_strategy_detail.button.reset_settings", "Сбросить настройки"),
            "fa5s.undo",
        )
        self._reset_settings_btn.clicked.connect(self._confirm_reset_settings_clicked)
        reset_row.addWidget(self._reset_settings_btn)
        self._reset_row_widget.setVisible(False)

        toolbar_layout.addWidget(self._reset_row_widget)

        settings_host_layout.addWidget(self._toolbar_frame)
        self.layout.addWidget(self._settings_host)
        _log_z2_detail_metric("_build_content.settings_block", (_time.perf_counter() - _t_settings) * 1000)

        # Strategy controls stay visible even for disabled targets.
        _t_strategies = _time.perf_counter()
        strategy_block_widgets = build_strategy_block_shell(settings_card_cls=SettingsCard)
        self._strategies_block = strategy_block_widgets.block_widget
        self._strategies_card = strategy_block_widgets.card_widget

        header_widgets = build_strategy_header_widgets(
            title_text=self._tr("page.z2_strategy_detail.tree.title", "Все стратегии"),
            strong_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
        )
        self._strategies_header_widget = header_widgets.header_widget
        self._strategies_title_label = header_widgets.title_label
        self._strategies_summary_label = header_widgets.summary_label
        self._strategies_card.add_widget(self._strategies_header_widget)

        # Поиск, фильтрация и сортировка
        toolbar_widgets = build_strategy_toolbar_widgets(
            parent=self,
            tr=self._tr,
            tokens=tokens,
            search_line_edit_cls=SearchLineEdit,
            combo_cls=ComboBox,
            transparent_tool_button_cls=TransparentToolButton,
            set_tooltip=set_tooltip,
            build_filter_combo_fn=build_strategy_filter_combo,
            technique_filters=STRATEGY_TECHNIQUE_FILTERS,
            on_search_changed=self._on_search_changed,
            on_filter_changed=self._on_technique_filter_changed,
            on_sort_changed=self._on_sort_combo_changed,
            on_edit_args_clicked=self._toggle_args_editor,
        )
        self._search_bar_widget = toolbar_widgets.toolbar_widget
        self._search_input = toolbar_widgets.search_input
        self._filter_combo = toolbar_widgets.filter_combo
        self._sort_combo = toolbar_widgets.sort_combo
        self._edit_args_btn = toolbar_widgets.edit_args_btn

        # Initialize dynamic visuals/tooltips (sort/filter buttons).
        self._apply_page_theme(force=True)
        self._update_technique_filter_ui()
        self._populate_sort_combo()

        self._strategies_card.add_widget(self._search_bar_widget)

        self._args_editor_dirty = False

        # TCP multi-phase "tabs" (shown only for tcp categories in direct_zapret2)
        phase_widgets = build_tcp_phase_bar_widgets(
            parent=self,
            segmented_widget_cls=SegmentedWidget,
            on_click=self._on_phase_pivot_item_clicked,
            on_changed=self._on_phase_tab_changed,
            phase_tabs=TCP_PHASE_TAB_ORDER,
        )
        self._phases_bar_widget = phase_widgets.container_widget
        self._phase_tabbar = phase_widgets.tabbar
        self._phase_tab_index_by_key = phase_widgets.index_by_key
        self._phase_tab_key_by_index = phase_widgets.key_by_index
        self._strategies_card.add_widget(self._phases_bar_widget)

        # Лёгкий список стратегий: item-based, без сотен QWidget в layout
        self._strategies_tree = build_strategies_tree_widget(
            parent=self,
            tree_cls=StrategyTree,
            on_row_clicked=self._on_row_clicked,
            on_favorite_toggled=self._on_favorite_toggled,
            on_working_mark_requested=self._on_tree_working_mark_requested,
            on_preview_requested=self._on_tree_preview_requested,
            on_preview_pinned_requested=self._on_tree_preview_pinned_requested,
            on_preview_hide_requested=self._on_tree_preview_hide_requested,
        )
        self._strategies_card.add_widget(self._strategies_tree)
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

    def _prepare_target_payload_request(self, target_key: str) -> None:
        normalized_key = str(target_key or "").strip().lower()
        self._target_key = normalized_key
        self._stop_loading()
        self.show_loading()
        self._success_icon.hide()
        self._target_payload = None
        self._target_info = None
        try:
            self._settings_host.setVisible(False)
        except Exception:
            pass
        try:
            self._toolbar_frame.setVisible(False)
        except Exception:
            pass
        try:
            self._strategies_block.setVisible(False)
        except Exception:
            pass
        try:
            self._title.setText(self._tr("page.z2_strategy_detail.header.select_category", "Выберите target"))
            self._subtitle.setText("")
        except Exception:
            pass
        try:
            self._update_selected_strategy_header("none")
        except Exception:
            pass

    def _load_target_payload_sync(self, target_key: str | None = None, *, refresh: bool = False):
        key = str(target_key or self._target_key or "").strip().lower()
        if not key:
            return None
        try:
            payload = self._require_app_context().direct_ui_snapshot_service.load_target_detail_payload(
                "direct_zapret2",
                key,
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
        return StrategyDetailPageController.build_args_editor_open_plan(
            self._direct_facade,
            payload=getattr(self, "_target_payload", None),
            target_key=self._target_key,
            selected_strategy_id=self._selected_strategy_id,
        )

    def _create_preset_from_current(self, name: str):
        return StrategyDetailPageController.create_preset(self._direct_facade, name=name)

    def _rename_current_preset(self, *, old_file_name: str, old_name: str, new_name: str):
        return StrategyDetailPageController.rename_preset(
            self._direct_facade,
            old_file_name=old_file_name,
            old_name=old_name,
            new_name=new_name,
        )

    def _request_target_payload(self, target_key: str, *, refresh: bool, reason: str) -> None:
        request = start_target_payload_request(
            target_key=target_key,
            reason=reason,
            refresh=refresh,
            current_request_id=self._target_payload_runtime.current_request_id(),
            build_request_plan_fn=StrategyDetailPageController.build_target_payload_request_plan,
            issue_page_load_token_fn=self.issue_page_load_token,
            prepare_request_fn=self._prepare_target_payload_request,
            now_fn=_time.perf_counter,
            worker_cls=DirectTargetDetailSnapshotWorker,
            parent=self,
            on_loaded_callback=self._on_target_payload_loaded,
        )
        if request is None:
            return

        request_id, started_at, worker = request
        self._target_payload_runtime.register_request(
            request_id=request_id,
            started_at=started_at,
            worker=worker,
        )
        worker.start()

    def _on_target_payload_loaded(self, request_id: int, snapshot, token: int, *, reason: str) -> None:
        handle_loaded_payload(
            request_id=request_id,
            snapshot=snapshot,
            token=token,
            reason=reason,
            current_request_id=self._target_payload_runtime.current_request_id(),
            fallback_target_key=self._target_key,
            token_is_current_fn=self.is_page_load_token_current,
            build_loaded_plan_fn=StrategyDetailPageController.build_payload_loaded_plan,
            stop_loading_fn=self._stop_loading,
            hide_success_icon_fn=lambda: self._success_icon.hide(),
            log_fn=log,
            apply_payload_fn=self._apply_target_payload,
            started_at=self._target_payload_runtime.request_started_at,
        )

    def _apply_target_payload(
        self,
        normalized_key: str,
        payload,
        *,
        reason: str,
        started_at: float | None = None,
    ) -> None:
        _t_total = started_at if started_at is not None else _time.perf_counter()
        log(f"StrategyDetailPage.show_target: {normalized_key}", "DEBUG")
        self._target_key = normalized_key
        self._target_payload = payload
        target_info = payload.target_item
        apply_plan = StrategyDetailPageController.build_target_payload_apply_plan(
            payload=payload,
            has_strategy_rows=bool(self._strategies_tree and self._strategies_tree.has_rows()),
            loaded_strategy_type=self._loaded_strategy_type,
            loaded_strategy_set=self._loaded_strategy_set,
            loaded_tcp_phase_mode=self._loaded_tcp_phase_mode,
            tr=self._tr,
        )
        policy = apply_plan.policy
        self._target_info = target_info
        self._current_strategy_id = apply_plan.current_strategy_id
        self._selected_strategy_id = apply_plan.selected_strategy_id
        self._favorite_strategy_ids = prepare_target_payload_apply_ui(
            normalized_key=normalized_key,
            feedback_store=self._feedback_store,
            close_preview_fn=self._close_preview_dialog,
            settings_host=self._settings_host,
            toolbar_frame=self._toolbar_frame,
            title_label=self._title,
            subtitle_label=self._subtitle,
            breadcrumb=self._breadcrumb,
            apply_plan=apply_plan,
            detail_text=target_info.full_name,
            control_text=self._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"),
            strategies_text=self._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"),
            apply_shell_state_fn=apply_target_payload_shell_state,
            apply_header_state_fn=apply_target_payload_header_state,
        )
        self._update_selected_strategy_header(self._selected_strategy_id)

        self._apply_phase_mode_policy(policy)
        reuse_list = apply_plan.should_reuse_list

        apply_payload_reuse_plan(
            reuse_list=reuse_list,
            clear_strategies_fn=self._clear_strategies,
            load_strategies_fn=self._load_strategies,
            policy=policy,
            strategies_tree=self._strategies_tree,
            favorite_ids=self._favorite_strategy_ids,
            refresh_working_marks_fn=self._refresh_working_marks_for_target,
            current_strategy_id=self._current_strategy_id,
            apply_current_strategy_tree_state_fn=apply_current_strategy_tree_state,
            restore_scroll_state_fn=self._restore_scroll_state,
            normalized_key=normalized_key,
        )

        is_enabled = apply_plan.target_enabled
        self._update_status_icon(is_enabled)

        if self._tcp_phase_mode:
            self._load_tcp_phase_state_from_preset()
            self._apply_tcp_phase_tabs_visibility()
            preferred = None
            try:
                preferred = (self._last_active_phase_key_by_target or {}).get(normalized_key)
            except Exception:
                preferred = None
            if not preferred:
                preferred = self._load_target_last_tcp_phase_tab(normalized_key)
                if preferred:
                    try:
                        self._last_active_phase_key_by_target[normalized_key] = preferred
                    except Exception:
                        pass
            if preferred:
                self._set_active_phase_chip(preferred)
            else:
                self._select_default_tcp_phase_tab()

        finalize_target_payload_apply_ui(
            policy=policy,
            normalized_key=normalized_key,
            load_target_filter_mode_fn=self._load_target_filter_mode,
            filter_mode_selector=self._filter_mode_selector,
            apply_filter_mode_selector_state_fn=apply_filter_mode_selector_state,
            apply_target_mode_visibility_fn=self._apply_target_mode_visibility,
            apply_target_payload_filter_reset_fn=apply_target_payload_filter_reset,
            search_input=self._search_input,
            active_filters=self._active_filters,
            load_target_sort_fn=self._load_target_sort,
            set_sort_mode_fn=lambda mode: setattr(self, "_sort_mode", mode),
            update_technique_filter_ui_fn=self._update_technique_filter_ui,
            apply_sort_fn=self._apply_sort,
            apply_filters_fn=self._apply_filters,
            load_syndata_settings_fn=self._load_syndata_settings,
            apply_syndata_settings_fn=self._apply_syndata_settings,
            refresh_args_editor_state_fn=self._refresh_args_editor_state,
            set_target_enabled_ui_fn=self._set_target_enabled_ui,
            target_enabled=is_enabled,
            stop_loading_fn=self._stop_loading,
            hide_success_icon_fn=lambda: self._success_icon.hide(),
            log_metric_fn=lambda marker, started_at, extra: _log_z2_detail_metric(
                marker,
                (_time.perf_counter() - started_at) * 1000,
                extra=f"{extra}, reuse_list={'yes' if reuse_list else 'no'}",
            ),
            started_at=_t_total,
            reason=reason,
            tcp_phase_mode=bool(self._tcp_phase_mode),
        )

        log(f"StrategyDetailPage: показан target {self._target_key}, sort_mode={self._sort_mode}", "DEBUG")

    def show_target(self, target_key: str):
        """Открывает detail page для target из текущего source preset."""
        normalized_target_key = str(target_key or "").strip().lower()
        if not normalized_target_key:
            return

        prev_key = self._target_payload_runtime.current_or_pending_target_key(self._target_key)
        try:
            pending_key = str(self._pending_syndata_target_key or "").strip()
        except Exception:
            pending_key = ""
        if pending_key and pending_key != normalized_target_key:
            self._flush_syndata_settings_save()
        if prev_key:
            self._save_scroll_state(prev_key)

        # Не форсируем sync build тяжёлого detail-shell во время навигации.
        # Если страница ещё не собрана или пока скрыта, просто запоминаем target
        # и запрашиваем payload уже в обычном activation lifecycle.
        if not (self.isVisible() and getattr(self, "_content_built", False)):
            self._target_payload_runtime.remember_pending_target(normalized_target_key)
            return

        self._target_payload_runtime.clear_pending_target()
        self._request_target_payload(normalized_target_key, refresh=False, reason="show_target")

    def refresh_from_preset_switch(self):
        """
        Асинхронно перечитывает активный пресет и обновляет текущий target (если открыт).
        Вызывается из MainWindow после активации пресета.
        """
        if self._cleanup_in_progress:
            return
        if not self.isVisible():
            self._preset_refresh_runtime.mark_pending()
            return
        try:
            self._preset_refresh_runtime.clear_pending()
            QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._apply_preset_refresh())
        except Exception:
            try:
                self._apply_preset_refresh()
            except Exception:
                pass

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
        if self._cleanup_in_progress:
            return
        apply_preset_refresh(
            is_visible=self.isVisible(),
            target_key=self._target_key,
            build_preset_refresh_plan_fn=StrategyDetailPageController.build_preset_refresh_plan,
            mark_pending_fn=self._preset_refresh_runtime.mark_pending,
            request_payload_fn=self._request_target_payload,
        )

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
        """Очищает список стратегий"""
        # Останавливаем ленивую загрузку если она идёт
        self._strategies_load_runtime.reset(delete_later=True)

        if self._strategies_tree:
            self._strategies_tree.clear_strategies()
        self._strategies_data_by_id = {}
        self._loaded_strategy_type = None
        self._loaded_strategy_set = None
        self._loaded_tcp_phase_mode = False
        self._default_strategy_order = []
        self._strategies_loaded_fully = False
        self._update_strategies_summary()

    def _is_dpi_running_now(self) -> bool:
        """Смотрит на канонический runtime-state вместо локальных догадок."""
        app_runtime_state = getattr(self.parent_app, "app_runtime_state", None)
        if app_runtime_state is None:
            return False
        try:
            return bool(app_runtime_state.is_launch_running())
        except Exception:
            return False

    def _load_strategies(self, policy: StrategyDetailModePolicy | None = None):
        """Загружает стратегии для текущего target'а."""
        if self._cleanup_in_progress:
            return
        _t_total = _time.perf_counter()
        try:
            payload = self._target_payload or self._load_target_payload_sync(self._target_key, refresh=False)
            if payload is not None:
                self._target_payload = payload
                target_info = payload.target_item or self._target_info
            else:
                target_info = self._target_info
            if target_info:
                log(f"StrategyDetailPage: target {self._target_key}, strategy_type={target_info.strategy_type}", "DEBUG")
            else:
                log(f"StrategyDetailPage: target {self._target_key} не найден в target metadata service!", "ERROR")
                return

            retry_count = int(getattr(self, "_retry_count", 0) or 0)
            plan = StrategyDetailPageController.build_strategies_load_plan(
                target_info=target_info,
                payload=payload,
                policy=policy,
                retry_count=retry_count,
                launch_running=self._is_dpi_running_now(),
                is_visible=self.isVisible(),
                custom_strategy_id=CUSTOM_STRATEGY_ID,
                tr=self._tr,
            )
            self._detail_mode_policy = plan.resolved_policy

            log(
                f"StrategyDetailPage: загружено {len(plan.strategies_data_by_id)} стратегий для {self._target_key}",
                "DEBUG",
            )

            self._strategies_data_by_id = dict(plan.strategies_data_by_id or {})
            self._default_strategy_order = list(plan.default_strategy_order)
            self._loaded_strategy_type = plan.loaded_strategy_type
            self._loaded_strategy_set = plan.loaded_strategy_set
            self._loaded_tcp_phase_mode = plan.loaded_tcp_phase_mode

            if plan.is_empty:
                try:
                    self._strategies_tree.clear_strategies()
                except Exception:
                    pass
                self._update_strategies_summary()
                log(f"StrategyDetailPage: список стратегий пуст для {self._target_key}", "INFO")
                self._stop_loading()
                self._retry_count = plan.next_retry_count

                if plan.should_schedule_retry:
                    QTimer.singleShot(1000, lambda: (not self._cleanup_in_progress) and self._load_strategies())
                elif plan.should_suppress_warning:
                    log(
                        f"StrategyDetailPage: suppress 'no strategies' warning while DPI is stopped ({self._target_key})",
                        "DEBUG",
                    )
                elif plan.should_show_warning and InfoBar:
                    InfoBar.warning(
                        title=plan.warning_title,
                        content=plan.warning_content,
                        parent=self.window(),
                    )
                return

            self._retry_count = plan.next_retry_count
            self._strategies_load_runtime.set_pending_items(list(plan.pending_items))
            self._strategies_loaded_fully = False

            # Запускаем пакетную загрузку
            self._strategies_load_runtime.bump_generation()
            timer = self._strategies_load_runtime.ensure_timer(
                parent=self,
                timeout_callback=self._load_next_strategies_batch,
            )
            timer.start(5) # Быстрая подгрузка батчами
            _log_z2_detail_metric(
                "_load_strategies.total",
                (_time.perf_counter() - _t_total) * 1000,
                extra=f"target={self._target_key}, strategies={len(plan.strategies_data_by_id)}, tcp_phase={'yes' if plan.loaded_tcp_phase_mode else 'no'}",
            )
            
        except Exception as e:
            log(f"StrategyDetailPage.error loading strategies: {e}", "ERROR")
            self._stop_loading()

    def _add_strategy_row(self, strategy_id: str, name: str, args: list[str] | None = None) -> None:
        if not self._strategies_tree:
            return

        args_list = [str(a).strip() for a in (args or []) if str(a).strip()]
        is_favorite = (strategy_id != "none") and (strategy_id in self._favorite_strategy_ids)
        is_working = None
        if self._target_key and strategy_id not in ("none", CUSTOM_STRATEGY_ID):
            try:
                is_working = self._feedback_store.get_mark(self._target_key, strategy_id)
            except Exception:
                is_working = None

        try:
            self._strategies_tree.add_strategy(
                StrategyTreeRow(
                    strategy_id=strategy_id,
                    name=name,
                    args=args_list,
                    is_favorite=is_favorite,
                    is_working=is_working,
                )
            )
        except Exception as e:
            log(f"Strategy row add failed for {strategy_id}: {e}", "DEBUG")

    def _load_next_strategies_batch(self) -> None:
        """Lazily appends strategies to the tree in small UI-friendly chunks."""
        if not self._strategies_tree:
            return

        runtime = self._strategies_load_runtime
        total = runtime.total_items()
        start = runtime.start_index()
        initial_plan = StrategyDetailPageController.build_batch_update_plan(
            total=total,
            start=start,
            end=start,
            search_active=False,
            has_active_filters=bool(self._active_filters),
            tcp_phase_mode=bool(self._tcp_phase_mode),
        )
        if initial_plan.is_complete:
            if initial_plan.should_stop_timer:
                runtime.stop_timer(delete_later=False)
            if initial_plan.should_mark_loaded_fully:
                self._strategies_loaded_fully = True
            return

        chunk_size = 32
        end = min(start + chunk_size, total)
        _t_batch = _time.perf_counter()

        try:
            self._strategies_tree.begin_bulk_update()
            for i in range(start, end):
                item = runtime.item_at(i)
                strategy_id = str(getattr(item, "strategy_id", "") or "").strip()
                if not strategy_id:
                    continue
                name = str(getattr(item, "name", "") or strategy_id).strip() or strategy_id
                args_list = StrategyDetailPageController.extract_pending_item_args(
                    strategy_id=strategy_id,
                    strategy_data=self._strategies_data_by_id.get(strategy_id, {}),
                    pending_item=item,
                )
                self._add_strategy_row(strategy_id, name, args_list)
        finally:
            try:
                self._strategies_tree.end_bulk_update()
            except Exception:
                pass

        runtime.advance_to(end)
        try:
            _log_z2_detail_metric(
                "_load_next_strategies_batch",
                (_time.perf_counter() - _t_batch) * 1000,
                extra=f"target={self._target_key}, rows={end - start}, progress={end}/{total}",
            )
        except Exception:
            pass

        try:
            search_active = bool(self._search_input and self._search_input.text().strip())
        except Exception:
            search_active = False
        plan = StrategyDetailPageController.build_batch_update_plan(
            total=total,
            start=start,
            end=end,
            search_active=search_active,
            has_active_filters=bool(self._active_filters),
            tcp_phase_mode=bool(self._tcp_phase_mode),
        )
        if plan.should_apply_filters:
            self._apply_filters()
        elif plan.should_update_summary:
            self._update_strategies_summary()

        if not plan.is_complete:
            return

        if plan.should_stop_timer:
            runtime.stop_timer(delete_later=False)

        if plan.should_mark_loaded_fully:
            self._strategies_loaded_fully = True

        completion_plan = StrategyDetailPageController.build_tree_completion_plan(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            current_strategy_id=self._current_strategy_id,
            has_current_strategy=bool(self._strategies_tree.has_strategy(self._current_strategy_id)),
            has_none_strategy=bool(self._strategies_tree.has_strategy("none")),
        )
        if completion_plan.should_refresh_working_marks:
            self._refresh_working_marks_for_target()
        if completion_plan.should_apply_sort:
            self._apply_sort()

        if completion_plan.should_sync_tcp_phase_selection:
            self._sync_tree_selection_to_active_phase()
        else:
            if completion_plan.should_select_current_strategy:
                self._strategies_tree.set_selected_strategy(completion_plan.selected_strategy_id)
            elif completion_plan.should_select_none_fallback:
                self._strategies_tree.set_selected_strategy("none")

        if completion_plan.should_refresh_scroll_range:
            self._refresh_scroll_range()
        if completion_plan.should_update_summary:
            self._update_strategies_summary()
        if completion_plan.should_restore_scroll_state:
            self._restore_scroll_state(self._target_key, defer=True)

    def _refresh_working_marks_for_target(self) -> None:
        if not (self._target_key and self._strategies_tree):
            return
        plan = StrategyDetailPageController.build_working_marks_plan(
            target_key=self._target_key,
            strategy_ids=list(self._strategies_tree.get_strategy_ids() or []),
            custom_strategy_id=CUSTOM_STRATEGY_ID,
            mark_getter=lambda strategy_id: self._feedback_store.get_mark(self._target_key, strategy_id),
        )
        apply_working_mark_updates(
            self._strategies_tree,
            plan.updates,
        )

    def _get_preview_strategy_data(self, strategy_id: str) -> dict:
        plan = StrategyDetailPageController.build_preview_strategy_data(
            strategy_id=strategy_id,
            strategy_data=self._strategies_data_by_id.get(strategy_id, {}),
        )
        return dict(plan.data or {})

    def _get_preview_rating(self, strategy_id: str, target_key: str):
        return StrategyDetailPageController.get_preview_rating(
            self._feedback_store,
            strategy_id=strategy_id,
            target_key=target_key,
        )

    def _toggle_preview_rating(self, strategy_id: str, rating: str, target_key: str):
        result = StrategyDetailPageController.toggle_preview_rating(
            self._feedback_store,
            strategy_id=strategy_id,
            rating=rating,
            target_key=target_key,
        )
        apply_tree_working_state(
            self._strategies_tree,
            strategy_id=strategy_id,
            state=result.resulting_mark_state,
            should_update=result.should_update_tree_state,
        )
        return result.resulting_rating

    def _close_preview_dialog(self, force: bool = False):
        self._preview_dialog, self._preview_pinned = close_preview_dialog(
            self._preview_dialog,
            preview_pinned=self._preview_pinned,
            force=force,
        )

    def close_transient_overlays(self) -> None:
        try:
            self._close_preview_dialog(force=True)
        except Exception:
            pass
        try:
            self._close_filter_combo_popup()
        except Exception:
            pass

    def _on_preview_closed(self) -> None:
        self._preview_dialog = None
        self._preview_pinned = False

    def _ensure_preview_dialog(self):
        parent_win = self._host_window or self.window() or self
        self._preview_dialog = ensure_preview_dialog_instance(
            self._preview_dialog,
            parent_win=parent_win,
            on_closed=self._on_preview_closed,
            dialog_cls=ArgsPreviewDialog,
        )
        return self._preview_dialog

    def _show_preview_dialog(self, strategy_id: str, global_pos) -> None:
        if not (self._target_key and strategy_id and strategy_id != "none"):
            return

        data = self._get_preview_strategy_data(strategy_id)

        try:
            dlg = self._ensure_preview_dialog()
            if dlg is None:
                return

            show_preview_dialog_for_strategy(
                dlg,
                target_key=self._target_key,
                strategy_id=strategy_id,
                global_pos=global_pos,
                strategy_data=data,
                rating_getter=self._get_preview_rating,
                rating_toggler=self._toggle_preview_rating,
            )
        except Exception as e:
            log(f"Preview dialog failed: {e}", "DEBUG")

    def _on_tree_preview_requested(self, strategy_id: str, global_pos):
        pass  # Hover preview is intentionally disabled.

    def _on_tree_preview_pinned_requested(self, strategy_id: str, global_pos):
        self._show_preview_dialog(strategy_id, global_pos)

    def _on_tree_preview_hide_requested(self) -> None:
        pass  # No hover preview instance to hide.

    def _on_tree_working_mark_requested(self, strategy_id: str, is_working):
        result = StrategyDetailPageController.save_strategy_mark(
            self._feedback_store,
            strategy_id=strategy_id,
            is_working=is_working,
            target_key=self._target_key,
        )
        apply_tree_working_state(
            self._strategies_tree,
            strategy_id=strategy_id,
            state=result.resulting_mark_state,
            should_update=result.should_update_tree_state,
        )
        if result.should_emit_signal and self._target_key:
            self.strategy_marked.emit(self._target_key, strategy_id, is_working)

    def _apply_syndata_settings(self, settings: dict):
        """Applies persisted syndata settings to controls without re-saving."""
        data = dict(settings or {})
        try:
            self._syndata_toggle.blockSignals(True)
            self._blob_combo.blockSignals(True)
            self._tls_mod_combo.blockSignals(True)
            self._out_range_spin.blockSignals(True)
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
            self._out_range_spin.setValue(max(1, int(data.get("out_range", 8) or 8)))

            self._out_range_mode = str(data.get("out_range_mode", "d") or "d")
            try:
                self._out_range_seg.setCurrentItem(self._out_range_mode)
            except Exception:
                pass

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
        """Открывает WinUI-диалог создания нового пресета."""
        name = prompt_preset_name(
            dialog_cls=PresetNameDialog,
            mode="create",
            parent=self.window(),
            language=self._ui_language,
        )
        if not name:
            return
        try:
            result = self._create_preset_from_current(name)
            present_preset_action_result(
                result,
                info_bar=InfoBar,
                parent=self.window(),
                log_fn=log,
                on_structure_changed=self._notify_preset_structure_changed,
            )
        except Exception as e:
            present_preset_exception(
                action_error_message="Ошибка создания пресета",
                exception=e,
                info_bar=InfoBar,
                parent=self.window(),
                error_title=self._tr("common.error.title", "Ошибка"),
                log_fn=log,
            )

    def _on_rename_preset_clicked(self):
        """Открывает WinUI-диалог переименования текущего активного пресета."""
        try:
            coordinator = self._require_app_context().direct_flow_coordinator
            old_file_name = (
                coordinator.get_selected_source_file_name("direct_zapret2") or ""
            ).strip()

            selected_manifest = coordinator.get_selected_source_manifest("direct_zapret2")
            old_name = str(selected_manifest.name if selected_manifest is not None else "").strip()
        except Exception as e:
            present_preset_exception(
                action_error_message="Ошибка подготовки переименования пресета",
                exception=e,
                info_bar=InfoBar,
                parent=self.window(),
                error_title=self._tr("common.error.title", "Ошибка"),
                log_fn=log,
            )
            return

        if not old_name or not old_file_name:
            result = StrategyDetailPageController.build_missing_active_preset_result()
            present_preset_action_result(
                result,
                info_bar=InfoBar,
                parent=self.window(),
                log_fn=log,
                on_structure_changed=self._notify_preset_structure_changed,
            )
            return

        new_name = prompt_preset_name(
            dialog_cls=PresetNameDialog,
            mode="rename",
            old_name=old_name,
            parent=self.window(),
            language=self._ui_language,
        )
        if not new_name or new_name == old_name:
            return
        try:
            result = self._rename_current_preset(
                old_file_name=old_file_name,
                old_name=old_name,
                new_name=new_name,
            )
            present_preset_action_result(
                result,
                info_bar=InfoBar,
                parent=self.window(),
                log_fn=log,
                on_structure_changed=self._notify_preset_structure_changed,
            )
        except Exception as e:
            present_preset_exception(
                action_error_message="Ошибка переименования пресета",
                exception=e,
                info_bar=InfoBar,
                parent=self.window(),
                error_title=self._tr("common.error.title", "Ошибка"),
                log_fn=log,
            )

    def _on_reset_settings_confirmed(self):
        """Сбрасывает настройки target на значения по умолчанию (встроенный шаблон)."""
        if not self._target_key:
            return

        # 1. Reset through the direct facade (saves to the source preset file)
        success = self._reset_target_settings(self._target_key)
        plan = StrategyDetailPageController.build_reset_settings_plan(target_key=self._target_key, success=success)
        log(plan.log_message, plan.log_level)
        if not plan.ok:
            return

        self._preset_refresh_runtime.mark_suppressed()
        payload = self._reload_current_target_payload() if plan.should_reload_payload else None

        if plan.should_apply_syndata_settings:
            self._apply_syndata_settings(self._load_syndata_settings(self._target_key))

        if plan.should_refresh_filter_mode and hasattr(self, '_filter_mode_frame') and self._filter_mode_frame.isVisible():
            current_mode = (
                str(getattr(payload, "filter_mode", "") or "").strip().lower()
                if payload is not None else self._load_target_filter_mode(self._target_key)
            )
            apply_filter_mode_selector_state(
                self._filter_mode_selector,
                mode=current_mode,
            )

        if plan.should_refresh_strategy_selection:
            current_strategy_id = (
                (getattr(payload.details, "current_strategy", "none") or "none")
                if payload is not None else "none"
            )

            self._selected_strategy_id = current_strategy_id or "none"
            self._current_strategy_id = current_strategy_id or "none"

            if self._tcp_phase_mode:
                self._load_tcp_phase_state_from_preset()
                self._apply_tcp_phase_tabs_visibility()
                self._select_default_tcp_phase_tab()
                self._apply_filters()
            else:
                apply_tree_selected_strategy_state(
                    self._strategies_tree,
                    strategy_id=self._selected_strategy_id,
                )

        if plan.should_show_loading:
            self.show_loading()
        self._update_selected_strategy_header(self._selected_strategy_id)
        if plan.should_refresh_args_editor:
            self._refresh_args_editor_state()
        if plan.should_refresh_target_enabled_ui:
            self._set_target_enabled_ui((self._selected_strategy_id or "none") != "none")

    def _confirm_reset_settings_clicked(self) -> None:
        if MessageBox is not None:
            try:
                box = MessageBox(
                    self._tr("page.z2_strategy_detail.button.reset_settings", "Сбросить настройки"),
                    self._tr("page.z2_strategy_detail.button.reset_settings.confirm", "Сбросить все?"),
                    self.window(),
                )
                if not box.exec():
                    return
            except Exception:
                pass
        self._on_reset_settings_confirmed()

    def _on_row_clicked(self, strategy_id: str):
        """Обработчик клика по строке стратегии - выбор активной"""
        if self._tcp_phase_mode:
            self._on_tcp_phase_row_clicked(strategy_id)
            return

        plan = StrategyDetailPageController.build_row_click_plan(
            strategy_id=strategy_id,
            prev_strategy_id=self._selected_strategy_id,
            has_target_key=bool(self._target_key),
        )

        if plan.remembered_last_enabled_strategy_id:
            self._last_enabled_strategy_id = plan.remembered_last_enabled_strategy_id

        self._selected_strategy_id = plan.selected_strategy_id
        apply_tree_selected_strategy_state(
            self._strategies_tree,
            strategy_id=plan.selected_strategy_id,
        )
        self._update_selected_strategy_header(self._selected_strategy_id)

        if plan.should_hide_args_editor:
            self._hide_args_editor(clear_text=False)

        apply_loading_plan_action(
            plan.loading_state,
            show_loading_fn=self.show_loading,
            stop_loading_fn=self._stop_loading,
            show_success_fn=self.show_success,
            success_icon=self._success_icon,
        )

        self._refresh_args_editor_state()
        self._set_target_enabled_ui(plan.target_enabled)

        if plan.should_emit_strategy_selected and self._target_key:
            self._preset_refresh_runtime.set_suppressed(plan.suppress_next_preset_refresh)
            self.strategy_selected.emit(self._target_key, plan.selected_strategy_id)

    def _update_status_icon(self, active: bool):
        """Обновляет галочку статуса в заголовке"""
        plan = StrategyDetailPageController.build_status_icon_plan(active=active)
        apply_loading_plan_action(
            plan.action,
            show_loading_fn=self.show_loading,
            stop_loading_fn=self._stop_loading,
            show_success_fn=self.show_success,
            success_icon=self._success_icon,
        )

    def show_loading(self):
        """Показывает анимированный спиннер загрузки"""
        apply_loading_indicator_state(
            self._spinner,
            self._success_icon,
            loading=True,
        )
        self._waiting_for_process_start = True  # Ждём запуска DPI
        # В direct_zapret2 режимах "apply" часто не меняет состояние процесса (hot-reload),
        # поэтому даём быстрый таймаут, чтобы UI не зависал на спиннере.
        self._start_apply_feedback_timer()
    def _stop_loading(self):
        """Останавливает анимацию загрузки"""
        apply_loading_indicator_state(
            self._spinner,
            self._success_icon,
            loading=False,
            success=False,
        )
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
        plan = StrategyDetailPageController.build_apply_feedback_timeout_plan(
            waiting_for_process_start=self._waiting_for_process_start,
            selected_strategy_id=self._selected_strategy_id,
        )
        apply_loading_plan_action(
            plan.action,
            show_loading_fn=self.show_loading,
            stop_loading_fn=self._stop_loading,
            show_success_fn=self.show_success,
            success_icon=self._success_icon,
        )

    def show_success(self):
        """Показывает зелёную галочку успеха"""
        self._stop_loading()
        apply_loading_indicator_state(
            self._spinner,
            self._success_icon,
            success=True,
            success_pixmap=get_cached_qta_pixmap('fa5s.check-circle', color='#4ade80', size=16),
        )

    def _on_args_changed(self, strategy_id: str, args: list):
        """Обработчик изменения аргументов стратегии"""
        if self._cleanup_in_progress:
            return
        if self._target_key:
            self.args_changed.emit(self._target_key, strategy_id, args)
            log(f"Args changed: {self._target_key}/{strategy_id} = {args}", "DEBUG")

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
        """Returns the stored strategy args (tcp_args/udp_args) for the current target."""
        if not self._target_key:
            return ""
        payload = getattr(self, "_target_payload", None)
        if payload is not None and str(getattr(payload, "target_key", "") or "") == self._target_key:
            return str(getattr(payload, "raw_args_text", "") or "")
        return self._read_target_raw_args_text(self._target_key)

    def _get_strategy_args_text_by_id(self, strategy_id: str) -> str:
        data = dict(self._strategies_data_by_id.get(strategy_id, {}) or {})
        args = data.get("args", "")
        if isinstance(args, (list, tuple)):
            args = "\n".join([str(a) for a in args if a is not None])
        return _normalize_args_text(str(args or ""))

    def _infer_strategy_id_from_args_exact(self, args_text: str) -> str:
        """
        Best-effort exact match against loaded strategies.

        Returns:
            - matching strategy_id if found
            - "custom" if args are non-empty but don't match a single known strategy
            - "none" if args are empty
        """
        normalized = _normalize_args_text(args_text)
        if not normalized:
            return "none"

        for sid, data in (self._strategies_data_by_id or {}).items():
            if not sid or sid in ("none", TCP_FAKE_DISABLED_STRATEGY_ID):
                continue
            args_val = (data or {}).get("args") if isinstance(data, dict) else ""
            if isinstance(args_val, (list, tuple)):
                args_val = "\n".join([str(a) for a in args_val if a is not None])
            candidate = _normalize_args_text(str(args_val or ""))
            if candidate and candidate == normalized:
                return sid

        return CUSTOM_STRATEGY_ID

    def _extract_desync_techniques_from_args(self, args_text: str) -> list[str]:
        out: list[str] = []
        for raw in (args_text or "").splitlines():
            line = raw.strip()
            if not line or not line.startswith("--"):
                continue
            tech = _extract_desync_technique_from_arg(line)
            if tech:
                out.append(tech)
        return out

    def _infer_tcp_phase_key_for_strategy_args(self, args_text: str) -> str | None:
        """
        Returns a single phase key if all desync lines belong to the same phase.
        Otherwise returns None (multi-phase/unknown).
        """
        phase_keys: set[str] = set()
        for tech in self._extract_desync_techniques_from_args(args_text):
            phase = _map_desync_technique_to_tcp_phase(tech)
            if phase:
                phase_keys.add(phase)
        if len(phase_keys) == 1:
            return next(iter(phase_keys))
        return None

    def _update_tcp_phase_chip_markers(self) -> None:
        """
        Highlights all active phases (even when not currently selected).

        In the tab UI, this is implemented by cyan tab text for active phases.
        """
        if not self._tcp_phase_mode:
            return

        tabbar = self._phase_tabbar
        if not tabbar:
            return

        update_tcp_phase_chip_markers(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            tabbar=tabbar,
            phase_tab_index_by_key=self._phase_tab_index_by_key,
            tcp_phase_tab_order=TCP_PHASE_TAB_ORDER,
            selected_ids=self._tcp_phase_selected_ids,
            custom_args=self._tcp_phase_custom_args,
            fake_disabled_strategy_id=TCP_FAKE_DISABLED_STRATEGY_ID,
            custom_strategy_id=CUSTOM_STRATEGY_ID,
            build_marker_plan_fn=StrategyDetailPageController.build_tcp_phase_marker_plan,
        )

    def _load_tcp_phase_state_from_preset(self) -> None:
        """Parses current tcp_args into phase selections (best-effort)."""
        self._tcp_phase_selected_ids = {}
        self._tcp_phase_custom_args = {}
        self._tcp_hide_fake_phase = False

        selected_ids, custom_args, hide_fake_phase = load_tcp_phase_state(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            target_key=self._target_key,
            args_text=self._get_target_strategy_args_text(),
            strategies_data_by_id=self._strategies_data_by_id,
            phase_order=TCP_PHASE_COMMAND_ORDER,
            embedded_fake_techniques=TCP_EMBEDDED_FAKE_TECHNIQUES,
            fake_disabled_strategy_id=TCP_FAKE_DISABLED_STRATEGY_ID,
            custom_strategy_id=CUSTOM_STRATEGY_ID,
            normalize_args_text_fn=_normalize_args_text,
            extract_desync_technique_fn=_extract_desync_technique_from_arg,
            map_phase_fn=_map_desync_technique_to_tcp_phase,
            infer_phase_key_fn=self._infer_tcp_phase_key_for_strategy_args,
            build_state_plan_fn=StrategyDetailPageController.build_tcp_phase_state_plan,
        )
        self._tcp_phase_selected_ids = selected_ids
        self._tcp_phase_custom_args = custom_args
        self._tcp_hide_fake_phase = hide_fake_phase

        self._update_selected_strategy_header(self._selected_strategy_id)
        self._update_tcp_phase_chip_markers()

    def _apply_tcp_phase_tabs_visibility(self) -> None:
        """Shows/hides the FAKE phase tab depending on selected main techniques."""
        apply_tcp_phase_tabs_visibility(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            phase_tabbar=self._phase_tabbar,
            hide_fake_phase=bool(self._tcp_hide_fake_phase),
            active_phase_key=self._active_phase_key,
            build_tabs_visibility_plan_fn=StrategyDetailPageController.build_tcp_phase_tabs_visibility_plan,
            set_active_phase_chip_fn=self._set_active_phase_chip,
            reapply_filters_fn=self._apply_filters,
        )

    def _set_active_phase_chip(self, phase_key: str) -> None:
        """Selects a phase tab programmatically without firing user side effects twice."""
        final_phase_key = set_active_phase_chip(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            phase_tabbar=self._phase_tabbar,
            phase_tab_index_by_key=self._phase_tab_index_by_key,
            requested_phase_key=phase_key,
            build_active_phase_chip_plan_fn=StrategyDetailPageController.build_active_phase_chip_plan,
        )
        if final_phase_key:
            self._active_phase_key = final_phase_key

    def _select_default_tcp_phase_tab(self) -> None:
        """Chooses the initial active tab for TCP phase UI."""
        select_default_tcp_phase_tab(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            selected_ids=self._tcp_phase_selected_ids,
            hide_fake_phase=bool(self._tcp_hide_fake_phase),
            phase_priority=["multisplit", "multidisorder", "multidisorder_legacy", "tcpseg", "oob", "other"],
            build_default_tab_plan_fn=StrategyDetailPageController.build_default_tcp_phase_tab_plan,
            set_active_phase_chip_fn=self._set_active_phase_chip,
        )

    def _save_tcp_phase_state_to_preset(self, *, show_loading: bool = True) -> None:
        """Persists current phase state into preset tcp_args and emits selection update."""
        if not (self._tcp_phase_mode and self._target_key):
            return

        strategy_args_by_id = build_strategy_args_lookup(
            strategies_data_by_id=self._strategies_data_by_id,
            load_args_text_fn=self._get_strategy_args_text_by_id,
        )
        new_args = StrategyDetailPageController.build_tcp_phase_args_text(
            selected_ids=self._tcp_phase_selected_ids,
            custom_args=self._tcp_phase_custom_args,
            hide_fake_phase=bool(self._tcp_hide_fake_phase),
            phase_order=TCP_PHASE_COMMAND_ORDER,
            strategy_args_by_id=strategy_args_by_id,
            fake_disabled_strategy_id=TCP_FAKE_DISABLED_STRATEGY_ID,
            custom_strategy_id=CUSTOM_STRATEGY_ID,
        )

        try:
            if not self._write_target_raw_args_text(
                self._target_key,
                new_args,
                save_and_sync=True,
            ):
                return
            self._preset_refresh_runtime.mark_suppressed()
            payload = self._reload_current_target_payload()
            plan = StrategyDetailPageController.build_tcp_phase_save_result_plan(
                payload=payload,
                show_loading=show_loading,
            )
            apply_tcp_phase_save_result(
                plan,
                target_key=self._target_key,
                set_selected_state_fn=lambda selected_id, current_id: (
                    setattr(self, "_selected_strategy_id", selected_id),
                    setattr(self, "_current_strategy_id", current_id),
                ),
                set_target_enabled_ui_fn=self._set_target_enabled_ui,
                refresh_args_editor_fn=self._refresh_args_editor_state,
                show_loading_fn=self.show_loading,
                stop_loading_fn=self._stop_loading,
                hide_success_icon_fn=lambda: self._success_icon.hide(),
                update_header_fn=self._update_selected_strategy_header,
                update_markers_fn=self._update_tcp_phase_chip_markers,
                emit_selection_fn=self.strategy_selected.emit,
            )

        except Exception as e:
            log(f"TCP phase save failed: {e}", "ERROR")

    def _on_tcp_phase_row_clicked(self, strategy_id: str) -> None:
        """TCP multi-phase: applies selection for the currently active phase."""
        if not self._strategies_tree:
            return
        try:
            is_visible = bool(self._strategies_tree.is_strategy_visible(strategy_id))
        except Exception:
            is_visible = False

        strategy_args_by_id = build_strategy_args_lookup(
            strategies_data_by_id=self._strategies_data_by_id,
            load_args_text_fn=self._get_strategy_args_text_by_id,
        )
        plan = StrategyDetailPageController.build_tcp_phase_row_click_plan(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            target_key=self._target_key,
            active_phase_key=self._active_phase_key,
            strategy_id=strategy_id,
            is_visible=is_visible,
            selected_ids=self._tcp_phase_selected_ids,
            custom_args=self._tcp_phase_custom_args,
            strategy_args_by_id=strategy_args_by_id,
            phase_order=TCP_PHASE_COMMAND_ORDER,
            embedded_fake_techniques=TCP_EMBEDDED_FAKE_TECHNIQUES,
            custom_strategy_id=CUSTOM_STRATEGY_ID,
            fake_disabled_strategy_id=TCP_FAKE_DISABLED_STRATEGY_ID,
        )
        apply_tcp_phase_row_click_result(
            plan,
            set_phase_state_fn=lambda selected_ids, custom_args, hide_fake_phase: (
                setattr(self, "_tcp_phase_selected_ids", selected_ids),
                setattr(self, "_tcp_phase_custom_args", custom_args),
                setattr(self, "_tcp_hide_fake_phase", hide_fake_phase),
            ),
            strategies_tree=self._strategies_tree,
            apply_tabs_visibility_fn=self._apply_tcp_phase_tabs_visibility,
            save_state_fn=self._save_tcp_phase_state_to_preset,
        )

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
        """Called when user clicks the favorite star in the UI."""
        result = StrategyDetailPageController.toggle_favorite(
            self._feedback_store,
            strategy_id=strategy_id,
            is_favorite=is_favorite,
            target_key=self._target_key,
            favorite_ids=self._favorite_strategy_ids,
        )
        if not result.ok:
            return

        self._favorite_strategy_ids = set(result.updated_favorite_ids)

    def _get_default_strategy(self) -> str:
        """Возвращает первую доступную стратегию из текущего каталога target."""
        for sid in (self._default_strategy_order or []):
            if sid and sid != "none":
                return sid
        return "none"

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
        """Loads the last selected TCP phase tab for a target (persisted in registry)."""
        try:
            from config.reg import reg
            from config.config import REGISTRY_PATH_GUI

        except Exception:
            return None

        key = str(target_key or "").strip().lower()
        if not key:
            return None

        try:
            raw = reg(REGISTRY_PATH_GUI, self._REG_TCP_PHASE_TABS_BY_TARGET)
            if not raw:
                return None
            data = json.loads(raw) if isinstance(raw, str) else {}
            phase = str((data or {}).get(key) or "").strip().lower()
            if phase and phase in (self._phase_tab_index_by_key or {}):
                return phase
        except Exception:
            return None

        return None

    def _save_target_last_tcp_phase_tab(self, target_key: str, phase_key: str) -> None:
        """Saves the last selected TCP phase tab for a target (best-effort)."""
        try:
            from config.reg import reg
            from config.config import REGISTRY_PATH_GUI

        except Exception:
            return

        target_key_n = str(target_key or "").strip().lower()
        phase = str(phase_key or "").strip().lower()
        if not target_key_n or not phase:
            return

        # Validate phase key early to avoid persisting garbage.
        if self._tcp_phase_mode and phase not in (self._phase_tab_index_by_key or {}):
            return

        try:
            raw = reg(REGISTRY_PATH_GUI, self._REG_TCP_PHASE_TABS_BY_TARGET)
            data = {}
            if isinstance(raw, str) and raw.strip():
                try:
                    data = json.loads(raw) or {}
                except Exception:
                    data = {}
            if not isinstance(data, dict):
                data = {}
            data[target_key_n] = phase
            reg(REGISTRY_PATH_GUI, self._REG_TCP_PHASE_TABS_BY_TARGET, json.dumps(data, ensure_ascii=False))
        except Exception:
            return

    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
    # OUT RANGE METHODS
    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР

    def _select_out_range_mode(self, mode: str):
        """╨Т╤Л╨▒╨╛╤А ╤А╨╡╨╢╨╕╨╝╨░ out_range (n ╨╕╨╗╨╕ d)"""
        if mode != self._out_range_mode:
            self._out_range_mode = mode
            try:
                self._out_range_seg.setCurrentItem(mode)
            except Exception:
                pass
            self._schedule_syndata_settings_save()

    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
    # SYNDATA SETTINGS METHODS
    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР

    def _on_send_toggled(self, checked: bool):
        """╨Ю╨▒╤А╨░╨▒╨╛╤В╤З╨╕╨║ ╨▓╨║╨╗╤О╤З╨╡╨╜╨╕╤П/╨▓╤Л╨║╨╗╤О╤З╨╡╨╜╨╕╤П send ╨┐╨░╤А╨░╨╝╨╡╤В╤А╨╛╨▓"""
        self._send_settings.setVisible(checked)
        self._schedule_syndata_settings_save()

    def _on_syndata_toggled(self, checked: bool):
        """╨Ю╨▒╤А╨░╨▒╨╛╤В╤З╨╕╨║ ╨▓╨║╨╗╤О╤З╨╡╨╜╨╕╤П/╨▓╤Л╨║╨╗╤О╤З╨╡╨╜╨╕╤П syndata ╨┐╨░╤А╨░╨╝╨╡╤В╤А╨╛╨▓"""
        self._syndata_settings.setVisible(checked)
        self._schedule_syndata_settings_save()

    def _schedule_syndata_settings_save(self, delay_ms: int = 180):
        """Пакетирует частые изменения UI в одно сохранение preset-а.

        Это особенно важно для SpinBox/TTL-селекторов: пользователю удобно
        быстро прокрутить несколько значений подряд, а вот писать preset и
        триггерить синхронизацию после каждого шага — лишняя работа.
        """
        plan = StrategyDetailPageController.build_syndata_timer_plan(
            target_key=self._target_key,
            delay_ms=delay_ms,
        )
        if not plan.should_schedule:
            return
        self._pending_syndata_target_key = plan.pending_target_key
        try:
            self._syndata_save_timer.start(plan.delay_ms)
        except Exception:
            self._flush_syndata_settings_save()

    def _flush_syndata_settings_save(self):
        """Сохраняет out_range/send/syndata через новый direct facade."""
        raw_payload = {
            "enabled": self._syndata_toggle.isChecked(),
            "blob": self._blob_combo.currentText(),
            "tls_mod": self._tls_mod_combo.currentText(),
            "autottl_delta": self._autottl_delta_selector.value(),
            "autottl_min": self._autottl_min_selector.value(),
            "autottl_max": self._autottl_max_selector.value(),
            "out_range": self._out_range_spin.value(),
            "out_range_mode": self._out_range_mode,
            "tcp_flags_unset": self._tcp_flags_combo.currentText(),
            "send_enabled": self._send_toggle.isChecked(),
            "send_repeats": self._send_repeats_spin.value(),
            "send_ip_ttl": self._send_ip_ttl_selector.value(),
            "send_ip6_ttl": self._send_ip6_ttl_selector.value(),
            "send_ip_id": self._send_ip_id_combo.currentText(),
            "send_badsum": self._send_badsum_check.isChecked(),
        }
        plan = StrategyDetailPageController.build_syndata_persist_plan(
            target_key=self._target_key,
            pending_target_key=self._pending_syndata_target_key,
            payload=raw_payload,
        )
        if not plan.should_save:
            return
        self._pending_syndata_target_key = None

        log(f"Syndata settings saved for {plan.normalized_target_key}: {plan.payload}", "DEBUG")
        self._preset_refresh_runtime.mark_suppressed()
        self._write_target_details_settings(
            plan.normalized_target_key,
            plan.payload,
            save_and_sync=True,
        )

    def _load_syndata_settings(self, target_key: str) -> dict:
        """Читает текущие настройки target из PresetTargetDetails."""
        details = self._get_target_details(target_key)
        protocol = str(getattr(self._target_info, "protocol", "") or "")
        return StrategyDetailPageController.build_target_settings_payload(details=details, protocol=protocol)


    def _refresh_args_editor_state(self):
        refresh_args_editor_state(
            edit_args_btn=getattr(self, "_edit_args_btn", None),
            target_key=self._target_key,
            selected_strategy_id=self._selected_strategy_id,
            build_state_plan_fn=StrategyDetailPageController.build_args_editor_state_plan,
            apply_args_editor_state_fn=apply_args_editor_state,
            hide_editor_fn=self._hide_args_editor,
        )

    def _toggle_args_editor(self):
        """Открывает MessageBoxBase диалог для редактирования args текущего target'а."""
        open_args_editor_dialog(
            build_open_plan_fn=self._build_args_editor_open_plan,
            parent=self.window(),
            language=self._ui_language,
            run_args_editor_dialog_fn=run_args_editor_dialog,
            apply_args_fn=self._apply_args_editor,
        )

    def _hide_args_editor(self, clear_text: bool = False):
        """Стаб для обратной совместимости — редактор теперь диалог."""
        self._args_editor_dirty = hide_args_editor_state(clear_text=clear_text)

    def _load_args_into_editor(self):
        """Стаб для обратной совместимости."""
        pass

    def _on_args_editor_changed(self):
        """Стаб для обратной совместимости."""
        pass

    def _apply_args_editor(self, raw: str = ""):
        apply_plan = StrategyDetailPageController.build_args_apply_plan(
            target_key=self._target_key,
            selected_strategy_id=self._selected_strategy_id,
            raw_text=raw,
        )
        if not apply_plan.should_apply:
            return

        try:
            if not self._write_target_raw_args_text(
                self._target_key,
                apply_plan.normalized_text,
                save_and_sync=True,
            ):
                return
            self._preset_refresh_runtime.mark_suppressed()
            payload = self._reload_current_target_payload()
            result_plan = StrategyDetailPageController.build_args_apply_result_plan(payload=payload)
            self._selected_strategy_id = result_plan.selected_strategy_id
            self._current_strategy_id = result_plan.current_strategy_id
            self._args_editor_dirty = False
            if result_plan.should_show_loading:
                self.show_loading()
            if result_plan.should_emit_args_changed:
                self._on_args_changed(self._selected_strategy_id, apply_plan.args_lines)

        except Exception as e:
            log(f"Args editor: failed to save args: {e}", "ERROR")

    def _on_search_changed(self, text: str):
        """Фильтрует стратегии по поисковому запросу"""
        self._apply_filters()

    def _on_filter_toggled(self, technique: str, active: bool):
        """Обработчик переключения фильтра"""
        if active:
            self._active_filters.add(technique)
        else:
            self._active_filters.discard(technique)
        self._update_technique_filter_ui()
        self._apply_filters()

    def _populate_sort_combo(self) -> None:
        entries = StrategyDetailPageController.build_sort_options(tr=self._tr)
        populate_sort_combo(getattr(self, "_sort_combo", None), entries)
        self._update_sort_button_ui()

    def _update_sort_button_ui(self) -> None:
        self._last_sort_icon_color = update_sort_button_ui(
            combo=getattr(self, "_sort_combo", None),
            button=getattr(self, "_sort_btn", None),
            sort_mode=self._sort_mode,
            tr=self._tr,
            previous_icon_color=self._last_sort_icon_color,
            get_theme_tokens_fn=get_theme_tokens,
            build_tooltip_fn=StrategyDetailPageController.build_sort_tooltip,
            apply_sort_combo_state_fn=apply_sort_combo_state,
            apply_sort_button_state_fn=apply_sort_button_state,
            set_tooltip_fn=set_tooltip,
            icon_builder=lambda icon_color: get_themed_qta_icon('fa5s.sort-alpha-down', color=icon_color),
        )

    def _on_sort_combo_changed(self, index: int) -> None:
        combo = getattr(self, "_sort_combo", None)
        if combo is None:
            return

        requested_mode = "default"
        try:
            requested_mode = str(combo.itemData(index) or "default").strip().lower() or "default"
        except Exception:
            pass

        plan = StrategyDetailPageController.build_sort_change_plan(
            requested_mode=requested_mode,
            current_mode=self._sort_mode,
            target_key=self._target_key,
        )
        if not plan.should_apply:
            return

        self._sort_mode = plan.normalized_mode
        if plan.should_persist:
            self._save_target_sort(self._target_key, self._sort_mode)
        self._apply_sort()

    def _on_technique_filter_changed(self, index: int) -> None:
        """Обработчик выбора техники в ComboBox фильтра."""
        self._active_filters.clear()
        if index > 0 and index <= len(STRATEGY_TECHNIQUE_FILTERS):
            key = STRATEGY_TECHNIQUE_FILTERS[index - 1][1]
            self._active_filters.add(key)
        self._apply_filters()

    def _update_technique_filter_ui(self) -> None:
        """Синхронизирует ComboBox с текущим состоянием _active_filters."""
        update_technique_filter_ui(
            combo=getattr(self, "_filter_combo", None),
            active_filters=self._active_filters,
            technique_filters=STRATEGY_TECHNIQUE_FILTERS,
            build_technique_filter_plan_fn=StrategyDetailPageController.build_technique_filter_plan,
            apply_technique_filter_combo_state_fn=apply_technique_filter_combo_state,
        )

    def _update_strategies_summary(self) -> None:
        search_text = ""
        if getattr(self, "_search_input", None) is not None:
            try:
                search_text = self._search_input.text()
            except Exception:
                search_text = ""

        changed, self._last_strategies_summary_text = update_strategies_summary(
            label=getattr(self, "_strategies_summary_label", None),
            tree=getattr(self, "_strategies_tree", None),
            search_text=search_text,
            tcp_phase_mode=self._tcp_phase_mode,
            active_phase_key=self._active_phase_key,
            active_filters=self._active_filters,
            technique_filters=STRATEGY_TECHNIQUE_FILTERS,
            tr=self._tr,
            previous_text=self._last_strategies_summary_text,
            build_summary_fn=StrategyDetailPageController.build_strategies_summary,
            apply_summary_label_fn=apply_strategies_summary_label,
        )
        if not changed:
            return

    def _on_phase_tab_changed(self, route_key: str) -> None:
        """TCP multi-phase: handler for Pivot currentItemChanged signal."""
        plan = StrategyDetailPageController.build_phase_tab_change_plan(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            phase_key=route_key,
            target_key=self._target_key,
        )
        if not plan.should_apply:
            return

        self._active_phase_key = plan.normalized_phase_key
        try:
            if plan.should_persist:
                self._last_active_phase_key_by_target[self._target_key] = plan.normalized_phase_key
                self._save_target_last_tcp_phase_tab(self._target_key, plan.normalized_phase_key)
        except Exception:
            pass

        self._apply_filters()
        if plan.should_sync_phase_selection:
            self._sync_tree_selection_to_active_phase()

    def _on_phase_pivot_item_clicked(self, key: str) -> None:
        """Called on every click on a phase pivot item (including re-click of current item)."""
        plan = StrategyDetailPageController.build_phase_tab_reclick_plan(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            clicked_key=key,
            active_phase_key=self._active_phase_key,
        )
        if plan.should_apply:
            self._apply_filters()
            if plan.should_sync_phase_selection:
                self._sync_tree_selection_to_active_phase()

    def _apply_filters(self):
        """Применяет фильтры по технике к списку стратегий"""
        if not self._strategies_tree:
            return
        _t_total = _time.perf_counter()
        search_text = self._search_input.text() if self._search_input else ""
        selected_sid = self._selected_strategy_id or self._current_strategy_id or "none"
        filter_plan = StrategyDetailPageController.build_filter_apply_plan(
            tcp_phase_mode=bool(self._tcp_phase_mode),
            active_phase_key=self._active_phase_key,
            search_text=search_text,
            active_filters=self._active_filters,
            selected_strategy_id=self._selected_strategy_id,
            current_strategy_id=self._current_strategy_id,
            has_selected_strategy=bool(self._strategies_tree.has_strategy(selected_sid)),
            is_selected_visible=bool(self._strategies_tree.is_strategy_visible(selected_sid)) if selected_sid else False,
        )
        apply_filter_plan_to_tree(
            tree=self._strategies_tree,
            filter_plan=filter_plan,
            target_key=self._target_key,
            update_summary_fn=self._update_strategies_summary,
            sync_phase_selection_fn=self._sync_tree_selection_to_active_phase,
            log_metric_fn=lambda marker, started_at, extra: _log_z2_detail_metric(
                marker,
                (_time.perf_counter() - started_at) * 1000,
                extra=extra,
            ),
            started_at=_t_total,
        )

    def _sync_tree_selection_to_active_phase(self) -> None:
        """TCP multi-phase: restores highlighted row for the currently active phase."""
        sync_tree_selection_to_active_phase(
            strategies_tree=self._strategies_tree,
            tcp_phase_mode=bool(self._tcp_phase_mode),
            active_phase_key=self._active_phase_key,
            tcp_phase_selected_ids=self._tcp_phase_selected_ids,
            custom_strategy_id=CUSTOM_STRATEGY_ID,
            build_phase_selection_plan_fn=StrategyDetailPageController.build_phase_selection_plan,
        )

    def _show_sort_menu(self):
        """Показывает RoundMenu сортировки с иконками."""
        def _set_sort(mode: str):
            plan = StrategyDetailPageController.build_sort_change_plan(
                requested_mode=mode,
                current_mode=self._sort_mode,
                target_key=self._target_key,
            )
            if not plan.should_apply:
                return
            self._sort_mode = plan.normalized_mode
            if plan.should_persist:
                self._save_target_sort(self._target_key, self._sort_mode)
            self._apply_sort()

        if getattr(self, "_sort_btn", None) is None:
            return
        show_sort_menu(
            parent=self,
            sort_button=self._sort_btn,
            current_mode=self._sort_mode,
            has_fluent=_HAS_FLUENT,
            round_menu_cls=RoundMenu,
            action_cls=Action,
            fluent_icon=FluentIcon,
            build_sort_options_fn=StrategyDetailPageController.build_sort_options,
            tr=self._tr,
            on_select=_set_sort,
            exec_popup_menu_fn=exec_popup_menu,
        )

    def _apply_sort(self):
        """Применяет текущую сортировку"""
        if not self._strategies_tree:
            return
        _t_total = _time.perf_counter()
        selected_sid = self._selected_strategy_id or self._current_strategy_id or "none"
        plan = StrategyDetailPageController.build_sort_apply_plan(
            sort_mode=self._sort_mode,
            selected_strategy_id=self._selected_strategy_id,
            current_strategy_id=self._current_strategy_id,
            has_selected_strategy=bool(self._strategies_tree.has_strategy(selected_sid)),
        )
        self._sort_mode = apply_sort_plan_to_tree(
            tree=self._strategies_tree,
            sort_plan=plan,
            target_key=self._target_key,
            set_sort_mode_fn=lambda mode: setattr(self, "_sort_mode", mode),
            update_sort_button_ui_fn=self._update_sort_button_ui,
            update_summary_fn=self._update_strategies_summary,
            log_metric_fn=lambda marker, started_at, extra: _log_z2_detail_metric(
                marker,
                (_time.perf_counter() - started_at) * 1000,
                extra=extra,
            ),
            started_at=_t_total,
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if not getattr(self, "_content_built", False):
            return

        if getattr(self, "_breadcrumb", None) is not None:
            self._breadcrumb.blockSignals(True)
            try:
                self._breadcrumb.clear()
                self._breadcrumb.addItem("control", self._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"))
                self._breadcrumb.addItem(
                    "strategies", self._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI")
                )
                detail = ""
                try:
                    detail = self._target_info.full_name if self._target_info else ""
                except Exception:
                    detail = ""
                self._breadcrumb.addItem(
                    "detail",
                    detail or self._tr("page.z2_strategy_detail.header.category_fallback", "Target"),
                )
            finally:
                self._breadcrumb.blockSignals(False)

        if getattr(self, "_parent_link", None) is not None:
            self._parent_link.setText(self._tr("page.z2_strategy_detail.back.strategies", "Стратегии DPI"))

        if getattr(self, "_title", None) is not None:
            target_title = ""
            protocol = ""
            ports = ""
            try:
                if self._target_info:
                    target_title = str(getattr(self._target_info, "full_name", "") or "").strip()
                    protocol = str(getattr(self._target_info, "protocol", "") or "").strip()
                    ports = str(getattr(self._target_info, "ports", "") or "").strip()
            except Exception:
                pass
            self._title.setText(target_title or self._tr("page.z2_strategy_detail.header.select_category", "Выберите target"))
            if getattr(self, "_subtitle", None) is not None:
                if protocol:
                    self._subtitle.setText(
                        f"{protocol}  |  "
                        f"{self._tr('page.z2_strategy_detail.subtitle.ports', 'порты: {ports}', ports=ports)}"
                    )
                else:
                    self._subtitle.setText("")

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

        if getattr(self, "_out_range_mode_label", None) is not None:
            self._out_range_mode_label.setText(self._tr("page.z2_strategy_detail.out_range.mode", "Режим:"))
        if getattr(self, "_out_range_value_label", None) is not None:
            self._out_range_value_label.setText(self._tr("page.z2_strategy_detail.out_range.value", "Значение:"))
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
                    "n = количество пакетов с самого первого, d = отсчитывать ТОЛЬКО количество пакетов с данными",
                ),
            )
        if getattr(self, "_out_range_spin", None) is not None:
            set_tooltip(
                self._out_range_spin,
                self._tr(
                    "page.z2_strategy_detail.out_range.value.tooltip",
                    "--out-range: ограничение количества исходящих пакетов (n) или задержки (d)",
                ),
            )

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
        self._update_selected_strategy_header(self._selected_strategy_id)
