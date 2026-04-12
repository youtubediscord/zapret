# ui/main_window.py
"""
Главное окно приложения — навигация через qfluentwidgets FluentWindow.

Все страницы добавляются через addSubInterface() вместо ручного SideNavBar + QStackedWidget.
Бизнес-логика (сигналы, обработчики) сохранена без изменений.
"""
from PyQt6.QtCore import QTimer, pyqtSignal, QModelIndex
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QCompleter
from typing import Any, cast


try:
    from qfluentwidgets import (
        NavigationItemPosition, FluentIcon,
    )
    try:
        from qfluentwidgets import SearchLineEdit
    except ImportError:
        SearchLineEdit = QLineEdit
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False
    NavigationItemPosition = cast(Any, None)
    FluentIcon = cast(Any, None)
    SearchLineEdit = QLineEdit

from ui.page_names import PageName
from ui.router import get_page_route_key
from ui.text_catalog import tr as tr_catalog
from ui.main_window_navigation import (
    redirect_to_strategies_page_for_method,
)
from ui.main_window_navigation_build import (
    add_nav_item,
    apply_nav_visibility_filter,
    apply_ui_language_to_page,
    attach_sidebar_search_to_titlebar,
    get_nav_label,
    get_sidebar_search_pages,
    init_navigation,
    on_sidebar_search_changed,
    on_sidebar_search_result_activated,
    on_sidebar_search_result_text_activated,
    refresh_navigation_texts,
    refresh_pages_language,
    resolve_ui_language,
    route_search_result,
    route_sidebar_search_by_text,
    setup_sidebar_search_completer,
    sync_nav_visibility,
    update_sidebar_search_suggestions,
    update_titlebar_search_width,
)
from ui.main_window_pages import (
    connect_lazy_page_signals,
    connect_signal_once,
    create_pages,
    ensure_page,
    ensure_page_in_stacked_widget,
    get_eager_page_names,
    get_loaded_page,
    has_nav_item,
    set_stacked_widget_current_page,
)
from ui.main_window_mode_switch import (
    auto_start_after_main_window_method_switch,
    complete_main_window_method_switch,
)
from ui.main_window_display import (
    get_direct_strategy_summary,
    set_status_text as set_main_window_status_text,
    update_autostart_display as update_main_window_autostart_display,
    update_current_strategy_display as update_main_window_current_strategy_display,
    update_subscription_display as update_main_window_subscription_display,
)
from ui.main_window_page_dispatch import (
    call_loaded_page_method,
    show_active_strategy_page_loading,
    show_active_strategy_page_success,
)
from ui.main_window_bootstrap_flow import (
    create_preset_runtime_coordinator,
    ensure_session_memory_defaults,
    finalize_page_signal_bootstrap,
    finish_ui_bootstrap,
    get_current_launch_method_for_preset_runtime,
    initialize_build_ui_state,
    resolve_active_preset_watch_path,
)
from ui.main_window_startup_metrics import (
    log_startup_page_init_summary,
    pump_startup_ui,
    record_startup_page_init_metric,
)
from ui.main_window_state_flow import (
    refresh_pages_after_preset_switch,
)

