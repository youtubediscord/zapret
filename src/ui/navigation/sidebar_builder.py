from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QWidget

from log.log import log

from ui.navigation.layout_plan import (
    build_sidebar_group_plans,
    iter_sidebar_entries_after_page,
)
from ui.navigation.schema import (
    get_eager_page_names_for_method,
    get_hidden_pages_for_method,
    get_nav_visibility,
    get_page_route_key,
)
from app.page_names import PageName
from ui.startup_ui_metrics import pump_startup_ui
from app.ui_texts import tr as tr_catalog
from ui.window_ui_session import get_window_ui_session


SIDEBAR_SEARCH_AFTER_INTERACTIVE_MS = 1_000
SIDEBAR_HIDDEN_MODE_ITEMS_AFTER_INTERACTIVE_MS = 1_600
SIDEBAR_EXPANDED_UI_STATE_KEY = "sidebar_expanded"


def _get_page_host(window):
    session = get_window_ui_session(window)
    return None if session is None else session.page_host


def _ensure_page(window, page_name: PageName):
    page_host = _get_page_host(window)
    if page_host is None:
        return None
    return page_host.ensure_page(page_name)


def _get_loaded_pages(window) -> dict[PageName, QWidget]:
    session = get_window_ui_session(window)
    return {} if session is None else session.pages


def _ensure_page_in_stack(window, page: QWidget | None) -> None:
    page_host = _get_page_host(window)
    if page_host is not None:
        page_host.ensure_page_in_stacked_widget(page)


def _is_expanded_display_mode(display_mode) -> bool | None:
    mode_name = str(getattr(display_mode, "name", "") or "").upper()
    if mode_name in {"EXPAND", "MENU"}:
        return True
    if mode_name in {"COMPACT", "MINIMAL"}:
        return False
    return None


def _read_saved_sidebar_expanded() -> bool:
    try:
        from settings.store import get_ui_state_settings

        ui_state = get_ui_state_settings()
    except Exception:
        return True
    return bool(ui_state.get(SIDEBAR_EXPANDED_UI_STATE_KEY, True))


def _save_sidebar_expanded(expanded: bool) -> None:
    try:
        from settings.store import set_ui_state_settings

        set_ui_state_settings({SIDEBAR_EXPANDED_UI_STATE_KEY: bool(expanded)})
    except Exception:
        pass


def _restore_sidebar_expanded_state(window) -> None:
    nav = getattr(window, "navigationInterface", None)
    if nav is None:
        return

    if _read_saved_sidebar_expanded():
        expand = getattr(nav, "expand", None)
        if callable(expand):
            expand(False)
        return

    panel = getattr(nav, "panel", None)
    collapse = getattr(panel, "collapse", None)
    if callable(collapse):
        collapse()


def _bind_sidebar_expanded_state(window) -> None:
    nav = getattr(window, "navigationInterface", None)
    signal = getattr(nav, "displayModeChanged", None)
    connect = getattr(signal, "connect", None)
    if not callable(connect):
        return

    def _on_display_mode_changed(display_mode) -> None:
        expanded = _is_expanded_display_mode(display_mode)
        if expanded is not None:
            _save_sidebar_expanded(expanded)

    connect(_on_display_mode_changed)


def _scroll_layout_index(window, widget) -> int:
    nav = getattr(window, "navigationInterface", None)
    panel = getattr(nav, "panel", None)
    scroll_layout = getattr(panel, "scrollLayout", None)
    if scroll_layout is None or widget is None:
        return -1
    try:
        return int(scroll_layout.indexOf(widget))
    except Exception:
        return -1


def _get_scroll_widget_for_layout_entry(window, entry) -> QWidget | None:
    session = get_window_ui_session(window)
    if session is None:
        return None
    if getattr(entry, "kind", "") == "page":
        return session.nav_items.get(entry.page_name)
    if getattr(entry, "kind", "") == "header":
        return session.nav_header_by_group.get(entry.group_name)
    return None


