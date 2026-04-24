from __future__ import annotations

from app_context import build_app_context, install_app_context
from config.build_info import APP_VERSION
from config.window_metrics import HEIGHT, MIN_WIDTH, WIDTH

from log.log import log

from main.runtime_state import (
    log_startup_metric as emit_startup_metric,
    startup_elapsed_ms,
)
from ui.holiday_effects import HolidayEffectsManager
from ui.app_window_locator import register_app_window
from ui.window_close_controller import WindowCloseController
from ui.window_geometry_controller import WindowGeometryController
from ui.window_notification_controller import WindowNotificationController


def window_bootstrap_for(window_cls, *, start_in_tray: bool):
    app_context = build_app_context(initial_ui_state=window_cls._build_initial_ui_state())
    install_app_context(app_context)
    window = window_cls(start_in_tray=start_in_tray, app_context=app_context)
    register_app_window(window)
    return app_context, window


def manager_bootstrap_for(window) -> None:
    from managers.initialization_manager import InitializationManager
    from managers.subscription_manager import SubscriptionManager
    from managers.ui_manager import UIManager
    from winws_runtime.monitoring import ProcessMonitorManager

    window.initialization_manager = InitializationManager(window)
    window.subscription_manager = SubscriptionManager(window)
    window.process_monitor_manager = ProcessMonitorManager(window)
    window.ui_manager = UIManager(window)


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

        self.setWindowTitle(f"Zapret2 v{APP_VERSION}")
        self.setMinimumSize(MIN_WIDTH, 400)
        self.window_close_controller = WindowCloseController(self)
        self.window_geometry_controller = WindowGeometryController(
            self,
            min_width=MIN_WIDTH,
            min_height=400,
            default_width=WIDTH,
            default_height=HEIGHT,
        )
        self.window_notification_controller = WindowNotificationController(self)
        self.window_notification_controller.register_global_error_notifier()
        self.window_geometry_controller.restore_geometry()

        self._holiday_effects = HolidayEffectsManager(self)
        self._startup_ttff_logged = False
        self._startup_ttff_ms = None
        self._startup_interactive_logged = False
        self._startup_interactive_ms = None
        self._startup_managers_ready_logged = False
        self._startup_managers_ready_ms = None
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
            self.show()
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
            subscription_manager = getattr(self, "subscription_manager", None)
            if subscription_manager is not None:
                subscription_manager.initialize_async()
        except Exception:
            pass

        notification_controller = getattr(self, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.schedule_startup_notification_queue(0)

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
            try:
                import traceback

                log(traceback.format_exc(), "DEBUG")
            except Exception:
                pass
            return

        log(f"⏱ Startup: build_ui {(_time.perf_counter() - build_started_at) * 1000:.0f}ms", "DEBUG")
        log(f"⏱ Startup: deferred init total {(_time.perf_counter() - total_started_at) * 1000:.0f}ms", "DEBUG")
        self.continue_startup_requested.emit()

    def _continue_deferred_init(self) -> None:
        """Продолжает старт уже после показа базового UI."""
        import time as _time

        total_started_at = _time.perf_counter()
        managers_started_at = _time.perf_counter()

        manager_bootstrap_for(self)
        log(f"⏱ Startup: managers init {(_time.perf_counter() - managers_started_at) * 1000:.0f}ms", "DEBUG")

        self.update_title_with_subscription_status(False, None, 0, source="init")
        self.initialization_manager.run_async_init()
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
            emit_startup_metric("Interactive", f"{source}, +{delta_ms}ms after TTFF")
        else:
            emit_startup_metric("Interactive", source)
        try:
            self.startup_interactive_ready.emit(str(source or "interactive"))
        except Exception:
            pass

    def _mark_startup_managers_ready(self, source: str = "managers_init_done") -> None:
        if self._startup_managers_ready_logged:
            return

        self._startup_managers_ready_logged = True
        managers_ready_ms = startup_elapsed_ms()
        self._startup_managers_ready_ms = managers_ready_ms

        details = source
        interactive_ms = self._startup_interactive_ms
        if isinstance(interactive_ms, int):
            delta_ms = max(0, managers_ready_ms - interactive_ms)
            details = f"{source}, +{delta_ms}ms after Interactive"
        elif isinstance(self._startup_ttff_ms, int):
            delta_ms = max(0, managers_ready_ms - self._startup_ttff_ms)
            details = f"{source}, +{delta_ms}ms after TTFF"

        emit_startup_metric("CoreStartupReady", details)

    def _mark_startup_post_init_done(self, source: str = "post_init_tasks") -> None:
        if self._startup_post_init_done_logged:
            return

        self._startup_post_init_done_logged = True
        post_init_ms = startup_elapsed_ms()
        self._startup_post_init_done_ms = post_init_ms

        details = source
        managers_ready_ms = self._startup_managers_ready_ms
        if isinstance(managers_ready_ms, int):
            delta_ms = max(0, post_init_ms - managers_ready_ms)
            details = f"{source}, +{delta_ms}ms after CoreStartupReady"
        elif isinstance(self._startup_interactive_ms, int):
            delta_ms = max(0, post_init_ms - self._startup_interactive_ms)
            details = f"{source}, +{delta_ms}ms after Interactive"

        emit_startup_metric("PostInitDispatched", details)
        self._startup_post_init_ready = True
        try:
            self.startup_post_init_ready.emit(str(source or "post_init"))
        except Exception:
            pass
        self._start_background_init()
        notification_controller = getattr(self, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.schedule_startup_notification_queue(0)
