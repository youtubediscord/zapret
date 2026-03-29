# ui/main_window.py
"""
Главное окно приложения — навигация через qfluentwidgets FluentWindow.

Все страницы добавляются через addSubInterface() вместо ручного SideNavBar + QStackedWidget.
Бизнес-логика (сигналы, обработчики) сохранена без изменений.
"""
from PyQt6.QtCore import QTimer, QCoreApplication, QEventLoop, pyqtSignal, Qt, QModelIndex
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QCompleter
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from importlib import import_module
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

from ui.page_names import PageName, SectionName
from ui.mode_page_scope import (
    get_sidebar_search_pages_for_method,
    should_add_nav_page_on_init,
)
from ui.text_catalog import (
    find_search_entries,
    format_search_result,
    get_nav_page_label,
    normalize_language,
    tr as tr_catalog,
)
from ui.main_window_compat import setup_main_window_compatibility_attrs
from ui.main_window_navigation import (
    open_zapret1_preset_detail,
    open_zapret1_preset_folders,
    open_zapret2_preset_detail,
    open_zapret2_preset_folders,
    navigate_to_control,
    navigate_to_strategies,
    redirect_to_strategies_page_for_method,
    refresh_active_zapret2_user_presets_page,
    refresh_page_if_possible,
    refresh_zapret1_user_presets_page,
    show_active_zapret2_control_page,
    show_autostart_page as show_main_window_autostart_page,
    show_hosts_page as show_main_window_hosts_page,
    show_servers_page as show_main_window_servers_page,
    show_active_zapret2_user_presets_page,
    show_zapret1_user_presets_page,
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
    on_ui_language_changed as on_main_window_ui_language_changed,
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
    resolve_page_name,
)
from ui.main_window_mode_switch import (
    auto_start_after_main_window_method_switch,
    complete_main_window_method_switch,
    handle_main_window_launch_method_changed,
)
from ui.main_window_display import (
    get_direct_strategy_summary,
    on_autostart_disabled,
    on_autostart_enabled,
    on_subscription_updated,
    open_subscription_dialog,
    set_status_text as set_main_window_status_text,
    update_autostart_display as update_main_window_autostart_display,
    update_current_strategy_display as update_main_window_current_strategy_display,
    update_subscription_display as update_main_window_subscription_display,
)
from ui.main_window_refresh import refresh_main_window_pages_after_preset_switch
from ui.main_window_signals import connect_main_window_page_signals
from core.runtime.preset_runtime_coordinator import (
    PresetRuntimeCoordinator,
    resolve_active_preset_watch_path,
)

# ---------------------------------------------------------------------------
# Page class specs — UNCHANGED from original
# ---------------------------------------------------------------------------

