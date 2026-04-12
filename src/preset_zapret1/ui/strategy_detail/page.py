# preset_zapret1/ui/strategy_detail/page.py
"""Zapret 1 strategy detail page with Zapret 2-style layout."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from core.runtime.direct_ui_snapshot_service import DirectTargetDetailSnapshotWorker
from ui.pages.base_page import BasePage
from ui.compat_widgets import ActionButton, RefreshButton, SettingsCard
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.widgets.direct_zapret2_strategies_tree import DirectZapret2StrategiesTree
from ui.text_catalog import tr as tr_catalog
from core.presets.ui.strategy_detail_shared import (
    build_detail_subtitle_widgets,
    build_strategies_tree_widget,
    run_args_editor_dialog,
)
from preset_zapret2.ui.strategy_detail.apply import apply_tree_selected_strategy_state
from preset_zapret1.ui.strategy_detail.controller import StrategyDetailPageV1Controller
from preset_zapret1.ui.strategy_detail.build import build_strategy_detail_v1_main_sections
from preset_zapret1.ui.strategy_detail.build import build_strategy_detail_v1_header
from preset_zapret1.ui.strategy_detail.args import ArgsEditorDialogV1
from preset_zapret1.ui.strategy_detail.args_workflow import (
    open_args_editor_dialog_v1,
    save_custom_args_v1,
)
from preset_zapret1.ui.strategy_detail.data_helpers import (
    get_target_details_v1,
    load_current_strategy_id_v1,
    load_target_filter_mode_v1,
    load_target_payload_sync_v1,
    require_app_context_v1,
    target_supports_filter_switch_v1,
)
from preset_zapret1.ui.strategy_detail.feedback_helpers import (
    hide_success_feedback_v1,
    show_loading_feedback_v1,
    show_success_feedback_v1,
)
from preset_zapret1.ui.strategy_detail.filtering_helpers import (
    apply_search_filter_v1,
    apply_sort_mode_v1,
    normalize_search_text,
    rebuild_tree_rows_v1,
    resolve_sort_mode_change,
)
from preset_zapret1.ui.strategy_detail.payload_workflow import (
    apply_loaded_target_payload_v1,
    apply_missing_payload_v1,
    apply_preset_refresh_v1,
    handle_loaded_payload_v1,
    start_target_payload_request_v1,
)
from preset_zapret1.ui.strategy_detail.page_workflow import (
    activate_page_v1,
    bind_ui_state_store_v1,
    cleanup_page_v1,
    handle_breadcrumb_changed_v1,
    handle_ui_state_changed_v1,
    rebuild_breadcrumb_v1,
    reload_target_v1,
    show_target_v1,
)
from preset_zapret1.ui.strategy_detail.selection_workflow import (
    handle_enable_toggle_v1,
    handle_filter_mode_change_v1,
    handle_strategy_selection_v1,
)
from preset_zapret1.ui.strategy_detail.runtime_helpers import (
    apply_strategy_detail_v1_language,
    refresh_args_preview,
    sync_target_controls,
    update_header_labels,
    update_selected_label,
)
from log import log

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
        self._pending_target_key: str = ""
        self._preset_refresh_pending = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._cleanup_in_progress = False

        self._strategies: dict[str, dict] = {}
        self._current_strategy_id: str = "none"
        self._sort_mode: str = "recommended"  # recommended | alpha_asc | alpha_desc
        self._search_text: str = ""

        self._breadcrumb = None
        self._tree: DirectZapret2StrategiesTree | None = None
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
            direct_tree_cls=DirectZapret2StrategiesTree,
            on_enable_toggled=self._on_enable_toggled,
            on_filter_mode_changed=self._on_filter_mode_changed,
            on_reload_target=self._reload_target,
            on_search_text_changed=self._on_search_text_changed,
            on_sort_combo_changed=self._on_sort_combo_changed,
            on_open_args_editor=self._open_args_editor,
            on_strategy_selected=self._on_strategy_selected,
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
        return load_target_payload_sync_v1(
            target_key=target_key,
            current_target_key=self._target_key,
            require_app_context_fn=self._require_app_context,
            set_payload_fn=lambda payload: setattr(self, "_target_payload", payload),
            refresh=refresh,
        )

    def _require_app_context(self):
        return require_app_context_v1(self.window())

    def _request_target_payload(self, target_key: str, *, refresh: bool, reason: str) -> None:
        request_state = start_target_payload_request_v1(
            cleanup_in_progress=self._cleanup_in_progress,
            target_key=target_key,
            reason=reason,
            refresh=refresh,
            current_request_id=self._target_payload_request_id,
            issue_page_load_token_fn=self.issue_page_load_token,
            require_app_context_fn=self._require_app_context,
            worker_cls=DirectTargetDetailSnapshotWorker,
            parent=self,
            on_loaded_callback=self._on_target_payload_loaded,
            show_loading_fn=self.show_loading,
        )
        if request_state is None:
            return

        normalized_key, request_id, worker = request_state
        self._target_key = normalized_key
        self._target_payload_request_id = request_id
        self._target_payload_worker = worker
        worker.start()

    def _on_target_payload_loaded(self, request_id: int, snapshot, token: int) -> None:
        handle_loaded_payload_v1(
            cleanup_in_progress=self._cleanup_in_progress,
            request_id=request_id,
            snapshot=snapshot,
            token=token,
            current_request_id=self._target_payload_request_id,
            is_page_load_token_current_fn=self.is_page_load_token_current,
            refresh_btn=self._refresh_btn,
            on_missing_payload_fn=self._handle_missing_target_payload,
            set_payload_fn=lambda payload: setattr(self, "_target_payload", payload),
            normalize_target_info_fn=self._normalize_target_info,
            target_key=self._target_key,
            load_current_strategy_id_fn=self._load_current_strategy_id,
            set_current_strategy_id_fn=lambda value: setattr(self, "_current_strategy_id", value),
            set_last_enabled_strategy_id_fn=lambda value: setattr(self, "_last_enabled_strategy_id", value),
            update_header_labels_fn=self._apply_loaded_header_state,
            rebuild_breadcrumb_fn=self._rebuild_breadcrumb,
            apply_loaded_target_payload_fn=self._apply_loaded_target_payload,
        )

    def _handle_missing_target_payload(self) -> None:
        apply_missing_payload_v1(
            refresh_btn=self._refresh_btn,
            stop_spinner_fn=self._stop_spinner,
            clear_strategies_and_rebuild_fn=self._clear_strategies_and_rebuild,
            refresh_args_preview_fn=self._refresh_args_preview,
            update_selected_label_fn=self._update_selected_label,
            sync_target_controls_fn=self._sync_target_controls,
            hide_success_fn=self._hide_success,
        )

    def _apply_loaded_header_state(self, normalized_info: dict[str, Any]) -> None:
        self._target_info = normalized_info
        self._update_header_labels()

    def _clear_strategies_and_rebuild(self) -> None:
        self._strategies = {}
        self._rebuild_tree_rows()

    def _stop_spinner(self) -> None:
        if self._spinner is not None:
            try:
                if hasattr(self._spinner, "stop"):
                    self._spinner.stop()
            except Exception:
                pass
            self._spinner.hide()

    def _apply_loaded_target_payload(self) -> None:
        apply_loaded_target_payload_v1(
            payload=getattr(self, "_target_payload", None),
            set_strategies_fn=lambda value: setattr(self, "_strategies", value),
            rebuild_tree_rows_fn=self._rebuild_tree_rows,
            refresh_args_preview_fn=self._refresh_args_preview,
            update_selected_label_fn=self._update_selected_label,
            sync_target_controls_fn=self._sync_target_controls,
            show_success_fn=self.show_success,
        )

    def show_target(self, target_key: str, direct_facade=None) -> None:
        show_target_v1(
            cleanup_in_progress=self._cleanup_in_progress,
            target_key=target_key,
            direct_facade=direct_facade,
            current_direct_facade=self._direct_facade,
            require_app_context_fn=self._require_app_context,
            is_visible=self.isVisible(),
            set_direct_facade_fn=lambda value: setattr(self, "_direct_facade", value),
            set_pending_target_key_fn=lambda value: setattr(self, "_pending_target_key", value),
            request_target_payload_fn=self._request_target_payload,
        )

    def on_page_activated(self) -> None:
        activate_page_v1(
            cleanup_in_progress=self._cleanup_in_progress,
            pending_target_key=self._pending_target_key,
            target_key=self._target_key,
            preset_refresh_pending=self._preset_refresh_pending,
            set_pending_target_key_fn=lambda value: setattr(self, "_pending_target_key", value),
            clear_preset_refresh_pending_fn=lambda: setattr(self, "_preset_refresh_pending", False),
            request_target_payload_fn=self._request_target_payload,
            rebuild_breadcrumb_fn=self._rebuild_breadcrumb,
            single_shot_fn=QTimer.singleShot,
            refresh_from_preset_switch_fn=lambda: (not self._cleanup_in_progress) and self.refresh_from_preset_switch(),
        )

    # ------------------------------------------------------------------
    # Data mapping / loading
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_target_info(target_key: str, target_info: Any) -> dict[str, Any]:
        return StrategyDetailPageV1Controller.normalize_target_info(target_key, target_info)

    def _load_current_strategy_id(self) -> str:
        return load_current_strategy_id_v1(
            direct_facade=self._direct_facade,
            target_key=self._target_key,
            get_target_details_fn=self._get_target_details,
        )

    def _get_target_details(self, target_key: str | None = None):
        return get_target_details_v1(
            target_key=target_key,
            current_target_key=self._target_key,
            direct_facade=self._direct_facade,
            current_payload=getattr(self, "_target_payload", None),
            load_target_payload_sync_fn=self._load_target_payload_sync,
        )

    def _reload_target(self, *_args) -> None:
        reload_target_v1(
            target_key=self._target_key,
            refresh_btn=self._refresh_btn,
            request_target_payload_fn=self._request_target_payload,
            on_error_fallback_fn=self._reload_target_error_fallback,
            log_fn=log,
        )

    def _reload_target_error_fallback(self) -> None:
        self._strategies = {}
        self._rebuild_tree_rows()
        self._refresh_args_preview()
        self._update_selected_label()
        self._sync_target_controls()
        self._hide_success()

    def refresh_from_preset_switch(self) -> None:
        """Перечитывает текущий target после смены активного source preset."""
        self._preset_refresh_pending = False
        apply_preset_refresh_v1(
            cleanup_in_progress=self._cleanup_in_progress,
            is_visible=self.isVisible(),
            target_key=self._target_key,
            mark_pending_fn=lambda: setattr(self, "_preset_refresh_pending", True),
            request_payload_fn=self._request_target_payload,
        )

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

    # ------------------------------------------------------------------
    # Header updates
    # ------------------------------------------------------------------

    def _update_header_labels(self) -> None:
        update_header_labels(
            title_label=self._title_label,
            desc_label=self._desc_label,
            subtitle_label=self._subtitle_label,
            tr_fn=self._tr,
            target_info=self._target_info,
            target_key=self._target_key,
            update_selected_label_fn=self._update_selected_label,
        )

    def _update_selected_label(self) -> None:
        update_selected_label(
            selected_label=self._selected_label,
            tr_fn=self._tr,
            current_strategy_id=self._current_strategy_id,
            strategy_display_name_fn=self._strategy_display_name,
        )

    # ------------------------------------------------------------------
    # Search / sort controls
    # ------------------------------------------------------------------

    def _on_search_text_changed(self, text: str) -> None:
        self._search_text = normalize_search_text(text)
        self._apply_search_filter()

    def _on_sort_combo_changed(self, *_args) -> None:
        mode = resolve_sort_mode_change(
            sort_combo=self._sort_combo,
            current_sort_mode=self._sort_mode,
        )
        if mode is None:
            return
        self._sort_mode = mode
        self._rebuild_tree_rows()

    def _apply_sort_mode(self) -> None:
        apply_sort_mode_v1(
            tree=self._tree,
            sort_mode=self._sort_mode,
        )

    def _apply_search_filter(self) -> None:
        apply_search_filter_v1(
            tree=self._tree,
            search_text=self._search_text,
        )

    def _target_supports_filter_switch(self) -> bool:
        return target_supports_filter_switch_v1(self._target_info)

    def _sync_target_controls(self) -> None:
        sync_target_controls(
            enable_toggle=self._enable_toggle,
            edit_args_btn=self._edit_args_btn,
            filter_mode_frame=self._filter_mode_frame,
            filter_mode_selector=self._filter_mode_selector,
            current_strategy_id=self._current_strategy_id,
            target_key=self._target_key,
            target_supports_filter_switch_fn=self._target_supports_filter_switch,
            load_target_filter_mode_fn=self._load_target_filter_mode,
        )

    def _load_target_filter_mode(self, target_key: str) -> str:
        return load_target_filter_mode_v1(
            direct_facade=self._direct_facade,
            target_key=target_key,
            current_payload=getattr(self, "_target_payload", None),
        )

    def _on_filter_mode_changed(self, new_mode: str) -> None:
        handle_filter_mode_change_v1(
            direct_facade=self._direct_facade,
            target_key=self._target_key,
            new_mode=new_mode,
            tr_fn=self._tr,
            info_bar_cls=InfoBar,
            has_fluent=_HAS_FLUENT,
            parent_window=self.window(),
            log_fn=log,
            sync_target_controls_fn=self._sync_target_controls,
        )

    def _default_strategy_id(self) -> str:
        return StrategyDetailPageV1Controller.default_strategy_id(self._strategies, self._sort_mode)

    def _on_enable_toggled(self, enabled: bool) -> None:
        handle_enable_toggle_v1(
            direct_facade=self._direct_facade,
            target_key=self._target_key,
            enabled=enabled,
            last_enabled_strategy_id=self._last_enabled_strategy_id,
            default_strategy_id_fn=self._default_strategy_id,
            enable_toggle=self._enable_toggle,
            sync_target_controls_fn=self._sync_target_controls,
            select_strategy_fn=self._on_strategy_selected,
            current_strategy_id=self._current_strategy_id,
            set_last_enabled_strategy_id_fn=lambda value: setattr(self, "_last_enabled_strategy_id", value),
        )

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    def _on_strategy_selected(self, strategy_id: str) -> None:
        handle_strategy_selection_v1(
            direct_facade=self._direct_facade,
            target_key=self._target_key,
            strategy_id=strategy_id,
            show_loading_fn=self.show_loading,
            set_current_strategy_id_fn=lambda value: setattr(self, "_current_strategy_id", value),
            set_last_enabled_strategy_id_fn=lambda value: setattr(self, "_last_enabled_strategy_id", value),
            update_selected_label_fn=self._update_selected_label,
            refresh_args_preview_fn=self._refresh_args_preview,
            sync_target_controls_fn=self._sync_target_controls,
            apply_tree_selected_strategy_state_fn=apply_tree_selected_strategy_state,
            tree=self._tree,
            emit_strategy_selected_fn=self.strategy_selected.emit,
            log_fn=log,
            has_fluent=_HAS_FLUENT,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            strategy_display_name_fn=self._strategy_display_name,
            parent_window=self.window(),
            show_success_fn=self.show_success,
            reload_target_fn=self._reload_target,
        )

    def _strategy_display_name(self, strategy_id: str) -> str:
        return StrategyDetailPageV1Controller.strategy_display_name(strategy_id, self._strategies, self._tr)

    # ------------------------------------------------------------------
    # Args preview / editor
    # ------------------------------------------------------------------

    def _refresh_args_preview(self) -> None:
        refresh_args_preview(
            args_preview_label=self._args_preview_label,
            tr_fn=self._tr,
            get_current_args_fn=self._get_current_args,
        )

    def _get_current_args(self) -> str:
        if not self._direct_facade or not self._target_key:
            return ""
        payload = getattr(self, "_target_payload", None)
        if payload is not None and str(getattr(payload, "target_key", "") or "") == self._target_key:
            return str(getattr(payload, "raw_args_text", "") or "").strip()
        payload = self._load_target_payload_sync(self._target_key, refresh=False)
        if payload is not None:
            return str(getattr(payload, "raw_args_text", "") or "").strip()
        return ""

    def _open_args_editor(self, *_args) -> None:
        open_args_editor_dialog_v1(
            has_fluent=_HAS_FLUENT,
            current_strategy_id=self._current_strategy_id,
            get_current_args_fn=self._get_current_args,
            parent=self.window(),
            language=self._ui_language,
            run_args_editor_dialog_fn=lambda **kwargs: run_args_editor_dialog(
                dialog_cls=ArgsEditorDialogV1,
                **kwargs,
            ),
            apply_args_fn=self._save_custom_args,
            log_fn=log,
        )

    def _save_custom_args(self, args_text: str) -> None:
        save_custom_args_v1(
            direct_facade=self._direct_facade,
            target_key=self._target_key,
            args_text=args_text,
            load_target_payload_sync_fn=self._load_target_payload_sync,
            set_current_strategy_id_fn=lambda value: setattr(self, "_current_strategy_id", value),
            set_last_enabled_strategy_id_fn=lambda value: setattr(self, "_last_enabled_strategy_id", value),
            emit_strategy_selected_fn=self.strategy_selected.emit,
            sync_target_controls_fn=self._sync_target_controls,
            has_fluent=_HAS_FLUENT,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
            request_target_payload_fn=self._request_target_payload,
            log_fn=log,
        )

    # ------------------------------------------------------------------
    # Feedback indicators
    # ------------------------------------------------------------------

    def show_loading(self) -> None:
        show_loading_feedback_v1(
            cleanup_in_progress=self._cleanup_in_progress,
            spinner=self._spinner,
            success_icon=self._success_icon,
        )

    def show_success(self) -> None:
        try:
            from ui.theme import get_cached_qta_pixmap

            success_pixmap = get_cached_qta_pixmap("fa5s.check-circle", color="#6ccb5f", size=16)
        except Exception:
            success_pixmap = None

        show_success_feedback_v1(
            cleanup_in_progress=self._cleanup_in_progress,
            spinner=self._spinner,
            success_icon=self._success_icon,
            success_timer=self._success_timer,
            success_pixmap=success_pixmap,
        )

    def _hide_success(self) -> None:
        hide_success_feedback_v1(
            cleanup_in_progress=self._cleanup_in_progress,
            spinner=self._spinner,
            success_icon=self._success_icon,
        )

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
        cleanup_page_v1(
            set_cleanup_in_progress_fn=lambda value: setattr(self, "_cleanup_in_progress", value),
            set_pending_target_key_fn=lambda value: setattr(self, "_pending_target_key", value),
            clear_preset_refresh_pending_fn=lambda: setattr(self, "_preset_refresh_pending", False),
            increment_request_id_fn=lambda: setattr(self, "_target_payload_request_id", self._target_payload_request_id + 1),
            success_timer=self._success_timer,
            current_unsubscribe=self._ui_state_unsubscribe,
            set_unsubscribe_fn=lambda value: setattr(self, "_ui_state_unsubscribe", value),
            set_store_fn=lambda value: setattr(self, "_ui_state_store", value),
        )
