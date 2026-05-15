from __future__ import annotations

import time


def schedule_dns_startup(*, apply_dns_on_startup_async, status_callback=None) -> int:
    """Планирует применение DNS после основного запуска и возвращает длительность планирования."""
    started_at = time.perf_counter()

    apply_dns_on_startup_async(status_callback=status_callback)
    return int((time.perf_counter() - started_at) * 1000)
