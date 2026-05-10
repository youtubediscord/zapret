from __future__ import annotations

import traceback
import time as _time

from app_context import build_app_context, install_app_context
from config.window_metrics import HEIGHT, MIN_WIDTH, WIDTH

from log.log import log

from main.runtime_state import (
    log_startup_metric as emit_startup_metric,
    startup_elapsed_ms,
)
from ui.app_window_locator import register_app_window
from ui.window_close_controller import WindowCloseController
from ui.window_geometry_controller import WindowGeometryController
from ui.window_notification_controller import WindowNotificationController


def window_bootstrap_for(window_cls, *, start_in_tray: bool):
    t_context = _time.perf_counter()
    app_context = build_app_context(initial_ui_state=window_cls._build_initial_ui_state())
    emit_startup_metric(
        "StartupWindowBootstrapContext",
        f"{(_time.perf_counter() - t_context) * 1000:.0f}ms",
    )
    install_app_context(app_context)
    t_window = _time.perf_counter()
    window = window_cls(start_in_tray=start_in_tray, app_context=app_context)
    emit_startup_metric(
        "StartupWindowBootstrapWindow",
        f"{(_time.perf_counter() - t_window) * 1000:.0f}ms",
    )
    register_app_window(window)
    return app_context, window


def startup_bootstrap_for(window) -> None:
    from donater.public import SubscriptionManager
    from main.startup_coordinator import StartupCoordinator
    from winws_runtime.monitoring import ProcessMonitorManager

    window.startup_coordinator = StartupCoordinator(window)
    window.subscription_manager = SubscriptionManager(window)
    window.process_monitor_manager = ProcessMonitorManager(window)


