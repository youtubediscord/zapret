# ui/pages/zapret1/strategy_detail_page_v1.py
"""Zapret 1 strategy detail page with Zapret 2-style layout."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QFont

from core.runtime.direct_ui_snapshot_service import DirectTargetDetailSnapshotWorker
from ui.pages.base_page import BasePage
from ui.compat_widgets import ActionButton, RefreshButton, SettingsCard
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.widgets.direct_zapret2_strategies_tree import DirectZapret2StrategiesTree, StrategyTreeRow
from ui.text_catalog import tr as tr_catalog
from ui.smooth_scroll import apply_editor_smooth_scroll_preference
from ui.pages.strategy_detail_components import (
    build_detail_subtitle_widgets,
    build_strategies_tree_widget,
    run_args_editor_dialog,
)
from ui.pages.zapret2.strategy_detail_apply import (
    apply_loading_indicator_state,
    apply_tree_selected_strategy_state,
)
from ui.pages.zapret1.strategy_detail_page_v1_controller import StrategyDetailPageV1Controller
from log import log

try:
    from qfluentwidgets import (
        BodyLabel,
        CaptionLabel,
        StrongBodyLabel,
        TitleLabel,
        SubtitleLabel,
        LineEdit,
        ComboBox,
        TextEdit,
        BreadcrumbBar,
        MessageBoxBase,
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
        QLabel as StrongBodyLabel,
        QLabel as TitleLabel,
        QLabel as SubtitleLabel,
        QLineEdit as LineEdit,
        QComboBox as ComboBox,
        QTextEdit as TextEdit,
        QDialog as MessageBoxBase,
        QCheckBox as SwitchButton,
    )

    BreadcrumbBar = None  # type: ignore
    IndeterminateProgressRing = QWidget  # type: ignore
    PixmapLabel = QLabel  # type: ignore
    InfoBar = None  # type: ignore
    TransparentPushButton = QPushButton  # type: ignore
    _HAS_FLUENT = False

try:
    import qtawesome as qta

    _HAS_QTA = True
except ImportError:
    qta = None  # type: ignore
    _HAS_QTA = False


class _ArgsEditorDialog(MessageBoxBase):  # type: ignore[misc, valid-type]
    """Диалог ручного редактирования аргументов стратегии."""

    def __init__(self, initial_text: str = "", parent=None, language: str = "ru"):
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            text = tr_catalog(key, language=self._ui_language, default=default)
            if kwargs:
                try:
                    return text.format(**kwargs)
                except Exception:
                    return text
            return text

        self._tr = _tr

        if not _HAS_FLUENT:
            return

        self._title_lbl = SubtitleLabel(
            self._tr("page.z1_strategy_detail.args_dialog.title", "Аргументы стратегии")
        )
        self.viewLayout.addWidget(self._title_lbl)

        hint = CaptionLabel(
            self._tr(
                "page.z1_strategy_detail.args_dialog.hint",
                "Один аргумент на строку. Изменяет только выбранный target.",
            )
        )
        self.viewLayout.addWidget(hint)

        self._text_edit = TextEdit()
        apply_editor_smooth_scroll_preference(self._text_edit)
        self._text_edit.setPlaceholderText(
            self._tr(
                "page.z1_strategy_detail.args_dialog.placeholder",
                "Например:\n--dpi-desync=multisplit\n--dpi-desync-split-pos=1",
            )
        )
        self._text_edit.setMinimumWidth(460)
        self._text_edit.setMinimumHeight(150)
        self._text_edit.setMaximumHeight(260)
        self._text_edit.setFont(QFont("Consolas", 10))
        self._text_edit.setPlainText(initial_text)
        self.viewLayout.addWidget(self._text_edit)

        self.yesButton.setText(self._tr("page.z1_strategy_detail.args_dialog.button.save", "Сохранить"))
        self.cancelButton.setText(self._tr("page.z1_strategy_detail.args_dialog.button.cancel", "Отмена"))

    def validate(self) -> bool:
        return True

    def get_text(self) -> str:
        if hasattr(self, "_text_edit"):
            return self._text_edit.toPlainText()
        return ""


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

        # Header with breadcrumb + title/subtitle
        header = QFrame()
        header.setFrameShape(QFrame.Shape.NoFrame)
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 10)
        header_layout.setSpacing(4)

        self._setup_breadcrumb()
        if self._breadcrumb is not None:
            header_layout.addWidget(self._breadcrumb)

        self._title_label = TitleLabel(
            self._tr("page.z1_strategy_detail.header.category_fallback", "Target")
        )
        header_layout.addWidget(self._title_label)

        subtitle_widgets = build_detail_subtitle_widgets(
            parent=self,
            body_label_cls=BodyLabel,
            spinner_cls=IndeterminateProgressRing if _HAS_FLUENT else QWidget,
            pixmap_label_cls=PixmapLabel,
            subtitle_strategy_label_cls=CaptionLabel,
            detail_text_color="#9aa2af",
        )
        self._spinner = subtitle_widgets.spinner
        self._success_icon = subtitle_widgets.success_icon
        self._subtitle_label = subtitle_widgets.subtitle_label
        self._selected_label = subtitle_widgets.subtitle_strategy_label
        self._selected_label.setFont(QFont("Segoe UI", 10))
        header_layout.addWidget(subtitle_widgets.container_widget)

        self._desc_label = BodyLabel("")
        self._desc_label.setWordWrap(True)
        header_layout.addWidget(self._desc_label)

        self.add_widget(header)

        # Toolbar card
        toolbar_card = SettingsCard()
        toolbar_layout = QVBoxLayout()
        toolbar_layout.setSpacing(8)

        state_row = QHBoxLayout()
        state_row.setSpacing(8)

        state_label = BodyLabel(
            self._tr("page.z1_strategy_detail.state.category_bypass", "Обход для target'а")
        )
        self._state_label = state_label
        state_row.addWidget(state_label)

        self._enable_toggle = SwitchButton(parent=self)
        if hasattr(self._enable_toggle, "setOnText"):
            self._enable_toggle.setOnText(self._tr("page.z1_strategy_detail.toggle.on", "Включено"))
        if hasattr(self._enable_toggle, "setOffText"):
            self._enable_toggle.setOffText(self._tr("page.z1_strategy_detail.toggle.off", "Выключено"))
        if hasattr(self._enable_toggle, "checkedChanged"):
            self._enable_toggle.checkedChanged.connect(self._on_enable_toggled)
        else:
            self._enable_toggle.toggled.connect(self._on_enable_toggled)
        state_row.addWidget(self._enable_toggle)

        self._filter_mode_frame = QWidget()
        filter_row = QHBoxLayout(self._filter_mode_frame)
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(6)
        self._filter_label = CaptionLabel(self._tr("page.z1_strategy_detail.filter.label", "Фильтр:"))
        filter_row.addWidget(self._filter_label)

        self._filter_mode_selector = SwitchButton(parent=self)
        if hasattr(self._filter_mode_selector, "setOnText"):
            self._filter_mode_selector.setOnText(self._tr("page.z1_strategy_detail.filter.ipset", "IPset"))
        if hasattr(self._filter_mode_selector, "setOffText"):
            self._filter_mode_selector.setOffText(self._tr("page.z1_strategy_detail.filter.hostlist", "Hostlist"))
        if hasattr(self._filter_mode_selector, "checkedChanged"):
            self._filter_mode_selector.checkedChanged.connect(
                lambda checked: self._on_filter_mode_changed("ipset" if checked else "hostlist")
            )
        else:
            self._filter_mode_selector.toggled.connect(
                lambda checked: self._on_filter_mode_changed("ipset" if checked else "hostlist")
            )
        filter_row.addWidget(self._filter_mode_selector)
        self._filter_mode_frame.hide()
        state_row.addWidget(self._filter_mode_frame)
        state_row.addStretch(1)

        toolbar_layout.addLayout(state_row)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self._refresh_btn = RefreshButton()
        self._refresh_btn.clicked.connect(self._reload_target)
        controls_row.addWidget(self._refresh_btn)

        self._search_edit = LineEdit()
        self._search_edit.setPlaceholderText(
            self._tr(
                "page.z1_strategy_detail.search.placeholder",
                "Поиск стратегии по названию или аргументам",
            )
        )
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        controls_row.addWidget(self._search_edit, 1)

        self._sort_combo = ComboBox()
        self._sort_combo.addItem(
            self._tr("page.z1_strategy_detail.sort.recommended", "По рекомендации"),
            userData="recommended",
        )
        self._sort_combo.addItem(
            self._tr("page.z1_strategy_detail.sort.alpha_asc", "По алфавиту A-Z"),
            userData="alpha_asc",
        )
        self._sort_combo.addItem(
            self._tr("page.z1_strategy_detail.sort.alpha_desc", "По алфавиту Z-A"),
            userData="alpha_desc",
        )
        self._sort_combo.currentIndexChanged.connect(self._on_sort_combo_changed)
        controls_row.addWidget(self._sort_combo)

        self._edit_args_btn = ActionButton(
            self._tr("page.z1_strategy_detail.button.edit_args", "Редактировать аргументы"),
            "fa5s.edit",
        )
        self._edit_args_btn.clicked.connect(self._open_args_editor)
        controls_row.addWidget(self._edit_args_btn)

        toolbar_layout.addLayout(controls_row)

        self._args_preview_label = CaptionLabel(
            self._tr("page.z1_strategy_detail.args.none", "(нет аргументов)")
        )
        self._args_preview_label.setWordWrap(True)
        self._args_preview_label.setFont(QFont("Consolas", 9))
        toolbar_layout.addWidget(self._args_preview_label)

        toolbar_card.add_layout(toolbar_layout)
        self._toolbar_card = toolbar_card
        self.add_widget(toolbar_card)

        # Strategies tree card
        list_card = SettingsCard(self._tr("page.z1_strategy_detail.card.strategies", "Стратегии"))
        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)

        self._tree = build_strategies_tree_widget(
            parent=self,
            tree_cls=DirectZapret2StrategiesTree,
            on_row_clicked=self._on_strategy_selected,
            on_favorite_toggled=lambda *_args: None,
            on_working_mark_requested=lambda *_args: None,
            on_preview_requested=lambda *_args: None,
            on_preview_pinned_requested=lambda *_args: None,
            on_preview_hide_requested=lambda: None,
        )
        list_layout.addWidget(self._tree, 1)

        self._empty_label = CaptionLabel(
            self._tr(
                "page.z1_strategy_detail.empty.no_strategies",
                "Нет доступных стратегий. Проверьте %APPDATA%\\zapret\\direct_zapret1\\",
            )
        )
        self._empty_label.setWordWrap(True)
        self._empty_label.hide()
        list_layout.addWidget(self._empty_label)

        list_card.add_layout(list_layout)
        self._list_card = list_card
        self.add_widget(list_card, 1)

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
        if self._breadcrumb is None:
            return

        target_title = self._target_info.get("full_name", self._target_key) if self._target_key else "Target"
        self._breadcrumb.blockSignals(True)
        try:
            self._breadcrumb.clear()
            self._breadcrumb.addItem(
                "control",
                self._tr("page.z1_strategy_detail.breadcrumb.control", "Управление"),
            )
            self._breadcrumb.addItem(
                "strategies",
                self._tr("page.z1_strategy_detail.breadcrumb.strategies", "Прямой запуск Zapret 1"),
            )
            self._breadcrumb.addItem("detail", target_title)
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_changed(self, key: str) -> None:
        self._rebuild_breadcrumb()
        if key == "strategies":
            self.back_clicked.emit()
        elif key == "control":
            self.navigate_to_control.emit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _load_target_payload_sync(self, target_key: str | None = None, *, refresh: bool = False):
        key = str(target_key or self._target_key or "").strip().lower()
        if not key:
            return None
        try:
            payload = self._get_direct_ui_snapshot_service().load_target_detail_payload(
                "direct_zapret1",
                key,
                refresh=refresh,
            )
        except Exception:
            return None
        if payload is not None and str(getattr(payload, "target_key", "") or "").strip().lower() == key:
            self._target_payload = payload
        return payload

    def _get_direct_ui_snapshot_service(self):
        app_context = getattr(self.window(), "app_context", None)
        service = getattr(app_context, "direct_ui_snapshot_service", None)
        if service is None:
            from core.services import get_direct_ui_snapshot_service

            service = get_direct_ui_snapshot_service()
        return service

    def _request_target_payload(self, target_key: str, *, refresh: bool, reason: str) -> None:
        normalized_key = str(target_key or "").strip().lower()
        if not normalized_key:
            return
        token = self.issue_page_load_token(reason=f"{reason}:{normalized_key}")
        self._target_payload_request_id += 1
        request_id = self._target_payload_request_id
        self._target_key = normalized_key
        self.show_loading()
        worker = DirectTargetDetailSnapshotWorker(
            request_id,
            launch_method="direct_zapret1",
            target_key=normalized_key,
            refresh=refresh,
            parent=self,
        )
        worker.loaded.connect(
            lambda loaded_request_id, snapshot, load_token=token: self._on_target_payload_loaded(
                loaded_request_id,
                snapshot,
                load_token,
            )
        )
        self._target_payload_worker = worker
        worker.start()

    def _on_target_payload_loaded(self, request_id: int, snapshot, token: int) -> None:
        if request_id != self._target_payload_request_id:
            return
        if not self.is_page_load_token_current(token):
            return
        if self._refresh_btn:
            self._refresh_btn.set_loading(False)
        payload = getattr(snapshot, "payload", None)
        if payload is None:
            self._strategies = {}
            self._rebuild_tree_rows()
            self._refresh_args_preview()
            self._update_selected_label()
            self._sync_target_controls()
            if self._spinner is not None:
                try:
                    if hasattr(self._spinner, "stop"):
                        self._spinner.stop()
                except Exception:
                    pass
                self._spinner.hide()
            self._hide_success()
            return
        self._target_payload = payload
        target_info = getattr(payload, "target_item", None)
        self._target_info = self._normalize_target_info(self._target_key, target_info)
        self._current_strategy_id = self._load_current_strategy_id()
        if self._current_strategy_id and self._current_strategy_id != "none":
            self._last_enabled_strategy_id = self._current_strategy_id
        self._update_header_labels()
        self._rebuild_breadcrumb()
        self._apply_loaded_target_payload()

    def _apply_loaded_target_payload(self) -> None:
        payload = getattr(self, "_target_payload", None)
        if payload is not None:
            self._strategies = dict(getattr(payload, "strategy_entries", {}) or {})
        else:
            self._strategies = {}
        self._rebuild_tree_rows()
        self._refresh_args_preview()
        self._update_selected_label()
        self._sync_target_controls()
        self.show_success()

    def show_target(self, target_key: str, direct_facade=None) -> None:
        normalized_target_key = str(target_key or "").strip().lower()
        if not normalized_target_key:
            return
        if direct_facade is not None:
            self._direct_facade = direct_facade
        if self._direct_facade is None:
            try:
                from core.presets.direct_facade import DirectPresetFacade

                self._direct_facade = DirectPresetFacade.from_launch_method("direct_zapret1")
            except Exception:
                self._direct_facade = None
        if not self.isVisible():
            self._pending_target_key = normalized_target_key
            return
        self._pending_target_key = ""
        self._request_target_payload(normalized_target_key, refresh=False, reason="show_target")

    def on_page_activated(self) -> None:
        pending_target_key = str(getattr(self, "_pending_target_key", "") or "").strip().lower()
        if pending_target_key:
            self._pending_target_key = ""
            self._request_target_payload(pending_target_key, refresh=False, reason="show_target")
            return
        self._rebuild_breadcrumb()
        if self._target_key and self._preset_refresh_pending:
            self._preset_refresh_pending = False
            QTimer.singleShot(0, self.refresh_from_preset_switch)

    # ------------------------------------------------------------------
    # Data mapping / loading
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_target_info(target_key: str, target_info: Any) -> dict[str, Any]:
        return StrategyDetailPageV1Controller.normalize_target_info(target_key, target_info)

    def _load_current_strategy_id(self) -> str:
        if not self._direct_facade or not self._target_key:
            return "none"
        try:
            details = self._get_target_details(self._target_key)
            if details is not None:
                return (str(details.current_strategy or "none").strip() or "none")
            selections = self._direct_facade.get_strategy_selections() or {}
            return (selections.get(self._target_key) or "none").strip() or "none"
        except Exception:
            return "none"

    def _get_target_details(self, target_key: str | None = None):
        key = str(target_key or self._target_key or "").strip().lower()
        if not key or not getattr(self, "_direct_facade", None):
            return None
        payload = getattr(self, "_target_payload", None)
        if payload is not None and str(getattr(payload, "target_key", "") or "") == key:
            return payload.details
        payload = self._load_target_payload_sync(key, refresh=False)
        if payload is None:
            return None
        return getattr(payload, "details", None)

    def _reload_target(self, *_args) -> None:
        if not self._target_key:
            return
        if self._refresh_btn:
            self._refresh_btn.set_loading(True)

        try:
            self._request_target_payload(self._target_key, refresh=True, reason="reload")
        except Exception as e:
            log(f"Zapret1StrategyDetailPage: cannot load strategies: {e}", "ERROR")
            self._strategies = {}
            self._rebuild_tree_rows()
            self._refresh_args_preview()
            self._update_selected_label()
            self._sync_target_controls()
            self._hide_success()

    def refresh_from_preset_switch(self) -> None:
        """Перечитывает текущий target после смены активного source preset."""
        if not self.isVisible():
            self._preset_refresh_pending = True
            return
        if not self._target_key:
            return
        self._preset_refresh_pending = False
        self._request_target_payload(self._target_key, refresh=True, reason="preset_switch")

    def _sorted_strategy_items(self) -> list[dict]:
        return StrategyDetailPageV1Controller.sorted_strategy_items(self._strategies, self._sort_mode)

    def _rebuild_tree_rows(self) -> None:
        if not self._tree:
            return

        self._tree.clear_strategies()

        self._tree.add_strategy(
            StrategyTreeRow(
                strategy_id="none",
                name=self._tr("page.z1_strategy_detail.tree.disabled.name", "Выключено"),
                args=[
                    self._tr(
                        "page.z1_strategy_detail.tree.disabled.args",
                        "Отключить обход DPI для этого target'а",
                    )
                ],
            )
        )

        if self._current_strategy_id == "custom":
            custom_lines = [ln.strip() for ln in self._get_current_args().splitlines() if ln.strip()]
            self._tree.add_strategy(
                StrategyTreeRow(
                    strategy_id="custom",
                    name=self._tr("page.z1_strategy_detail.tree.custom.name", "Свой набор"),
                    args=custom_lines
                    or [
                        self._tr(
                            "page.z1_strategy_detail.tree.custom.args",
                            "Пользовательские аргументы",
                        )
                    ],
                )
            )

        for strat in self._sorted_strategy_items():
            sid = (strat.get("id") or "").strip()
            if not sid:
                continue
            args_lines = [ln.strip() for ln in (strat.get("args") or "").splitlines() if ln.strip()]
            self._tree.add_strategy(
                StrategyTreeRow(
                    strategy_id=sid,
                    name=strat.get("name", sid),
                    args=args_lines,
                )
            )

        self._apply_sort_mode()
        self._apply_search_filter()

        active_sid = self._current_strategy_id if self._tree.has_strategy(self._current_strategy_id) else "none"
        self._tree.set_selected_strategy(active_sid)

        if self._empty_label is not None:
            self._empty_label.setVisible(not bool(self._strategies))

    # ------------------------------------------------------------------
    # Header updates
    # ------------------------------------------------------------------

    def _update_header_labels(self) -> None:
        full_name = self._target_info.get("full_name", self._target_key) or self._target_key
        description = self._target_info.get("description", "")
        protocol = self._target_info.get("protocol", "")
        ports = self._target_info.get("ports", "")

        if self._title_label is not None:
            self._title_label.setText(full_name)
        if self._desc_label is not None:
            self._desc_label.setText(description)
            self._desc_label.setVisible(bool(description))

        subtitle_parts = []
        if protocol:
            subtitle_parts.append(str(protocol))
        if ports:
            subtitle_parts.append(
                self._tr("page.z1_strategy_detail.subtitle.ports", "порты: {ports}", ports=ports)
            )

        if self._subtitle_label is not None:
            self._subtitle_label.setText(" | ".join(subtitle_parts))

        self._update_selected_label()

    def _update_selected_label(self) -> None:
        if self._selected_label is not None:
            self._selected_label.setText(
                self._tr(
                    "page.z1_strategy_detail.selected.current",
                    "Текущая стратегия: {strategy}",
                    strategy=self._strategy_display_name(self._current_strategy_id),
                )
            )

    # ------------------------------------------------------------------
    # Search / sort controls
    # ------------------------------------------------------------------

    def _on_search_text_changed(self, text: str) -> None:
        self._search_text = (text or "").strip().lower()
        self._apply_search_filter()

    def _on_sort_combo_changed(self, *_args) -> None:
        if not self._sort_combo:
            return
        mode = self._sort_combo.currentData()
        mode = str(mode or "recommended")
        if mode == self._sort_mode:
            return
        self._sort_mode = mode
        self._rebuild_tree_rows()

    def _apply_sort_mode(self) -> None:
        if not self._tree:
            return

        sort_map = {
            "recommended": "default",
            "alpha_asc": "name_asc",
            "alpha_desc": "name_desc",
        }
        self._tree.set_sort_mode(sort_map.get(self._sort_mode, "default"))
        self._tree.apply_sort()

    def _apply_search_filter(self) -> None:
        if self._tree:
            self._tree.apply_filter(self._search_text, set())

    def _target_supports_filter_switch(self) -> bool:
        host = str(self._target_info.get("base_filter_hostlist") or "").strip()
        ipset = str(self._target_info.get("base_filter_ipset") or "").strip()
        return bool(host and ipset)

    def _sync_target_controls(self) -> None:
        enabled = (self._current_strategy_id or "none") != "none"

        if self._enable_toggle is not None:
            self._enable_toggle.blockSignals(True)
            if hasattr(self._enable_toggle, "setChecked"):
                self._enable_toggle.setChecked(enabled)
            self._enable_toggle.blockSignals(False)

        if self._edit_args_btn is not None:
            self._edit_args_btn.setEnabled(enabled)

        if self._filter_mode_frame is not None:
            can_switch = self._target_supports_filter_switch()
            self._filter_mode_frame.setVisible(can_switch)
            if can_switch and self._filter_mode_selector is not None:
                saved_mode = self._load_target_filter_mode(self._target_key)
                self._filter_mode_selector.blockSignals(True)
                self._filter_mode_selector.setChecked(saved_mode == "ipset")
                self._filter_mode_selector.blockSignals(False)

    def _load_target_filter_mode(self, target_key: str) -> str:
        if not self._direct_facade:
            return "hostlist"
        payload = getattr(self, "_target_payload", None)
        if payload is not None and str(getattr(payload, "target_key", "") or "") == str(target_key or "").strip().lower():
            return str(getattr(payload, "filter_mode", "") or "hostlist")
        try:
            return self._direct_facade.get_target_filter_mode(target_key)
        except Exception:
            return "hostlist"

    def _on_filter_mode_changed(self, new_mode: str) -> None:
        if not self._direct_facade or not self._target_key:
            return
        try:
            ok = self._direct_facade.update_target_filter_mode(
                self._target_key,
                new_mode,
                save_and_sync=True,
            )
            if ok is False:
                raise RuntimeError(
                    self._tr(
                        "page.z1_strategy_detail.error.filter_mode_save",
                        "Не удалось сохранить режим фильтрации",
                    )
                )
            log(f"V1 filter mode set: {self._target_key} = {new_mode}", "INFO")
            if _HAS_FLUENT and InfoBar is not None:
                InfoBar.success(
                    title=self._tr("page.z1_strategy_detail.infobar.filter_mode.title", "Режим фильтрации"),
                    content=self._tr("page.z1_strategy_detail.filter.ipset", "IPset")
                    if new_mode == "ipset"
                    else self._tr("page.z1_strategy_detail.filter.hostlist", "Hostlist"),
                    parent=self.window(),
                    duration=1500,
                )
        except Exception as e:
            log(f"V1 filter mode error: {e}", "ERROR")
            if _HAS_FLUENT and InfoBar is not None:
                InfoBar.error(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=str(e),
                    parent=self.window(),
                )
            self._sync_target_controls()

    def _default_strategy_id(self) -> str:
        return StrategyDetailPageV1Controller.default_strategy_id(self._strategies, self._sort_mode)

    def _on_enable_toggled(self, enabled: bool) -> None:
        if not self._direct_facade or not self._target_key:
            return

        if enabled:
            strategy_id = (self._last_enabled_strategy_id or "").strip()
            if not strategy_id or strategy_id == "none":
                strategy_id = self._default_strategy_id()
            if strategy_id == "none":
                if self._enable_toggle is not None:
                    self._enable_toggle.blockSignals(True)
                    self._enable_toggle.setChecked(False)
                    self._enable_toggle.blockSignals(False)
                self._sync_target_controls()
                return
            self._on_strategy_selected(strategy_id)
            return

        if self._current_strategy_id and self._current_strategy_id != "none":
            self._last_enabled_strategy_id = self._current_strategy_id
        self._on_strategy_selected("none")

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    def _on_strategy_selected(self, strategy_id: str) -> None:
        if not self._direct_facade or not self._target_key:
            return

        sid = (strategy_id or "none").strip() or "none"
        self.show_loading()
        try:
            ok = self._direct_facade.set_strategy_selection(
                self._target_key,
                sid,
                save_and_sync=True,
            )
            if ok is False:
                raise RuntimeError("Не удалось сохранить выбор стратегии")

            self._current_strategy_id = sid
            if sid != "none":
                self._last_enabled_strategy_id = sid
            self._update_selected_label()
            self._refresh_args_preview()
            self._sync_target_controls()

            apply_tree_selected_strategy_state(
                self._tree,
                strategy_id=sid,
            )

            self.strategy_selected.emit(self._target_key, sid)
            log(f"V1 strategy set: {self._target_key} = {sid}", "INFO")

            if _HAS_FLUENT and InfoBar is not None:
                InfoBar.success(
                    title=self._tr("page.z1_strategy_detail.infobar.strategy_applied", "Стратегия применена"),
                    content=self._strategy_display_name(sid),
                    parent=self.window(),
                    duration=1800,
                )

            self.show_success()

        except Exception as e:
            log(f"V1 strategy selection error: {e}", "ERROR")
            if _HAS_FLUENT and InfoBar is not None:
                InfoBar.error(title="Ошибка", content=str(e), parent=self.window())
            self._reload_target()

    def _strategy_display_name(self, strategy_id: str) -> str:
        return StrategyDetailPageV1Controller.strategy_display_name(strategy_id, self._strategies, self._tr)

    # ------------------------------------------------------------------
    # Args preview / editor
    # ------------------------------------------------------------------

    def _refresh_args_preview(self) -> None:
        if self._args_preview_label is None:
            return

        current_args = self._get_current_args()
        if not current_args:
            self._args_preview_label.setText(self._tr("page.z1_strategy_detail.args.none", "(нет аргументов)"))
            return

        lines = [ln for ln in current_args.splitlines() if ln.strip()]
        preview = "\n".join(lines[:8])
        if len(lines) > 8:
            preview += self._tr(
                "page.z1_strategy_detail.args.more",
                "\n... (+{count} строк)",
                count=len(lines) - 8,
            )
        self._args_preview_label.setText(preview)

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
        if not _HAS_FLUENT or (self._current_strategy_id or "none") == "none":
            return
        try:
            edited_text = run_args_editor_dialog(
                initial_text=self._get_current_args(),
                parent=self.window(),
                language=self._ui_language,
                dialog_cls=_ArgsEditorDialog,
            )
            if edited_text is not None:
                self._save_custom_args(edited_text.strip())
        except Exception as e:
            log(f"Zapret1StrategyDetailPage: args editor error: {e}", "ERROR")

    def _save_custom_args(self, args_text: str) -> None:
        if not self._direct_facade or not self._target_key:
            return

        try:
            if not self._direct_facade.update_target_raw_args_text(
                self._target_key,
                args_text,
                save_and_sync=True,
            ):
                return
            payload = self._load_target_payload_sync(self._target_key, refresh=True)
            self._current_strategy_id = (
                str(getattr(getattr(payload, "details", None), "current_strategy", "none") or "none")
                if payload is not None else "none"
            )
            if self._current_strategy_id != "none":
                self._last_enabled_strategy_id = self._current_strategy_id
            self.strategy_selected.emit(self._target_key, self._current_strategy_id)
            self._sync_target_controls()

            if _HAS_FLUENT and InfoBar is not None:
                if args_text:
                    InfoBar.success(
                        title=self._tr("page.z1_strategy_detail.infobar.args_saved.title", "Аргументы сохранены"),
                        content=self._tr(
                            "page.z1_strategy_detail.infobar.args_saved.content",
                            "Пользовательские аргументы применены",
                        ),
                        parent=self.window(),
                        duration=1800,
                    )
                else:
                    InfoBar.success(
                        title=self._tr("page.z1_strategy_detail.infobar.args_cleared.title", "Аргументы очищены"),
                        content=self._tr(
                            "page.z1_strategy_detail.infobar.args_cleared.content",
                            "Target возвращён в режим 'Выключено'",
                        ),
                        parent=self.window(),
                        duration=1800,
                    )

            self._request_target_payload(self._target_key, refresh=True, reason="args_saved")

        except Exception as e:
            log(f"V1 save custom args error: {e}", "ERROR")
            if _HAS_FLUENT and InfoBar is not None:
                InfoBar.error(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=str(e),
                    parent=self.window(),
                )

    # ------------------------------------------------------------------
    # Feedback indicators
    # ------------------------------------------------------------------

    def show_loading(self) -> None:
        apply_loading_indicator_state(
            self._spinner,
            self._success_icon,
            loading=True,
        )

    def show_success(self) -> None:
        success_pixmap = None
        if _HAS_QTA and qta is not None:
            try:
                success_pixmap = qta.icon("fa5s.check-circle", color="#6ccb5f").pixmap(16, 16)
            except Exception:
                success_pixmap = None
        apply_loading_indicator_state(
            self._spinner,
            self._success_icon,
            success=True,
            success_pixmap=success_pixmap,
        )

        self._success_timer.start(1200)

    def _hide_success(self) -> None:
        apply_loading_indicator_state(
            self._spinner,
            self._success_icon,
            loading=False,
            success=False,
        )

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
            fields={"active_preset_revision", "preset_content_revision"},
            emit_initial=False,
        )

    def _on_ui_state_changed(self, _state: AppUiState, changed_fields: frozenset[str]) -> None:
        if "active_preset_revision" in changed_fields or "preset_content_revision" in changed_fields:
            self.refresh_from_preset_switch()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._back_btn is not None:
            self._back_btn.setText(
                self._tr("page.z1_strategy_detail.back.strategies", "← Стратегии Zapret 1")
            )

        if self._title_label is not None and not self._target_key:
            self._title_label.setText(
                self._tr("page.z1_strategy_detail.header.category_fallback", "Target")
            )

        if self._state_label is not None:
            self._state_label.setText(
                self._tr("page.z1_strategy_detail.state.category_bypass", "Обход для target'а")
            )

        if self._enable_toggle is not None:
            if hasattr(self._enable_toggle, "setOnText"):
                self._enable_toggle.setOnText(self._tr("page.z1_strategy_detail.toggle.on", "Включено"))
            if hasattr(self._enable_toggle, "setOffText"):
                self._enable_toggle.setOffText(self._tr("page.z1_strategy_detail.toggle.off", "Выключено"))

        if self._filter_label is not None:
            self._filter_label.setText(self._tr("page.z1_strategy_detail.filter.label", "Фильтр:"))

        if self._filter_mode_selector is not None:
            if hasattr(self._filter_mode_selector, "setOnText"):
                self._filter_mode_selector.setOnText(self._tr("page.z1_strategy_detail.filter.ipset", "IPset"))
            if hasattr(self._filter_mode_selector, "setOffText"):
                self._filter_mode_selector.setOffText(
                    self._tr("page.z1_strategy_detail.filter.hostlist", "Hostlist")
                )

        if self._search_edit is not None:
            self._search_edit.setPlaceholderText(
                self._tr(
                    "page.z1_strategy_detail.search.placeholder",
                    "Поиск стратегии по названию или аргументам",
                )
            )

        if self._sort_combo is not None:
            selected_mode = self._sort_combo.currentData() or self._sort_mode
            self._sort_combo.blockSignals(True)
            self._sort_combo.clear()
            self._sort_combo.addItem(
                self._tr("page.z1_strategy_detail.sort.recommended", "По рекомендации"),
                userData="recommended",
            )
            self._sort_combo.addItem(
                self._tr("page.z1_strategy_detail.sort.alpha_asc", "По алфавиту A-Z"),
                userData="alpha_asc",
            )
            self._sort_combo.addItem(
                self._tr("page.z1_strategy_detail.sort.alpha_desc", "По алфавиту Z-A"),
                userData="alpha_desc",
            )
            idx = self._sort_combo.findData(selected_mode)
            self._sort_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._sort_combo.blockSignals(False)

        if self._edit_args_btn is not None:
            self._edit_args_btn.setText(
                self._tr("page.z1_strategy_detail.button.edit_args", "Редактировать аргументы")
            )

        if self._list_card is not None:
            self._list_card.set_title(self._tr("page.z1_strategy_detail.card.strategies", "Стратегии"))

        if self._empty_label is not None:
            self._empty_label.setText(
                self._tr(
                    "page.z1_strategy_detail.empty.no_strategies",
                    "Нет доступных стратегий. Проверьте %APPDATA%\\zapret\\direct_zapret1\\",
                )
            )

        self._rebuild_breadcrumb()
        self._update_header_labels()
        self._rebuild_tree_rows()
        self._refresh_args_preview()