def _resolve_scroll_insert_index(window, page_name: PageName, method: str | None) -> int | None:
    for entry in iter_sidebar_entries_after_page(method, page_name):
        next_widget = _get_scroll_widget_for_layout_entry(window, entry)
        next_index = _scroll_layout_index(window, next_widget)
        if next_index >= 0:
            return next_index

    return None


def add_nav_item(
    window,
    page_name: PageName,
    position,
    *,
    initial_visible: bool | None = None,
    insert_index: int | None = None,
    pump_ui: bool = False,
) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return

    if page_name in session.nav_items:
        return

    from ui.navigation.search import show_page
    from ui.navigation.text_sync import get_nav_label

    route_key = get_page_route_key(page_name)
    if not route_key:
        log(f"[NAV] _add {page_name.name}: route key is missing - skip", "DEBUG")
        return

    icon = session.nav_icons.get(page_name, session.default_nav_icon)
    text = get_nav_label(window, page_name)
    eager_pages = set(get_eager_page_names_for_method(window.get_launch_method()))

    if insert_index is not None:
        if page_name in eager_pages:
            page = _ensure_page(window, page_name)
            if page is None:
                log(f"[NAV] insert eager {page_name.name}: page is None - skip", "DEBUG")
                return

            if page.objectName() != route_key:
                page.setObjectName(route_key)

        log(f"[NAV] insertItem {page_name.name} routeKey={route_key!r} index={insert_index}", "DEBUG")
        item = window.navigationInterface.insertItem(
            int(insert_index),
            routeKey=route_key,
            icon=icon,
            text=text,
            onClick=lambda checked=False, page_to_show=page_name, current_window=window: show_page(current_window, page_to_show),
            selectable=True,
            position=position,
        )
        log(f"[NAV] insertItem {page_name.name} item={item}", "DEBUG")
    elif page_name in eager_pages:
        page = _ensure_page(window, page_name)
        if page is None:
            log(f"[NAV] _add eager {page_name.name}: page is None - skip", "DEBUG")
            return

        if page.objectName() != route_key:
            page.setObjectName(route_key)

        log(f"[NAV] addSubInterface {page_name.name} objectName={page.objectName()!r}", "DEBUG")
        item = window.addSubInterface(page, icon, text, position=position)
        log(f"[NAV] addSubInterface {page_name.name} item={item}", "DEBUG")
    else:
        log(f"[NAV] addItem lazy {page_name.name} routeKey={route_key!r}", "DEBUG")
        item = window.navigationInterface.addItem(
            routeKey=route_key,
            icon=icon,
            text=text,
            onClick=lambda checked=False, page_to_show=page_name, current_window=window: show_page(current_window, page_to_show),
            selectable=True,
            position=position,
        )
        log(f"[NAV] addItem lazy {page_name.name} item={item}", "DEBUG")

    if item is not None:
        session.nav_items[page_name] = item
        if initial_visible is not None:
            try:
                item.setVisible(bool(initial_visible))
            except Exception:
                pass
    else:
        log(f"[NAV] addSubInterface returned None for {page_name.name} - not in nav_items!", "WARNING")

    if pump_ui:
        pump_startup_ui(window)


def _install_sidebar_search(window) -> None:
    import time as _time

    started_at = _time.perf_counter()
    session = get_window_ui_session(window)
    if session is None:
        return
    if session.sidebar_search_nav_widget is not None:
        return

    widget_cls = session.sidebar_search_widget_cls
    if widget_cls is None:
        return

    from ui.navigation.search import (
        attach_sidebar_search_to_titlebar,
        on_sidebar_search_changed,
        setup_sidebar_search_completer,
        update_titlebar_search_width,
    )

    session.sidebar_search_nav_widget = widget_cls()
    session.sidebar_search_nav_widget.textChanged.connect(
        lambda text, current_window=window: on_sidebar_search_changed(current_window, text)
    )
    session.sidebar_search_nav_widget.set_placeholder_text(
        tr_catalog("sidebar.search.placeholder", language=session.ui_language)
    )
    setup_sidebar_search_completer(window)
    attach_sidebar_search_to_titlebar(window)
    update_titlebar_search_width(window)
    try:
        window.log_startup_metric(
            "StartupSidebarSearchReady",
            f"{(_time.perf_counter() - started_at) * 1000:.0f}ms",
        )
    except Exception:
        pass


