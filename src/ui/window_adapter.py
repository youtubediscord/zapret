from __future__ import annotations

from PyQt6.QtCore import QTimer

from ui.navigation.search import route_search_result, update_titlebar_search_width
from app.page_names import PageName
from ui.window_ui_session import get_window_ui_session


def show_page(window, page_name: PageName, *, allow_internal: bool = False) -> bool:
    session = get_window_ui_session(window)
    if session is None:
        return False
    return session.page_host.show_page(page_name, allow_internal=allow_internal)


def ensure_page(window, page_name: PageName):
    session = get_window_ui_session(window)
    if session is None:
        return None
    return session.page_host.ensure_page(page_name)


def get_loaded_page(window, page_name: PageName):
    session = get_window_ui_session(window)
    if session is None:
        return None
    return session.page_host.get_loaded_page(page_name)


def send_page_command(
    window,
    page_name: PageName,
    command: str,
    payload: dict | None = None,
    *,
    ensure: bool = True,
) -> bool:
    session = get_window_ui_session(window)
    if session is None:
        return False
    return session.page_host.send_page_command(
        page_name,
        command,
        payload,
        ensure=ensure,
    )


def get_current_page(window):
    session = get_window_ui_session(window)
    if session is None:
        return None
    return session.page_host.current_page()


def sync_titlebar_search_width(window) -> None:
    update_titlebar_search_width(window)


def refresh_titlebar_layout(window) -> None:
    """Обновляет верхнюю панель после первого показа окна."""
    sync_titlebar_search_width(window)

    title_bar = getattr(window, "titleBar", None)
    if title_bar is None:
        return

    layout = getattr(title_bar, "hBoxLayout", None)
    if layout is not None:
        try:
            layout.activate()
        except Exception:
            pass

    try:
        title_bar.updateGeometry()
    except Exception:
        pass
    try:
        title_bar.update()
    except Exception:
        pass


def route_window_search_result(window, page_name: PageName, tab_key: str = "") -> bool:
    return route_search_result(window, page_name, tab_key)


def persist_window_geometry(window) -> None:
    window.window_geometry_runtime.persist_now(force=True)


def release_input_interaction_states(window) -> None:
    window.release_input_interaction_states()


def hide_window(window) -> None:
    window.hide()


def _refresh_window_after_show(window) -> None:
    try:
        from ui.theme_refresh import flush_pending_theme_refreshes

        flush_pending_theme_refreshes(window)
    except Exception:
        pass

    try:
        from ui.navigation.sidebar_builder import sync_nav_visibility

        sync_nav_visibility(window)
    except Exception:
        pass


def _restore_geometry_before_hidden_show(window) -> None:
    try:
        if bool(window.isVisible()):
            return
    except Exception:
        return

    geometry_runtime = getattr(window, "window_geometry_runtime", None)
    restore_geometry = getattr(geometry_runtime, "restore_geometry", None)
    if not callable(restore_geometry):
        return

    try:
        restore_geometry()
    except Exception:
        pass


def show_window(window) -> None:
    try:
        from ui.navigation.sidebar_builder import sync_existing_nav_visibility

        sync_existing_nav_visibility(window)
    except Exception:
        pass

    _restore_geometry_before_hidden_show(window)
    window.show()
    window.showNormal()
    window.window_geometry_runtime.request_zoom_state(
        window.window_geometry_runtime.remembered_zoom_state()
    )
    window.raise_()
    window.activateWindow()
    QTimer.singleShot(0, lambda current_window=window: _refresh_window_after_show(current_window))


def request_exit(window, *, stop_dpi: bool) -> None:
    window.request_exit(stop_dpi=bool(stop_dpi))


__all__ = [
    "ensure_page",
    "get_current_page",
    "get_loaded_page",
    "hide_window",
    "persist_window_geometry",
    "refresh_titlebar_layout",
    "release_input_interaction_states",
    "request_exit",
    "route_window_search_result",
    "send_page_command",
    "show_page",
    "show_window",
    "sync_titlebar_search_width",
]
