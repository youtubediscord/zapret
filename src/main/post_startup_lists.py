from __future__ import annotations

from typing import TYPE_CHECKING

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_window_alive
from main.post_startup_list_workers import run_startup_lists_check
from main.post_startup_threading import schedule_after, start_daemon_thread

if TYPE_CHECKING:
    from main.window import LupiDPIApp


def install_lists_check(window: "LupiDPIApp") -> None:
    def _start_lists_check() -> None:
        if not is_window_alive(window):
            return
        start_daemon_thread("ListsStartupPostInitCheck", run_startup_lists_check)

    def _schedule_lists_check() -> None:
        if not is_window_alive(window):
            return
        delay_ms = 1000
        log(f"Проверки списков отложены на {delay_ms}ms после post-init", "DEBUG")
        window.log_startup_metric("StartupPostInitListsQueued", f"{delay_ms}ms after post-init")
        schedule_after(
            delay_ms,
            lambda: is_window_alive(window) and _start_lists_check(),
        )

    bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_lists_check,
        is_ready=lambda: bool(getattr(window, "_startup_post_init_ready", False)),
    )
