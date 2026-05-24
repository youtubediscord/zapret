from __future__ import annotations

import time

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_threading import schedule_after, start_daemon_thread
from settings.dpi.strategy_settings import get_strategy_launch_method
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE, is_preset_launch_method, normalize_launch_method


DEFAULT_PROFILE_WARMUP_METHODS: tuple[str, ...] = (ZAPRET2_MODE, ZAPRET1_MODE)


def profile_warmup_methods(current_method: str) -> tuple[str, ...]:
    current = normalize_launch_method(current_method)
    if not is_preset_launch_method(current):
        return DEFAULT_PROFILE_WARMUP_METHODS
    return (current, *(method for method in DEFAULT_PROFILE_WARMUP_METHODS if method != current))


def install_profile_warmup(
    startup_host,
    *,
    profile_feature,
    log_startup_metric,
    delay_ms: int = 1_800,
) -> None:
    def _run_profile_warmup_method(method: str) -> None:
        if not is_startup_host_alive(startup_host):
            return
        started_at = time.perf_counter()
        try:
            profile_feature.list_profiles(method)
        except Exception as exc:
            log(f"Фоновый прогрев профилей {method} не выполнен: {exc}", "DEBUG")
            return
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        log(f"Фоновый прогрев профилей {method}: {elapsed_ms:.1f}ms", "DEBUG")

    def _start_profile_warmup(methods: tuple[str, ...]) -> None:
        log_startup_metric("StartupProfileWarmupStarted", ", ".join(methods))
        for method in methods:
            start_daemon_thread(
                f"ProfileWarmup-{method}",
                lambda method=method: _run_profile_warmup_method(method),
            )

    def _schedule_profile_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        delay = max(0, int(delay_ms))
        methods = profile_warmup_methods(get_strategy_launch_method())
        log_startup_metric("StartupProfileWarmupQueued", f"{delay}ms after interactive")
        log(f"Фоновый прогрев профилей отложен на {delay}ms", "DEBUG")
        schedule_after(
            delay,
            lambda: is_startup_host_alive(startup_host) and _start_profile_warmup(methods),
        )

    bind_startup_gate(
        startup_host.startup_interactive_ready,
        _schedule_profile_warmup,
        is_ready=lambda: bool(startup_host.startup_state.interactive_logged),
    )


__all__ = [
    "DEFAULT_PROFILE_WARMUP_METHODS",
    "install_profile_warmup",
    "profile_warmup_methods",
]
