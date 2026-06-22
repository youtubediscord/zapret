from __future__ import annotations

import time

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_threading import enqueue_subsystem_task, schedule_after
from ui.performance_metrics import log_ui_timing_since


HOSTS_PAGE_WARMUP_DELAY_MS = 0


def install_hosts_page_warmup(
    startup_host,
    *,
    hosts_feature=None,
    log_startup_metric,
    delay_ms: int = HOSTS_PAGE_WARMUP_DELAY_MS,
) -> None:
    def _run_hosts_page_data_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        started_at = time.perf_counter()
        log_startup_metric("StartupHostsPageWarmupStarted", "backend_cache")
        try:
            if hosts_feature is None:
                return
            hosts_feature.warm_page_data_cache()
            log_startup_metric("StartupHostsPageWarmupFinished", "backend_cache")
        except Exception as exc:
            log(f"Фоновая подготовка страницы hosts не выполнена: {exc}", "DEBUG")
            return
        log_ui_timing_since("warmup", "hosts", "backend_page_data", started_at, important=True)

    def _start_hosts_page_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        enqueue_subsystem_task("hosts", "HostsPageDataWarmup", _run_hosts_page_data_warmup)

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


__all__ = ["HOSTS_PAGE_WARMUP_DELAY_MS", "install_hosts_page_warmup"]
