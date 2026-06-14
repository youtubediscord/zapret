from __future__ import annotations

import time
from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_threading import enqueue_subsystem_task, schedule_after
from settings.dpi.strategy_settings import get_strategy_launch_method
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE, is_preset_launch_method, normalize_launch_method
from ui.navigation_pages import resolve_preset_setup_page_for_method


DEFAULT_PROFILE_WARMUP_METHODS: tuple[str, ...] = (ZAPRET2_MODE, ZAPRET1_MODE)
PROFILE_WARMUP_DELAY_MS = 0
PROFILE_SECONDARY_WARMUP_DELAY_MS = 1_800
PRESET_SETUP_PAGE_WARMUP_DELAY_MS = 2_200


class _ProfileWarmupBridge(QObject):
    method_ready = pyqtSignal(str)


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
    delay_ms: int = PROFILE_WARMUP_DELAY_MS,
    secondary_delay_ms: int = PROFILE_SECONDARY_WARMUP_DELAY_MS,
    preset_setup_page_delay_ms: int = PRESET_SETUP_PAGE_WARMUP_DELAY_MS,
    on_profile_warmup_ready: Callable[[str], None] | None = None,
) -> None:
    warmup_bridge = _ProfileWarmupBridge()
    if on_profile_warmup_ready is not None:
        warmup_bridge.method_ready.connect(on_profile_warmup_ready)

    def _run_profile_warmup_method(method: str) -> None:
        if not is_startup_host_alive(startup_host):
            return
        started_at = time.perf_counter()
        try:
            profile_feature.warm_profile_list(method)
        except Exception as exc:
            log(f"Фоновый прогрев профилей {method} не выполнен: {exc}", "DEBUG")
            return
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        log(f"Фоновый прогрев профилей {method}: {elapsed_ms:.1f}ms", "DEBUG")
        if not is_startup_host_alive(startup_host):
            return
        if on_profile_warmup_ready is not None:
            try:
                warmup_bridge.method_ready.emit(method)
            except Exception as exc:
                log(f"Не удалось обновить UI после прогрева профилей {method}: {exc}", "DEBUG")

    def _run_preset_setup_page_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        method = get_strategy_launch_method()
        page_name = resolve_preset_setup_page_for_method(method)
        if page_name is None:
            return
        started_at = time.perf_counter()
        try:
            page = startup_host.ensure_page(page_name)
            if page is None:
                return
            log_startup_metric("StartupPresetSetupUiWarmupFinished", page_name.name)
        except Exception as exc:
            log(f"Фоновая подготовка страницы профилей preset-а не выполнена: {exc}", "DEBUG")
            return
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        log(f"Фоновая подготовка страницы профилей preset-а {page_name.name}: {elapsed_ms:.1f}ms", "DEBUG")

    def _start_profile_warmup(methods: tuple[str, ...]) -> None:
        log_startup_metric("StartupProfileWarmupStarted", ", ".join(methods))
        for method in methods:
            enqueue_subsystem_task(
                "profile",
                f"ProfileWarmup-{method}",
                lambda method=method: _run_profile_warmup_method(method),
            )

    def _schedule_profile_warmup() -> None:
        if not is_startup_host_alive(startup_host):
            return
        delay = max(0, int(delay_ms))
        methods = profile_warmup_methods(get_strategy_launch_method())
        current_methods = methods[:1]
        secondary_methods = methods[1:]
        secondary_delay = max(delay, int(secondary_delay_ms))
        detail = f"{delay}ms current after interactive"
        if secondary_methods:
            detail = f"{detail}; {secondary_delay}ms secondary after interactive"
        log_startup_metric("StartupProfileWarmupQueued", detail)
        log(f"Фоновый прогрев профилей отложен на {delay}ms", "DEBUG")
        schedule_after(
            delay,
            lambda: is_startup_host_alive(startup_host) and _start_profile_warmup(current_methods),
        )
        if secondary_methods:
            schedule_after(
                secondary_delay,
                lambda: is_startup_host_alive(startup_host) and _start_profile_warmup(secondary_methods),
            )
        page_delay = max(delay, int(preset_setup_page_delay_ms))
        log_startup_metric("StartupPresetSetupUiWarmupQueued", f"{page_delay}ms after interactive")
        schedule_after(
            page_delay,
            lambda: is_startup_host_alive(startup_host) and _run_preset_setup_page_warmup(),
        )

    bind_startup_gate(
        startup_host.startup_interactive_ready,
        _schedule_profile_warmup,
        is_ready=lambda: bool(startup_host.startup_state.interactive_logged),
    )


__all__ = [
    "DEFAULT_PROFILE_WARMUP_METHODS",
    "PRESET_SETUP_PAGE_WARMUP_DELAY_MS",
    "PROFILE_SECONDARY_WARMUP_DELAY_MS",
    "PROFILE_WARMUP_DELAY_MS",
    "install_profile_warmup",
    "profile_warmup_methods",
]
