from __future__ import annotations

from queue import Empty, Full
from typing import Any


MAIN_LOG_VIEW_MAX_LINES = 10_000
WINWS_OUTPUT_MAX_LINES = 3_000
ERROR_LOG_VIEW_MAX_LINES = 1_000
DIAGNOSTICS_LOG_VIEW_MAX_LINES = 3_000
BLOCKCHECK_LOG_VIEW_MAX_LINES = 5_000
TELEGRAM_PROXY_LOG_VIEW_MAX_LINES = 3_000
TELEGRAM_PROXY_DIAG_VIEW_MAX_LINES = 2_000
TELEGRAM_PROXY_PENDING_MAX_LINES = 1_000
ORCHESTRA_PENDING_MAX_LINES = 1_000


def apply_text_line_limit(text_widget: Any, max_lines: int) -> bool:
    """Ставит лимит строк для Qt-текстового виджета."""
    try:
        limit = max(1, int(max_lines))
    except Exception:
        return False

    try:
        document = text_widget.document()
        document.setMaximumBlockCount(limit)
        return True
    except Exception:
        return False


def append_bounded_line(lines: list[str], line: str, *, max_lines: int) -> None:
    """Добавляет строку в список и оставляет только последние max_lines."""
    try:
        limit = max(1, int(max_lines))
    except Exception:
        limit = 1

    lines.append(line)
    overflow = len(lines) - limit
    if overflow > 0:
        del lines[:overflow]


def put_latest_bounded(log_queue: Any, value: str, *, max_items: int) -> None:
    """Кладёт строку в очередь, выкидывая самые старые элементы при переполнении."""
    try:
        limit = max(1, int(max_items))
    except Exception:
        limit = 1

    try:
        while int(log_queue.qsize()) >= limit:
            try:
                log_queue.get_nowait()
            except Empty:
                break
    except Exception:
        pass

    try:
        log_queue.put_nowait(value)
    except Full:
        try:
            log_queue.get_nowait()
            log_queue.put_nowait(value)
        except Exception:
            pass
