from __future__ import annotations

from typing import TYPE_CHECKING

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_window_alive
from main.post_startup_threading import schedule_after
from main.tray_startup import init_tray

if TYPE_CHECKING:
    from main.window import LupiDPIApp


def install_tray_startup(window: "LupiDPIApp") -> None:
    """Создаёт системный трей после основного запуска для обычного старта окна."""
    if bool(getattr(window, "start_in_tray", False)):
        return

    def _start_tray() -> None:
        if not is_window_alive(window):
            return
        if getattr(window, "tray_manager", None) is not None:
            return

        try:
            init_tray(window)
        except Exception as exc:
            log(f"Не удалось создать системный трей после запуска: {exc}", "WARNING")

    def _schedule_tray_startup() -> None:
        if not is_window_alive(window):
            return

        delay_ms = 1500
        log(f"Системный трей отложен на {delay_ms}ms после post-init", "DEBUG")
        try:
            window.log_startup_metric("StartupPostInitTrayQueued", f"{delay_ms}ms after post-init")
        except Exception as exc:
            log(f"Не удалось записать startup-метрику StartupPostInitTrayQueued: {exc}", "DEBUG")

        schedule_after(
            delay_ms,
            lambda: is_window_alive(window) and _start_tray(),
        )

    bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_tray_startup,
        is_ready=lambda: bool(getattr(window, "_startup_post_init_ready", False)),
    )
