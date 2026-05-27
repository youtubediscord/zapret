from __future__ import annotations

import time

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_threading import schedule_after, start_daemon_thread
from settings.dpi.strategy_settings import get_strategy_launch_method
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE, is_preset_launch_method, normalize_launch_method


DEFAULT_USER_PRESETS_WARMUP_METHODS: tuple[str, ...] = (ZAPRET2_MODE, ZAPRET1_MODE)


def user_presets_warmup_methods(current_method: str) -> tuple[str, ...]:
    current = normalize_launch_method(current_method)
    if not is_preset_launch_method(current):
        return DEFAULT_USER_PRESETS_WARMUP_METHODS
    return (current, *(method for method in DEFAULT_USER_PRESETS_WARMUP_METHODS if method != current))


def install_user_presets_warmup(
    startup_host,
    *,
    presets_feature,
    log_startup_metric,
    delay_ms: int = 3_500,
    secondary_delay_ms: int = 15_000,
) -> None:
    def _run_user_presets_warmup_method(method: str) -> None:
        if not is_startup_host_alive(startup_host):
            return
        started_at = time.perf_counter()
        try:
            metadata = presets_feature.warm_preset_list_metadata_cache(method)
        except Exception as exc:
            log(f"Фоновый прогрев списка preset-ов {method} не выполнен: {exc}", "DEBUG")
            return
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        log(f"Фоновый прогрев списка preset-ов {method}: {elapsed_ms:.1f}ms ({len(metadata or {})} presets)", "DEBUG")

    def _start_user_presets_warmup(methods: tuple[str, ...]) -> None:
        log_startup_metric("StartupUserPresetsWarmupStarted", ", ".join(methods))
        for method in methods:
            start_daemon_thread(
                f"UserPresetsWarmup-{method}",
                lambda method=method: _run_user_presets_warmup_method(method),
            )

    def _schedule_user_presets_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        delay = max(0, int(delay_ms))
        methods = user_presets_warmup_methods(get_strategy_launch_method())
        current_methods = methods[:1]
        secondary_methods = methods[1:]
        secondary_delay = max(delay, int(secondary_delay_ms))
        detail = f"{delay}ms current after interactive"
        if secondary_methods:
            detail = f"{detail}; {secondary_delay}ms secondary after interactive"
        log_startup_metric("StartupUserPresetsWarmupQueued", detail)
        log(f"Фоновый прогрев списка preset-ов отложен на {delay}ms", "DEBUG")
        schedule_after(
            delay,
            lambda: is_startup_host_alive(startup_host) and _start_user_presets_warmup(current_methods),
        )
        if secondary_methods:
            schedule_after(
                secondary_delay,
                lambda: is_startup_host_alive(startup_host) and _start_user_presets_warmup(secondary_methods),
            )

    bind_startup_gate(
        startup_host.startup_interactive_ready,
        _schedule_user_presets_warmup,
        is_ready=lambda: bool(startup_host.startup_state.interactive_logged),
    )


__all__ = [
    "DEFAULT_USER_PRESETS_WARMUP_METHODS",
    "install_user_presets_warmup",
    "user_presets_warmup_methods",
]
