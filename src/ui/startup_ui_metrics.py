from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QEventLoop

from app.page_names import PageName
from ui.window_ui_session import get_window_ui_session


def pump_startup_ui(window, force: bool = False) -> None:
    """Отдаёт управление event loop во время тяжёлой сборки стартового UI."""
    try:
        session = get_window_ui_session(window)
        if session is None:
            return

        session.startup_ui_pump_counter = int(session.startup_ui_pump_counter or 0) + 1
        if not force and (session.startup_ui_pump_counter % 2) != 0:
            return

        app = QCoreApplication.instance()
        if app is None:
            return

        app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents, 8)
    except Exception:
        pass


def record_startup_page_init_metric(window, page_name: PageName, elapsed_ms: int) -> None:
    elapsed_i = max(0, int(elapsed_ms))

    session = get_window_ui_session(window)
    if session is not None:
        session.startup_page_init_metrics.append((page_name.name, elapsed_i))

    try:
        from log.log import log as _log


        level = "⏱ STARTUP" if elapsed_i >= 120 else "DEBUG"
        _log(f"⏱ Startup UI PageInit: {page_name.name} {elapsed_i}ms", level)
    except Exception:
        pass


def log_startup_page_init_summary(window) -> None:
    session = get_window_ui_session(window)
    if session is None or not session.startup_page_init_metrics:
        return

    try:
        from log.log import log as _log


        metrics = session.startup_page_init_metrics
        top = sorted(metrics, key=lambda item: item[1], reverse=True)[:6]
        summary = ", ".join(f"{name}={elapsed}ms" for name, elapsed in top)
        _log(f"⏱ Startup UI PageInit TOP: {summary}", "⏱ STARTUP")
    except Exception:
        pass