_PAGE_CLASS_SPECS: dict[PageName, tuple[str, str, str]] = {
    PageName.HOME: ("home_page", "ui.pages.home_page", "HomePage"),
    PageName.CONTROL: ("control_page", "ui.pages.control_page", "ControlPage"),
    PageName.ZAPRET2_DIRECT_CONTROL: (
        "zapret2_direct_control_page",
        "ui.pages.zapret2.direct_control_page",
        "Zapret2DirectControlPage",
    ),
    PageName.ZAPRET2_DIRECT: (
        "zapret2_strategies_page",
        "ui.pages.zapret2.direct_zapret2_page",
        "Zapret2StrategiesPageNew",
    ),
    PageName.ZAPRET2_STRATEGY_DETAIL: (
        "strategy_detail_page",
        "ui.pages.zapret2.strategy_detail_page",
        "StrategyDetailPage",
    ),
    PageName.ZAPRET2_PRESET_DETAIL: (
        "zapret2_preset_detail_page",
        "ui.pages.zapret2.preset_detail_page",
        "Zapret2PresetDetailPage",
    ),
    PageName.ZAPRET2_PRESET_FOLDERS: (
        "zapret2_preset_folders_page",
        "ui.pages.zapret2.preset_folders_page",
        "Zapret2PresetFoldersPage",
    ),
    PageName.ZAPRET2_ORCHESTRA: (
        "zapret2_orchestra_strategies_page",
        "ui.pages.zapret2_orchestra_strategies_page",
        "Zapret2OrchestraStrategiesPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_CONTROL: (
        "orchestra_zapret2_control_page",
        "ui.pages.orchestra_zapret2.direct_control_page",
        "OrchestraZapret2DirectControlPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_USER_PRESETS: (
        "orchestra_zapret2_user_presets_page",
        "ui.pages.orchestra_zapret2.user_presets_page",
        "OrchestraZapret2UserPresetsPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_STRATEGY_DETAIL: (
        "orchestra_strategy_detail_page",
        "ui.pages.orchestra_zapret2.strategy_detail_page",
        "OrchestraZapret2StrategyDetailPage",
    ),
    PageName.ZAPRET1_DIRECT_CONTROL: (
        "zapret1_direct_control_page",
        "ui.pages.zapret1.direct_control_page",
        "Zapret1DirectControlPage",
    ),
    PageName.ZAPRET1_DIRECT: (
        "zapret1_strategies_page",
        "ui.pages.zapret1.direct_zapret1_page",
        "Zapret1StrategiesPage",
    ),
    PageName.ZAPRET1_USER_PRESETS: (
        "zapret1_user_presets_page",
        "ui.pages.zapret1.user_presets_page",
        "Zapret1UserPresetsPage",
    ),
    PageName.ZAPRET1_STRATEGY_DETAIL: (
        "zapret1_strategy_detail_page",
        "ui.pages.zapret1.strategy_detail_page_v1",
        "Zapret1StrategyDetailPage",
    ),
    PageName.ZAPRET1_PRESET_DETAIL: (
        "zapret1_preset_detail_page",
        "ui.pages.zapret1.preset_detail_page",
        "Zapret1PresetDetailPage",
    ),
    PageName.ZAPRET1_PRESET_FOLDERS: (
        "zapret1_preset_folders_page",
        "ui.pages.zapret1.preset_folders_page",
        "Zapret1PresetFoldersPage",
    ),
    PageName.HOSTLIST: ("hostlist_page", "ui.pages.hostlist_page", "HostlistPage"),
    PageName.BLOBS: ("blobs_page", "ui.pages.blobs_page", "BlobsPage"),
    PageName.DPI_SETTINGS: ("dpi_settings_page", "ui.pages.dpi_settings_page", "DpiSettingsPage"),
    PageName.ZAPRET2_USER_PRESETS: (
        "zapret2_user_presets_page",
        "ui.pages.zapret2.user_presets_page",
        "Zapret2UserPresetsPage",
    ),
    PageName.NETROGAT: ("netrogat_page", "ui.pages.netrogat_page", "NetrogatPage"),
    PageName.CUSTOM_DOMAINS: ("custom_domains_page", "ui.pages.custom_domains_page", "CustomDomainsPage"),
    PageName.CUSTOM_IPSET: ("custom_ipset_page", "ui.pages.custom_ipset_page", "CustomIpSetPage"),
    PageName.AUTOSTART: ("autostart_page", "ui.pages.autostart_page", "AutostartPage"),
    PageName.NETWORK: ("network_page", "ui.pages.network_page", "NetworkPage"),
    PageName.HOSTS: ("hosts_page", "ui.pages.hosts_page", "HostsPage"),
    PageName.BLOCKCHECK: ("blockcheck_page", "ui.pages.blockcheck_page", "BlockcheckPage"),
    PageName.APPEARANCE: ("appearance_page", "ui.pages.appearance_page", "AppearancePage"),
    PageName.PREMIUM: ("premium_page", "ui.pages.premium_page", "PremiumPage"),
    PageName.LOGS: ("logs_page", "ui.pages.logs_page", "LogsPage"),
    PageName.SERVERS: ("servers_page", "ui.pages.servers_page", "ServersPage"),
    PageName.ABOUT: ("about_page", "ui.pages.about_page", "AboutPage"),
    PageName.SUPPORT: ("support_page", "ui.pages.support_page", "SupportPage"),
    PageName.ORCHESTRA: ("orchestra_page", "ui.pages.orchestra_page", "OrchestraPage"),
    PageName.ORCHESTRA_SETTINGS: (
        "orchestra_settings_page",
        "ui.pages.orchestra",
        "OrchestraSettingsPage",
    ),
    PageName.TELEGRAM_PROXY: (
        "telegram_proxy_page",
        "ui.pages.telegram_proxy_page",
        "TelegramProxyPage",
    ),
}

