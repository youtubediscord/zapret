from __future__ import annotations

from dataclasses import dataclass

from log.log import log
from main.startup_coordinator import StartupCoordinator, StartupWindowShell
from main.window_startup_services import init_theme_manager


@dataclass(slots=True)
class WindowStartupRuntime:
    continue_deferred_init: object | None = None
    startup_coordinator: StartupCoordinator | None = None


def attach_startup_deps_to_window(window, features) -> WindowStartupRuntime:
    startup_runtime = WindowStartupRuntime()

    def _start_background_init() -> None:
        if window.startup_state.background_init_started:
            return
        window.startup_state.background_init_started = True

        try:
            features.premium.initialize_subscription()
        except Exception as exc:
            log(f"Startup: subscription background init failed: {exc}", "DEBUG")

        window.window_notification_center.schedule_startup_notification_queue(0)

    def _mark_startup_post_init_done(source: str = "post_init_tasks") -> None:
        window.mark_startup_post_init_done(source)
        _start_background_init()
        window.window_notification_center.schedule_startup_notification_queue(0)

    def _build_startup_coordinator() -> StartupCoordinator:
        window_shell = StartupWindowShell(
            start_in_tray=bool(window.start_in_tray),
            set_status=window.set_status,
            mark_startup_core_ready=window.mark_startup_core_ready,
            mark_startup_post_init_done=_mark_startup_post_init_done,
            init_theme_manager=lambda: init_theme_manager(
                window,
                appearance_feature=features.appearance,
            ),
        )
        return StartupCoordinator(
            runtime_feature=features.runtime,
            tray_feature=features.tray,
            window_shell=window_shell,
            log_startup_metric=window.log_startup_metric,
            migrate_gui_autostart=features.program_settings.ensure_gui_autostart_migrated,
        )

    def _continue_deferred_init() -> None:
        import time as _time

        total_started_at = _time.perf_counter()
        bootstrap_started_at = _time.perf_counter()

        features.premium.prepare_subscription()
        coordinator = _build_startup_coordinator()
        startup_runtime.startup_coordinator = coordinator
        log(f"⏱ Startup: startup bootstrap {(_time.perf_counter() - bootstrap_started_at) * 1000:.0f}ms", "DEBUG")

        coordinator.run_async_init()
        log(f"⏱ Startup: continue init total {(_time.perf_counter() - total_started_at) * 1000:.0f}ms", "DEBUG")

        window.finalize_ui_bootstrap_requested.emit()

    startup_runtime.continue_deferred_init = _continue_deferred_init
    return startup_runtime


__all__ = ["attach_startup_deps_to_window"]
