from __future__ import annotations

import traceback
import time as _time

from app.runtime import build_app_runtime
from config.window_metrics import HEIGHT, MIN_WIDTH, WIDTH

from log.log import log

from main.runtime_state import (
    log_startup_metric as emit_startup_metric,
    startup_elapsed_ms,
)
from ui.app_window_locator import register_app_window
from ui.window_close_flow import WindowCloseFlow
from ui.window_geometry_runtime import WindowGeometryRuntime
from ui.window_notification_center import WindowNotificationCenter
from main.window_close_state import WindowCloseState
from main.window_startup_state import WindowStartupState
from main.window_visual_state import WindowVisualState


def window_bootstrap_for(window_cls, *, start_in_tray: bool):
    t_window = _time.perf_counter()
    window = window_cls(start_in_tray=start_in_tray)
    emit_startup_metric(
        "StartupWindowBootstrapWindow",
        f"{(_time.perf_counter() - t_window) * 1000:.0f}ms",
    )
    register_app_window(window)
    return window


def startup_bootstrap_for(window):
    from main.startup_coordinator import StartupCoordinator, StartupWindowShell
    from main.window_startup_services import init_theme_manager

    features = window.app_runtime.features
    features.tray.configure(
        notify=window.window_notification_center.notify,
        log_startup_metric=window.log_startup_metric,
    )
    window_shell = StartupWindowShell(
        start_in_tray=bool(window.start_in_tray),
        set_status=window.set_status,
        mark_startup_interactive=window.mark_startup_interactive,
        mark_startup_core_ready=window.mark_startup_core_ready,
        mark_startup_post_init_done=window.mark_startup_post_init_done,
        init_theme_manager=lambda: init_theme_manager(window),
    )
    coordinator = StartupCoordinator(
        window.app_runtime,
        window_shell,
        log_startup_metric=window.log_startup_metric,
    )
    features.premium.prepare_subscription()
    return coordinator