_PAGE_ALIASES: dict[PageName, PageName] = {
    PageName.IPSET: PageName.HOSTLIST,
    # Legacy routes kept for backward compatibility
    PageName.DIAGNOSTICS_TAB: PageName.BLOCKCHECK,
    PageName.CONNECTION_TEST: PageName.BLOCKCHECK,
    PageName.DNS_CHECK: PageName.BLOCKCHECK,
}

_EAGER_PAGE_NAMES_BASE: tuple[PageName, ...] = (
    PageName.AUTOSTART,
    PageName.DPI_SETTINGS,
    PageName.APPEARANCE,
    PageName.ABOUT,
    PageName.PREMIUM,
)

_EAGER_MODE_ENTRY_PAGE: dict[str, PageName] = {
    "direct_zapret2": PageName.ZAPRET2_DIRECT_CONTROL,
    "direct_zapret2_orchestra": PageName.ZAPRET2_ORCHESTRA_CONTROL,
    "direct_zapret1": PageName.ZAPRET1_DIRECT_CONTROL,
    "orchestra": PageName.ORCHESTRA,
}


# ---------------------------------------------------------------------------
# Navigation icon mapping (SectionName/PageName -> FluentIcon)
# ---------------------------------------------------------------------------
_NAV_ICONS = {
    PageName.HOME: FluentIcon.HOME if HAS_FLUENT else None,
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
    PageName.ZAPRET2_ORCHESTRA: FluentIcon.ROBOT if HAS_FLUENT else None,
    PageName.ZAPRET2_ORCHESTRA_CONTROL: FluentIcon.GAME if HAS_FLUENT else None,
    PageName.ZAPRET2_ORCHESTRA_USER_PRESETS: FluentIcon.FOLDER if HAS_FLUENT else None,
    PageName.ZAPRET1_DIRECT_CONTROL: FluentIcon.GAME if HAS_FLUENT else None,
    PageName.ZAPRET1_DIRECT: FluentIcon.PLAY if HAS_FLUENT else None,
    PageName.ZAPRET1_USER_PRESETS: FluentIcon.FOLDER if HAS_FLUENT else None,
    PageName.TELEGRAM_PROXY: FluentIcon.SEND if HAS_FLUENT else None,
}