# ---------------------------------------------------------------------------
# Navigation icon mapping (SectionName/PageName -> FluentIcon)
# ---------------------------------------------------------------------------
_NAV_ICONS = {
    PageName.CONTROL: FluentIcon.COMMAND_PROMPT if HAS_FLUENT else None,
    PageName.ZAPRET2_DIRECT_CONTROL: FluentIcon.GAME if HAS_FLUENT else None,
    PageName.AUTOSTART: FluentIcon.POWER_BUTTON if HAS_FLUENT else None,
    PageName.NETWORK: FluentIcon.WIFI if HAS_FLUENT else None,
    PageName.HOSTS: FluentIcon.GLOBE if HAS_FLUENT else None,
    PageName.BLOCKCHECK: FluentIcon.CODE if HAS_FLUENT else None,
    PageName.APPEARANCE: FluentIcon.PALETTE if HAS_FLUENT else None,
    PageName.PREMIUM: FluentIcon.HEART if HAS_FLUENT else None,
    PageName.LOGS: FluentIcon.HISTORY if HAS_FLUENT else None,
    PageName.ABOUT: FluentIcon.INFO if HAS_FLUENT else None,
    PageName.DPI_SETTINGS: FluentIcon.SETTING if HAS_FLUENT else None,
    PageName.HOSTLIST: FluentIcon.BOOK_SHELF if HAS_FLUENT else None,
    PageName.BLOBS: FluentIcon.CLOUD if HAS_FLUENT else None,
    PageName.NETROGAT: FluentIcon.REMOVE_FROM if HAS_FLUENT else None,
    PageName.CUSTOM_DOMAINS: FluentIcon.ADD if HAS_FLUENT else None,
    PageName.CUSTOM_IPSET: FluentIcon.ADD if HAS_FLUENT else None,
    PageName.ZAPRET2_USER_PRESETS: FluentIcon.FOLDER if HAS_FLUENT else None,
    PageName.SERVERS: FluentIcon.UPDATE if HAS_FLUENT else None,
    PageName.SUPPORT: FluentIcon.CHAT if HAS_FLUENT else None,
    PageName.ORCHESTRA: FluentIcon.MUSIC if HAS_FLUENT else None,
    PageName.ORCHESTRA_SETTINGS: FluentIcon.SETTING if HAS_FLUENT else None,
    PageName.ZAPRET2_DIRECT: FluentIcon.PLAY if HAS_FLUENT else None,
    PageName.ZAPRET1_DIRECT_CONTROL: FluentIcon.GAME if HAS_FLUENT else None,
    PageName.ZAPRET1_DIRECT: FluentIcon.PLAY if HAS_FLUENT else None,
    PageName.ZAPRET1_USER_PRESETS: FluentIcon.FOLDER if HAS_FLUENT else None,
    PageName.TELEGRAM_PROXY: FluentIcon.SEND if HAS_FLUENT else None,
}

# Russian labels for navigation
_NAV_LABELS = {
    PageName.CONTROL: "Управление",
    PageName.ZAPRET2_DIRECT_CONTROL: "Управление Zapret 2",
    PageName.AUTOSTART: "Автозапуск",
    PageName.NETWORK: "Сеть",
    PageName.HOSTS: "Редактор файла hosts",
    PageName.BLOCKCHECK: "BlockCheck",
    PageName.APPEARANCE: "Оформление",
    PageName.PREMIUM: "Донат",
    PageName.LOGS: "Логи",
    PageName.ABOUT: "О программе",
    PageName.DPI_SETTINGS: "Сменить режим DPI",
    PageName.HOSTLIST: "Листы",
    PageName.BLOBS: "Блобы",
    PageName.NETROGAT: "Исключения",
    PageName.CUSTOM_DOMAINS: "Мои hostlist",
    PageName.CUSTOM_IPSET: "Мои ipset",
    PageName.ZAPRET2_USER_PRESETS: "Мои пресеты",
    PageName.SERVERS: "Обновления",
    PageName.SUPPORT: "Поддержка",
    PageName.ORCHESTRA: "Оркестратор",
    PageName.ORCHESTRA_SETTINGS: "Настройки оркестратора",
    PageName.ZAPRET2_DIRECT: "Прямой запуск",
    PageName.ZAPRET1_DIRECT_CONTROL: "Управление Zapret 1",
    PageName.ZAPRET1_DIRECT: "Стратегии Z1",
    PageName.ZAPRET1_USER_PRESETS: "Мои пресеты Z1",
    PageName.TELEGRAM_PROXY: "Telegram Proxy",
}


if HAS_FLUENT:
    class _SidebarSearchNavWidget(QWidget):
        textChanged = pyqtSignal(str)

        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)
            self._search = SearchLineEdit(self)
            self._completion_timer = QTimer(self)
            self._completion_timer.setSingleShot(True)
            self._completion_timer.timeout.connect(self._show_completions_deferred)
            self._search.setPlaceholderText(tr_catalog("sidebar.search.placeholder"))
            try:
                self._search.setClearButtonEnabled(True)
            except Exception:
                pass
            self._search.textChanged.connect(self.textChanged.emit)

            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 4, 0, 4)
            layout.setSpacing(0)
            layout.addWidget(self._search)

            self.setFixedHeight(40)

        def clear(self) -> None:
            self._search.clear()

        def text(self) -> str:
            return self._search.text()

        def set_placeholder_text(self, text: str) -> None:
            self._search.setPlaceholderText(text or "")

        def set_completer(self, completer: QCompleter) -> None:
            self._search.setCompleter(completer)

        def show_completions(self) -> None:
            # Defer popup interaction to avoid re-entrant completer/model updates
            # from textChanged handlers, which can crash native Qt on Windows.
            if not self.isVisible() or not self._search.isVisible() or not self._search.hasFocus():
                return
            self._completion_timer.start(0)

        def _show_completions_deferred(self) -> None:
            completer = self._search.completer()
            if completer is None:
                return
            if not self._search.text().strip():
                return

            try:
                completion_model = completer.completionModel()
                if completion_model is not None and completion_model.rowCount() <= 0:
                    return
            except Exception:
                pass

            completer.setCompletionPrefix(self._search.text())
            # Avoid direct popup forcing here: on some Windows/Qt stacks it can
            # crash natively during re-entrant completer/model updates.


