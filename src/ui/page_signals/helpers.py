from __future__ import annotations

from ui.page_contracts import get_page_signal
from ui.page_names import PageName
from ui.window_adapter import ensure_window_adapter


def connect_signal_once(window, key: str, signal_obj, slot_obj) -> None:
    if key in window._lazy_signal_connections:
        return
    try:
        signal_obj.connect(slot_obj)
        window._lazy_signal_connections.add(key)
    except Exception:
        pass


def connect_page_signal_if_present(window, key: str, page, signal_name: str, slot_obj) -> bool:
    signal_obj = get_page_signal(page, signal_name)
    if signal_obj is None:
        return False
    connect_signal_once(window, key, signal_obj, slot_obj)
    return True


def connect_show_page_signal(window, key: str, signal_obj, target_page: PageName, *, allow_internal: bool = False) -> None:
    connect_signal_once(
        window,
        key,
        signal_obj,
        lambda target=target_page, adapter=ensure_window_adapter(window), internal=allow_internal: adapter.show_page(
            target,
            allow_internal=internal,
        ),
    )


def connect_show_page_signal_if_present(
    window,
    key: str,
    page,
    signal_name: str,
    target_page: PageName,
    *,
    allow_internal: bool = False,
) -> bool:
    signal_obj = get_page_signal(page, signal_name)
    if signal_obj is None:
        return False
    connect_show_page_signal(window, key, signal_obj, target_page, allow_internal=allow_internal)
    return True


__all__ = [
    "connect_page_signal_if_present",
    "connect_show_page_signal",
    "connect_show_page_signal_if_present",
    "connect_signal_once",
]
