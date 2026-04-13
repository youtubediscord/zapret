# filters/ui/filter_list/zapret1/strategy_detail_page.py
"""Zapret 1 strategy detail page with Zapret 2-style layout."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from direct_preset.runtime import DirectTargetDetailSnapshotWorker
from ui.pages.base_page import BasePage
from ui.compat_widgets import ActionButton, RefreshButton, SettingsCard
from app_state.main_window_state import AppUiState, MainWindowStateStore
from filters.ui.strategy_tree import StrategyTree
from ui.text_catalog import tr as tr_catalog
from filters.ui.strategy_detail.shared import (
    build_detail_subtitle_widgets,
    build_strategies_tree_widget,
    run_args_editor_dialog,
)
from filters.strategy_detail.zapret1.controller import StrategyDetailPageV1Controller
from filters.ui.strategy_detail.zapret1.page_interactions_runtime import (
    close_preview_dialog_runtime_v1,
    close_transient_overlays_runtime_v1,
    ensure_preview_dialog_runtime_v1,
    get_preview_rating_runtime_v1,
    get_preview_strategy_data_runtime_v1,
    on_favorite_toggled_runtime_v1,
    on_preview_closed_runtime_v1,
    on_tree_preview_hide_requested_runtime_v1,
    on_tree_preview_pinned_requested_runtime_v1,
    on_tree_preview_requested_runtime_v1,
    on_tree_working_mark_requested_runtime_v1,
    open_args_editor_runtime_v1,
    save_custom_args_runtime_v1,
    show_preview_dialog_runtime_v1,
    toggle_preview_rating_runtime_v1,
)
from filters.ui.strategy_detail.zapret1.page_runtime import (
    apply_search_filter_runtime_v1,
    apply_sort_mode_runtime_v1,
    default_strategy_id_runtime_v1,
    get_current_args_runtime_v1,
    hide_success_runtime_v1,
    load_target_filter_mode_runtime_v1,
    on_enable_toggled_runtime_v1,
    on_filter_mode_changed_runtime_v1,
    on_search_text_changed_runtime_v1,
    on_sort_combo_changed_runtime_v1,
    on_strategy_selected_runtime_v1,
    refresh_args_preview_runtime_v1,
    show_loading_runtime_v1,
    show_success_runtime_v1,
    strategy_display_name_runtime_v1,
    sync_target_controls_runtime_v1,
    target_supports_filter_switch_runtime_v1,
    update_header_labels_runtime_v1,
    update_selected_label_runtime_v1,
)
from filters.ui.strategy_detail.zapret1.page_payload_runtime import (
    activate_page_runtime_v1,
    apply_loaded_header_state_runtime_v1,
    apply_loaded_target_payload_runtime_v1,
    clear_strategies_and_rebuild_runtime_v1,
    get_target_details_runtime_v1,
    handle_missing_target_payload_runtime_v1,
    load_current_strategy_id_runtime_v1,
    load_target_payload_sync_runtime_v1,
    on_target_payload_loaded_runtime_v1,
    refresh_from_preset_switch_runtime_v1,
    reload_target_error_fallback_runtime_v1,
    reload_target_runtime_v1,
    request_target_payload_runtime_v1,
    show_target_runtime_v1,
    stop_spinner_runtime_v1,
)
from filters.ui.strategy_detail.zapret1.build import build_strategy_detail_v1_main_sections
from filters.ui.strategy_detail.zapret1.build import build_strategy_detail_v1_header
from filters.ui.strategy_detail.zapret1.args import ArgsEditorDialogV1
from ui.page_dependencies import require_page_app_context
from filters.ui.strategy_detail.zapret1.filtering_ui import rebuild_tree_rows_v1
from filters.ui.strategy_detail.zapret1.page_workflow import (
    bind_ui_state_store_v1,
    cleanup_page_v1,
    handle_breadcrumb_changed_v1,
    handle_ui_state_changed_v1,
    rebuild_breadcrumb_v1,
)
from filters.ui.strategy_detail.zapret1.runtime_helpers import apply_strategy_detail_v1_language
from log.log import log

from filters.ui.strategy_detail.args_preview_dialog import ArgsPreviewDialog

try:
    from qfluentwidgets import (
        BodyLabel,
        CaptionLabel,
        TitleLabel,
        LineEdit,
        ComboBox,
        BreadcrumbBar,
        IndeterminateProgressRing,
        PixmapLabel,
        InfoBar,
        TransparentPushButton,
        SwitchButton,
    )

    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import (  # type: ignore
        QLabel as BodyLabel,
        QLabel as CaptionLabel,
        QLabel as TitleLabel,
        QLineEdit as LineEdit,
        QComboBox as ComboBox,
        QCheckBox as SwitchButton,
    )

    BreadcrumbBar = None  # type: ignore
    IndeterminateProgressRing = QWidget  # type: ignore
    PixmapLabel = QLabel  # type: ignore
    InfoBar = None  # type: ignore
    TransparentPushButton = QPushButton  # type: ignore
    _HAS_FLUENT = False

class Zapret1StrategyDetailPage(BasePage):
    """Страница выбора стратегии для одного target'а Zapret 1."""

    strategy_selected = pyqtSignal(str, str)  # target_key, strategy_id
    back_clicked = pyqtSignal()  # go to target list
    navigate_to_control = pyqtSignal()  # go to control page

    def __init__(self, parent=None):
        super().__init__(title="", subtitle="", parent=parent)
        self.parent_app = parent

        self._target_key: str = ""
        self._target_info: dict[str, Any] = {}
        self._direct_facade = None
        self._target_payload = None
        self._target_payload_worker = None
        self._target_payload_request_id = 0
        self._preset_refresh_pending = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._cleanup_in_progress = False
        self._feedback_store = None
        self._favorite_strategy_ids: set[str] = set()
        self._preview_dialog = None
        self._preview_pinned = False
        self._args_preview_dialog_cls = ArgsPreviewDialog
        self._run_args_editor_dialog_fn = lambda **kwargs: run_args_editor_dialog(
            dialog_cls=ArgsEditorDialogV1,
            **kwargs,
        )
        self._info_bar_cls = InfoBar
        self._target_payload_worker_cls = DirectTargetDetailSnapshotWorker
        self._single_shot_fn = QTimer.singleShot
        self._log_fn = log

        self._strategies: dict[str, dict] = {}
        self._current_strategy_id: str = "none"
        self._sort_mode: str = "recommended"  # recommended | alpha_asc | alpha_desc
        self._search_text: str = ""

        self._breadcrumb = None
        self._tree: StrategyTree | None = None
        self._refresh_btn: RefreshButton | None = None
        self._search_edit: Any = None
        self._sort_combo: Any = None
        self._spinner: Any = None
        self._success_icon: Any = None
        self._title_label: Any = None
        self._subtitle_label: Any = None
        self._selected_label: Any = None
        self._desc_label: Any = None
        self._args_preview_label: Any = None
        self._empty_label: Any = None
        self._edit_args_btn: Any = None
        self._enable_toggle: Any = None
        self._filter_mode_frame: Any = None
        self._filter_mode_selector: Any = None
        self._state_label: Any = None
        self._filter_label: Any = None
        self._list_card: Any = None
        self._toolbar_card: Any = None
        self._back_btn: Any = None

        self._last_enabled_strategy_id: str = ""

        self._success_timer = QTimer(self)
        self._success_timer.setSingleShot(True)
        self._success_timer.timeout.connect(self._hide_success)

        self._build_ui()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        try:
            self.layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)
        except Exception:
            pass

        try:
            if hasattr(self, "content") and self.content is not None:
                self.content.setMaximumSize(16777215, 16777215)
        except Exception:
            pass

        if self.title_label is not None:
            self.title_label.hide()
        if self.subtitle_label is not None:
            self.subtitle_label.hide()

        self._setup_breadcrumb()
        header_widgets = build_strategy_detail_v1_header(
            parent=self,
            tr_fn=self._tr,
            body_label_cls=BodyLabel,
            title_label_cls=TitleLabel,
            caption_label_cls=CaptionLabel,
            spinner_cls=IndeterminateProgressRing if _HAS_FLUENT else QWidget,
            pixmap_label_cls=PixmapLabel,
            build_detail_subtitle_widgets_fn=build_detail_subtitle_widgets,
            breadcrumb=self._breadcrumb,
        )
        self._spinner = header_widgets.spinner
        self._success_icon = header_widgets.success_icon
        self._title_label = header_widgets.title_label
        self._subtitle_label = header_widgets.subtitle_label
        self._selected_label = header_widgets.selected_label
        self._desc_label = header_widgets.desc_label
        self.add_widget(header_widgets.header_widget)

        main_widgets = build_strategy_detail_v1_main_sections(
            parent=self,
            tr_fn=self._tr,
            action_button_cls=ActionButton,
            refresh_button_cls=RefreshButton,
            settings_card_cls=SettingsCard,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            line_edit_cls=LineEdit,
            combo_box_cls=ComboBox,
            switch_button_cls=SwitchButton,
            build_tree_widget_fn=build_strategies_tree_widget,
            direct_tree_cls=StrategyTree,
            on_enable_toggled=self._on_enable_toggled,
            on_filter_mode_changed=self._on_filter_mode_changed,
            on_reload_target=self._reload_target,
            on_search_text_changed=self._on_search_text_changed,
            on_sort_combo_changed=self._on_sort_combo_changed,
            on_open_args_editor=self._open_args_editor,
            on_strategy_selected=self._on_strategy_selected,
            on_favorite_toggled=self._on_favorite_toggled,
            on_working_mark_requested=self._on_tree_working_mark_requested,
            on_preview_requested=self._on_tree_preview_requested,
            on_preview_pinned_requested=self._on_tree_preview_pinned_requested,
            on_preview_hide_requested=self._on_tree_preview_hide_requested,
        )
        self._toolbar_card = main_widgets.toolbar_card
        self._state_label = main_widgets.state_label
        self._enable_toggle = main_widgets.enable_toggle
        self._filter_mode_frame = main_widgets.filter_mode_frame
        self._filter_label = main_widgets.filter_label
        self._filter_mode_selector = main_widgets.filter_mode_selector
        self._refresh_btn = main_widgets.refresh_btn
        self._search_edit = main_widgets.search_edit
        self._sort_combo = main_widgets.sort_combo
        self._edit_args_btn = main_widgets.edit_args_btn
        self._args_preview_label = main_widgets.args_preview_label
        self._list_card = main_widgets.list_card
        self._tree = main_widgets.tree
        self._empty_label = main_widgets.empty_label
        self.add_widget(self._toolbar_card)
        self.add_widget(self._list_card, 1)

    def _setup_breadcrumb(self) -> None:
        if _HAS_FLUENT and BreadcrumbBar is not None:
            try:
                self._breadcrumb = BreadcrumbBar(self)
                self._rebuild_breadcrumb()
                self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_changed)
                return
            except Exception:
                pass

        self._breadcrumb = None
        try:
            back_btn = TransparentPushButton(parent=self)
            back_btn.setText(self._tr("page.z1_strategy_detail.back.strategies", "← Стратегии Zapret 1"))
            back_btn.clicked.connect(self.back_clicked.emit)
            self._back_btn = back_btn
            self.add_widget(back_btn)
        except Exception:
            pass

    def _rebuild_breadcrumb(self) -> None:
        rebuild_breadcrumb_v1(
            breadcrumb=self._breadcrumb,
            tr_fn=self._tr,
            target_info=self._target_info,
            target_key=self._target_key,
        )

    def _on_breadcrumb_changed(self, key: str) -> None:
        handle_breadcrumb_changed_v1(
            key=key,
            rebuild_breadcrumb_fn=self._rebuild_breadcrumb,
            emit_back_fn=self.back_clicked.emit,
            emit_navigate_to_control_fn=self.navigate_to_control.emit,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _load_target_payload_sync(self, target_key: str | None = None, *, refresh: bool = False):
        return load_target_payload_sync_runtime_v1(self, target_key=target_key, refresh=refresh)

    def _require_app_context(self):
        return require_page_app_context(
            self,
            parent=self.parent(),
            error_message="AppContext is required for Zapret1 strategy detail page",
        )

    def _request_target_payload(self, target_key: str, *, refresh: bool, reason: str) -> None:
        request_target_payload_runtime_v1(self, target_key, refresh=refresh, reason=reason)

    def _on_target_payload_loaded(self, request_id: int, snapshot, token: int) -> None:
        on_target_payload_loaded_runtime_v1(self, request_id, snapshot, token)

    def _handle_missing_target_payload(self) -> None:
        handle_missing_target_payload_runtime_v1(self)

    def _apply_loaded_header_state(self, normalized_info: dict[str, Any]) -> None:
        apply_loaded_header_state_runtime_v1(self, normalized_info)

    def _clear_strategies_and_rebuild(self) -> None:
        clear_strategies_and_rebuild_runtime_v1(self)

    def _stop_spinner(self) -> None:
        stop_spinner_runtime_v1(self)

    def _apply_loaded_target_payload(self) -> None:
        apply_loaded_target_payload_runtime_v1(self)

    def show_target(self, target_key: str, direct_facade=None) -> None:
        show_target_runtime_v1(self, target_key, direct_facade=direct_facade)

    def on_page_activated(self) -> None:
        activate_page_runtime_v1(self)

    # ------------------------------------------------------------------
    # Data mapping / loading
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_target_info(target_key: str, target_info: Any) -> dict[str, Any]:
        return StrategyDetailPageV1Controller.normalize_target_info(target_key, target_info)

    def _load_current_strategy_id(self) -> str:
        return load_current_strategy_id_runtime_v1(self)

    def _get_target_details(self, target_key: str | None = None):
        return get_target_details_runtime_v1(self, target_key=target_key)

    def _reload_target(self, *_args) -> None:
        reload_target_runtime_v1(self, *_args)

    def _reload_target_error_fallback(self) -> None:
        reload_target_error_fallback_runtime_v1(self)

    def refresh_from_preset_switch(self) -> None:
        refresh_from_preset_switch_runtime_v1(self)

    def _sorted_strategy_items(self) -> list[dict]:
        return StrategyDetailPageV1Controller.sorted_strategy_items(self._strategies, self._sort_mode)

    def _rebuild_tree_rows(self) -> None:
        rebuild_tree_rows_v1(
            tree=self._tree,
            tr_fn=self._tr,
            current_strategy_id=self._current_strategy_id,
            get_current_args_fn=self._get_current_args,
            sorted_strategy_items=self._sorted_strategy_items(),
            apply_sort_mode_fn=self._apply_sort_mode,
            apply_search_filter_fn=self._apply_search_filter,
            empty_label=self._empty_label,
            strategies=self._strategies,
        )

    def _ensure_interaction_stores(self) -> None:
        if self._feedback_store is not None:
            return
        try:
            app_context = self._require_app_context()
        except Exception:
            return
        self._feedback_store = getattr(app_context, "strategy_feedback_store", None)

    def _refresh_marks_and_favorites_for_target(self) -> None:
        self._ensure_interaction_stores()
        tree = self._tree
        target_key = str(self._target_key or "").strip()
        if tree is None or not target_key:
            return

        favorite_ids: set[str] = set()
        if self._feedback_store is not None:
            try:
                favorite_ids = set(self._feedback_store.get_favorites(target_key))
            except Exception:
                favorite_ids = set()
        self._favorite_strategy_ids = set(favorite_ids)

        for strategy_id in list(tree.get_strategy_ids() or []):
            if strategy_id != "none":
                tree.set_favorite_state(strategy_id, strategy_id in favorite_ids)
            if self._feedback_store is None:
                continue
            try:
                state = self._feedback_store.get_mark(target_key, strategy_id)
            except Exception:
                state = None
            tree.set_working_state(strategy_id, state)

    # ------------------------------------------------------------------
    # Header updates
    # ------------------------------------------------------------------

    def _update_header_labels(self) -> None:
        update_header_labels_runtime_v1(self)

    def _update_selected_label(self) -> None:
        update_selected_label_runtime_v1(self)

    # ------------------------------------------------------------------
    # Search / sort controls
    # ------------------------------------------------------------------

    def _on_search_text_changed(self, text: str) -> None:
        on_search_text_changed_runtime_v1(self, text)

    def _on_sort_combo_changed(self, *_args) -> None:
        on_sort_combo_changed_runtime_v1(self, *_args)

    def _apply_sort_mode(self) -> None:
        apply_sort_mode_runtime_v1(self)

    def _apply_search_filter(self) -> None:
        apply_search_filter_runtime_v1(self)

    def _target_supports_filter_switch(self) -> bool:
        return target_supports_filter_switch_runtime_v1(self)

    def _sync_target_controls(self) -> None:
        sync_target_controls_runtime_v1(self)

    def _load_target_filter_mode(self, target_key: str) -> str:
        return load_target_filter_mode_runtime_v1(self, target_key)

    def _on_filter_mode_changed(self, new_mode: str) -> None:
        on_filter_mode_changed_runtime_v1(self, new_mode)

    def _default_strategy_id(self) -> str:
        return default_strategy_id_runtime_v1(self)

    def _on_enable_toggled(self, enabled: bool) -> None:
        on_enable_toggled_runtime_v1(self, enabled)

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    def _on_strategy_selected(self, strategy_id: str) -> None:
        on_strategy_selected_runtime_v1(self, strategy_id)

    def _strategy_display_name(self, strategy_id: str) -> str:
        return strategy_display_name_runtime_v1(self, strategy_id)

    # ------------------------------------------------------------------
    # Args preview / editor
    # ------------------------------------------------------------------

    def _refresh_args_preview(self) -> None:
        refresh_args_preview_runtime_v1(self)

    def _get_current_args(self) -> str:
        return get_current_args_runtime_v1(self)

    def _open_args_editor(self, *_args) -> None:
        open_args_editor_runtime_v1(self)

    def _save_custom_args(self, args_text: str) -> None:
        save_custom_args_runtime_v1(self, args_text)

    def _get_preview_strategy_data(self, strategy_id: str) -> dict:
        return get_preview_strategy_data_runtime_v1(self, strategy_id)

    def _get_preview_rating(self, strategy_id: str, target_key: str):
        return get_preview_rating_runtime_v1(self, strategy_id, target_key)

    def _toggle_preview_rating(self, strategy_id: str, rating: str, target_key: str):
        return toggle_preview_rating_runtime_v1(self, strategy_id, rating, target_key)

    def _close_preview_dialog(self, force: bool = False):
        close_preview_dialog_runtime_v1(self, force=force)

    def close_transient_overlays(self) -> None:
        close_transient_overlays_runtime_v1(self)

    def _on_preview_closed(self) -> None:
        on_preview_closed_runtime_v1(self)

    def _ensure_preview_dialog(self):
        return ensure_preview_dialog_runtime_v1(self)

    def _show_preview_dialog(self, strategy_id: str, global_pos) -> None:
        show_preview_dialog_runtime_v1(self, strategy_id, global_pos)

    def _on_tree_preview_requested(self, strategy_id: str, global_pos):
        on_tree_preview_requested_runtime_v1(self, strategy_id, global_pos)

    def _on_tree_preview_pinned_requested(self, strategy_id: str, global_pos):
        on_tree_preview_pinned_requested_runtime_v1(self, strategy_id, global_pos)

    def _on_tree_preview_hide_requested(self) -> None:
        on_tree_preview_hide_requested_runtime_v1(self)

    def _on_tree_working_mark_requested(self, strategy_id: str, is_working):
        on_tree_working_mark_requested_runtime_v1(self, strategy_id, is_working)

    def _on_favorite_toggled(self, strategy_id: str, is_favorite: bool) -> None:
        on_favorite_toggled_runtime_v1(self, strategy_id, is_favorite)

    # ------------------------------------------------------------------
    # Feedback indicators
    # ------------------------------------------------------------------

    def show_loading(self) -> None:
        show_loading_runtime_v1(self)

    def show_success(self) -> None:
        show_success_runtime_v1(self)

    def _hide_success(self) -> None:
        hide_success_runtime_v1(self)

    def bind_ui_state_store(self, store: MainWindowStateStore) -> None:
        bind_ui_state_store_v1(
            current_store=self._ui_state_store,
            store=store,
            current_unsubscribe=self._ui_state_unsubscribe,
            set_store_fn=lambda value: setattr(self, "_ui_state_store", value),
            set_unsubscribe_fn=lambda value: setattr(self, "_ui_state_unsubscribe", value),
            on_ui_state_changed=self._on_ui_state_changed,
        )

    def _on_ui_state_changed(self, _state: AppUiState, changed_fields: frozenset[str]) -> None:
        handle_ui_state_changed_v1(
            cleanup_in_progress=self._cleanup_in_progress,
            changed_fields=changed_fields,
            refresh_from_preset_switch_fn=self.refresh_from_preset_switch,
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_strategy_detail_v1_language(
            tr_fn=self._tr,
            target_key=self._target_key,
            back_btn=self._back_btn,
            title_label=self._title_label,
            state_label=self._state_label,
            enable_toggle=self._enable_toggle,
            filter_label=self._filter_label,
            filter_mode_selector=self._filter_mode_selector,
            search_edit=self._search_edit,
            sort_combo=self._sort_combo,
            sort_mode=self._sort_mode,
            edit_args_btn=self._edit_args_btn,
            list_card=self._list_card,
            empty_label=self._empty_label,
            rebuild_breadcrumb_fn=self._rebuild_breadcrumb,
            update_header_labels_fn=self._update_header_labels,
            rebuild_tree_rows_fn=self._rebuild_tree_rows,
            refresh_args_preview_fn=self._refresh_args_preview,
        )

    def cleanup(self) -> None:
        try:
            self._close_preview_dialog(force=True)
        except Exception:
            pass
        cleanup_page_v1(
            set_cleanup_in_progress_fn=lambda value: setattr(self, "_cleanup_in_progress", value),
            clear_preset_refresh_pending_fn=lambda: setattr(self, "_preset_refresh_pending", False),
            increment_request_id_fn=lambda: setattr(self, "_target_payload_request_id", self._target_payload_request_id + 1),
            success_timer=self._success_timer,
            current_unsubscribe=self._ui_state_unsubscribe,
            set_unsubscribe_fn=lambda value: setattr(self, "_ui_state_unsubscribe", value),
            set_store_fn=lambda value: setattr(self, "_ui_state_store", value),
        )
