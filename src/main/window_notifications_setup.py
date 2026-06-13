from __future__ import annotations

import time as _time

from main.runtime_state import log_startup_metric as emit_startup_metric
from ui.window_notification_center import WindowNotificationCenter
from ui.window_notification_actions import WindowNotificationRuntimeActions


def show_page(window, page_name, *, allow_internal: bool = False) -> bool:
    from ui.window_adapter import show_page

    return bool(show_page(window, page_name, allow_internal=allow_internal))


def attach_window_notifications(window, features) -> None:
    t_notifications = _time.perf_counter()
    external_actions = (
        features.external_actions
        if hasattr(features, "external_actions")
        else _build_external_actions_feature()
    )
    window.window_notification_center = WindowNotificationCenter(
        window,
        startup_state=window.startup_state,
        runtime_actions=WindowNotificationRuntimeActions(
            is_available=features.runtime.is_available,
            cancel_start_after_conflict_prompt=features.runtime.cancel_start_after_conflict_prompt,
            execute_windivert_autofix=features.runtime.execute_windivert_autofix,
            install_windows_server_wlanapi=features.runtime.install_windows_server_wlanapi,
            prepare_launch_conflict_resolution=features.runtime.prepare_launch_conflict_resolution,
            continue_start_after_conflict_resolution=features.runtime.continue_start_after_conflict_resolution,
        ),
        create_open_url_worker=external_actions.create_open_url_worker,
        create_notification_action_worker=external_actions.create_notification_action_worker,
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


def _build_external_actions_feature():
    from app.feature_facades.external import build_external_actions_feature

    return build_external_actions_feature()


__all__ = ["attach_window_notifications"]