class WindowStartupMixin:
    def __init__(self, start_in_tray: bool = False, *, app_context):
        super().__init__()

        from settings.dpi.strategy_settings import get_strategy_launch_method

        current_method = get_strategy_launch_method()
        log(f"Метод запуска стратегий: {current_method}", "INFO")

        self.start_in_tray = start_in_tray
        self.app_context = app_context
        self.ui_state_store = app_context.ui_state_store
        self.app_runtime_state = app_context.app_runtime_state
        self.launch_runtime_service = app_context.launch_runtime_service

        self._dpi_autostart_initiated = False
        self._is_exiting = False
        self._stop_dpi_on_exit = False
        self._closing_completely = False
        self._deferred_init_started = False
        self._startup_post_init_ready = False
        self._startup_subscription_ready = False
        self._startup_background_init_started = False
        self._tray_launch_notification_pending = bool(self.start_in_tray)

        self.setMinimumSize(MIN_WIDTH, 400)
        self.window_close_controller = WindowCloseController(self)
        self.window_geometry_controller = WindowGeometryController(
            self,
            min_width=MIN_WIDTH,
            min_height=400,
            default_width=WIDTH,
            default_height=HEIGHT,
        )
        t_notifications = _time.perf_counter()
        self.window_notification_controller = WindowNotificationController(self)
        self.window_notification_controller.register_global_error_notifier()
        emit_startup_metric(
            "StartupWindowInitNotifications",
            f"{(_time.perf_counter() - t_notifications) * 1000:.0f}ms",
        )

        t_geometry = _time.perf_counter()
        self.window_geometry_controller.restore_geometry()
        emit_startup_metric(
            "StartupWindowInitRestoreGeometry",
            f"{(_time.perf_counter() - t_geometry) * 1000:.0f}ms",
        )

        # Праздничные overlay-слои не нужны для первого кадра окна.
        # Создаём их лениво только если пользователь реально включает
        # гирлянду/снежинки или когда код позже действительно попросит этот слой.
        self._holiday_effects = None
        self._startup_ttff_logged = False
        self._startup_ttff_ms = None
        self._startup_interactive_logged = False
        self._startup_interactive_ms = None
        self._startup_core_ready_logged = False
        self._startup_core_ready_ms = None
        self._startup_post_init_done_logged = False
        self._startup_post_init_done_ms = None
        self._last_active_preset_content_path = ""
        self._last_active_preset_content_ms = 0

        self.deferred_init_requested.connect(self._deferred_init, self._queued_connection())
        self.continue_startup_requested.connect(self._continue_deferred_init, self._queued_connection())
        self.finalize_ui_bootstrap_requested.connect(self._finalize_ui_bootstrap, self._queued_connection())
        self.runner_failure_requested.connect(self._apply_runner_failure_update, self._queued_connection())
        self.active_preset_content_changed_requested.connect(self._apply_active_preset_content_changed, self._queued_connection())

        if not self.start_in_tray and not self.isVisible():
            t_show = _time.perf_counter()
            self.show()
            emit_startup_metric(
                "StartupWindowInitShowCall",
                f"{(_time.perf_counter() - t_show) * 1000:.0f}ms",
            )
            log("Основное окно показано (FluentWindow, init в фоне)", "DEBUG")

        self.deferred_init_requested.emit()

    @staticmethod
    def _queued_connection():
        from PyQt6.QtCore import Qt

        return Qt.ConnectionType.QueuedConnection

    def _mark_startup_subscription_ready(self, source: str = "subscription_ready") -> None:
        _ = source
        self._startup_subscription_ready = True

    def _start_background_init(self) -> None:
        if self._startup_background_init_started:
            return
        self._startup_background_init_started = True

        try:
            self.subscription_manager.initialize_async()
        except Exception as e:
            log(f"Startup: subscription background init failed: {e}", "DEBUG")

        self.window_notification_controller.schedule_startup_notification_queue(0)

    def _deferred_init(self) -> None:
        """Heavy initialization — runs after first frame is shown."""
        if self._deferred_init_started:
            return
        self._deferred_init_started = True

        import time as _time

        total_started_at = _time.perf_counter()
        log("⏱ Startup: deferred init started", "DEBUG")

        build_started_at = _time.perf_counter()
        try:
            self.build_ui(WIDTH, HEIGHT)
        except Exception as e:
            log(f"Startup: build_ui failed: {e}", "ERROR")
            log(traceback.format_exc(), "DEBUG")
            return

        log(f"⏱ Startup: build_ui {(_time.perf_counter() - build_started_at) * 1000:.0f}ms", "DEBUG")
        log(f"⏱ Startup: deferred init total {(_time.perf_counter() - total_started_at) * 1000:.0f}ms", "DEBUG")
        self.continue_startup_requested.emit()

    def _continue_deferred_init(self) -> None:
        """Продолжает старт уже после показа базового UI."""
        import time as _time

        total_started_at = _time.perf_counter()
        bootstrap_started_at = _time.perf_counter()

        startup_bootstrap_for(self)
        log(f"⏱ Startup: startup bootstrap {(_time.perf_counter() - bootstrap_started_at) * 1000:.0f}ms", "DEBUG")

        self.startup_coordinator.run_async_init()
        log(f"⏱ Startup: continue init total {(_time.perf_counter() - total_started_at) * 1000:.0f}ms", "DEBUG")

        self.finalize_ui_bootstrap_requested.emit()

    def _finalize_ui_bootstrap(self) -> None:
        """Завершает не критичную для первого кадра сборку главного окна."""
        try:
            self.finish_ui_bootstrap()
        except Exception as e:
            log(f"Startup: finish_ui_bootstrap failed: {e}", "DEBUG")

    def _mark_startup_interactive(self, source: str = "ui_signals_connected") -> None:
        if self._startup_interactive_logged:
            return

        self._startup_interactive_logged = True
        interactive_ms = startup_elapsed_ms()
        self._startup_interactive_ms = interactive_ms

        ttff_ms = self._startup_ttff_ms
        if isinstance(ttff_ms, int):
            delta_ms = max(0, interactive_ms - ttff_ms)
            emit_startup_metric("StartupInteractive", f"{source}, +{delta_ms}ms after StartupTTFF")
        else:
            emit_startup_metric("StartupInteractive", source)
        try:
            self.startup_interactive_ready.emit(str(source or "interactive"))
        except Exception as e:
            log(f"Startup: startup_interactive_ready signal failed: {e}", "DEBUG")

    def _mark_startup_core_ready(self, source: str = "startup_core_ready") -> None:
        if self._startup_core_ready_logged:
            return

        self._startup_core_ready_logged = True
        core_ready_ms = startup_elapsed_ms()
        self._startup_core_ready_ms = core_ready_ms

        details = source
        interactive_ms = self._startup_interactive_ms
        if isinstance(interactive_ms, int):
            delta_ms = max(0, core_ready_ms - interactive_ms)
            details = f"{source}, +{delta_ms}ms after StartupInteractive"
        elif isinstance(self._startup_ttff_ms, int):
            delta_ms = max(0, core_ready_ms - self._startup_ttff_ms)
            details = f"{source}, +{delta_ms}ms after StartupTTFF"

        emit_startup_metric("StartupCoreReady", details)

    def _mark_startup_post_init_done(self, source: str = "post_init_tasks") -> None:
        if self._startup_post_init_done_logged:
            return

        self._startup_post_init_done_logged = True
        post_init_ms = startup_elapsed_ms()
        self._startup_post_init_done_ms = post_init_ms

        details = source
        core_ready_ms = self._startup_core_ready_ms
        if isinstance(core_ready_ms, int):
            delta_ms = max(0, post_init_ms - core_ready_ms)
            details = f"{source}, +{delta_ms}ms after StartupCoreReady"
        elif isinstance(self._startup_interactive_ms, int):
            delta_ms = max(0, post_init_ms - self._startup_interactive_ms)
            details = f"{source}, +{delta_ms}ms after StartupInteractive"

        emit_startup_metric("StartupPostInit", details)
        self._startup_post_init_ready = True
        try:
            self.startup_post_init_ready.emit(str(source or "post_init"))
        except Exception as e:
            log(f"Startup: startup_post_init_ready signal failed: {e}", "DEBUG")
        self._start_background_init()
        self.window_notification_controller.schedule_startup_notification_queue(0)
