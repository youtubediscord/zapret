from __future__ import annotations

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_list_workers import run_startup_lists_check
from main.post_startup_threading import enqueue_subsystem_task, schedule_after


LISTS_STARTUP_CHECK_DELAY_MS = 7_500


def install_lists_check(
    startup_host,
    *,
    startup_lists_check,
    log_startup_metric,
) -> None:
    def _start_lists_check() -> None:
        if not is_startup_host_alive(startup_host):
            return
        enqueue_subsystem_task(
            "lists",
            "ListsStartupPostInitCheck",
            lambda: run_startup_lists_check(
                startup_lists_check=startup_lists_check,
            ),
        )

    def _schedule_lists_check() -> None:
        if not is_startup_host_alive(startup_host):
            return
        delay_ms = LISTS_STARTUP_CHECK_DELAY_MS
        log(f"Проверки списков отложены на {delay_ms}ms после post-init", "DEBUG")
        log_startup_metric("StartupPostInitListsQueued", f"{delay_ms}ms after post-init")
        schedule_after(
            delay_ms,
            lambda: is_startup_host_alive(startup_host) and _start_lists_check(),
        )

    bind_startup_gate(
        startup_host.startup_post_init_ready,
        _schedule_lists_check,
        is_ready=lambda: bool(startup_host.startup_state.post_init_ready),
    )
