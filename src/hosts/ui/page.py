# hosts/ui/page.py
"""Страница управления Hosts файлом - разблокировка сервисов"""

import time
from string import Template
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtWidgets import (
    QWidget, QLabel,
    QLayout
)

import hosts.page_plans as hosts_page_plans
from hosts.ui.page_runtime import create_page_hosts_runtime, create_runtime_cache
from ui.pages.base_page import BasePage
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from hosts.ui.sections_build import (
    build_hosts_adobe_section,
    build_hosts_browser_warning,
    build_hosts_info_note,
    build_hosts_status_section,
)
from hosts.ui.services_build import (
    build_hosts_service_row,
    build_hosts_services_container,
    build_hosts_services_group,
    build_hosts_services_section_title,
)
from hosts.ui.selection_workflow import (
    apply_bulk_profile_selection_ui,
    apply_direct_toggle_ui,
    apply_profile_selection_ui,
)
from hosts.catalog_workflow import (
    apply_catalog_refresh_signature,
    ensure_catalog_watcher,
    reconcile_catalog_after_hidden_refresh,
)
from hosts.ui.access_workflow import (
    apply_restore_hosts_permissions_result_flow,
    check_hosts_access,
    dismiss_hosts_error_bar,
    show_hosts_access_error,
)
from hosts.operation_workflow import (
    complete_hosts_operation,
    reset_all_service_profiles_ui,
    start_hosts_operation,
)
from hosts.ui.page_lifecycle_helpers import (
    activate_hosts_page,
    apply_hosts_page_language,
    apply_hosts_page_theme,
    cleanup_hosts_page,
    close_service_combo_popups,
    install_host_window_event_filter,
    run_hosts_runtime_init_once,
)
from app.ui_texts import tr as tr_catalog

from log.log import log

from ui.theme import get_theme_tokens, get_themed_qta_icon
from ui.theme_semantic import get_semantic_palette

from qfluentwidgets import (
    BodyLabel, CaptionLabel, ComboBox, InfoBar, MessageBox, PushButton,
    StrongBodyLabel, SwitchButton,
)


_FLUENT_CHIP_STYLE_TEMPLATE = Template(
    """
QPushButton {
    background-color: transparent;
    border: none;
    color: $fg_muted;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 500;
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    text-decoration: none;
}
QPushButton:hover {
    color: $accent_hex;
    text-decoration: underline;
}
QPushButton:pressed {
    color: rgba($accent_rgb, 0.85);
}
QPushButton:disabled {
    color: $fg_faint;
}
"""
)


def _get_fluent_chip_style(tokens=None) -> str:
    tokens = tokens or get_theme_tokens()
    return _FLUENT_CHIP_STYLE_TEMPLATE.substitute(
        fg_muted=tokens.fg_muted,
        fg_faint=tokens.fg_faint,
        accent_hex=tokens.accent_hex,
        accent_rgb=tokens.accent_rgb_str,
    )

def _is_fluent_combo(obj) -> bool:
    """Проверяет, является ли объект qfluentwidgets ComboBox."""
    if ComboBox is not None and isinstance(obj, ComboBox):
        return True
    return False


