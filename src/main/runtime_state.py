from __future__ import annotations

import os
import sys
import time as _startup_clock


_STARTUP_T0 = _startup_clock.perf_counter()


def startup_elapsed_ms() -> int:
    return int((_startup_clock.perf_counter() - _STARTUP_T0) * 1000)


def is_startup_debug_enabled() -> bool:
    raw = os.environ.get("ZAPRET_STARTUP_DEBUG")
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    for arg in sys.argv[1:]:
        if str(arg).strip().lower() in {"--startup-debug", "--verbose-log"}:
            return True

    return False


def is_cpu_diagnostic_enabled() -> bool:
    raw = os.environ.get("ZAPRET_CPU_DIAGNOSTIC")
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    for arg in sys.argv[1:]:
        if str(arg).strip().lower() in {"--cpu-diagnostic", "--cpu-debug"}:
            return True

    return False


def log_startup_metric(marker: str, details: str = "") -> None:
    from log.log import log


    suffix = f" | {details}" if details else ""
    log(f"⏱ Startup {marker}: {startup_elapsed_ms()}ms{suffix}", "⏱ STARTUP")
