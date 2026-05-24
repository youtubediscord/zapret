from __future__ import annotations

from main.post_startup import PostStartupDeps
from main.post_startup_host import build_post_startup_host


def build_application_post_startup_deps(*, window, app_runtime) -> PostStartupDeps:
    """Build post-startup dependencies from the application assembly layer."""

    features = app_runtime.features
    notifications = window.window_notification_center
    return PostStartupDeps(
        startup_host=build_post_startup_host(window),
        profile_feature=features.profile,
        dns_feature=features.dns,
        premium_feature=features.premium,
        logs_feature=features.logs,
        notify=notifications.notify,
        notify_many=notifications.notify_many,
        set_status=window.set_status,
        log_startup_metric=window.log_startup_metric,
        start_proxy_if_enabled_async=features.telegram_proxy.start_proxy_if_enabled_async,
        startup_lists_check=features.lists.startup_lists_check,
        apply_dns_on_startup_async=features.dns.apply_dns_on_startup_async,
        install_tray_post_startup=features.tray.install_post_startup,
        updater_feature=features.updater,
    )


__all__ = ["build_application_post_startup_deps"]