class MainWindowUI:
    """
    Mixin: creates pages and registers them with FluentWindow navigation.
    """

    def build_ui(self, width: int, height: int):
        """Build UI: create pages and populate FluentWindow navigation sidebar.

        Note: window geometry (size/position) is restored in __init__ via the
        dedicated window geometry controller before this is called — do NOT
        resize here, that would overwrite the saved geometry.
        """
        _ = width
        _ = height
        initialize_build_ui_state(
            self,
            nav_icons=_NAV_ICONS,
            nav_labels=_NAV_LABELS,
            has_fluent=HAS_FLUENT,
            default_nav_icon=FluentIcon.APPLICATION if HAS_FLUENT else None,
            nav_scroll_position=NavigationItemPosition.SCROLL if HAS_FLUENT else None,
            sidebar_search_widget_cls=_SidebarSearchNavWidget if HAS_FLUENT else None,
        )
        self._preset_runtime_coordinator = create_preset_runtime_coordinator(self)

        self._page_signal_bootstrap_complete = False
        create_pages(self)

        # Register pages in navigation sidebar
        init_navigation(self)

        # После перехода на lazy pages уже созданные eager-страницы тоже должны
        # получить те же подключения сигналов, что и ленивые страницы.
        finalize_page_signal_bootstrap(self)

        # Session memory
        ensure_session_memory_defaults(self)

    def finish_ui_bootstrap(self) -> None:
        """Дозавершает тяжёлые связи главного окна после первого показа UI.

        На старте нам важно как можно быстрее показать рабочее окно и первую
        страницу. Общие подписки окна на preset-store, file watcher активного
        пресета и часть сервисных связей можно подключить позже, отдельным
        шагом, не блокируя первый визуальный отклик.
        """
        finish_ui_bootstrap(self)

    @staticmethod
    def _get_current_launch_method_for_preset_runtime() -> str:
        return get_current_launch_method_for_preset_runtime()

    def _resolve_active_preset_watch_path(self) -> str:
        return resolve_active_preset_watch_path(self)

    def _pump_startup_ui(self, force: bool = False) -> None:
        pump_startup_ui(self, force=force)

    def _record_startup_page_init_metric(self, page_name: PageName, elapsed_ms: int) -> None:
        record_startup_page_init_metric(self, page_name, elapsed_ms)

    def _log_startup_page_init_summary(self) -> None:
        log_startup_page_init_summary(self)

    def _get_launch_method(self) -> str:
        try:
            from strategy_menu import get_strategy_launch_method

            method = (get_strategy_launch_method() or "").strip().lower()
        except Exception:
            method = ""
        return method or "direct_zapret2"

    def _add_nav_item(self, page_name: PageName, position) -> None:
        add_nav_item(self, page_name, position)

    # ------------------------------------------------------------------
    # Navigation setup (FluentWindow sidebar)
    # ------------------------------------------------------------------

    def _init_navigation(self):
        init_navigation(self)

    def _attach_sidebar_search_to_titlebar(self) -> None:
        attach_sidebar_search_to_titlebar(self)

    def _update_titlebar_search_width(self) -> None:
        update_titlebar_search_width(self)

    def _sync_nav_visibility(self, method: str | None = None) -> None:
        sync_nav_visibility(self, method)

    def _on_sidebar_search_changed(self, text: str) -> None:
        on_sidebar_search_changed(self, text)

    def _apply_nav_visibility_filter(self) -> None:
        apply_nav_visibility_filter(self)

    def _resolve_ui_language(self) -> str:
        return resolve_ui_language(self)

    def _get_nav_label(self, page_name: PageName) -> str:
        return get_nav_label(self, page_name)

    def _get_sidebar_search_pages(self) -> set[PageName]:
        return get_sidebar_search_pages(self)

    def _setup_sidebar_search_completer(self) -> None:
        setup_sidebar_search_completer(self)

    def _update_sidebar_search_suggestions(self) -> None:
        update_sidebar_search_suggestions(self)

    def _on_sidebar_search_result_activated(self, index: QModelIndex) -> None:
        on_sidebar_search_result_activated(self, index)

    def _on_sidebar_search_result_text_activated(self, text: str) -> None:
        on_sidebar_search_result_text_activated(self, text)

    def _route_sidebar_search_by_text(self, text: str, prefer_first: bool = False) -> bool:
        return route_sidebar_search_by_text(self, text, prefer_first=prefer_first)

    def _route_search_result(self, page_name: PageName, tab_key: str = "") -> None:
        route_search_result(self, page_name, tab_key)

    def _refresh_navigation_texts(self) -> None:
        refresh_navigation_texts(self)

    def _apply_ui_language_to_page(self, page: QWidget | None) -> None:
        apply_ui_language_to_page(self, page)

    def _refresh_pages_language(self) -> None:
        refresh_pages_language(self)

    # ------------------------------------------------------------------
    # Page creation (lazy + eager) — UNCHANGED logic
    # ------------------------------------------------------------------

    def _get_eager_page_names(self) -> tuple[PageName, ...]:
        return get_eager_page_names(self)

    def _create_pages(self):
        create_pages(self)

    def _connect_signal_once(self, key: str, signal_obj, slot_obj) -> None:
        connect_signal_once(self, key, signal_obj, slot_obj)

    def _connect_lazy_page_signals(self, page_name: PageName, page: QWidget) -> None:
        connect_lazy_page_signals(self, page_name, page)


    def _ensure_page_in_stacked_widget(self, page: QWidget | None) -> None:
        ensure_page_in_stacked_widget(self, page)

    def _ensure_page(self, name: PageName) -> QWidget | None:
        return ensure_page(self, name)

    def _get_loaded_page(self, name: PageName) -> QWidget | None:
        return get_loaded_page(self, name)

    def get_loaded_page(self, name: PageName) -> QWidget | None:
        return get_loaded_page(self, name)

    def get_page(self, name: PageName) -> QWidget:
        return self._ensure_page(name)

    def show_page(self, name: PageName) -> bool:
        """Switch to the given page. Works with FluentWindow's switchTo()."""
        page = self._ensure_page(name)
        if page is None:
            return False
        self._ensure_page_in_stacked_widget(page)
        use_nav_route = has_nav_item(self, name)

        switched = set_stacked_widget_current_page(self, page, animate=use_nav_route)
        if not switched:
            return False

        try:
            route_key = get_page_route_key(name)
            if route_key and use_nav_route:
                self.navigationInterface.setCurrentItem(route_key)
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------
    # All handler methods — PRESERVED from original
    # ------------------------------------------------------------------

    def _refresh_pages_after_preset_switch(self):
        refresh_pages_after_preset_switch(self)

    def _complete_method_switch(self, method: str):
        complete_main_window_method_switch(self, method)

    def _redirect_to_strategies_page_for_method(self, method: str) -> None:
        redirect_to_strategies_page_for_method(self, method)

    def _auto_start_after_method_switch(self, method: str):
        auto_start_after_main_window_method_switch(self, method)

    def _get_direct_strategy_summary(self, max_items: int = 2) -> str:
        return get_direct_strategy_summary(self, max_items=max_items)

    def update_current_strategy_display(self, strategy_name: str):
        update_main_window_current_strategy_display(self, strategy_name)

    def update_autostart_display(self, enabled: bool, strategy_name: str = None):
        update_main_window_autostart_display(self, enabled, strategy_name)

    def update_subscription_display(self, is_premium: bool, days: int = None):
        update_main_window_subscription_display(self, is_premium, days)

    def set_status_text(self, text: str, status: str = "neutral"):
        set_main_window_status_text(self, text, status)

    def _navigate_to_dpi_settings(self):
        self.show_page(PageName.DPI_SETTINGS)