def _schedule_sidebar_search_after_interactive(window) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return
    if session.sidebar_search_widget_cls is None:
        return

    scheduled = False

    def _schedule(*_args) -> None:
        nonlocal scheduled
        if scheduled:
            return
        scheduled = True
        try:
            window.log_startup_metric(
                "StartupSidebarSearchQueued",
                f"{SIDEBAR_SEARCH_AFTER_INTERACTIVE_MS}ms after interactive",
            )
        except Exception:
            pass
        QTimer.singleShot(
            SIDEBAR_SEARCH_AFTER_INTERACTIVE_MS,
            lambda: _install_sidebar_search(window),
        )

    try:
        if bool(getattr(window.startup_state, "interactive_logged", False)):
            _schedule()
            return
    except Exception:
        _schedule()
        return

    try:
        window.startup_interactive_ready.connect(_schedule)
    except Exception:
        _schedule()


def _install_hidden_mode_nav_items(window) -> None:
    import time as _time

    started_at = _time.perf_counter()
    session = get_window_ui_session(window)
    if session is None:
        return

    try:
        method = window.get_launch_method()
    except Exception:
        method = None
    visibility_by_page = get_nav_visibility(method)
    added_count = 0

    for page_name, should_show in visibility_by_page.items():
        if bool(should_show):
            continue
        if page_name in session.nav_items:
            continue
        add_nav_item(
            window,
            page_name,
            session.nav_scroll_position,
            initial_visible=False,
            insert_index=_resolve_scroll_insert_index(window, page_name, method),
            pump_ui=False,
        )
        if page_name in session.nav_items:
            added_count += 1
            session.nav_mode_visibility[page_name] = False

    if added_count:
        apply_nav_visibility_filter(window)
    try:
        window.log_startup_metric(
            "StartupHiddenModeNavReady",
            f"{added_count} items, {(_time.perf_counter() - started_at) * 1000:.0f}ms",
        )
    except Exception:
        pass


def _schedule_hidden_mode_nav_items_after_interactive(window) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return

    scheduled = False

    def _schedule(*_args) -> None:
        nonlocal scheduled
        if scheduled:
            return
        scheduled = True
        try:
            window.log_startup_metric(
                "StartupHiddenModeNavQueued",
                f"{SIDEBAR_HIDDEN_MODE_ITEMS_AFTER_INTERACTIVE_MS}ms after interactive",
            )
        except Exception:
            pass
        QTimer.singleShot(
            SIDEBAR_HIDDEN_MODE_ITEMS_AFTER_INTERACTIVE_MS,
            lambda: _install_hidden_mode_nav_items(window),
        )

    try:
        if bool(getattr(window.startup_state, "interactive_logged", False)):
            _schedule()
            return
    except Exception:
        _schedule()
        return

    try:
        window.startup_interactive_ready.connect(_schedule)
    except Exception:
        _schedule()