# Russian labels for navigation
_NAV_LABELS = {
    PageName.HOME: "Главная",
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
    PageName.ZAPRET2_ORCHESTRA: "Прямой запуск",
    PageName.ZAPRET2_ORCHESTRA_CONTROL: "Управление оркестр. Zapret 2",
    PageName.ZAPRET2_ORCHESTRA_USER_PRESETS: "Мои пресеты",
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

        Note: window geometry (size/position) is restored in __init__ via
        restore_window_geometry() before this is called — do NOT resize here,
        that would overwrite the saved geometry.
        """
        self.pages: dict[PageName, QWidget] = {}
        self._page_aliases: dict[PageName, PageName] = dict(_PAGE_ALIASES)
        self._page_class_specs = _PAGE_CLASS_SPECS
        self._eager_page_names_base = _EAGER_PAGE_NAMES_BASE
        self._eager_mode_entry_page = _EAGER_MODE_ENTRY_PAGE
        self._nav_icons = _NAV_ICONS
        self._nav_labels = _NAV_LABELS
        self._default_nav_icon = FluentIcon.APPLICATION if HAS_FLUENT else None
        self._has_fluent_nav = HAS_FLUENT
        self._nav_scroll_position = NavigationItemPosition.SCROLL if HAS_FLUENT else None
        self._sidebar_search_widget_cls = _SidebarSearchNavWidget if HAS_FLUENT else None
        self._lazy_signal_connections: set[str] = set()
        self._startup_ui_pump_counter = 0
        self._nav_search_query = ""
        self._nav_mode_visibility: dict[PageName, bool] = {}
        self._nav_headers: list[tuple[QWidget, tuple[PageName, ...], str]] = []
        self._sidebar_search_nav_widget = None
        self._sidebar_search_model: QStandardItemModel | None = None
        self._sidebar_search_completer: QCompleter | None = None
        self._sidebar_search_titlebar_attached = False
        self._ui_language = resolve_ui_language(self)
        self._startup_page_init_metrics: list[tuple[str, int]] = []
        self._preset_runtime_coordinator = PresetRuntimeCoordinator(
            self,
            get_launch_method=self._get_current_launch_method_for_preset_runtime,
            get_active_preset_path=resolve_active_preset_watch_path,
            is_dpi_running=lambda: bool(
                hasattr(self, "dpi_controller")
                and self.dpi_controller
                and self.dpi_controller.is_running()
            ),
            restart_dpi_async=lambda: self.dpi_controller.restart_dpi_async(),
            refresh_after_switch=self._refresh_pages_after_preset_switch,
        )

        self._page_signal_bootstrap_complete = False
        create_pages(self)

        # Register pages in navigation sidebar
        init_navigation(self)

        # Wire up signals
        connect_main_window_page_signals(self)
        self._page_signal_bootstrap_complete = True

        # Backward-compat attrs
        setup_main_window_compatibility_attrs(self)
        self._log_startup_page_init_summary()

        # Session memory
        if not hasattr(self, "_direct_zapret2_last_opened_target_key"):
            self._direct_zapret2_last_opened_target_key = None
        if not hasattr(self, "_direct_zapret2_restore_detail_on_open"):
            self._direct_zapret2_restore_detail_on_open = False

    @staticmethod
    def _get_current_launch_method_for_preset_runtime() -> str:
        try:
            from strategy_menu import get_strategy_launch_method

            return str(get_strategy_launch_method() or "").strip().lower()
        except Exception:
            return ""

    def _pump_startup_ui(self, force: bool = False) -> None:
        """Yield to event loop during heavy startup UI composition.

        Qt widgets must be created on the main GUI thread, so we can't move page
        construction to worker threads. Instead, we periodically process pending
        paint/timer events so startup splash animations remain smooth.
        """
        try:
            self._startup_ui_pump_counter = int(getattr(self, "_startup_ui_pump_counter", 0)) + 1
            if not force and (self._startup_ui_pump_counter % 2) != 0:
                return

            app = QCoreApplication.instance()
            if app is None:
                return

            app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents, 8)
        except Exception:
            pass

    def _record_startup_page_init_metric(self, page_name: PageName, elapsed_ms: int) -> None:
        elapsed_i = max(0, int(elapsed_ms))

        metrics = getattr(self, "_startup_page_init_metrics", None)
        if isinstance(metrics, list):
            metrics.append((page_name.name, elapsed_i))

        try:
            from log import log as _log

            level = "⏱ STARTUP" if elapsed_i >= 120 else "DEBUG"
            _log(f"⏱ Startup UI PageInit: {page_name.name} {elapsed_i}ms", level)
        except Exception:
            pass

    def _log_startup_page_init_summary(self) -> None:
        metrics = getattr(self, "_startup_page_init_metrics", None)
        if not isinstance(metrics, list) or not metrics:
            return

        try:
            from log import log as _log

            top = sorted(metrics, key=lambda item: item[1], reverse=True)[:6]
            summary = ", ".join(f"{name}={elapsed}ms" for name, elapsed in top)
            _log(f"⏱ Startup UI PageInit TOP: {summary}", "⏱ STARTUP")
        except Exception:
            pass

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

    def _on_ui_language_changed(self, language: str) -> None:
        on_main_window_ui_language_changed(self, language)

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

    def _resolve_page_name(self, name: PageName) -> PageName:
        return resolve_page_name(self, name)

    def _connect_signal_once(self, key: str, signal_obj, slot_obj) -> None:
        connect_signal_once(self, key, signal_obj, slot_obj)

    def _connect_lazy_page_signals(self, page_name: PageName, page: QWidget) -> None:
        connect_lazy_page_signals(self, page_name, page)


    def _ensure_page_in_stacked_widget(self, page: QWidget | None) -> None:
        ensure_page_in_stacked_widget(self, page)

    def _ensure_page(self, name: PageName) -> QWidget | None:
        return ensure_page(self, name)

    def get_page(self, name: PageName) -> QWidget:
        return self._ensure_page(name)

    def show_page(self, name: PageName) -> bool:
        """Switch to the given page. Works with FluentWindow's switchTo()."""
        page = self._ensure_page(name)
        if page is None:
            return False
        self._ensure_page_in_stacked_widget(page)
        try:
            self.switchTo(page)
        except Exception:
            # Fallback for pages not registered in nav
            self._ensure_page_in_stacked_widget(page)
            if hasattr(self, 'stackedWidget'):
                self.stackedWidget.setCurrentWidget(page)
        return True

    def _show_active_zapret2_user_presets_page(self) -> None:
        show_active_zapret2_user_presets_page(self)

    def _show_zapret1_user_presets_page(self) -> None:
        show_zapret1_user_presets_page(self)

    def _refresh_page_if_possible(self, page_name: PageName) -> None:
        refresh_page_if_possible(self, page_name)

    def _refresh_active_zapret2_user_presets_page(self) -> None:
        refresh_active_zapret2_user_presets_page(self)

    def _refresh_zapret1_user_presets_page(self) -> None:
        refresh_zapret1_user_presets_page(self)

    def _open_zapret2_preset_detail(self, preset_name: str) -> None:
        open_zapret2_preset_detail(self, preset_name)

    def _open_zapret1_preset_detail(self, preset_name: str) -> None:
        open_zapret1_preset_detail(self, preset_name)

    def _open_zapret2_preset_folders(self) -> None:
        open_zapret2_preset_folders(self)

    def _open_zapret1_preset_folders(self) -> None:
        open_zapret1_preset_folders(self)


    # ------------------------------------------------------------------
    # All handler methods — PRESERVED from original
    # ------------------------------------------------------------------

    def _on_direct_mode_changed(self, mode: str):
        """Force rebuild of Прямой запуск page on next show."""
        page = getattr(self, "zapret2_strategies_page", None)
        if page and hasattr(page, "_strategy_set_snapshot"):
            page._strategy_set_snapshot = None

    def _on_background_refresh_needed(self):
        """Re-applies window background (called when tinted_bg or accent changes)."""
        try:
            from ui.theme import apply_window_background
            apply_window_background(self.window())
        except Exception:
            pass

    def _on_background_preset_changed(self, preset: str):
        """Apply new background preset to the window."""
        try:
            from ui.theme import apply_window_background
            apply_window_background(self.window(), preset=preset)
        except Exception:
            pass

    def _on_opacity_changed(self, value: int):
        """Apply window opacity from appearance_page slider."""
        win = self.window()
        if hasattr(win, 'set_window_opacity'):
            win.set_window_opacity(value)

    def _on_mica_changed(self, enabled: bool):
        """Save Mica setting and re-apply window background."""
        try:
            from config.reg import set_mica_enabled
            set_mica_enabled(enabled)
        except Exception:
            pass
        try:
            from ui.theme import apply_window_background
            apply_window_background(self.window())
        except Exception:
            pass

    def _on_animations_changed(self, enabled: bool):
        """Enable/disable all QPropertyAnimation-based animations (qfluentwidgets + Qt native)."""
        try:
            from PyQt6.QtCore import QPropertyAnimation, QAbstractAnimation

            if enabled:
                # Restore original start()
                if hasattr(QPropertyAnimation, '_zapret_original_start'):
                    QPropertyAnimation.start = QPropertyAnimation._zapret_original_start
                    del QPropertyAnimation._zapret_original_start
            else:
                # Monkey-patch start() to set duration=0 before every animation run
                if not hasattr(QPropertyAnimation, '_zapret_original_start'):
                    _orig = QPropertyAnimation.start
                    QPropertyAnimation._zapret_original_start = _orig

                    def _instant_start(
                        self,
                        policy=QAbstractAnimation.DeletionPolicy.KeepWhenStopped,
                    ):
                        self.setDuration(0)
                        QPropertyAnimation._zapret_original_start(self, policy)

                    QPropertyAnimation.start = _instant_start
        except Exception:
            pass

    def _on_smooth_scroll_changed(self, enabled: bool):
        """Toggle smooth scrolling on all existing pages and nested widgets."""
        try:
            from PyQt6.QtCore import Qt
            from PyQt6.QtWidgets import QWidget
            from qfluentwidgets.common.smooth_scroll import SmoothMode

            mode = SmoothMode.COSINE if enabled else SmoothMode.NO_SMOOTH

            def _apply_delegate_mode(delegate) -> None:
                if delegate is None:
                    return

                try:
                    if hasattr(delegate, "useAni"):
                        if not hasattr(delegate, "_zapret_base_use_ani"):
                            delegate._zapret_base_use_ani = bool(delegate.useAni)
                        delegate.useAni = bool(delegate._zapret_base_use_ani) if enabled else False
                except Exception:
                    pass

                for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                    smooth = getattr(delegate, smooth_attr, None)
                    setter = getattr(smooth, "setSmoothMode", None)
                    if callable(setter):
                        try:
                            setter(mode)
                        except Exception:
                            pass

                setter = getattr(delegate, "setSmoothMode", None)
                if callable(setter):
                    try:
                        setter(mode)
                    except TypeError:
                        try:
                            setter(mode, Qt.Orientation.Vertical)
                        except Exception:
                            pass
                    except Exception:
                        pass

            def _apply_smooth_mode(target) -> None:
                setter = getattr(target, "setSmoothMode", None)
                if callable(setter):
                    try:
                        setter(mode, Qt.Orientation.Vertical)
                    except TypeError:
                        try:
                            setter(mode)
                        except Exception:
                            pass
                    except Exception:
                        pass

                _apply_delegate_mode(getattr(target, "scrollDelegate", None))
                _apply_delegate_mode(getattr(target, "scrollDelagate", None))
                _apply_delegate_mode(getattr(target, "delegate", None))
                _apply_delegate_mode(getattr(target, "_presets_scroll_delegate", None))
                _apply_delegate_mode(getattr(target, "_smooth_scroll_delegate", None))

                custom_setter = getattr(target, "set_smooth_scroll_enabled", None)
                if callable(custom_setter):
                    try:
                        custom_setter(enabled)
                    except Exception:
                        pass

            for page in list(self.pages.values()):
                _apply_smooth_mode(page)
                for child in page.findChildren(QWidget):
                    _apply_smooth_mode(child)
        except Exception:
            pass

    def _refresh_pages_after_preset_switch(self):
        refresh_main_window_pages_after_preset_switch(self)

    def _on_clear_learned_requested(self):
        from log import log
        log("Запрошена очистка данных обучения", "INFO")
        if hasattr(self, 'orchestra_runner') and self.orchestra_runner:
            self.orchestra_runner.clear_learned_data()
            log("Данные обучения очищены", "INFO")

    def _on_launch_method_changed(self, method: str):
        handle_main_window_launch_method_changed(self, method)

    def _complete_method_switch(self, method: str):
        complete_main_window_method_switch(self, method)

    def _redirect_to_strategies_page_for_method(self, method: str) -> None:
        redirect_to_strategies_page_for_method(self, method)

    def _auto_start_after_method_switch(self, method: str):
        auto_start_after_main_window_method_switch(self, method)

    def _proxy_start_click(self):
        self.home_page.start_btn.click()

    def _proxy_stop_click(self):
        self.home_page.stop_btn.click()

    def _proxy_stop_and_exit(self):
        from log import log
        log("Остановка winws и закрытие программы...", "INFO")
        if hasattr(self, "request_exit"):
            self.request_exit(stop_dpi=True)
            return
        if hasattr(self, 'dpi_controller') and self.dpi_controller:
            self._closing_completely = True
            self.dpi_controller.stop_and_exit_async()
        else:
            self.home_page.stop_btn.click()
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()

    def _proxy_test_click(self):
        self.home_page.test_btn.click()

    def _proxy_folder_click(self):
        self.home_page.folder_btn.click()

    def _open_subscription_dialog(self):
        open_subscription_dialog(self)

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

    def _on_autostart_enabled(self):
        on_autostart_enabled(self)

    def _on_autostart_disabled(self):
        on_autostart_disabled(self)

    def _on_subscription_updated(self, is_premium: bool, days_remaining: int):
        on_subscription_updated(self, is_premium, days_remaining)

        if hasattr(self, 'appearance_page') and self.appearance_page:
            self.appearance_page.set_premium_status(is_premium)

    def _on_strategy_selected_from_page(self, strategy_id: str, strategy_name: str):
        from log import log
        try:
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
        except Exception:
            launch_method = "direct_zapret2"

        sender = None
        try:
            sender = self.sender()
        except Exception:
            sender = None

        if launch_method == "direct_zapret2" and sender is getattr(self, "zapret2_strategies_page", None):
            display_name = self._get_direct_strategy_summary()
            self.update_current_strategy_display(display_name)
            if hasattr(self, "parent_app"):
                try:
                    self.parent_app.current_strategy_name = display_name
                except Exception:
                    pass
            return

        log(f"Стратегия выбрана из страницы: {strategy_id} - {strategy_name}", "INFO")
        self.update_current_strategy_display(strategy_name)

        if hasattr(self, 'parent_app') and hasattr(self.parent_app, 'on_strategy_selected_from_dialog'):
            self.parent_app.on_strategy_selected_from_dialog(strategy_id, strategy_name)

    def _on_open_target_detail(self, target_key: str, current_strategy_id: str):
        from log import log

        try:
            detail_page = self._ensure_page(PageName.ZAPRET2_STRATEGY_DETAIL)
            if detail_page and hasattr(detail_page, 'show_target'):
                detail_page.show_target(target_key)

            self.show_page(PageName.ZAPRET2_STRATEGY_DETAIL)

            try:
                self._direct_zapret2_last_opened_target_key = target_key
                self._direct_zapret2_restore_detail_on_open = True
            except Exception:
                pass
        except Exception as e:
            log(f"Error opening target detail: {e}", "ERROR")

    def _on_strategy_detail_back(self):
        from strategy_menu import get_strategy_launch_method
        method = get_strategy_launch_method()

        if method == "direct_zapret2_orchestra":
            self.show_page(PageName.ZAPRET2_ORCHESTRA_CONTROL)
        elif method == "direct_zapret2":
            self.show_page(PageName.ZAPRET2_DIRECT)
        elif method == "direct_zapret1":
            self.show_page(PageName.ZAPRET1_DIRECT_CONTROL)
        else:
            self.show_page(PageName.CONTROL)

    def _on_strategy_detail_selected(self, target_key: str, strategy_id: str):
        from log import log
        log(f"Strategy selected from detail: {target_key} = {strategy_id}", "INFO")
        if hasattr(self, 'zapret2_strategies_page') and hasattr(self.zapret2_strategies_page, 'apply_strategy_selection'):
            self.zapret2_strategies_page.apply_strategy_selection(target_key, strategy_id)

    def _on_strategy_detail_filter_mode_changed(self, target_key: str, filter_mode: str):
        try:
            if hasattr(self, 'zapret2_strategies_page') and hasattr(self.zapret2_strategies_page, 'apply_filter_mode_change'):
                self.zapret2_strategies_page.apply_filter_mode_change(target_key, filter_mode)
        except Exception:
            pass

    # ── Zapret 1 strategy detail ────────────────────────────────────────────

    def _open_zapret1_target_detail(self, target_key: str, target_info: dict) -> None:
        from log import log
        try:
            detail_page = self._ensure_page(PageName.ZAPRET1_STRATEGY_DETAIL)
            if detail_page is None:
                log("ZAPRET1_STRATEGY_DETAIL page not found", "ERROR")
                return

            from core.presets.direct_facade import DirectPresetFacade

            def _reload_dpi():
                try:
                    page = getattr(self, "zapret1_direct_control_page", None)
                    if page and hasattr(page, "_reload_dpi"):
                        page._reload_dpi()
                except Exception:
                    pass

            manager = DirectPresetFacade.from_launch_method(
                "direct_zapret1",
                on_dpi_reload_needed=_reload_dpi,
            )
            _ = target_info
            detail_page.show_target(target_key, manager)
            self.show_page(PageName.ZAPRET1_STRATEGY_DETAIL)
        except Exception as e:
            log(f"Error opening V1 target detail: {e}", "ERROR")

    def _on_z1_strategy_detail_selected(self, target_key: str, strategy_id: str) -> None:
        from log import log
        log(f"V1 strategy detail selected: {target_key} = {strategy_id}", "INFO")
        # Обновить подписи на странице списка target'ов
        page = getattr(self, "zapret1_strategies_page", None)
        if page and hasattr(page, "_refresh_subtitles"):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, page._refresh_subtitles)

    def show_autostart_page(self):
        show_main_window_autostart_page(self)

    def show_hosts_page(self):
        show_main_window_hosts_page(self)

    def show_servers_page(self):
        show_main_window_servers_page(self)

    def _show_active_zapret2_control_page(self):
        show_active_zapret2_control_page(self)

    def _navigate_to_control(self):
        navigate_to_control(self)

    def _navigate_to_strategies(self):
        navigate_to_strategies(self)

    def _navigate_to_dpi_settings(self):
        self.show_page(PageName.DPI_SETTINGS)
