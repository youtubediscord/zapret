from __future__ import annotations

import time

from app.page_names import PageName
from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_threading import schedule_after


def install_hosts_page_warmup(
    startup_host,
    *,
    log_startup_metric,
    delay_ms: int = 0,
) -> None:
    def _start_hosts_page_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        started_at = time.perf_counter()
        log_startup_metric("StartupHostsPageWarmupStarted", "ensure_page")
        try:
            page = startup_host.ensure_page(PageName.HOSTS)
            if page is None:
                return
            warmup = getattr(page, "warmup_initial_load", None)
            if callable(warmup):
                warmup()
                log_startup_metric("StartupHostsPageWarmupFinished", "warmup_initial_load")
        except Exception as exc:
            log(f"Фоновая подготовка страницы hosts не выполнена: {exc}", "DEBUG")
            return
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        log(f"Фоновая подготовка страницы hosts: {elapsed_ms:.1f}ms", "DEBUG")

    def _schedule_hosts_page_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        delay = max(0, int(delay_ms))
        log_startup_metric("StartupHostsPageWarmupQueued", f"{delay}ms after interactive")
        schedule_after(
            delay,
            lambda: is_startup_host_alive(startup_host) and _start_hosts_page_warmup(),
        )

    bind_startup_gate(
        startup_host.startup_interactive_ready,
        _schedule_hosts_page_warmup,
        is_ready=lambda: bool(startup_host.startup_state.interactive_logged),
    )


__all__ = ["install_hosts_page_warmup"]
