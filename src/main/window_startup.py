from __future__ import annotations

import traceback
from config.window_metrics import HEIGHT, WIDTH
from PyQt6.QtCore import QTimer

from log.log import log

from main.runtime_state import (
    log_startup_metric as emit_startup_metric,
    startup_elapsed_ms,
)
from main.window_close_state import WindowCloseState
from main.window_startup_state import WindowStartupState
from main.window_visual_state import WindowVisualState


STARTUP_CONTINUE_AFTER_UI_READY_MS = 250


class WindowStartupMixin:
    def __init__(self, start_in_tray: bool = False):
        self.start_in_tray = start_in_tray
        self.close_state = WindowCloseState()
        self.startup_state = WindowStartupState(
            tray_launch_notification_pending=bool(self.start_in_tray),
        )
        self.visual_state = WindowVisualState()

        super().__init__()

        from settings.dpi.strategy_settings import get_strategy_launch_method

        current_method = get_strategy_launch_method()
        log(f"Метод запуска стратегий: {current_method}", "INFO")

    @staticmethod
    def _queued_connection():
        from PyQt6.QtCore import Qt

        return Qt.ConnectionType.QueuedConnection

    def mark_startup_subscription_ready(self, source: str = "subscription_ready") -> None:
        _ = source
        self.startup_state.subscription_ready = True

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

        self.mark_startup_interactive("ui_ready")
        log(f"⏱ Startup: build_ui {(_time.perf_counter() - build_started_at) * 1000:.0f}ms", "DEBUG")
        log(f"⏱ Startup: deferred init total {(_time.perf_counter() - total_started_at) * 1000:.0f}ms", "DEBUG")
        emit_startup_metric("StartupContinueAfterUiReadyQueued", f"{STARTUP_CONTINUE_AFTER_UI_READY_MS}ms")
        QTimer.singleShot(STARTUP_CONTINUE_AFTER_UI_READY_MS, self._continue_startup_after_ui_ready)

    def _continue_startup_after_ui_ready(self) -> None:
        emit_startup_metric("StartupContinueAfterUiReadyDispatch", "continue_startup_requested")
        self.continue_startup_requested.emit()

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
