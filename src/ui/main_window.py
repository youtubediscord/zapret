# ui/main_window.py
"""
Главное окно приложения — навигация через qfluentwidgets FluentWindow.

Все страницы добавляются через addSubInterface() вместо ручного SideNavBar + QStackedWidget.
Бизнес-логика (сигналы, обработчики) сохранена без изменений.
"""
from PyQt6.QtCore import QTimer, QCoreApplication, QEventLoop, pyqtSignal, QModelIndex
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QCompleter
from PyQt6.QtGui import QStandardItemModel
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
from ui.page_registry import PAGE_CLASS_SPECS
from ui.router import get_page_route_key, resolve_strategy_detail_back_page_for_method, resolve_strategy_page_for_method
from ui.text_catalog import tr as tr_catalog
from ui.main_window_navigation import (
    open_zapret1_strategy_detail,
    open_zapret1_preset_detail,
    open_zapret2_preset_detail,
    open_zapret2_strategy_detail,
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
    get_loaded_page,
    has_nav_item,
    set_stacked_widget_current_page,
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
from ui.animation_policy import (
    apply_window_animation_policy,
    apply_window_editor_smooth_scroll_policy,
    apply_window_smooth_scroll_policy,
)
from ui.main_window_signals import connect_main_window_page_signals
from core.runtime.preset_runtime_coordinator import (
    PresetRuntimeCoordinator,
    resolve_active_preset_watch_path,
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
        self.pages: dict[PageName, QWidget] = {}
        self._page_class_specs = PAGE_CLASS_SPECS
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
            switch_direct_preset_async=lambda method: self.dpi_controller.switch_direct_preset_async(method),
            refresh_after_switch=self._refresh_pages_after_preset_switch,
        )

        self._page_signal_bootstrap_complete = False
        create_pages(self)

        # Register pages in navigation sidebar
        init_navigation(self)

        # После перехода на lazy pages уже созданные eager-страницы тоже должны
        # получить те же подключения сигналов, что и ленивые страницы.
        self._page_signal_bootstrap_complete = True
        for page_name, page in list(self.pages.items()):
            connect_lazy_page_signals(self, page_name, page)
            ensure_page_in_stacked_widget(self, page)

        # Session memory
        if not hasattr(self, "_direct_zapret2_last_opened_target_key"):
            self._direct_zapret2_last_opened_target_key = None
        if not hasattr(self, "_direct_zapret2_restore_detail_on_open"):
            self._direct_zapret2_restore_detail_on_open = False
        if not hasattr(self, "_main_window_page_signals_connected"):
            self._main_window_page_signals_connected = False

    def finish_ui_bootstrap(self) -> None:
        """Дозавершает тяжёлые связи главного окна после первого показа UI.

        На старте нам важно как можно быстрее показать рабочее окно и первую
        страницу. Общие подписки окна на preset-store, file watcher активного
        пресета и часть сервисных связей можно подключить позже, отдельным
        шагом, не блокируя первый визуальный отклик.
        """
        if bool(getattr(self, "_main_window_page_signals_connected", False)):
            return

        connect_main_window_page_signals(self)
        self._main_window_page_signals_connected = True
        self._log_startup_page_init_summary()

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
        paint/timer events so окно успевало плавно дорисовываться во время старта.
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

    # ------------------------------------------------------------------
    # All handler methods — PRESERVED from original
    # ------------------------------------------------------------------

    def _on_direct_mode_changed(self, mode: str):
        """Сигнализирует всем direct Z2 страницам, что basic/advanced режим изменился."""
        _ = mode
        try:
            if getattr(self, "ui_state_store", None) is not None:
                self.ui_state_store.bump_mode_revision()
        except Exception:
            pass

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
        apply_window_animation_policy(self, enabled)

    def _on_smooth_scroll_changed(self, enabled: bool):
        """Переключает плавную прокрутку страниц, списков и деревьев, но не редакторов."""
        apply_window_smooth_scroll_policy(self, enabled)

    def _on_editor_smooth_scroll_changed(self, enabled: bool):
        """Переключает плавную прокрутку только у текстовых редакторов."""
        apply_window_editor_smooth_scroll_policy(self, enabled)

    def _refresh_pages_after_preset_switch(self):
        try:
            display_name = self._get_direct_strategy_summary()
            if display_name:
                self.update_current_strategy_display(display_name)
        except Exception as e:
            from log import log
            log(f"Ошибка обновления display стратегии после смены пресета: {e}", "DEBUG")

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

    def _get_active_strategy_page_name(self) -> PageName | None:
        return resolve_strategy_page_for_method(self._get_launch_method())

    def _call_loaded_strategy_page_method(self, method_name: str) -> bool:
        page_name = self._get_active_strategy_page_name()
        if page_name is None:
            return False
        return self._call_loaded_page_method(page_name, method_name)

    def _call_loaded_page_method(
        self,
        page_name: PageName,
        method_name: str,
        *args,
        delay_ms: int = 0,
    ) -> bool:
        page = self.get_loaded_page(page_name)
        if page is None:
            return False
        handler = getattr(page, method_name, None)
        if not callable(handler):
            return False

        def _invoke() -> None:
            if bool(getattr(self, "_is_exiting", False) or getattr(self, "_closing_completely", False)):
                return
            try:
                handler(*args)
            except Exception:
                pass

        if int(delay_ms or 0) > 0:
            QTimer.singleShot(int(delay_ms), _invoke)
            return True

        try:
            handler(*args)
            return True
        except Exception:
            return False

    def _show_active_strategy_page_loading(self) -> bool:
        return self._call_loaded_strategy_page_method("show_loading")

    def _show_active_strategy_page_success(self) -> bool:
        return self._call_loaded_strategy_page_method("show_success")

    def _dispatch_detail_page_result(
        self,
        page_name: PageName,
        method_name: str,
        *args,
        delay_ms: int = 0,
        log_message: str | None = None,
    ) -> bool:
        if log_message:
            from log import log

            log(log_message, "INFO")
        return self._call_loaded_page_method(
            page_name,
            method_name,
            *args,
            delay_ms=delay_ms,
        )

    def _open_strategy_detail_with_logging(
        self,
        target_key: str,
        *,
        opener,
        error_prefix: str,
    ) -> bool:
        from log import log

        try:
            return bool(opener(self, target_key))
        except Exception as e:
            log(f"{error_prefix}: {e}", "ERROR")
            return False

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

    def _get_strategy_selection_source_page(self, launch_method: str | None) -> QWidget | None:
        page_name = resolve_strategy_page_for_method(launch_method)
        if page_name is None:
            return None
        return self.get_loaded_page(page_name)

    def _resolve_strategy_selection_display_name(
        self,
        launch_method: str | None,
        sender,
        strategy_name: str,
    ) -> str:
        normalized = str(launch_method or "").strip().lower()
        if normalized == "direct_zapret2" and sender is self._get_strategy_selection_source_page(normalized):
            return self._get_direct_strategy_summary()
        return strategy_name

    def _on_strategy_selected_from_page(self, strategy_id: str, strategy_name: str):
        from log import log

        launch_method = self._get_launch_method()

        sender = None
        try:
            sender = self.sender()
        except Exception:
            sender = None

        display_name = self._resolve_strategy_selection_display_name(
            launch_method,
            sender,
            strategy_name,
        )
        if display_name != strategy_name:
            self.update_current_strategy_display(display_name)
            return

        log(f"Стратегия выбрана из страницы: {strategy_id} - {strategy_name}", "INFO")
        self.update_current_strategy_display(strategy_name)

    def _on_open_target_detail(self, target_key: str, current_strategy_id: str):
        _ = current_strategy_id
        self._open_strategy_detail_with_logging(
            target_key,
            opener=open_zapret2_strategy_detail,
            error_prefix="Error opening target detail",
        )

    def _on_strategy_detail_back(self):
        from strategy_menu import get_strategy_launch_method
        method = get_strategy_launch_method()
        self.show_page(resolve_strategy_detail_back_page_for_method(method))

    def _on_strategy_detail_selected(self, target_key: str, strategy_id: str):
        self._dispatch_detail_page_result(
            PageName.ZAPRET2_DIRECT,
            "apply_strategy_selection",
            target_key,
            strategy_id,
            log_message=f"Strategy selected from detail: {target_key} = {strategy_id}",
        )

    def _on_strategy_detail_filter_mode_changed(self, target_key: str, filter_mode: str):
        self._dispatch_detail_page_result(
            PageName.ZAPRET2_DIRECT,
            "apply_filter_mode_change",
            target_key,
            filter_mode,
        )

    # ── Zapret 1 strategy detail ────────────────────────────────────────────

    def _open_zapret1_target_detail(self, target_key: str, target_info: dict) -> None:
        _ = target_info
        self._open_strategy_detail_with_logging(
            target_key,
            opener=open_zapret1_strategy_detail,
            error_prefix="Error opening V1 target detail",
        )

    def _on_z1_strategy_detail_selected(self, target_key: str, strategy_id: str) -> None:
        self._dispatch_detail_page_result(
            PageName.ZAPRET1_DIRECT,
            "refresh_strategy_list_state",
            log_message=f"V1 strategy detail selected: {target_key} = {strategy_id}",
            delay_ms=100,
        )

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
