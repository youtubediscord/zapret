from __future__ import annotations

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_proxy_workers import start_telegram_proxy_if_enabled
from main.post_startup_threading import enqueue_subsystem_task, schedule_after


TELEGRAM_PROXY_STARTUP_DELAY_MS = 6_500


def install_telegram_proxy_startup(
    startup_host,
    *,
    start_proxy_if_enabled_async,
    log_startup_metric,
) -> None:
    def _start_telegram_proxy() -> None:
        if not is_startup_host_alive(startup_host):
            return
        enqueue_subsystem_task(
            "telegram_proxy",
            "TelegramProxyStartupPostInit",
            lambda: start_telegram_proxy_if_enabled(
                start_proxy_if_enabled_async=start_proxy_if_enabled_async,
            ),
        )

    def _schedule_telegram_proxy() -> None:
        if not is_startup_host_alive(startup_host):
            return
        delay_ms = TELEGRAM_PROXY_STARTUP_DELAY_MS
        log(f"Telegram Proxy отложен на {delay_ms}ms после post-init", "DEBUG")
        log_startup_metric("StartupPostInitTelegramProxyQueued", f"{delay_ms}ms after post-init")
        schedule_after(
            delay_ms,
            lambda: is_startup_host_alive(startup_host) and _start_telegram_proxy(),
        )

    bind_startup_gate(
        startup_host.startup_post_init_ready,
        _schedule_telegram_proxy,
        is_ready=lambda: bool(startup_host.startup_state.post_init_ready),
    )