class HostsPage(BasePage):
    """Страница управления Hosts файлом"""

    def __init__(self, parent=None, *, deps):
        super().__init__(
            "Hosts",
            "Управление разблокировкой сервисов через hosts файл",
            parent,
            title_key="page.hosts.title",
            subtitle_key="page.hosts.subtitle",
        )

        self._hosts = deps.hosts_feature
        self.hosts_runtime = None
        self.service_combos = {}
        self.service_icon_labels = {}
        self.service_icon_names = {}
        self.service_name_labels = {}
        self.service_icon_base_colors = {}
        self._services_section_title_labels = []
        self._service_group_title_labels = []
        self._service_group_chips_scrolls = []
        self._service_group_chip_buttons = []
        self._open_hosts_button = None
        self._info_text_label = None
        self._browser_warning_label = None
        self._adobe_desc_label = None
        self._adobe_title_label = None
        self._hosts_error_bar = None  # Текущий InfoBar ошибки доступа к hosts

        self._services_container = None
        self._services_layout = None
        self._catalog_sig = None
        self._catalog_dirty = False
        self._catalog_watch_timer = None
        self._host_window = None
        self._operation_runtime = OneShotWorkerRuntime()
        self._services_catalog_runtime = OneShotWorkerRuntime()
        self._catalog_refresh_runtime = OneShotWorkerRuntime()
        self._catalog_refresh_pending_trigger = ""
        self._catalog_refresh_start_scheduled = False
        self._selection_load_runtime = OneShotWorkerRuntime()
        self._selection_load_show_access_errors = False
        self._selection_load_pending = False
        self._selection_load_start_scheduled = False
        self._selection_save_runtime = OneShotWorkerRuntime()
        self._selection_save_pending = None
        self._selection_save_start_scheduled = False
        self._state_load_runtime = OneShotWorkerRuntime()
        self._state_load_pending = {"show_access_errors": False, "update_status": False}
        self._state_load_request_context = {"show_access_errors": False, "update_status": False}
        self._state_load_start_scheduled = False
        self._open_file_runtime = OneShotWorkerRuntime()
        self._open_file_pending = False
        self._open_file_start_scheduled = False
        self._permission_restore_runtime = OneShotWorkerRuntime()
        self._permission_restore_pending = False
        self._permission_restore_start_scheduled = False
        self._applying = False
        self._cleanup_in_progress = False
        self._runtime_cache = create_runtime_cache()
        self._last_error = None  # Последняя ошибка
        self._current_operation = None
        self._startup_initialized = False
        self._runtime_initialized = False
        self._runtime_access_checked = False
        self._service_dns_selection = {}

        self._build_ui()
        self._apply_page_theme(force=True)

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        """Applies theme tokens to widgets that still use raw setStyleSheet."""
        _ = force
        apply_hosts_page_theme(
            services_section_title_labels=self._services_section_title_labels,
            service_group_chips_scrolls=self._service_group_chips_scrolls,
            service_group_chip_buttons=self._service_group_chip_buttons,
            get_fluent_chip_style_fn=_get_fluent_chip_style,
            update_ui_fn=self._update_ui,
            get_theme_tokens_fn=lambda: tokens or get_theme_tokens(),
        )

    def on_page_activated(self) -> None:
        total_started_at = time.perf_counter()
        stage_started_at = time.perf_counter()
        self._run_runtime_init_once(show_access_errors=True)
        self._log_ui_timing("hosts_ui.runtime_init_once", stage_started_at)
        stage_started_at = time.perf_counter()
        self._start_catalog_watcher()
        self._log_ui_timing("hosts_ui.catalog_watcher.start", stage_started_at)
        stage_started_at = time.perf_counter()
        activate_hosts_page(
            install_host_window_event_filter_fn=self._install_host_window_event_filter,
            build_activation_plan_fn=hosts_page_plans.build_activation_plan,
            catalog_dirty=self._catalog_dirty,
            reconcile_hidden_refresh_fn=self._reconcile_catalog_after_hidden_refresh,
            invalidate_cache_fn=self._invalidate_cache,
            update_ui_fn=self._update_ui,
        )
        self._log_ui_timing("hosts_ui.activation_workflow", stage_started_at)
        self._log_ui_timing("hosts_ui.activation.total", total_started_at)

    def warmup_initial_load(self) -> bool:
        """Тихо готовит содержимое страницы до первого открытия пользователем."""
        if self._cleanup_in_progress:
            return False
        started_at = time.perf_counter()
        self._run_runtime_init_once(show_access_errors=False)
        self._log_ui_timing("hosts_ui.warmup.total", started_at)
        return True

    def _run_runtime_init_once(self, *, show_access_errors: bool = True) -> None:
        started_at = time.perf_counter()
        if self._runtime_initialized:
            if show_access_errors and not self._runtime_access_checked:
                self._check_hosts_access()
                self._runtime_access_checked = True
            return
        if not self._runtime_initialized:
            self._start_user_selection_load_worker(show_access_errors=show_access_errors)
            return
        self._finish_runtime_init_after_selection(show_access_errors=show_access_errors)

    def _start_user_selection_load_worker(self, *, show_access_errors: bool) -> None:
        self._selection_load_show_access_errors = (
            bool(self._selection_load_show_access_errors) or bool(show_access_errors)
        )
        if (
            self._selection_load_runtime.is_running()
            or self.__dict__.get("_selection_load_start_scheduled", False)
        ):
            self._selection_load_pending = True
            return
        started_at = time.perf_counter()
        self._selection_load_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._hosts.create_selection_load_worker(
                request_id,
                self,
            ),
            on_loaded=self._on_user_selection_load_finished,
            on_failed=self._on_user_selection_load_failed,
            on_finished=self._on_user_selection_load_worker_finished,
        )
        self._log_ui_timing("hosts_ui.user_selection.load.start_worker", started_at)

    def _on_user_selection_load_finished(self, request_id: int, selection) -> None:
        if not self._selection_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_selection_load_pending", False):
            return
        self._service_dns_selection = dict(selection or {})
        show_access_errors = bool(self._selection_load_show_access_errors)
        self._selection_load_show_access_errors = False
        self._finish_runtime_init_after_selection(show_access_errors=show_access_errors)

    def _on_user_selection_load_failed(self, request_id: int, error: str) -> None:
        if not self._selection_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_selection_load_pending", False):
            return
        log(f"Hosts: ошибка загрузки выбора профилей: {error}", "ERROR")
        show_access_errors = bool(self._selection_load_show_access_errors)
        self._selection_load_show_access_errors = False
        self._service_dns_selection = {}
        self._finish_runtime_init_after_selection(show_access_errors=show_access_errors)

    def _on_user_selection_load_worker_finished(self, _worker) -> None:
        if self._cleanup_in_progress:
            return
        if self.__dict__.get("_selection_load_pending", False):
            self._schedule_user_selection_load_start()

    def _schedule_user_selection_load_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_selection_load_start_scheduled", False):
            return
        self._selection_load_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_user_selection_load_start)

    def _run_scheduled_user_selection_load_start(self) -> None:
        self._selection_load_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        pending = bool(self.__dict__.get("_selection_load_pending", False))
        self._selection_load_pending = False
        if not pending:
            return
        show_access_errors = bool(self.__dict__.get("_selection_load_show_access_errors", False))
        self._start_user_selection_load_worker(show_access_errors=show_access_errors)

    def _finish_runtime_init_after_selection(self, *, show_access_errors: bool) -> None:
        started_at = time.perf_counter()
        if self._runtime_initialized:
            if show_access_errors and not self._runtime_access_checked:
                self._check_hosts_access()
                self._runtime_access_checked = True
            return
        if show_access_errors:
            check_access_fn = self._check_hosts_access
            self._runtime_access_checked = True
        else:
            check_access_fn = lambda: None
        run_hosts_runtime_init_once(
            runtime_initialized=self._runtime_initialized,
            set_runtime_initialized_fn=lambda value: setattr(self, "_runtime_initialized", value),
            install_host_window_event_filter_fn=self._install_host_window_event_filter,
            build_page_init_plan_fn=hosts_page_plans.build_page_init_plan,
            has_hosts_runtime=self.hosts_runtime is not None,
            init_hosts_runtime_fn=self._init_hosts_runtime,
            check_access_fn=check_access_fn,
            rebuild_services_fn=self._rebuild_services_selectors,
            mark_startup_initialized_fn=lambda: setattr(self, "_startup_initialized", True),
            invalidate_cache_fn=self._invalidate_cache,
            update_ui_fn=self._update_ui,
        )
        self._log_ui_timing("hosts_ui.runtime_init.total", started_at)

    def on_page_hidden(self) -> None:
        self._close_service_combo_popups()
        self._stop_catalog_watcher()

    def _install_host_window_event_filter(self) -> None:
        install_host_window_event_filter(
            page=self,
            current_host_window=self._host_window,
            set_host_window_fn=lambda value: setattr(self, "_host_window", value),
        )

    def _close_service_combo_popups(self) -> None:
        """Close all service profile dropdown popups if they are open."""
        close_service_combo_popups(self.service_combos)

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
                    self._close_service_combo_popups()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_hosts_page_language(
            tr_fn=self._tr,
            clear_btn=getattr(self, "clear_btn", None),
            open_hosts_button=self._open_hosts_button,
            info_text_label=self._info_text_label,
            browser_warning_label=self._browser_warning_label,
            adobe_desc_label=self._adobe_desc_label,
            adobe_title_label=self._adobe_title_label,
            startup_initialized=self._startup_initialized,
            applying=self._applying,
            rebuild_services_selectors_fn=self._rebuild_services_selectors,
            check_hosts_access_fn=self._check_hosts_access,
            update_ui_fn=self._update_ui,
        )

    def _init_hosts_runtime(self):
        if self.hosts_runtime is not None:
            return

        self.hosts_runtime = create_page_hosts_runtime(self._hosts.create_hosts_runtime)

    def _invalidate_cache(self):
        """Сбрасывает кеш активных доменов"""
        self._runtime_cache.invalidate()

    def _get_hosts_path_str(self) -> str:
        return self._hosts.get_hosts_path_str()

    def _build_ui(self):
        # Информационная заметка
        self._build_info_note()
        self.add_spacing(4)

        # Предупреждение о браузере
        self._build_browser_warning()
        self.add_spacing(6)

        # Статус
        self._build_status_section()
        self.add_spacing(6)

        # Сервисы (выбор DNS-профиля по каждому сервису)
        self._build_services_container()
        self.add_spacing(6)

        # Adobe
        self._build_adobe_section()
        self.add_spacing(6)


    def _build_services_container(self) -> None:
        widgets = build_hosts_services_container()
        self._services_container = widgets.container
        self._services_layout = widgets.layout
        self.add_widget(self._services_container)

    def _clear_layout(self, layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if not item:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)

    def _start_catalog_watcher(self) -> None:
        self._catalog_watch_timer = ensure_catalog_watcher(
            page=self,
            timer=self._catalog_watch_timer,
            interval_ms=5000,
            refresh_callback=self._refresh_catalog_if_needed,
        )

    def _stop_catalog_watcher(self) -> None:
        timer = self._catalog_watch_timer
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass

    def _reconcile_catalog_after_hidden_refresh(self) -> None:
        handled = reconcile_catalog_after_hidden_refresh(
            catalog_dirty=self._catalog_dirty,
            services_layout_exists=self._services_layout is not None,
            rebuild_services_selectors=self._rebuild_services_selectors,
            invalidate_cache=self._invalidate_cache,
        )
        if handled:
            self._catalog_dirty = False

    def _refresh_catalog_if_needed(self, trigger: str) -> None:
        if self._catalog_refresh_runtime.is_running() or self.__dict__.get("_catalog_refresh_start_scheduled", False):
            self._catalog_refresh_pending_trigger = str(trigger or "watcher")
            return
        self._catalog_refresh_pending_trigger = ""
        self._catalog_refresh_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._hosts.create_catalog_refresh_worker(
                request_id,
                trigger=str(trigger or "watcher"),
                parent=self,
            ),
            on_loaded=self._on_catalog_refresh_loaded,
            on_failed=self._on_catalog_refresh_failed,
            on_finished=self._on_catalog_refresh_worker_finished,
        )

    def _on_catalog_refresh_loaded(self, request_id: int, trigger: str, catalog_sig) -> None:
        if not self._catalog_refresh_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_catalog_refresh_pending_trigger"):
            return
        result = apply_catalog_refresh_signature(
            current_signature=self._catalog_sig,
            new_signature=catalog_sig,
            trigger=str(trigger or "watcher"),
            services_layout_exists=self._services_layout is not None,
            page_visible=self.isVisible(),
            invalidate_catalog_cache=self._hosts.invalidate_catalog_cache,
            rebuild_services_selectors=self._rebuild_services_selectors,
            log_info=lambda message: log(message, "INFO"),
        )
        if not result["changed"]:
            return
        self._catalog_dirty = bool(result["catalog_dirty"])
        self._catalog_sig = result["catalog_sig"]

    def _on_catalog_refresh_failed(self, request_id: int, trigger: str, error: str) -> None:
        if not self._catalog_refresh_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Hosts: ошибка проверки каталога ({trigger}): {error}", "ERROR")

    def _on_catalog_refresh_worker_finished(self, _worker) -> None:
        if self._cleanup_in_progress:
            return
        trigger = str(self._catalog_refresh_pending_trigger or "").strip()
        if trigger:
            self._schedule_catalog_refresh_start()

    def _schedule_catalog_refresh_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_catalog_refresh_start_scheduled", False):
            return
        self._catalog_refresh_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_catalog_refresh_start)

    def _run_scheduled_catalog_refresh_start(self) -> None:
        self._catalog_refresh_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        trigger = str(self.__dict__.get("_catalog_refresh_pending_trigger") or "").strip()
        self._catalog_refresh_pending_trigger = ""
        if not trigger:
            return
        self._refresh_catalog_if_needed(trigger)

    def _services_add_section_title(self, text: str) -> None:
        if self._services_layout is None:
            return
        label = build_hosts_services_section_title(text=text)
        self._services_section_title_labels.append(label)
        self._services_layout.addWidget(label)

    def _services_add_widget(self, widget: QWidget) -> None:
        if self._services_layout is None:
            return
        self._services_layout.addWidget(widget)

    def _reset_services_runtime_bindings(self) -> None:
        self.service_combos = {}
        self.service_icon_labels = {}
        self.service_icon_names = {}
        self.service_name_labels = {}
        self.service_icon_base_colors = {}
        self._services_section_title_labels = []
        self._service_group_title_labels = []
        self._service_group_chips_scrolls = []
        self._service_group_chip_buttons = []

    def _rebuild_services_selectors(self) -> None:
        if self._services_layout is None:
            return
        started_at = time.perf_counter()
        self._clear_layout(self._services_layout)
        self._reset_services_runtime_bindings()
        self._start_services_catalog_worker()
        self._log_ui_timing("hosts_ui.services.rebuild", started_at)

    def _start_services_catalog_worker(self) -> None:
        self._stop_services_catalog_worker(blocking=False)
        try:
            self._services_catalog_runtime.start_qobject_worker(
                parent=self,
                worker_factory=lambda _request_id: self._hosts.create_services_catalog_worker(
                    hosts_runtime=self.hosts_runtime,
                    current_selection=dict(self._service_dns_selection),
                    direct_title=self._tr("page.hosts.group.direct", "Напрямую из hosts"),
                    ai_title=self._tr("page.hosts.group.ai", "ИИ"),
                    other_title=self._tr("page.hosts.group.other", "Остальные"),
                ),
                on_loaded=self._on_services_catalog_loaded,
                on_failed=self._on_services_catalog_failed,
                on_finished=self._on_services_catalog_finished,
            )
        except Exception as exc:
            log(f"Hosts services catalog worker failed to start: {exc}", "ERROR")

    def _on_services_catalog_loaded(self, request_id: int, catalog_plan, catalog_sig) -> None:
        if not self._services_catalog_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        self._catalog_sig = catalog_sig
        self._build_services_selectors(catalog_plan)
        self._update_ui()

    def _on_services_catalog_failed(self, request_id: int, error: str) -> None:
        if not self._services_catalog_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        log(f"Hosts services catalog worker failed: {error}", "ERROR")

    def _on_services_catalog_finished(self, request_id: int, thread) -> None:
        _ = (request_id, thread)

    def _stop_services_catalog_worker(self, *, blocking: bool) -> None:
        self._services_catalog_runtime.stop(
            blocking=blocking,
            wait_timeout_ms=7000,
            log_fn=log,
            warning_prefix="Hosts services catalog worker",
        )

    def _show_error(self, message: str):
        """Показывает InfoBar с ошибкой доступа и кнопкой восстановления прав."""
        self._hosts_error_bar, self._last_error = show_hosts_access_error(
            current_bar=self._hosts_error_bar,
            last_error=self._last_error,
            message=message,
            tr_fn=self._tr,
            info_bar_cls=InfoBar,
            push_button_cls=PushButton,
            window=self.window(),
            on_restore=self._restore_hosts_permissions,
            log_warning=lambda text: log(text, "WARNING"),
            log_debug=lambda text: log(text, "DEBUG"),
        )

    def _dismiss_hosts_error_bar(self):
        """Закрывает текущий InfoBar ошибки доступа к hosts."""
        self._last_error = None
        dismiss_hosts_error_bar(self._hosts_error_bar)
        self._hosts_error_bar = None

    def _hide_error(self):
        """Скрывает ошибку доступа к hosts."""
        self._dismiss_hosts_error_bar()

    def _restore_hosts_permissions(self, bar=None, btn=None):
        """Восстанавливает стандартные права доступа к файлу hosts."""
        _ = btn
        if bar is not None:
            dismiss_hosts_error_bar(bar)
        self._hosts_error_bar = None
        self._last_error = None
        self._request_restore_hosts_permissions()

    def create_permission_restore_worker(self, request_id: int):
        return self._hosts.create_permission_restore_worker(request_id, self)

    def _request_restore_hosts_permissions(self) -> None:
        if (
            self._permission_restore_runtime.is_running()
            or self.__dict__.get("_permission_restore_start_scheduled", False)
        ):
            self._permission_restore_pending = True
            return
        self._permission_restore_pending = False
        self._permission_restore_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_permission_restore_worker(request_id),
            on_loaded=self._on_restore_hosts_permissions_finished,
            on_failed=self._on_restore_hosts_permissions_failed,
            on_finished=self._on_restore_hosts_permissions_worker_finished,
        )

    def _on_restore_hosts_permissions_finished(self, request_id: int, result) -> None:
        if not self._permission_restore_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_permission_restore_pending", False):
            return
        apply_restore_hosts_permissions_result_flow(
            result=result,
            info_bar_cls=InfoBar,
            window=self.window(),
            dismiss_error_bar=self._dismiss_hosts_error_bar,
            invalidate_cache=self._invalidate_cache,
            update_ui=self._update_ui,
            show_error=self._show_error,
        )

    def _on_restore_hosts_permissions_failed(self, request_id: int, error: str) -> None:
        if not self._permission_restore_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_permission_restore_pending", False):
            return
        self._dismiss_hosts_error_bar()
        self._show_error(str(error or ""))

    def _on_restore_hosts_permissions_worker_finished(self, _worker) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_permission_restore_pending", False):
            self._schedule_permission_restore_start()

    def _schedule_permission_restore_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_permission_restore_start_scheduled", False):
            return
        self._permission_restore_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_permission_restore_start)

    def _run_scheduled_permission_restore_start(self) -> None:
        self._permission_restore_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.__dict__.get("_permission_restore_pending", False):
            return
        self._permission_restore_pending = False
        self._request_restore_hosts_permissions()

    def _check_hosts_access(self):
        """Проверяет доступ к hosts файлу при загрузке страницы"""
        self._request_hosts_state_load(show_access_errors=True, update_status=False)

    def _apply_hosts_access_state(self, runtime_state) -> None:
        check_hosts_access(
            runtime_state=runtime_state,
            hosts_path=self._get_hosts_path_str(),
            tr_fn=self._tr,
            hide_error=self._hide_error,
            show_error=self._show_error,
        )

    def _build_info_note(self):
        """Информационная заметка о том, зачем нужен hosts"""
        widgets = build_hosts_info_note(tr_fn=self._tr)
        self._info_text_label = widgets.info_text_label
        self.add_widget(widgets.card)

    def _build_browser_warning(self):
        """Предупреждение о необходимости перезапуска браузера"""
        self._browser_warning_label = build_hosts_browser_warning(tr_fn=self._tr)
        self.add_widget(self._browser_warning_label)

    def _build_status_section(self):
        widgets = build_hosts_status_section(
            tr_fn=self._tr,
            active_count=0,
            on_clear_clicked=self._on_clear_clicked,
            on_open_hosts_file=self._open_hosts_file,
        )
        self.status_dot = widgets.status_dot
        self.status_label = widgets.status_label
        self.clear_btn = widgets.clear_button
        self._open_hosts_button = widgets.open_hosts_button
        self.add_widget(widgets.card)

    def _make_fluent_chip(self, label: str) -> PushButton:
        btn = PushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(24)
        btn.setStyleSheet(_get_fluent_chip_style())
        return btn

    def _get_building_services_ui(self) -> bool:
        return bool(getattr(self, "_building_services_ui", False))

    def _set_building_services_ui(self, value: bool) -> None:
        self._building_services_ui = bool(value)

    def _bulk_apply_dns_profile(self, service_names: list[str], profile_name: str | None) -> None:
        if self._applying:
            return

        plan = hosts_page_plans.build_bulk_profile_selection_plan(
            current_selection=self._service_dns_selection,
            service_names=service_names,
            profile_name=profile_name,
        )

        new_selection = apply_bulk_profile_selection_ui(
            plan=plan,
            profile_name=profile_name,
            service_names=service_names,
            service_combos=self.service_combos,
            is_fluent_combo=_is_fluent_combo,
            toggle_cls=SwitchButton,
            get_building_state=self._get_building_services_ui,
            set_building_state=self._set_building_services_ui,
            update_profile_visual=self._update_profile_row_visual,
            log_debug=lambda message: log(message, "DEBUG"),
        )
        if new_selection is not None:
            self._service_dns_selection = new_selection
            self._request_user_selection_save(self._service_dns_selection)
            if plan.apply_now:
                self._apply_current_selection()

    def _build_services_selectors(self, catalog_plan):
        started_at = time.perf_counter()
        OFF_LABEL = self._tr("page.hosts.services.off", "Откл.")

        self._services_add_section_title(
            tr_catalog("page.hosts.section.services", language=self._ui_language, default="Сервисы")
        )

        self._building_services_ui = True
        try:
            groups_started_at = time.perf_counter()
            for group_plan in catalog_plan.groups:
                group_widgets = build_hosts_services_group(
                    group_plan,
                    off_label=OFF_LABEL,
                    strong_body_label_cls=StrongBodyLabel,
                    make_chip=self._make_fluent_chip,
                    on_bulk_apply=self._bulk_apply_dns_profile,
                )
                card = group_widgets.card
                self._service_group_title_labels.append(group_widgets.title_label)
                if group_widgets.chips_scroll is not None:
                    self._service_group_chips_scrolls.append(group_widgets.chips_scroll)
                self._service_group_chip_buttons.extend(group_widgets.chip_buttons)

                for row_plan in group_plan.rows:
                    row_widgets = build_hosts_service_row(
                        row_plan,
                        body_label_cls=BodyLabel,
                        combo_cls=ComboBox,
                        toggle_cls=SwitchButton,
                        off_label=OFF_LABEL,
                        on_direct_toggle=self._on_direct_toggle_changed,
                        on_profile_changed=self._on_profile_changed,
                    )
                    self.service_name_labels[row_plan.service_name] = row_widgets.name_label
                    card.add_layout(row_widgets.row_layout)
                    self.service_combos[row_plan.service_name] = row_widgets.control
                    self.service_icon_labels[row_plan.service_name] = row_widgets.icon_label
                    self.service_icon_names[row_plan.service_name] = row_plan.icon_name
                    self.service_icon_base_colors[row_plan.service_name] = row_plan.icon_color

                    self._update_profile_row_visual(row_plan.service_name)

                self._services_add_widget(card)
            self._log_ui_timing("hosts_ui.services.groups.build", groups_started_at)
        finally:
            self._building_services_ui = False
            self._log_ui_timing("hosts_ui.services.build", started_at)

        self._service_dns_selection = dict(catalog_plan.new_selection)
        if catalog_plan.selection_changed:
            self._request_user_selection_save(self._service_dns_selection)

    def _on_direct_toggle_changed(self, service_name: str, checked: bool) -> None:
        if getattr(self, "_building_services_ui", False):
            self._update_profile_row_visual(service_name)
            return
        if self._applying:
            self._update_profile_row_visual(service_name)
            return

        plan = hosts_page_plans.build_mode_toggle_plan(
            current_selection=self._service_dns_selection,
            service_name=service_name,
            checked=checked,
        )
        self._service_dns_selection, should_apply = apply_direct_toggle_ui(
            plan=plan,
            service_name=service_name,
            service_combos=self.service_combos,
            toggle_cls=SwitchButton,
            get_building_state=self._get_building_services_ui,
            set_building_state=self._set_building_services_ui,
            update_profile_visual=self._update_profile_row_visual,
        )
        self._request_user_selection_save(self._service_dns_selection)
        if should_apply:
            self._apply_current_selection()

    def _build_adobe_section(self):
        self.add_section_title(text_key="page.hosts.section.additional")
        is_adobe_active = self.hosts_runtime.is_adobe_domains_active() if self.hosts_runtime else False
        widgets = build_hosts_adobe_section(
            tr_fn=self._tr,
            adobe_active=is_adobe_active,
            on_toggle_adobe=self._toggle_adobe,
            switch_button_cls=SwitchButton,
        )
        self._adobe_desc_label = widgets.description_label
        self._adobe_title_label = widgets.title_label
        self.adobe_switch = widgets.switch
        self.add_widget(widgets.card)

    # ═══════════════════════════════════════════════════════════════
    # ОБРАБОТЧИКИ
    # ═══════════════════════════════════════════════════════════════

    def _on_profile_changed(self, service_name: str, selected_profile: object):
        if getattr(self, "_building_services_ui", False):
            self._update_profile_row_visual(service_name)
            return
        if self._applying:
            self._update_profile_row_visual(service_name)
            return

        plan = hosts_page_plans.build_profile_selection_plan(
            current_selection=self._service_dns_selection,
            service_name=service_name,
            selected_profile=selected_profile,
        )
        self._service_dns_selection, should_apply = apply_profile_selection_ui(
            plan=plan,
            service_name=service_name,
            update_profile_visual=self._update_profile_row_visual,
        )
        self._request_user_selection_save(self._service_dns_selection)
        if should_apply:
            self._apply_current_selection()

    def _update_profile_row_visual(self, service_name: str):
        combo = self.service_combos.get(service_name)
        icon_label = self.service_icon_labels.get(service_name)
        tokens = get_theme_tokens()
        base_color = self.service_icon_base_colors.get(service_name)
        if not base_color:
            base_color = tokens.accent_hex
        if not combo or not icon_label:
            return

        enabled = False
        if _is_fluent_combo(combo):
            enabled = combo.currentData() is not None
        elif isinstance(combo, SwitchButton):
            enabled = bool(combo.isChecked())
        color = base_color if enabled else tokens.fg_faint
        icon_name = self.service_icon_names.get(service_name)
        try:
            icon = get_themed_qta_icon(icon_name or "fa5s.globe", color=color)
        except Exception:
            icon = get_themed_qta_icon("fa5s.globe", color=color)
        icon_label.setPixmap(icon.pixmap(18, 18))

    def _apply_current_selection(self):
        if self._applying:
            return
        self._request_user_selection_save(self._service_dns_selection)
        self._run_operation('apply_selection', dict(self._service_dns_selection))

    def _on_clear_clicked(self):
        if self._applying:
            return
        if MessageBox is not None:
            box = MessageBox(
                self._tr("page.hosts.dialog.clear.title", "Очистить записи ZapretGUI?"),
                self._tr(
                    "page.hosts.dialog.clear.body",
                    "Будет удалён только блок записей ZapretGUI. Ручные записи в файле hosts останутся на месте.",
                ),
                self.window(),
            )
            if not box.exec():
                return
        self._clear_hosts()

    def _clear_hosts(self):
        """Очищает hosts"""
        if self._applying:
            return

        self._run_operation('clear_all')

    def _open_hosts_file(self):
        self._request_open_hosts_file()

    def create_open_hosts_file_worker(self, request_id: int):
        return self._hosts.create_open_hosts_file_worker(request_id, self)

    def _request_open_hosts_file(self) -> None:
        if self._open_file_runtime.is_running() or self.__dict__.get("_open_file_start_scheduled", False):
            self._open_file_pending = True
            return
        self._open_file_pending = False
        self._open_file_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_open_hosts_file_worker(request_id),
            on_loaded=self._on_open_hosts_file_finished,
            on_failed=self._on_open_hosts_file_failed,
            on_finished=self._on_open_hosts_file_worker_finished,
        )

    def _on_open_hosts_file_finished(self, request_id: int, result) -> None:
        if not self._open_file_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        if self.__dict__.get("_open_file_pending", False):
            return
        if result.success:
            return
        self._show_open_hosts_file_error(str(getattr(result, "message", "") or getattr(result, "error", "")))

    def _on_open_hosts_file_failed(self, request_id: int, error: str) -> None:
        if not self._open_file_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        if self.__dict__.get("_open_file_pending", False):
            return
        self._show_open_hosts_file_error(str(error))

    def _on_open_hosts_file_worker_finished(self, _worker) -> None:
        if self._open_file_pending and not self._cleanup_in_progress:
            self._open_file_pending = False
            self._schedule_open_hosts_file_start()

    def _schedule_open_hosts_file_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_open_file_start_scheduled", False):
            self._open_file_pending = True
            return
        self._open_file_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_open_hosts_file_start)

    def _run_scheduled_open_hosts_file_start(self) -> None:
        self._open_file_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._request_open_hosts_file()

    def _show_open_hosts_file_error(self, error: str) -> None:
        if InfoBar:
            InfoBar.warning(
                title=self._tr("page.hosts.open.error.title", "Ошибка"),
                content=self._tr("page.hosts.open.error.content", "Не удалось открыть: {error}", error=error),
                parent=self.window(),
            )

    def _toggle_adobe(self, checked: bool):
        if self._applying:
            # Revert the switch without re-triggering the signal
            self.adobe_switch.blockSignals(True)
            self.adobe_switch.setChecked(not checked)
            self.adobe_switch.blockSignals(False)
            return
        self._run_operation('adobe_add' if checked else 'adobe_remove')

    def _run_operation(self, operation: str, payload=None):
        self._cleanup_in_progress = False
        runtime = start_hosts_operation(
            operation_runtime=self._operation_runtime,
            hosts_runtime=self.hosts_runtime,
            applying=self._applying,
            operation=operation,
            payload=payload,
            create_operation_worker_fn=self._hosts.create_operation_worker,
            on_operation_complete=self._on_operation_complete,
            on_thread_finished=self._on_hosts_thread_finished,
            parent=self,
        )
        if runtime is None:
            return
        self._applying = runtime["applying"]
        self._current_operation = runtime["current_operation"]

    def _on_hosts_thread_finished(self) -> None:
        pass

    def _request_user_selection_save(self, selection: dict[str, str]) -> None:
        payload = dict(selection or {})
        if self._selection_save_runtime.is_running() or self.__dict__.get("_selection_save_start_scheduled", False):
            self._selection_save_pending = payload
            return
        self._selection_save_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._hosts.create_selection_save_worker(
                request_id,
                payload,
                self,
            ),
            on_loaded=self._on_user_selection_save_finished,
            on_failed=self._on_user_selection_save_failed,
            on_finished=self._on_user_selection_save_worker_finished,
        )

    def _on_user_selection_save_finished(self, request_id: int, saved: bool) -> None:
        if not self._selection_save_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_selection_save_pending") is not None:
            return
        if not saved:
            log("Hosts: выбор профилей не был сохранён", "WARNING")

    def _on_user_selection_save_failed(self, request_id: int, error: str) -> None:
        if not self._selection_save_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Hosts: ошибка сохранения выбора профилей: {error}", "ERROR")

    def _on_user_selection_save_worker_finished(self, _worker) -> None:
        if self._cleanup_in_progress:
            return
        pending = self._selection_save_pending
        if pending is not None:
            self._schedule_user_selection_save_start()

    def _schedule_user_selection_save_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_selection_save_start_scheduled", False):
            return
        self._selection_save_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_user_selection_save_start)

    def _run_scheduled_user_selection_save_start(self) -> None:
        self._selection_save_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        selection = self.__dict__.get("_selection_save_pending")
        self._selection_save_pending = None
        if selection is None:
            return
        self._request_user_selection_save(selection)

    def _on_operation_complete(self, success: bool, message: str):
        if self._cleanup_in_progress:
            return
        state = complete_hosts_operation(
            current_operation=self._current_operation,
            success=success,
            message=message,
            hosts_path=self._get_hosts_path_str(),
            invalidate_cache=self._invalidate_cache,
            update_ui=self._update_ui,
            reset_profiles_ui=self._reset_all_service_profiles,
            hide_error=self._hide_error,
            show_error=self._show_error,
        )
        self._current_operation = state["current_operation"]
        self._applying = state["applying"]

    def _reset_all_service_profiles(self) -> None:
        """Сбрасывает выбор профилей в UI и settings.json (после очистки hosts)."""
        self._service_dns_selection = reset_all_service_profiles_ui(
            service_combos=self.service_combos,
            is_fluent_combo=_is_fluent_combo,
            toggle_cls=SwitchButton,
            get_building_state=self._get_building_services_ui,
            set_building_state=self._set_building_services_ui,
            update_profile_visual=self._update_profile_row_visual,
            save_user_selection_fn=self._request_user_selection_save,
        )

    def _update_ui(self):
        """Обновляет весь UI"""
        started_at = time.perf_counter()
        self._request_hosts_state_load(show_access_errors=False, update_status=True, started_at=started_at)

    def _request_hosts_state_load(
        self,
        *,
        show_access_errors: bool,
        update_status: bool,
        started_at: float | None = None,
    ) -> None:
        if self._cleanup_in_progress:
            return
        context = {
            "show_access_errors": bool(show_access_errors),
            "update_status": bool(update_status),
            "started_at": started_at,
        }
        if self._state_load_runtime.is_running() or self.__dict__.get("_state_load_start_scheduled", False):
            self._state_load_pending["show_access_errors"] = (
                bool(self._state_load_pending.get("show_access_errors")) or bool(show_access_errors)
            )
            self._state_load_pending["update_status"] = (
                bool(self._state_load_pending.get("update_status")) or bool(update_status)
            )
            return

        self._state_load_request_context = context
        self._state_load_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._hosts.create_state_load_worker(
                request_id,
                self.hosts_runtime,
                self,
            ),
            on_loaded=self._on_hosts_state_loaded,
            on_failed=self._on_hosts_state_failed,
            on_finished=self._on_hosts_state_worker_finished,
        )

    def _on_hosts_state_loaded(self, request_id: int, runtime_state) -> None:
        if not self._state_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        pending = dict(self.__dict__.get("_state_load_pending") or {})
        if bool(pending.get("show_access_errors")) or bool(pending.get("update_status")):
            return
        self._runtime_cache.runtime_state = runtime_state
        self._runtime_cache.active_domains = set(getattr(runtime_state, "active_domains", frozenset()) or frozenset())
        context = dict(self._state_load_request_context or {})
        if bool(context.get("show_access_errors")):
            self._apply_hosts_access_state(runtime_state)
        if bool(context.get("update_status")):
            self._apply_hosts_runtime_state_to_ui(runtime_state, started_at=context.get("started_at"))

    def _on_hosts_state_failed(self, request_id: int, error: str) -> None:
        if not self._state_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Hosts: ошибка загрузки состояния: {error}", "ERROR")
        if bool((self._state_load_request_context or {}).get("show_access_errors")):
            self._show_error(
                self._tr("page.hosts.error.read_hosts", "Ошибка чтения hosts: {error}", error=str(error or ""))
            )

    def _on_hosts_state_worker_finished(self, _worker) -> None:
        pending = dict(self._state_load_pending or {})
        if self._cleanup_in_progress:
            return
        if bool(pending.get("show_access_errors")) or bool(pending.get("update_status")):
            self._schedule_hosts_state_load_start()

    def _schedule_hosts_state_load_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_state_load_start_scheduled", False):
            return
        self._state_load_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_hosts_state_load_start)

    def _run_scheduled_hosts_state_load_start(self) -> None:
        self._state_load_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        pending = dict(self.__dict__.get("_state_load_pending") or {})
        self._state_load_pending = {"show_access_errors": False, "update_status": False}
        show_access_errors = bool(pending.get("show_access_errors"))
        update_status = bool(pending.get("update_status"))
        if not show_access_errors and not update_status:
            return
        self._request_hosts_state_load(
            show_access_errors=show_access_errors,
            update_status=update_status,
        )

    def _apply_hosts_runtime_state_to_ui(self, runtime_state, *, started_at: float | None = None) -> None:
        started_at = float(started_at or time.perf_counter())
        status_display = hosts_page_plans.build_status_display_plan(
            runtime_state,
            active_text=self._tr("page.hosts.status.active_domains", "Активно {count} доменов", count=len(runtime_state.active_domains)),
            none_text=self._tr("page.hosts.status.none_active", "Нет активных"),
        )
        tokens = get_theme_tokens()
        semantic = get_semantic_palette()

        # Статус
        if status_display.dot_active:
            self.status_dot.setStyleSheet(f"color: {semantic.success}; font-size: 12px;")
        else:
            self.status_dot.setStyleSheet(f"color: {tokens.fg_faint}; font-size: 12px;")
        self.status_label.setText(status_display.label_text)

        # Обновляем иконки под текущие выборы
        for name in list(self.service_combos.keys()):
            self._update_profile_row_visual(name)

        # Adobe
        is_adobe = status_display.adobe_active
        self.adobe_switch.blockSignals(True)
        self.adobe_switch.setChecked(is_adobe)
        self.adobe_switch.blockSignals(False)
        self._log_ui_timing("hosts_ui.update_ui.total", started_at)

    @staticmethod
    def _log_ui_timing(label: str, started_at: float) -> None:
        try:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            log(f"{label}: {elapsed_ms:.1f}ms", "DEBUG")
        except Exception:
            pass

    def refresh(self):
        """Обновляет страницу (сбрасывает кеш и перечитывает hosts)"""
        self._invalidate_cache()
        self._update_ui()

    def cleanup(self):
        """Очистка потоков при закрытии"""
        try:
            cleanup_hosts_page(
                set_cleanup_in_progress_fn=lambda value: setattr(self, "_cleanup_in_progress", value),
                current_host_window=self._host_window,
                set_host_window_fn=lambda value: setattr(self, "_host_window", value),
                page=self,
                catalog_watch_timer=self._catalog_watch_timer,
                set_catalog_watch_timer_fn=lambda value: setattr(self, "_catalog_watch_timer", value),
                log_fn=log,
            )
            self._operation_runtime.stop(
                blocking=True,
                log_fn=log,
                warning_prefix="Hosts operation worker",
            )
            self._operation_runtime.cancel()
            self._stop_services_catalog_worker(blocking=True)
            self._catalog_refresh_runtime.stop(
                blocking=True,
                log_fn=log,
                warning_prefix="Hosts catalog refresh worker",
            )
            self._selection_load_runtime.stop(
                blocking=True,
                log_fn=log,
                warning_prefix="Hosts selection load worker",
            )
            self._selection_load_pending = False
            self._selection_load_start_scheduled = False
            self._selection_save_runtime.stop(
                blocking=True,
                log_fn=log,
                warning_prefix="Hosts selection save worker",
            )
            self._state_load_runtime.stop(
                blocking=True,
                log_fn=log,
                warning_prefix="Hosts state load worker",
            )
            self._open_file_runtime.stop(
                blocking=True,
                log_fn=log,
                warning_prefix="Hosts open file worker",
            )
            self._permission_restore_runtime.stop(
                blocking=True,
                log_fn=log,
                warning_prefix="Hosts permission restore worker",
            )
            self._permission_restore_pending = False
            self._permission_restore_start_scheduled = False
        except Exception as e:
            log(f"Ошибка при очистке hosts_page: {e}", "DEBUG")
