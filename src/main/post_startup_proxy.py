from __future__ import annotations

from typing import TYPE_CHECKING

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_window_alive
from main.post_startup_proxy_workers import start_telegram_proxy_if_enabled
from main.post_startup_threading import schedule_after, start_daemon_thread

if TYPE_CHECKING:
    from main.window import LupiDPIApp


def install_telegram_proxy_startup(window: "LupiDPIApp") -> None:
    def _start_telegram_proxy() -> None:
        if not is_window_alive(window):
            return
        start_daemon_thread("TelegramProxyStartupPostInit", start_telegram_proxy_if_enabled)

    def _schedule_telegram_proxy() -> None:
        if not is_window_alive(window):
            return
        delay_ms = 1000
        log(f"Telegram Proxy отложен на {delay_ms}ms после post-init", "DEBUG")
        window.log_startup_metric("StartupPostInitTelegramProxyQueued", f"{delay_ms}ms after post-init")
        schedule_after(
            delay_ms,
            lambda: is_window_alive(window) and _start_telegram_proxy(),
        )

    bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_telegram_proxy,
        is_ready=lambda: bool(getattr(window, "_startup_post_init_ready", False)),
    )
