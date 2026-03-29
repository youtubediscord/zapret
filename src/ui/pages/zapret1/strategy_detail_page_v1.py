# ui/pages/zapret1/strategy_detail_page_v1.py
"""Zapret 1 strategy detail page with Zapret 2-style layout."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QFont

from ui.pages.base_page import BasePage
from ui.compat_widgets import ActionButton, RefreshButton, SettingsCard
from ui.widgets.direct_zapret2_strategies_tree import DirectZapret2StrategiesTree, StrategyTreeRow
from ui.text_catalog import tr as tr_catalog
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


_LABEL_ORDER = {
    "recommended": 0,
    "stable": 1,
    None: 2,
    "none": 2,
    "experimental": 3,
    "game": 4,
    "caution": 5,
}


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
        try:
            from config.reg import get_smooth_scroll_enabled
            from qfluentwidgets.common.smooth_scroll import SmoothMode

            smooth_enabled = get_smooth_scroll_enabled()
            mode = SmoothMode.COSINE if smooth_enabled else SmoothMode.NO_SMOOTH
            delegate = (
                getattr(self._text_edit, "scrollDelegate", None)
                or getattr(self._text_edit, "scrollDelagate", None)
                or getattr(self._text_edit, "delegate", None)
            )
            if delegate is not None:
                if hasattr(delegate, "useAni"):
                    if not hasattr(delegate, "_zapret_base_use_ani"):
                        delegate._zapret_base_use_ani = bool(delegate.useAni)
                    delegate.useAni = bool(delegate._zapret_base_use_ani) if smooth_enabled else False
                for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                    smooth = getattr(delegate, smooth_attr, None)
                    smooth_setter = getattr(smooth, "setSmoothMode", None)
                    if callable(smooth_setter):
                        smooth_setter(mode)

            setter = getattr(self._text_edit, "setSmoothMode", None)
            if callable(setter):
                try:
                    setter(mode, Qt.Orientation.Vertical)
                except TypeError:
                    setter(mode)
        except Exception:
            pass
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

        subtitle_row = QHBoxLayout()
        subtitle_row.setContentsMargins(0, 0, 0, 0)
        subtitle_row.setSpacing(6)

        if _HAS_FLUENT:
            self._spinner = IndeterminateProgressRing()
            self._spinner.setFixedSize(16, 16)
            self._spinner.setStrokeWidth(2)
        else:
            self._spinner = QWidget()
        self._spinner.hide()
        subtitle_row.addWidget(self._spinner)

        self._success_icon = PixmapLabel()
        self._success_icon.setFixedSize(16, 16)
        self._success_icon.hide()
        subtitle_row.addWidget(self._success_icon)

        self._subtitle_label = BodyLabel("")
        subtitle_row.addWidget(self._subtitle_label)

        self._selected_label = CaptionLabel("")
        self._selected_label.setFont(QFont("Segoe UI", 10))
        subtitle_row.addWidget(self._selected_label, 1)

        header_layout.addLayout(subtitle_row)

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
            accent=False,
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

        self._tree = DirectZapret2StrategiesTree(self)
        self._tree.strategy_clicked.connect(self._on_strategy_selected)
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

        cat_name = self._target_info.get("full_name", self._target_key) if self._target_key else "Target"
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
            self._breadcrumb.addItem("detail", cat_name)
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

    def show_target(self, target_key: str, direct_facade) -> None:
        self._target_key = str(target_key or "").strip().lower()
        self._direct_facade = direct_facade
        target_info = None
        try:
            target_info = direct_facade.get_target_ui_item(self._target_key)
        except Exception:
            target_info = None
        self._target_info = self._normalize_target_info(target_key, target_info)
        self._current_strategy_id = self._load_current_strategy_id()
        if self._current_strategy_id and self._current_strategy_id != "none":
            self._last_enabled_strategy_id = self._current_strategy_id

        self._update_header_labels()
        self._rebuild_breadcrumb()
        self._reload_target()

    def showEvent(self, event):
        super().showEvent(event)
        self._rebuild_breadcrumb()
        if self._target_key:
            QTimer.singleShot(0, self._reload_target)

    # ------------------------------------------------------------------
    # Data mapping / loading
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_target_info(target_key: str, target_info: Any) -> dict[str, Any]:
        if isinstance(target_info, dict):
            info = dict(target_info)
            info.setdefault("key", target_key)
            info.setdefault("full_name", target_key)
            info.setdefault("description", "")
            info.setdefault("base_filter", "")
            info.setdefault("base_filter_hostlist", "")
            info.setdefault("base_filter_ipset", "")
            return info

        return {
            "key": getattr(target_info, "key", target_key),
            "full_name": getattr(target_info, "full_name", target_key),
            "description": getattr(target_info, "description", ""),
            "protocol": getattr(target_info, "protocol", ""),
            "ports": getattr(target_info, "ports", ""),
            "icon_name": getattr(target_info, "icon_name", ""),
            "icon_color": getattr(target_info, "icon_color", "#909090"),
            "base_filter": getattr(target_info, "base_filter", ""),
            "base_filter_hostlist": getattr(target_info, "base_filter_hostlist", ""),
            "base_filter_ipset": getattr(target_info, "base_filter_ipset", ""),
        }

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
        try:
            return self._direct_facade.get_target_details(key)
        except Exception:
            return None

    def _reload_target(self, *_args) -> None:
        if not self._target_key:
            return
        if self._refresh_btn:
            self._refresh_btn.set_loading(True)

        self.show_loading()
        try:
            self._strategies = self._direct_facade.get_target_strategies(self._target_key) or {}
            self._current_strategy_id = self._load_current_strategy_id()
            if self._current_strategy_id and self._current_strategy_id != "none":
                self._last_enabled_strategy_id = self._current_strategy_id
            self._rebuild_tree_rows()
            self._refresh_args_preview()
            self._update_selected_label()
            self._sync_target_controls()
            self.show_success()
        except Exception as e:
            log(f"Zapret1StrategyDetailPage: cannot load strategies: {e}", "ERROR")
            self._strategies = {}
            self._rebuild_tree_rows()
            self._refresh_args_preview()
            self._update_selected_label()
            self._sync_target_controls()
            self._hide_success()
        finally:
            if self._refresh_btn:
                self._refresh_btn.set_loading(False)

    def _sorted_strategy_items(self) -> list[dict]:
        items = [s for s in (self._strategies or {}).values() if s.get("id")]

        if self._sort_mode == "alpha_asc":
            return sorted(items, key=lambda s: (s.get("name", "")).lower())
        if self._sort_mode == "alpha_desc":
            return sorted(items, key=lambda s: (s.get("name", "")).lower(), reverse=True)

        return sorted(
            items,
            key=lambda s: (
                _LABEL_ORDER.get(s.get("label"), 2),
                (s.get("name", "")).lower(),
            ),
        )

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
        try:
            details = self._get_target_details(target_key)
            if details is not None:
                return str(details.filter_mode or "hostlist")
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
        for item in self._sorted_strategy_items():
            sid = str(item.get("id") or "").strip()
            if sid and sid != "none":
                return sid
        return "none"

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

            if self._tree and self._tree.has_strategy(sid):
                self._tree.set_selected_strategy(sid)

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
        sid = (strategy_id or "").strip()
        if not sid or sid == "none":
            return self._tr("page.z1_strategy_detail.tree.disabled.name", "Выключено")
        if sid == "custom":
            return self._tr("page.z1_strategy_detail.tree.custom.name", "Свой набор")
        info = (self._strategies or {}).get(sid)
        if info:
            return info.get("name", sid)
        return sid

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
        try:
            return (self._direct_facade.get_target_raw_args_text(self._target_key) or "").strip()
        except Exception:
            return ""

    def _open_args_editor(self, *_args) -> None:
        if not _HAS_FLUENT or (self._current_strategy_id or "none") == "none":
            return
        try:
            dlg = _ArgsEditorDialog(
                self._get_current_args(),
                self.window(),
                language=self._ui_language,
            )
            if dlg.exec():
                self._save_custom_args(dlg.get_text().strip())
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
            self._current_strategy_id = (
                self._direct_facade.get_strategy_selections().get(self._target_key, "none") or "none"
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

            self._reload_target()

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
        if self._spinner is not None:
            try:
                if hasattr(self._spinner, "start"):
                    self._spinner.start()
            except Exception:
                pass
            self._spinner.show()

        if self._success_icon is not None:
            self._success_icon.hide()

    def show_success(self) -> None:
        if self._spinner is not None:
            try:
                if hasattr(self._spinner, "stop"):
                    self._spinner.stop()
            except Exception:
                pass
            self._spinner.hide()

        if self._success_icon is not None:
            if _HAS_QTA and qta is not None:
                try:
                    self._success_icon.setPixmap(qta.icon("fa5s.check-circle", color="#6ccb5f").pixmap(16, 16))
                except Exception:
                    pass
            self._success_icon.show()

        self._success_timer.start(1200)

    def _hide_success(self) -> None:
        if self._success_icon is not None:
            self._success_icon.hide()

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
