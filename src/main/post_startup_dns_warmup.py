from __future__ import annotations

import time

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_threading import schedule_after, start_daemon_thread


def install_dns_page_data_warmup(
    startup_host,
    *,
    dns_feature,
    log_startup_metric,
    delay_ms: int = 300,
) -> None:
    def _run_dns_page_data_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        started_at = time.perf_counter()
        try:
            dns_feature.warm_page_data_cache()
        except Exception as exc:
            log(f"Фоновый прогрев данных Network не выполнен: {exc}", "DEBUG")
            return
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        log(f"Фоновый прогрев данных Network: {elapsed_ms:.1f}ms", "DEBUG")

    def _start_dns_page_data_warmup() -> None:
        log_startup_metric("StartupPostInitNetworkDataWarmupStarted", "backend_cache")
        start_daemon_thread("DnsPageDataWarmup", _run_dns_page_data_warmup)

    def _schedule_dns_page_data_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        delay = max(0, int(delay_ms))
        log_startup_metric("StartupNetworkDataWarmupQueued", f"{delay}ms after interactive")
        log(f"Фоновый прогрев данных Network отложен на {delay}ms", "DEBUG")
        schedule_after(
            delay,
            lambda: is_startup_host_alive(startup_host) and _start_dns_page_data_warmup(),
        )

    bind_startup_gate(
        startup_host.startup_interactive_ready,
        _schedule_dns_page_data_warmup,
        is_ready=lambda: bool(startup_host.startup_state.interactive_logged),
    )


__all__ = ["install_dns_page_data_warmup"]
