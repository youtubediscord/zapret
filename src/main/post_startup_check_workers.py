from __future__ import annotations

import atexit
import time

from app_notifications import advisory_notification
from log.log import log


def collect_startup_checks_payload(*, verbose_logging_enabled: bool) -> dict:
    started_at = time.perf_counter()
    notifications: list[dict] = []

    from startup.bfe_util import preload_service_status, ensure_bfe_running, cleanup as bfe_cleanup
    from startup.check_start import collect_startup_notifications, check_goodbyedpi, check_mitmproxy

    preload_service_status("BFE")

    bfe_ok, bfe_notification = ensure_bfe_running()
    if bfe_notification is not None:
        notifications.append(bfe_notification)
    if not bfe_ok:
        log("BFE не запущен, продолжаем работу после предупреждения", "⚠ WARNING")

    startup_notifications = collect_startup_notifications()
    notifications.extend(startup_notifications or [])
    log(
        "Startup notifications collected: "
        f"count={len(startup_notifications or [])}",
        "⏱ STARTUP",
    )

    has_gdpi, gdpi_msg = check_goodbyedpi()
    if has_gdpi and gdpi_msg:
        notifications.append(
            advisory_notification(
                level="warning",
                title="Проверка при запуске",
                content=gdpi_msg,
                source="startup.goodbyedpi",
                queue="startup",
                duration=15000,
                dedupe_key="startup.goodbyedpi",
            )
        )

    has_mitmproxy, mitmproxy_msg = check_mitmproxy()
    if has_mitmproxy and mitmproxy_msg:
        notifications.append(
            advisory_notification(
                level="warning",
                title="Проверка при запуске",
                content=mitmproxy_msg,
                source="startup.mitmproxy",
                queue="startup",
                duration=15000,
                dedupe_key="startup.mitmproxy",
            )
        )

    if verbose_logging_enabled:
        from startup.admin_check_debug import debug_admin_status

        debug_admin_status()

    try:
        atexit.register(bfe_cleanup)
    except Exception:
        pass

    return {
        "notifications": notifications,
        "duration_ms": int((time.perf_counter() - started_at) * 1000),
    }
