from __future__ import annotations

from typing import TYPE_CHECKING

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_window_alive
from main.post_startup_dns_workers import schedule_dns_startup

if TYPE_CHECKING:
    from main.window import LupiDPIApp


def install_dns_startup(window: "LupiDPIApp") -> None:
    def _handle_startup_dns_status(message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return

        silent_prefixes = (
            "DNS будет применен",
            "⚙️ Принудительный DNS отключен",
            "⏳ Применение DNS настроек",
        )
        if text.startswith(silent_prefixes):
            log(f"DNS startup status suppressed from main status: {text}", "DEBUG")
            return

        try:
            window.set_status(text)
        except Exception as exc:
            log(f"Не удалось обновить DNS-статус запуска: {exc}", "DEBUG")

    def _schedule_dns_startup() -> None:
        if not is_window_alive(window):
            return
        try:
            duration_ms = schedule_dns_startup(status_callback=_handle_startup_dns_status)
            window.log_startup_metric(
                "StartupPostInitDnsQueued",
                f"{duration_ms}ms",
            )
        except Exception as exc:
            log(f"❌ Ошибка планирования DNS при запуске: {exc}", "ERROR")

    bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_dns_startup,
        is_ready=lambda: bool(getattr(window, "_startup_post_init_ready", False)),
    )
