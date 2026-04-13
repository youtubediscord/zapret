from __future__ import annotations

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
from ui.page_names import PageName
from ui.startup_ui_metrics import pump_startup_ui
from ui.text_catalog import tr as tr_catalog


def _get_page_host(window):
    return getattr(window, "_page_host", None)


def _ensure_page(window, page_name: PageName):
    page_host = _get_page_host(window)
    if page_host is None:
        return None
    return page_host.ensure_page(page_name)


def _get_loaded_pages(window) -> dict[PageName, QWidget]:
    page_host = _get_page_host(window)
    pages = getattr(page_host, "pages", None)
    if isinstance(pages, dict):
        return pages
    return {}


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
    if getattr(entry, "kind", "") == "page":
        return getattr(window, "_nav_items", {}).get(entry.page_name)
    if getattr(entry, "kind", "") == "header":
        return (getattr(window, "_nav_header_by_group", None) or {}).get(entry.group_name)
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
) -> None:
    if not getattr(window, "_has_fluent_nav", False):
        return

    if page_name in getattr(window, "_nav_items", {}):
        return

    from ui.navigation.search import show_page
    from ui.navigation.text_sync import get_nav_label

    route_key = get_page_route_key(page_name)
    if not route_key:
        log(f"[NAV] _add {page_name.name}: route key is missing - skip", "DEBUG")
        return

    icon = window._nav_icons.get(page_name, window._default_nav_icon)
    text = get_nav_label(window, page_name)
    eager_pages = set(get_eager_page_names_for_method(window._get_launch_method()))

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
            onClick=lambda checked=False, target=page_name, current_window=window: show_page(current_window, target),
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
            onClick=lambda checked=False, target=page_name, current_window=window: show_page(current_window, target),
            selectable=True,
            position=position,
        )
        log(f"[NAV] addItem lazy {page_name.name} item={item}", "DEBUG")

    if item is not None:
        window._nav_items[page_name] = item
        if initial_visible is not None:
            try:
                item.setVisible(bool(initial_visible))
            except Exception:
                pass
    else:
        log(f"[NAV] addSubInterface returned None for {page_name.name} - not in _nav_items!", "WARNING")

    pump_startup_ui(window)


def init_navigation(window) -> None:
    if not getattr(window, "_has_fluent_nav", False):
        return

    from ui.navigation.search import (
        attach_sidebar_search_to_titlebar,
        on_sidebar_search_changed,
        setup_sidebar_search_completer,
        update_titlebar_search_width,
    )

    pos_scroll = window._nav_scroll_position
    current_method = window._get_launch_method()

    window._nav_items = {}
    window._nav_search_query = ""
    window._nav_mode_visibility = {}
    window._nav_headers = []
    window._nav_header_by_group = {}
    window._sidebar_search_nav_widget = None
    window._sidebar_search_model = None
    window._sidebar_search_completer = None
    window._sidebar_search_titlebar_attached = False
    initial_visibility = get_nav_visibility(current_method)

    def _add(page_name, position=pos_scroll):
        add_nav_item(
            window,
            page_name,
            position,
            initial_visible=bool(initial_visibility.get(page_name, True)),
        )

    nav = window.navigationInterface

    if getattr(window, "_has_fluent_nav", False):
        widget_cls = getattr(window, "_sidebar_search_widget_cls", None)
        if widget_cls is not None:
            window._sidebar_search_nav_widget = widget_cls()
            window._sidebar_search_nav_widget.textChanged.connect(
                lambda text, current_window=window: on_sidebar_search_changed(current_window, text)
            )
            window._sidebar_search_nav_widget.set_placeholder_text(
                tr_catalog("sidebar.search.placeholder", language=window._ui_language)
            )
            setup_sidebar_search_completer(window)
            attach_sidebar_search_to_titlebar(window)
            update_titlebar_search_width(window)

    for group_plan in build_sidebar_group_plans(current_method):
        if group_plan.header_key:
            header = nav.addItemHeader(
                tr_catalog(group_plan.header_key, language=window._ui_language),
                pos_scroll,
            )
            window._nav_header_by_group[group_plan.group_name] = header
            window._nav_headers.append((header, group_plan.page_names, group_plan.header_key))

        for page_name in group_plan.page_names:
            _add(page_name)

    for hidden in get_hidden_pages_for_method(current_method):
        page = _get_loaded_pages(window).get(hidden)
        if page is not None:
            if not page.objectName():
                page.setObjectName(page.__class__.__name__)
            window.stackedWidget.addWidget(page)
            pump_startup_ui(window)

    window.navigationInterface.setMinimumExpandWidth(700)
    sync_nav_visibility(window)


def sync_nav_visibility(window, method: str | None = None) -> None:
    if not getattr(window, "_nav_items", None):
        return

    from ui.navigation.search import update_sidebar_search_suggestions

    if method is None:
        try:
            from settings.dpi.strategy_settings import get_strategy_launch_method

            method = (get_strategy_launch_method() or "").strip().lower()
        except Exception:
            method = "direct_zapret2"
    if not method:
        method = "direct_zapret2"

    targets = get_nav_visibility(method)

    log(f"[NAV] _sync_nav_visibility method={method!r}, _nav_items keys={[p.name for p in window._nav_items]}", "DEBUG")
    mode_visibility: dict[PageName, bool] = {
        page_name: True for page_name in window._nav_items
    }
    for page_name, should_show in targets.items():
        item = window._nav_items.get(page_name)
        if item is None and bool(should_show):
            add_nav_item(
                window,
                page_name,
                window._nav_scroll_position,
                insert_index=_resolve_scroll_insert_index(window, page_name, method),
            )
            item = window._nav_items.get(page_name)

        if item is not None:
            mode_visibility[page_name] = bool(should_show)
            log(f"[NAV]   {page_name.name} → modeVisible({should_show})", "DEBUG")
        elif bool(should_show):
            log(f"[NAV]   {page_name.name} → NOT in _nav_items!", "WARNING")

    window._nav_mode_visibility = mode_visibility
    apply_nav_visibility_filter(window)
    update_sidebar_search_suggestions(window)


def apply_nav_visibility_filter(window) -> None:
    if not getattr(window, "_nav_items", None):
        return

    from ui.navigation.text_sync import get_nav_label

    search_query = (getattr(window, "_nav_search_query", "") or "").casefold()
    mode_visibility = getattr(window, "_nav_mode_visibility", {}) or {}
    visible_by_page: dict[PageName, bool] = {}

    for page_name, item in window._nav_items.items():
        mode_visible = bool(mode_visibility.get(page_name, True))
        label = get_nav_label(window, page_name)
        matches_query = not search_query or (search_query in label.casefold())
        final_visible = mode_visible and matches_query
        item.setVisible(final_visible)
        visible_by_page[page_name] = final_visible

    for header, grouped_pages, _header_key in getattr(window, "_nav_headers", []):
        if header is None:
            continue
        header.setVisible(any(visible_by_page.get(page_name, False) for page_name in grouped_pages))


__all__ = [
    "add_nav_item",
    "apply_nav_visibility_filter",
    "init_navigation",
    "sync_nav_visibility",
]
