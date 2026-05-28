from __future__ import annotations

import time as _time

from main.runtime_state import log_startup_metric as emit_startup_metric
from ui.window_adapter import show_page
from ui.window_notification_center import WindowNotificationCenter


def attach_window_notifications(window, features) -> None:
    t_notifications = _time.perf_counter()
    window.window_notification_center = WindowNotificationCenter(
        window,
        startup_state=window.startup_state,
        runtime_feature=features.runtime,
        external_actions_feature=(
            features.external_actions
            if hasattr(features, "external_actions")
            else None
        ),
        show_tray_notification=features.tray.show_notification_if_available,
        show_page=lambda page_name, *, allow_internal=False: show_page(
            window,
            page_name,
            allow_internal=allow_internal,
        ),
        is_window_visible=window.isVisible,
        is_window_minimized=window.isMinimized,
    )
    window.window_notification_center.register_global_error_notifier()
    features.runtime.configure_notifications(
        notify=window.window_notification_center.notify,
    )
    features.tray.configure(
        notify=window.window_notification_center.notify,
        log_startup_metric=window.log_startup_metric,
    )
    emit_startup_metric(
        "StartupWindowInitNotifications",
        f"{(_time.perf_counter() - t_notifications) * 1000:.0f}ms",
    )


__all__ = ["attach_window_notifications"]
