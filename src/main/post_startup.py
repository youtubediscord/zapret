from __future__ import annotations

from typing import TYPE_CHECKING

from main.post_startup_checks import install_startup_checks
from main.post_startup_diagnostics import (
    install_cpu_diagnostic,
    install_global_exception_handler,
    install_qt_event_diagnostic_probe,
)
from main.post_startup_dns import install_dns_startup
from main.post_startup_lists import install_lists_check
from main.post_startup_maintenance import install_deferred_maintenance
from main.post_startup_proxy import install_telegram_proxy_startup
from main.post_startup_update import install_update_check

if TYPE_CHECKING:
    from main.window import LupiDPIApp


def install_post_startup_tasks(window: "LupiDPIApp") -> None:
    app_runtime = window.app_runtime
    notifications = window.window_notification_center
    log_startup_metric = window.log_startup_metric

    install_startup_checks(
        window,
        notify_many=notifications.notify_many,
        set_status=window.set_status,
        log_startup_metric=log_startup_metric,
    )
    install_deferred_maintenance(
        window,
        notify_many=notifications.notify_many,
        log_startup_metric=log_startup_metric,
    )
    install_telegram_proxy_startup(
        window,
        start_proxy_if_enabled_async=app_runtime.features.telegram_proxy.start_proxy_if_enabled_async,
        log_startup_metric=log_startup_metric,
    )
    install_lists_check(
        window,
        startup_lists_check=app_runtime.features.lists.startup_lists_check,
        log_startup_metric=log_startup_metric,
    )
    install_dns_startup(
        window,
        apply_dns_on_startup_async=app_runtime.features.dns.apply_dns_on_startup_async,
        set_status=window.set_status,
        log_startup_metric=log_startup_metric,
    )
    app_runtime.features.tray.install_post_startup()
    install_update_check(
        window,
        updater_feature=app_runtime.features.updater,
        notify=notifications.notify,
        set_status=window.set_status,
    )
    install_cpu_diagnostic()
    install_qt_event_diagnostic_probe()
    install_global_exception_handler()