class WindowStartupMixin:
    def __init__(self, start_in_tray: bool = False):
        super().__init__()

        from settings.dpi.strategy_settings import get_strategy_launch_method

        current_method = get_strategy_launch_method()
        log(f"Метод запуска стратегий: {current_method}", "INFO")

        self.start_in_tray = start_in_tray
        self.app_runtime = build_app_runtime(
            initial_ui_state=self._build_initial_ui_state(),
            host=self,
        )
        features = self.app_runtime.features

        self.close_state = WindowCloseState()
        self.startup_state = WindowStartupState(
            tray_launch_notification_pending=bool(self.start_in_tray),
        )
        self.visual_state = WindowVisualState()

        self.setMinimumSize(MIN_WIDTH, 400)
        self.window_close_flow = WindowCloseFlow(
            parent=self,
            close_state=self.close_state,
            runtime_feature=features.runtime,
            close_to_tray=self.close_to_tray,
            exit_stop_dpi=self.exit_stop_dpi,
            exit_keep_dpi=self.exit_keep_dpi,
        )
        self.window_geometry_runtime = WindowGeometryRuntime(
            self,
            min_width=MIN_WIDTH,
            min_height=400,
            default_width=WIDTH,
            default_height=HEIGHT,
            close_state=self.close_state,
        )
        t_notifications = _time.perf_counter()
        self.window_notification_center = WindowNotificationCenter(
            self,
            startup_state=self.startup_state,
            runtime_feature=features.runtime,
            show_tray_notification=features.tray.show_notification_if_available,
            show_page=lambda page_name, *, allow_internal=False: self.show_page(
                page_name,
                allow_internal=allow_internal,
            ),
            is_window_visible=self.isVisible,
            is_window_minimized=self.isMinimized,
        )
        self.window_notification_center.register_global_error_notifier()
        features.runtime.configure_notifications(
            notify=self.window_notification_center.notify,
        )
        features.tray.configure(
            notify=self.window_notification_center.notify,
            log_startup_metric=self.log_startup_metric,
        )
        emit_startup_metric(
            "StartupWindowInitNotifications",
            f"{(_time.perf_counter() - t_notifications) * 1000:.0f}ms",
        )

        t_geometry = _time.perf_counter()
        self.window_geometry_runtime.restore_geometry()
        emit_startup_metric(
            "StartupWindowInitRestoreGeometry",
            f"{(_time.perf_counter() - t_geometry) * 1000:.0f}ms",
        )

        # Праздничные overlay-слои не нужны для первого кадра окна.
        # Создаём их лениво только когда пользователь включает гирлянду/снежинки.
        self.deferred_init_requested.connect(self._deferred_init, self._queued_connection())
        self.continue_startup_requested.connect(self._continue_deferred_init, self._queued_connection())
        self.finalize_ui_bootstrap_requested.connect(self._finalize_ui_bootstrap, self._queued_connection())

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

    def _show_tray_notification_if_available(self, title: str, content: str) -> bool:
        return self.app_runtime.features.tray.show_notification_if_available(title, content)

    def mark_startup_subscription_ready(self, source: str = "subscription_ready") -> None:
        _ = source
        self.startup_state.subscription_ready = True

    def _start_background_init(self) -> None:
        if self.startup_state.background_init_started:
            return
        self.startup_state.background_init_started = True

        try:
            premium_feature = self.app_runtime.features.premium
            premium_feature.initialize_subscription()
        except Exception as e:
            log(f"Startup: subscription background init failed: {e}", "DEBUG")

        self.window_notification_center.schedule_startup_notification_queue(0)

    def _deferred_init(self) -> None:
        """Heavy initialization — runs after first frame is shown."""
        if self.startup_state.deferred_init_started:
            return
        self.startup_state.deferred_init_started = True

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

        coordinator = startup_bootstrap_for(self)
        log(f"⏱ Startup: startup bootstrap {(_time.perf_counter() - bootstrap_started_at) * 1000:.0f}ms", "DEBUG")

        coordinator.run_async_init()
        log(f"⏱ Startup: continue init total {(_time.perf_counter() - total_started_at) * 1000:.0f}ms", "DEBUG")

        self.finalize_ui_bootstrap_requested.emit()

    def _finalize_ui_bootstrap(self) -> None:
        """Завершает не критичную для первого кадра сборку главного окна."""
        try:
            self.finish_ui_bootstrap()
        except Exception as e:
            log(f"Startup: finish_ui_bootstrap failed: {e}", "DEBUG")

    def mark_startup_interactive(self, source: str = "ui_signals_connected") -> None:
        startup_state = self.startup_state
        if startup_state.interactive_logged:
            return

        startup_state.interactive_logged = True
        interactive_ms = startup_elapsed_ms()
        startup_state.interactive_ms = interactive_ms

        ttff_ms = startup_state.ttff_ms
        if isinstance(ttff_ms, int):
            delta_ms = max(0, interactive_ms - ttff_ms)
            emit_startup_metric("StartupInteractive", f"{source}, +{delta_ms}ms after StartupTTFF")
        else:
            emit_startup_metric("StartupInteractive", source)
        try:
            self.startup_interactive_ready.emit(str(source or "interactive"))
        except Exception as e:
            log(f"Startup: startup_interactive_ready signal failed: {e}", "DEBUG")

    def mark_startup_core_ready(self, source: str = "startup_core_ready") -> None:
        startup_state = self.startup_state
        if startup_state.core_ready_logged:
            return

        startup_state.core_ready_logged = True
        core_ready_ms = startup_elapsed_ms()
        startup_state.core_ready_ms = core_ready_ms

        details = source
        interactive_ms = startup_state.interactive_ms
        if isinstance(interactive_ms, int):
            delta_ms = max(0, core_ready_ms - interactive_ms)
            details = f"{source}, +{delta_ms}ms after StartupInteractive"
        elif isinstance(startup_state.ttff_ms, int):
            delta_ms = max(0, core_ready_ms - startup_state.ttff_ms)
            details = f"{source}, +{delta_ms}ms after StartupTTFF"

        emit_startup_metric("StartupCoreReady", details)

    def mark_startup_post_init_done(self, source: str = "post_init_tasks") -> None:
        startup_state = self.startup_state
        if startup_state.post_init_done_logged:
            return

        startup_state.post_init_done_logged = True
        post_init_ms = startup_elapsed_ms()
        startup_state.post_init_done_ms = post_init_ms

        details = source
        core_ready_ms = startup_state.core_ready_ms
        if isinstance(core_ready_ms, int):
            delta_ms = max(0, post_init_ms - core_ready_ms)
            details = f"{source}, +{delta_ms}ms after StartupCoreReady"
        elif isinstance(startup_state.interactive_ms, int):
            delta_ms = max(0, post_init_ms - startup_state.interactive_ms)
            details = f"{source}, +{delta_ms}ms after StartupInteractive"

        emit_startup_metric("StartupPostInit", details)
        startup_state.post_init_ready = True
        try:
            self.startup_post_init_ready.emit(str(source or "post_init"))
        except Exception as e:
            log(f"Startup: startup_post_init_ready signal failed: {e}", "DEBUG")
        self._start_background_init()
        self.window_notification_center.schedule_startup_notification_queue(0)
