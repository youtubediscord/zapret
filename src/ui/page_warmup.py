from __future__ import annotations

import time

from app.page_names import PageName
from log.log import log
from ui.page_performance import log_page_metric
from ui.window_ui_session import get_window_ui_session


def warm_page(window, page_name: PageName) -> bool:
    """Тихо догревает уже созданную страницу, не создавая новые Qt-виджеты."""
    session = get_window_ui_session(window)
    if session is None:
        return False

    page_host = getattr(session, "page_host", None)
    if page_host is None:
        return False

    started_at = time.perf_counter()
    page = page_host.get_loaded_page(page_name)
    if page is None:
        return False

    warmup = getattr(page, "warmup_initial_load", None)
    if callable(warmup):
        try:
            warmup()
        except Exception as exc:
            log(f"[PAGE_WARMUP] {page_name.name} warmup failed: {exc}", "DEBUG")
            return False

    log_page_metric(
        page_name,
        "warmup",
        (time.perf_counter() - started_at) * 1000,
    )
    return True


__all__ = ["warm_page"]
