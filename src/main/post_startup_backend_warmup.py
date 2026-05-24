from __future__ import annotations

import time

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_threading import schedule_after, start_daemon_thread
from settings import appearance as appearance_settings


def install_backend_page_data_warmup(
    startup_host,
    *,
    premium_feature,
    logs_feature,
    log_startup_metric,
    delay_ms: int = 350,
) -> None:
    def _run_named_warmup(name: str, callback) -> None:
        started_at = time.perf_counter()
        try:
            callback()
        except Exception as exc:
            log(f"Фоновый прогрев данных {name} не выполнен: {exc}", "DEBUG")
            return
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        log(f"Фоновый прогрев данных {name}: {elapsed_ms:.1f}ms", "DEBUG")

    def _start_backend_page_data_warmup() -> None:
        warmups = (
            ("Premium", premium_feature.warm_page_data_cache),
            ("Appearance", appearance_settings.warm_page_initial_state_cache),
            ("Logs", logs_feature.warm_page_data_cache),
        )
        log_startup_metric("StartupBackendPageDataWarmupStarted", "premium, appearance, logs")
        for name, callback in warmups:
            start_daemon_thread(
                f"BackendPageDataWarmup-{name}",
                lambda name=name, callback=callback: (
                    is_startup_host_alive(startup_host) and _run_named_warmup(name, callback)
                ),
            )

    def _schedule_backend_page_data_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        delay = max(0, int(delay_ms))
        log_startup_metric("StartupBackendPageDataWarmupQueued", f"{delay}ms after interactive")
        log(f"Фоновый прогрев данных страниц отложен на {delay}ms", "DEBUG")
        schedule_after(
            delay,
            lambda: is_startup_host_alive(startup_host) and _start_backend_page_data_warmup(),
        )

    bind_startup_gate(
        startup_host.startup_interactive_ready,
        _schedule_backend_page_data_warmup,
        is_ready=lambda: bool(startup_host.startup_state.interactive_logged),
    )


__all__ = ["install_backend_page_data_warmup"]
