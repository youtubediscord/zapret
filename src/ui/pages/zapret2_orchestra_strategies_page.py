# ui/pages/zapret2_orchestra_strategies_page.py
"""Modern strategies page for direct_zapret2_orchestra mode."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout

from ui.pages.base_page import BasePage
from ui.compat_widgets import ActionButton, RefreshButton, ResetActionButton, SettingsCard, StatusIndicator
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.widgets import UnifiedStrategiesList
from ui.widgets.direct_zapret2_strategies_tree import DirectZapret2StrategiesTree, StrategyTreeRow
from ui.main_window_pages import get_loaded_page
from ui.page_names import PageName
from ui.text_catalog import tr as tr_catalog
from log import log

try:
    from qfluentwidgets import (
        BreadcrumbBar,
        BodyLabel,
        LineEdit,
        ComboBox,
        InfoBar,
    )

    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import (  # type: ignore
        QLabel as BodyLabel,
        QLineEdit as LineEdit,
        QComboBox as ComboBox,
    )

    BreadcrumbBar = None  # type: ignore
    InfoBar = None  # type: ignore
    _HAS_FLUENT = False


_LABEL_ORDER = {
    "recommended": 0,
    "stable": 1,
    None: 2,
    "none": 2,
    "experimental": 3,
    "game": 4,
    "caution": 5,
}


class Zapret2OrchestraStrategiesPage(BasePage):
    """Страница выбора стратегий для режима direct_zapret2_orchestra."""

    launch_method_changed = pyqtSignal(str)
    strategy_selected = pyqtSignal(str, str)

    _ROOT_TITLE = "Прямой запуск (Orchestra Z2)"
    _ROOT_SUBTITLE = (
        "Здесь для каждой категории можно выбрать свою стратегию обхода. "
        "После изменения выбор сразу сохраняется в активный orchestra-пресет "
        "и применяется к запущенному DPI."
    )

    def __init__(self, parent=None):
        super().__init__(
            title=self._ROOT_TITLE,
            subtitle=self._ROOT_SUBTITLE,
            parent=parent,
            title_key="page.z2_orchestra_strategies.title",
            subtitle_key="page.z2_orchestra_strategies.subtitle",
        )
        self.parent_app = parent

        self._ROOT_TITLE = tr_catalog("page.z2_orchestra_strategies.title", default=self._ROOT_TITLE)
        self._ROOT_SUBTITLE = tr_catalog("page.z2_orchestra_strategies.subtitle", default=self._ROOT_SUBTITLE)

        self._breadcrumb = None
        self._view_mode = "list"  # list | detail
        self._selected_category_key = ""
        self._sort_mode = "recommended"  # recommended | alpha_asc | alpha_desc
        self._search_text = ""

        self._categories: dict[str, Any] = {}
        self.category_selections: dict[str, str] = {}
        self._unified_list: UnifiedStrategiesList | None = None

        self._detail_tree: DirectZapret2StrategiesTree | None = None
        self._detail_search: Any = None
        self._detail_sort: Any = None
        self._detail_strategies: dict[str, dict] = {}

        self._reload_btn: RefreshButton | None = None
        self._status_indicator: StatusIndicator | None = None
        self.current_strategy_label: Any = None
        self._ui_state_store = None
        self._ui_state_unsubscribe = None

        self._built = False
        self._current_mode = self._get_launch_method()
        self._preset_refresh_pending = False

        self._process_check_timer = QTimer(self)
        self._process_check_timer.timeout.connect(self._check_process_status)
        self._process_check_attempts = 0
        self._max_check_attempts = 30
        self._runtime_started = False

        self._setup_breadcrumb()
        self._rebuild_current_view()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_page_activated(self, first_show: bool) -> None:
        _ = first_show
        method = self._get_launch_method()
        if method != self._current_mode:
            self._current_mode = method
            self._built = False
            if method != "direct_zapret2_orchestra":
                self._view_mode = "list"
                self._selected_category_key = ""

        if not self._built:
            QTimer.singleShot(0, self._rebuild_current_view)
        else:
            if self._preset_refresh_pending:
                self._preset_refresh_pending = False
                self._refresh_runtime_state()

        if not self._runtime_started:
            self._runtime_started = True
            self._start_process_monitoring()

    def on_page_hidden(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Navigation / breadcrumb
    # ------------------------------------------------------------------

    def _setup_breadcrumb(self) -> None:
        if _HAS_FLUENT and BreadcrumbBar is not None:
            try:
                self._breadcrumb = BreadcrumbBar(self)
                self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_changed)
                self._rebuild_breadcrumb()
                self.layout.insertWidget(0, self._breadcrumb)
                return
            except Exception:
                pass

        self._breadcrumb = None

    def _rebuild_breadcrumb(self) -> None:
        if self._breadcrumb is None:
            return

        self._breadcrumb.blockSignals(True)
        try:
            self._breadcrumb.clear()
            self._breadcrumb.addItem("control", "Управление")
            self._breadcrumb.addItem("strategies", "Стратегии (Оркестратор)")
            if self._view_mode == "detail" and self._selected_category_key:
                cat = self._categories.get(self._selected_category_key)
                cat_name = getattr(cat, "full_name", self._selected_category_key)
                self._breadcrumb.addItem("detail", str(cat_name))
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_changed(self, key: str) -> None:
        self._rebuild_breadcrumb()
        if key == "strategies":
            self._back_to_list()
        elif key == "control":
            self._navigate_to_control()

    def _navigate_to_control(self) -> None:
        try:
            if self.parent_app and hasattr(self.parent_app, "show_page"):
                self.parent_app.show_page(PageName.ZAPRET2_ORCHESTRA_CONTROL)
        except Exception:
            pass

    def _reset_mode_view_state(self) -> None:
        self._built = False
        self._view_mode = "list"
        self._selected_category_key = ""

    # ------------------------------------------------------------------
    # View build
    # ------------------------------------------------------------------

    def _rebuild_current_view(self, *, reload_data: bool = True) -> None:
        if reload_data or not self._categories:
            self._categories = self._load_categories()
            self.category_selections = self._load_current_selections()

        if self._view_mode == "detail" and self._selected_category_key not in self._categories:
            self._view_mode = "list"
            self._selected_category_key = ""

        if self._view_mode == "detail" and self._selected_category_key:
            self._build_detail_view(self._selected_category_key)
        else:
            self._build_list_view()

        self._built = True

    def _build_list_view(self) -> None:
        self._view_mode = "list"
        self._clear_dynamic_widgets()

        self.title_label.setText(self._ROOT_TITLE)
        if self.subtitle_label:
            self.subtitle_label.setText(self._ROOT_SUBTITLE)
            self.subtitle_label.show()

        self._rebuild_breadcrumb()

        self._build_status_card()
        self._build_actions_card(for_detail=False)

        if not self._categories:
            self.add_widget(
                BodyLabel(
                    tr_catalog(
                        "page.z2_orchestra_strategies.empty.no_categories",
                        language=self._ui_language,
                        default="Категории не найдены",
                    )
                )
            )
            return

        self._unified_list = UnifiedStrategiesList(self)
        self._unified_list.strategy_selected.connect(self._on_category_clicked)
        self._unified_list.selections_changed.connect(self._on_selections_changed)
        self._unified_list.build_list(
            self._categories,
            self.category_selections,
            filter_modes=self._load_filter_modes(),
        )
        self.add_widget(self._unified_list, 1)

        self._update_current_strategies_display()

    def _build_detail_view(self, category_key: str) -> None:
        self._view_mode = "detail"
        self._selected_category_key = category_key
        self._clear_dynamic_widgets()

        cat = self._categories.get(category_key)
        if not cat:
            self._back_to_list()
            return

        full_name = getattr(cat, "full_name", category_key)
        description = getattr(cat, "description", "")
        protocol = getattr(cat, "protocol", "")
        ports = getattr(cat, "ports", "")

        self.title_label.setText(str(full_name))
        if self.subtitle_label:
            parts = [str(description).strip()] if description else []
            protocol_parts = []
            if protocol:
                protocol_parts.append(str(protocol))
            if ports:
                protocol_parts.append(f"порты: {ports}")
            if protocol_parts:
                parts.append(" | ".join(protocol_parts))
            self.subtitle_label.setText("\n".join([p for p in parts if p]))
            self.subtitle_label.setVisible(bool(parts))

        self._rebuild_breadcrumb()

        self._build_status_card()
        self._build_actions_card(for_detail=True)
        self._build_detail_toolbar()
        self._build_detail_tree(category_key)

        self._update_current_strategies_display()

    def _build_status_card(self) -> None:
        card = SettingsCard()
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self._status_indicator = StatusIndicator()
        self._status_indicator.set_status(
            tr_catalog(
                "page.z2_orchestra_strategies.status.ready",
                language=self._ui_language,
                default="Готово к выбору",
            ),
            "neutral",
        )
        row.addWidget(self._status_indicator)

        row.addWidget(
            BodyLabel(
                tr_catalog("page.z2_orchestra_strategies.current.prefix", language=self._ui_language, default="Текущая:")
            )
        )

        self.current_strategy_label = BodyLabel(
            tr_catalog(
                "page.z2_orchestra_strategies.current.not_selected",
                language=self._ui_language,
                default="Не выбрана",
            )
        )
        row.addWidget(self.current_strategy_label, 1)

        row.addStretch()

        card.add_layout(row)
        self.add_widget(card)

    def _build_actions_card(self, for_detail: bool) -> None:
        card = SettingsCard()
        row = QHBoxLayout()
        row.setSpacing(8)

        self._reload_btn = RefreshButton()
        self._reload_btn.clicked.connect(self._reload_strategies)
        row.addWidget(self._reload_btn)

        folder_btn = ActionButton(
            tr_catalog("page.z2_orchestra_strategies.button.folder", language=self._ui_language, default="Папка"),
            "fa5s.folder-open",
        )
        folder_btn.clicked.connect(self._open_folder)
        row.addWidget(folder_btn)

        if for_detail:
            disable_btn = ResetActionButton(
                tr_catalog(
                    "page.z2_orchestra_strategies.button.disable_category",
                    language=self._ui_language,
                    default="Отключить категорию",
                ),
                confirm_text=tr_catalog(
                    "page.z2_orchestra_strategies.confirm.disable_category",
                    language=self._ui_language,
                    default="Установить 'none' для категории?",
                ),
            )
            disable_btn.reset_confirmed.connect(lambda: self._disable_selected_category())
            row.addWidget(disable_btn)

            back_btn = ActionButton(
                tr_catalog(
                    "page.z2_orchestra_strategies.button.back_categories",
                    language=self._ui_language,
                    default="← Категории",
                ),
                "fa5s.arrow-left",
            )
            back_btn.clicked.connect(self._back_to_list)
            row.addWidget(back_btn)
        else:
            clear_btn = ResetActionButton(
                tr_catalog("page.z2_orchestra_strategies.button.disable_all", language=self._ui_language, default="Выключить"),
                confirm_text=tr_catalog(
                    "page.z2_orchestra_strategies.confirm.disable_all",
                    language=self._ui_language,
                    default="Установить 'none' для всех категорий?",
                ),
            )
            clear_btn.reset_confirmed.connect(self._clear_all)
            row.addWidget(clear_btn)

            reset_btn = ResetActionButton(
                tr_catalog("page.z2_orchestra_strategies.button.reset", language=self._ui_language, default="Сбросить"),
                confirm_text=tr_catalog(
                    "page.z2_orchestra_strategies.confirm.reset",
                    language=self._ui_language,
                    default="Сбросить к значениям по умолчанию?",
                ),
            )
            reset_btn.reset_confirmed.connect(self._reset_to_defaults)
            row.addWidget(reset_btn)

        row.addStretch()

        card.add_layout(row)
        self.add_widget(card)

    def _build_detail_toolbar(self) -> None:
        card = SettingsCard()
        row = QHBoxLayout()
        row.setSpacing(8)

        self._detail_search = LineEdit()
        self._detail_search.setPlaceholderText(
            tr_catalog(
                "page.z2_orchestra_strategies.search.placeholder",
                language=self._ui_language,
                default="Поиск по названию или аргументам",
            )
        )
        self._detail_search.textChanged.connect(self._on_search_changed)
        row.addWidget(self._detail_search, 1)

        self._detail_sort = ComboBox()
        self._detail_sort.addItem(
            tr_catalog("page.z2_orchestra_strategies.sort.recommended", language=self._ui_language, default="По рекомендации"),
            userData="recommended",
        )
        self._detail_sort.addItem(
            tr_catalog("page.z2_orchestra_strategies.sort.alpha_asc", language=self._ui_language, default="По алфавиту A-Z"),
            userData="alpha_asc",
        )
        self._detail_sort.addItem(
            tr_catalog("page.z2_orchestra_strategies.sort.alpha_desc", language=self._ui_language, default="По алфавиту Z-A"),
            userData="alpha_desc",
        )
        self._detail_sort.currentIndexChanged.connect(self._on_sort_changed)
        row.addWidget(self._detail_sort)

        card.add_layout(row)
        self.add_widget(card)

    def _build_detail_tree(self, category_key: str) -> None:
        card = SettingsCard(
            tr_catalog("page.z2_orchestra_strategies.section.strategies", language=self._ui_language, default="Стратегии")
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._detail_tree = DirectZapret2StrategiesTree(self)
        self._detail_tree.strategy_clicked.connect(self._on_detail_strategy_clicked)
        layout.addWidget(self._detail_tree, 1)

        card.add_layout(layout)
        self.add_widget(card, 1)

        self._detail_strategies = self._load_category_strategies(category_key)
        self._rebuild_detail_rows(category_key)

    def _clear_dynamic_widgets(self) -> None:
        keep: set[QWidget] = {self.title_label}
        if self.subtitle_label:
            keep.add(self.subtitle_label)
        if isinstance(self._breadcrumb, QWidget):
            keep.add(self._breadcrumb)

        to_remove = []
        for i in range(self.vBoxLayout.count()):
            item = self.vBoxLayout.itemAt(i)
            w = item.widget() if item else None
            if w is not None and w not in keep:
                to_remove.append(w)

        for w in to_remove:
            self.vBoxLayout.removeWidget(w)
            w.setParent(None)

        self._status_indicator = None
        self.current_strategy_label = None
        self._reload_btn = None
        self._detail_tree = None
        self._detail_search = None
        self._detail_sort = None

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_launch_method() -> str:
        try:
            from strategy_menu import get_strategy_launch_method

            return get_strategy_launch_method()
        except Exception:
            return ""

    @staticmethod
    def _category_value(category: Any, key: str, default: Any = "") -> Any:
        if isinstance(category, dict):
            return category.get(key, default)
        return getattr(category, key, default)

    @staticmethod
    def _load_categories() -> dict[str, Any]:
        try:
            from preset_orchestra_zapret2.catalog import load_categories

            raw_categories = load_categories() or {}
            categories: dict[str, Any] = {}
            fallback_order = 0
            for category_key, info in raw_categories.items():
                key = str(category_key or "").strip().lower()
                if not key:
                    continue
                payload = dict(info or {})
                display_name = str(
                    payload.get("full_name")
                    or payload.get("name")
                    or payload.get("display_name")
                    or key
                ).strip() or key
                categories[key] = SimpleNamespace(
                    key=key,
                    full_name=display_name,
                    description=str(payload.get("description") or "").strip(),
                    protocol=str(payload.get("protocol") or "").strip(),
                    ports=str(payload.get("ports") or "").strip(),
                    order=int(payload.get("order") or fallback_order),
                    command_order=int(payload.get("command_order") or payload.get("order") or fallback_order),
                    command_group=str(payload.get("command_group") or payload.get("group") or "default").strip() or "default",
                    strategy_type=str(payload.get("strategy_type") or "tcp").strip() or "tcp",
                    requires_all_ports=bool(payload.get("requires_all_ports", False)),
                    icon_name=payload.get("icon_name"),
                    icon_color=str(payload.get("icon_color") or "#2196F3"),
                    tooltip=str(payload.get("tooltip") or "").strip(),
                    base_filter_hostlist=str(payload.get("base_filter_hostlist") or payload.get("base_filter") or "").strip(),
                    base_filter_ipset=str(payload.get("base_filter_ipset") or "").strip(),
                )
                fallback_order += 1
            return categories
        except Exception:
            return {}

    def _load_current_selections(self) -> dict[str, str]:
        try:
            from preset_orchestra_zapret2 import PresetManager

            raw = PresetManager().get_strategy_selections() or {}
        except Exception:
            raw = {}

        return {key: (raw.get(key) or "none") for key in (self._categories or {}).keys()}

    @staticmethod
    def _load_filter_modes() -> dict[str, str]:
        try:
            from preset_orchestra_zapret2 import PresetManager

            manager = PresetManager()
            out = {}
            for key in (Zapret2OrchestraStrategiesPage._load_categories() or {}).keys():
                mode = str(manager.get_category_filter_mode(key) or "").strip().lower()
                if mode in ("hostlist", "ipset"):
                    out[key] = mode
            return out
        except Exception:
            return {}

    def _load_category_strategies(self, category_key: str) -> dict[str, dict]:
        try:
            from preset_orchestra_zapret2.catalog import load_strategies

            category = (self._categories or {}).get(category_key)
            strategy_type = str(self._category_value(category, "strategy_type", "tcp") or "tcp").strip() or "tcp"
            strategies = load_strategies(strategy_type, strategy_set="orchestra") or {}
            result: dict[str, dict] = {}
            for sid, data in strategies.items():
                if not sid:
                    continue
                row = dict(data or {})
                row.setdefault("id", sid)
                result[sid] = row
            return result
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # List handlers
    # ------------------------------------------------------------------

    def _on_category_clicked(self, category_key: str, _strategy_id: str) -> None:
        self._selected_category_key = category_key
        self._sort_mode = "recommended"
        self._search_text = ""
        self._view_mode = "detail"
        self._rebuild_current_view(reload_data=False)

    def _on_selections_changed(self, selections: dict) -> None:
        self.category_selections = dict(selections or {})
        self._update_current_strategies_display()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        self._ROOT_TITLE = tr_catalog(
            "page.z2_orchestra_strategies.title",
            language=language,
            default=self._ROOT_TITLE,
        )
        self._ROOT_SUBTITLE = tr_catalog(
            "page.z2_orchestra_strategies.subtitle",
            language=language,
            default=self._ROOT_SUBTITLE,
        )

        if self._view_mode == "detail" and self._selected_category_key:
            cat = self._categories.get(self._selected_category_key)
            if cat is not None:
                try:
                    full_name = getattr(cat, "full_name", self._selected_category_key)
                    self.title_label.setText(str(full_name))
                except Exception:
                    pass
        else:
            try:
                self.title_label.setText(self._ROOT_TITLE)
                if self.subtitle_label:
                    self.subtitle_label.setText(self._ROOT_SUBTITLE)
                    self.subtitle_label.show()
            except Exception:
                pass

        self._rebuild_breadcrumb()
        try:
            if self._built:
                self._rebuild_current_view()
        except Exception:
            pass

    def _back_to_list(self) -> None:
        self._view_mode = "list"
        self._selected_category_key = ""
        self._rebuild_current_view(reload_data=False)

    # ------------------------------------------------------------------
    # Detail handlers
    # ------------------------------------------------------------------

    def _sorted_detail_items(self) -> list[dict]:
        rows = list((self._detail_strategies or {}).values())

        if self._sort_mode == "alpha_asc":
            return sorted(rows, key=lambda s: str(s.get("name", "")).lower())
        if self._sort_mode == "alpha_desc":
            return sorted(rows, key=lambda s: str(s.get("name", "")).lower(), reverse=True)

        return sorted(
            rows,
            key=lambda s: (
                _LABEL_ORDER.get(s.get("label"), 2),
                str(s.get("name", "")).lower(),
            ),
        )

    @staticmethod
    def _args_lines(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return [ln.strip() for ln in str(value or "").splitlines() if ln.strip()]

    def _rebuild_detail_rows(self, category_key: str) -> None:
        if not self._detail_tree:
            return

        current_sid = self.category_selections.get(category_key, "none")
        self._detail_tree.clear_strategies()

        self._detail_tree.add_strategy(
            StrategyTreeRow(
                strategy_id="none",
                name=tr_catalog(
                    "page.z2_orchestra_strategies.strategy.none",
                    language=self._ui_language,
                    default="Отключено",
                ),
                args=[
                    tr_catalog(
                        "page.z2_orchestra_strategies.strategy.none.description",
                        language=self._ui_language,
                        default="Отключить стратегию для категории",
                    )
                ],
            )
        )

        for row in self._sorted_detail_items():
            sid = str(row.get("id", "")).strip()
            if not sid or sid == "none":
                continue
            self._detail_tree.add_strategy(
                StrategyTreeRow(
                    strategy_id=sid,
                    name=str(row.get("name", sid)),
                    args=self._args_lines(row.get("args")),
                )
            )

        self._apply_detail_sort_mode()
        self._apply_detail_search_filter()

        if self._detail_tree.has_strategy(current_sid):
            self._detail_tree.set_selected_strategy(current_sid)
        else:
            self._detail_tree.set_selected_strategy("none")

    def _on_search_changed(self, text: str) -> None:
        self._search_text = (text or "").strip().lower()
        self._apply_detail_search_filter()

    def _on_sort_changed(self, *_args) -> None:
        if not self._detail_sort:
            return
        mode = str(self._detail_sort.currentData() or "recommended")
        if mode == self._sort_mode:
            return
        self._sort_mode = mode
        if self._selected_category_key:
            self._rebuild_detail_rows(self._selected_category_key)

    def _apply_detail_sort_mode(self) -> None:
        if not self._detail_tree:
            return

        sort_map = {
            "recommended": "default",
            "alpha_asc": "name_asc",
            "alpha_desc": "name_desc",
        }
        self._detail_tree.set_sort_mode(sort_map.get(self._sort_mode, "default"))
        self._detail_tree.apply_sort()

    def _apply_detail_search_filter(self) -> None:
        if self._detail_tree:
            self._detail_tree.apply_filter(self._search_text, set())

    def _on_detail_strategy_clicked(self, strategy_id: str) -> None:
        category_key = self._selected_category_key
        if not category_key:
            return
        self._apply_category_selection(category_key, strategy_id)

    def _disable_selected_category(self) -> None:
        if self._selected_category_key:
            self._apply_category_selection(self._selected_category_key, "none")

    # ------------------------------------------------------------------
    # Apply / runtime actions
    # ------------------------------------------------------------------

    def _apply_category_selection(self, category_key: str, strategy_id: str) -> None:
        sid = (strategy_id or "none").strip() or "none"

        self.show_loading()
        try:
            from preset_orchestra_zapret2 import PresetManager

            ok = PresetManager().set_strategy_selection(category_key, sid, save_and_sync=True)
            if not ok:
                raise RuntimeError("Не удалось сохранить выбор")

            self.category_selections[category_key] = sid

            if self._unified_list:
                self._unified_list.update_selection(category_key, sid)

            if self._detail_tree:
                self._detail_tree.set_selected_strategy(
                    sid if self._detail_tree.has_strategy(sid) else "none"
                )

            self._update_current_strategies_display()
            self._update_dpi_filters_display()

            if self._has_any_active_strategy():
                self._restart_dpi_with_current_selections()
            else:
                self._stop_dpi_for_no_active_strategies()

            self.strategy_selected.emit("orchestra", "Оркестратор Z2")
            log(f"Orchestra strategy set: {category_key} = {sid}", "INFO")

            if _HAS_FLUENT and InfoBar is not None:
                InfoBar.success(
                    title="Стратегия применена",
                    content=f"{category_key}: {sid}",
                    parent=self.window(),
                    duration=1600,
                )

            self.show_success()

        except Exception as e:
            log(f"Ошибка применения стратегии: {e}", "ERROR")
            if _HAS_FLUENT and InfoBar is not None:
                InfoBar.error(title="Ошибка", content=str(e), parent=self.window())
            self.show_error(str(e))

    def _restart_dpi_with_current_selections(self) -> None:
        try:
            from preset_orchestra_zapret2 import (
                ensure_default_preset_exists,
                get_active_preset_name,
                get_active_preset_path,
            )

            if not ensure_default_preset_exists():
                raise RuntimeError("Не удалось подготовить orchestra preset")

            preset_path = str(get_active_preset_path())
            preset_name = get_active_preset_name() or "Default"
            mode_data = {
                "name": f"Пресет: {preset_name}",
                "is_preset_file": True,
                "preset_path": preset_path,
            }

            app = self.parent_app
            if app and hasattr(app, "dpi_controller") and app.dpi_controller:
                app.dpi_controller.start_dpi_async(
                    selected_mode=mode_data,
                    launch_method="direct_zapret2_orchestra",
                )
                self._start_process_monitoring()
                return
        except Exception as e:
            log(f"Ошибка перезапуска DPI: {e}", "ERROR")

        self.show_success()

    def _stop_dpi_for_no_active_strategies(self) -> None:
        try:
            app = self.parent_app
            if app and hasattr(app, "dpi_controller") and app.dpi_controller:
                app.dpi_controller.stop_dpi_async()
        except Exception as e:
            log(f"Ошибка остановки DPI: {e}", "DEBUG")
        self.show_success()

    def _has_any_active_strategy(self) -> bool:
        for sid in (self.category_selections or {}).values():
            if sid and sid != "none":
                return True
        return False

    def _update_dpi_filters_display(self) -> None:
        try:
            from launcher_common import calculate_required_filters

            filters = calculate_required_filters(self.category_selections or {})
            app = self.parent_app
            if app is None:
                return
            dpi_page = get_loaded_page(app, PageName.DPI_SETTINGS)
            if dpi_page is not None:
                dpi_page.update_filter_display(filters)
        except Exception as e:
            log(f"Ошибка обновления фильтров: {e}", "DEBUG")

    # ------------------------------------------------------------------
    # Toolbar actions
    # ------------------------------------------------------------------

    def _reload_strategies(self, *_args) -> None:
        if self._reload_btn:
            self._reload_btn.set_loading(True)

        try:
            from preset_orchestra_zapret2.catalog import invalidate_categories_cache, invalidate_strategies_cache

            invalidate_categories_cache()
            invalidate_strategies_cache()
            self._categories = self._load_categories()
            self.category_selections = self._load_current_selections()

            if self._view_mode == "detail" and self._selected_category_key not in self._categories:
                self._view_mode = "list"
                self._selected_category_key = ""

            self._rebuild_current_view()
        except Exception as e:
            log(f"Ошибка перезагрузки стратегий: {e}", "ERROR")
        finally:
            if self._reload_btn:
                self._reload_btn.set_loading(False)

    @staticmethod
    def _open_folder(*_args) -> None:
        try:
            from config import get_zapret_userdata_dir

            folder = os.path.join(get_zapret_userdata_dir(), "orchestra_zapret2")
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
        except Exception as e:
            log(f"Ошибка открытия папки стратегий: {e}", "ERROR")

    def _clear_all(self) -> None:
        try:
            from preset_orchestra_zapret2 import PresetManager

            none_selections = {k: "none" for k in (self._categories or {}).keys()}
            ok = PresetManager().clear_all_strategy_selections(save_and_sync=True)
            if not ok:
                raise RuntimeError("Не удалось отключить все категории")
            self.category_selections = none_selections

            self._update_dpi_filters_display()
            self._stop_dpi_for_no_active_strategies()

            if self._unified_list:
                self._unified_list.set_selections(self.category_selections)
            if self._detail_tree:
                self._detail_tree.set_selected_strategy("none")

            self._update_current_strategies_display()
            log("Все категории выключены (none)", "INFO")
        except Exception as e:
            log(f"Ошибка массового выключения стратегий: {e}", "ERROR")

    def _reset_to_defaults(self) -> None:
        try:
            from preset_orchestra_zapret2 import PresetManager

            ok = PresetManager().reset_strategy_selections_to_defaults(save_and_sync=True)
            if not ok:
                raise RuntimeError("Не удалось сбросить orchestra категории")

            self.category_selections = self._load_current_selections()
            self._update_dpi_filters_display()

            if self._has_any_active_strategy():
                self._restart_dpi_with_current_selections()
            else:
                self._stop_dpi_for_no_active_strategies()

            self._rebuild_current_view()
            log("Настройки оркестратора сброшены к значениям по умолчанию", "INFO")
        except Exception as e:
            log(f"Ошибка сброса к значениям по умолчанию: {e}", "ERROR")

    # ------------------------------------------------------------------
    # Process monitor / status indicator
    # ------------------------------------------------------------------

    def show_loading(self) -> None:
        if self._status_indicator is not None:
            self._status_indicator.set_status(
                tr_catalog(
                    "page.z2_orchestra_strategies.status.applying",
                    language=self._ui_language,
                    default="Применение стратегии...",
                ),
                "running",
            )

    def show_success(self) -> None:
        if self._status_indicator is not None:
            self._status_indicator.set_status(
                tr_catalog(
                    "page.z2_orchestra_strategies.status.applied",
                    language=self._ui_language,
                    default="Стратегия применена",
                ),
                "success",
            )

    def show_error(self, details: str = "") -> None:
        if self._status_indicator is not None:
            text = tr_catalog(
                "page.z2_orchestra_strategies.status.error",
                language=self._ui_language,
                default="Не удалось применить стратегию",
            )
            details = str(details or "").strip()
            if details:
                text = f"{text}: {details}"
            self._status_indicator.set_status(text, "stopped")

    def _start_process_monitoring(self) -> None:
        self._process_check_attempts = 0
        if not self._process_check_timer.isActive():
            QTimer.singleShot(300, lambda: self._process_check_timer.start(200))

    def _stop_process_monitoring(self) -> None:
        if self._process_check_timer.isActive():
            self._process_check_timer.stop()

    def _check_process_status(self) -> None:
        try:
            self._process_check_attempts += 1

            app = self.parent_app
            if not app or not hasattr(app, "dpi_starter"):
                self._stop_process_monitoring()
                self.show_success()
                return

            running = app.dpi_starter.check_process_running_wmi(silent=True)
            if running:
                self._stop_process_monitoring()
                self.show_success()
                return

            if self._process_check_attempts >= self._max_check_attempts:
                self._stop_process_monitoring()
                self.show_success()
                return
        except Exception:
            self._stop_process_monitoring()
            self.show_success()

    # ------------------------------------------------------------------
    # Compatibility API
    # ------------------------------------------------------------------

    def _refresh_runtime_state(self) -> None:
        fresh = self._load_current_selections()
        self.category_selections = fresh

        if self._unified_list is not None:
            self._unified_list.set_selections(self.category_selections)

        if self._detail_tree is not None and self._selected_category_key:
            sid = self.category_selections.get(self._selected_category_key, "none")
            self._detail_tree.set_selected_strategy(sid if self._detail_tree.has_strategy(sid) else "none")

        self._update_current_strategies_display()

    def _update_current_strategies_display(self) -> None:
        if self.current_strategy_label is None:
            return

        active = sum(1 for sid in (self.category_selections or {}).values() if sid and sid != "none")
        if active > 0:
            self.current_strategy_label.setText(
                tr_catalog(
                    "page.z2_orchestra_strategies.current.active_count",
                    language=self._ui_language,
                    default="{count} активных",
                ).format(count=active)
            )
        else:
            self.current_strategy_label.setText(
                tr_catalog(
                    "page.z2_orchestra_strategies.current.not_selected",
                    language=self._ui_language,
                    default="Не выбрана",
                )
            )

    def update_current_strategy(self, name: str) -> None:
        _ = name
        if not self.isVisible():
            self._preset_refresh_pending = True
            return
        self._refresh_runtime_state()

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
            fields={"current_strategy_summary", "active_preset_revision", "preset_content_revision", "mode_revision"},
            emit_initial=True,
        )

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        if "mode_revision" in changed_fields:
            if not self.isVisible():
                self._current_mode = None
                self._reset_mode_view_state()
                return
            self.reload_for_mode_change()
            return
        if "active_preset_revision" in changed_fields or "preset_content_revision" in changed_fields:
            if not self.isVisible():
                self._preset_refresh_pending = True
                return
            self._refresh_runtime_state()
        if "current_strategy_summary" in changed_fields or not changed_fields:
            self.update_current_strategy(state.current_strategy_summary)

    def reload_for_mode_change(self) -> None:
        self._stop_process_monitoring()
        self._current_mode = None
        self._reset_mode_view_state()

        if self.isVisible():
            self._rebuild_current_view()

    def disable_categories_for_filter(self, filter_key: str, categories_to_disable: list) -> None:
        _ = filter_key
        if not categories_to_disable:
            return
        try:
            from preset_orchestra_zapret2 import PresetManager

            for key in categories_to_disable:
                if key in self.category_selections:
                    self.category_selections[key] = "none"

            ok = PresetManager().set_strategy_selections(self.category_selections, save_and_sync=True)
            if not ok:
                raise RuntimeError("Не удалось применить orchestra selections")

            if self._has_any_active_strategy():
                self._restart_dpi_with_current_selections()
            else:
                self._stop_dpi_for_no_active_strategies()

            self._update_dpi_filters_display()
            self._refresh_runtime_state()
        except Exception as e:
            log(f"Ошибка disable_categories_for_filter: {e}", "ERROR")

    def on_external_filters_changed(self, query) -> None:
        _ = query

    def on_external_sort_changed(self, sort_key: str, reverse: bool) -> None:
        _ = (sort_key, reverse)