def init_navigation(window) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return

    pos_scroll = session.nav_scroll_position
    current_method = window.get_launch_method()

    session.nav_items = {}
    session.nav_search_query = ""
    session.nav_mode_visibility = {}
    session.nav_headers = []
    session.nav_header_by_group = {}
    session.sidebar_search_nav_widget = None
    session.sidebar_search_model = None
    session.sidebar_search_completer = None
    session.sidebar_search_titlebar_attached = False
    initial_visibility = get_nav_visibility(current_method)

    def _add(page_name, position=pos_scroll):
        add_nav_item(
            window,
            page_name,
            position,
            initial_visible=bool(initial_visibility.get(page_name, True)),
        )

    nav = window.navigationInterface

    _schedule_sidebar_search_after_interactive(window)
    _schedule_hidden_mode_nav_items_after_interactive(window)

    for group_plan in build_sidebar_group_plans(current_method):
        if group_plan.header_key:
            header = nav.addItemHeader(
                tr_catalog(group_plan.header_key, language=session.ui_language),
                pos_scroll,
            )
            session.nav_header_by_group[group_plan.group_name] = header
            session.nav_headers.append((header, group_plan.page_names, group_plan.header_key))

        for page_name in group_plan.page_names:
            if not bool(initial_visibility.get(page_name, True)):
                continue
            _add(page_name)

    for hidden in get_hidden_pages_for_method(current_method):
        page = _get_loaded_pages(window).get(hidden)
        if page is not None:
            if not page.objectName():
                page.setObjectName(page.__class__.__name__)
            _ensure_page_in_stack(window, page)
            pump_startup_ui(window)

    window.navigationInterface.setMinimumExpandWidth(700)
    _restore_sidebar_expanded_state(window)
    _bind_sidebar_expanded_state(window)
    sync_nav_visibility(window)


def sync_nav_visibility(window, method: str | None = None) -> None:
    session = get_window_ui_session(window)
    if session is None or not session.nav_items:
        return

    from ui.navigation.search import update_sidebar_search_suggestions

    if method is None:
        from ui.workflows.common import get_current_launch_method

        method = get_current_launch_method(default="")
    if not method:
        from settings.mode import DEFAULT_LAUNCH_METHOD

        method = DEFAULT_LAUNCH_METHOD

    visibility_by_page = get_nav_visibility(method)

    log(f"[NAV] _sync_nav_visibility method={method!r}, nav_items keys={[p.name for p in session.nav_items]}", "DEBUG")
    for page_name, item in tuple(session.nav_items.items()):
        if page_name in visibility_by_page and not bool(visibility_by_page.get(page_name, True)):
            try:
                item.setVisible(False)
            except Exception:
                pass

    mode_visibility: dict[PageName, bool] = {
        page_name: bool(visibility_by_page.get(page_name, True))
        for page_name in session.nav_items
    }
    for page_name, should_show in visibility_by_page.items():
        item = session.nav_items.get(page_name)
        if item is None and bool(should_show):
            add_nav_item(
                window,
                page_name,
                session.nav_scroll_position,
                initial_visible=False,
                insert_index=_resolve_scroll_insert_index(window, page_name, method),
                pump_ui=True,
            )
            item = session.nav_items.get(page_name)

        if item is not None:
            mode_visibility[page_name] = bool(should_show)
            log(f"[NAV]   {page_name.name} → modeVisible({should_show})", "DEBUG")
        elif bool(should_show):
            log(f"[NAV]   {page_name.name} → NOT in nav_items!", "WARNING")

    session.nav_mode_visibility = mode_visibility
    apply_nav_visibility_filter(window)
    update_sidebar_search_suggestions(window)


def apply_nav_visibility_filter(window) -> None:
    session = get_window_ui_session(window)
    if session is None or not session.nav_items:
        return

    from ui.navigation.text_sync import get_nav_label

    search_query = (session.nav_search_query or "").casefold()
    mode_visibility = session.nav_mode_visibility or {}
    visible_by_page: dict[PageName, bool] = {}

    for page_name, item in session.nav_items.items():
        mode_visible = bool(mode_visibility.get(page_name, True))
        label = get_nav_label(window, page_name)
        matches_query = not search_query or (search_query in label.casefold())
        final_visible = mode_visible and matches_query
        item.setVisible(final_visible)
        visible_by_page[page_name] = final_visible

    for header, grouped_pages, _header_key in session.nav_headers:
        if header is None:
            continue
        header.setVisible(any(visible_by_page.get(page_name, False) for page_name in grouped_pages))


__all__ = [
    "add_nav_item",
    "apply_nav_visibility_filter",
    "init_navigation",
    "sync_nav_visibility",
]
