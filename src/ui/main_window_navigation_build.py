from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QCompleter, QWidget

from log import log
from ui.page_names import PageName
from ui.router import (
    get_hidden_pages_for_method,
    get_nav_visibility,
    get_page_route_key,
    get_sidebar_pages_for_method,
    get_sidebar_search_pages_for_method,
)
from ui.text_catalog import (
    find_search_entries,
    format_search_result,
    get_nav_page_label,
    normalize_language,
    tr as tr_catalog,
)
from ui.main_window_pages import get_eager_page_names


@dataclass(frozen=True)
class SidebarSearchTarget:
    page_name: PageName
    tab_key: str = ""


def add_nav_item(window, page_name: PageName, position, *, initial_visible: bool | None = None) -> None:
    if not getattr(window, "_has_fluent_nav", False):
        return

    if page_name in getattr(window, "_nav_items", {}):
        return

    route_key = get_page_route_key(page_name)
    if not route_key:
        log(f"[NAV] _add {page_name.name}: route key is missing - skip", "DEBUG")
        return

    icon = window._nav_icons.get(page_name, window._default_nav_icon)
    text = get_nav_label(window, page_name)
    eager_pages = set(get_eager_page_names(window))

    if page_name in eager_pages:
        page = window._ensure_page(page_name)
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
            onClick=lambda checked=False, target=page_name: window.show_page(target),
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

    window._pump_startup_ui()


def init_navigation(window) -> None:
    if not getattr(window, "_has_fluent_nav", False):
        return

    pos_scroll = window._nav_scroll_position
    current_method = window._get_launch_method()

    window._nav_items = {}
    window._nav_search_query = ""
    window._nav_mode_visibility = {}
    window._nav_headers = []
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
            window._sidebar_search_nav_widget.textChanged.connect(window._on_sidebar_search_changed)
            window._sidebar_search_nav_widget.set_placeholder_text(
                tr_catalog("sidebar.search.placeholder", language=window._ui_language)
            )
            setup_sidebar_search_completer(window)
            attach_sidebar_search_to_titlebar(window)
            update_titlebar_search_width(window)

    for page_name in get_sidebar_pages_for_method(current_method, sidebar_group="root"):
        _add(page_name)

    settings_header_key = "nav.header.settings"
    settings_header = nav.addItemHeader(tr_catalog(settings_header_key, language=window._ui_language), pos_scroll)
    settings_pages = get_sidebar_pages_for_method(current_method, sidebar_group="settings")
    for page_name in settings_pages:
        _add(page_name)
    window._nav_headers.append((settings_header, settings_pages, settings_header_key))

    system_header_key = "nav.header.system"
    system_header = nav.addItemHeader(tr_catalog(system_header_key, language=window._ui_language), pos_scroll)
    system_pages = get_sidebar_pages_for_method(current_method, sidebar_group="system")
    for page_name in system_pages:
        _add(page_name)
    window._nav_headers.append((system_header, system_pages, system_header_key))

    diagnostics_header_key = "nav.header.diagnostics"
    diagnostics_header = nav.addItemHeader(tr_catalog(diagnostics_header_key, language=window._ui_language), pos_scroll)
    diagnostics_pages = get_sidebar_pages_for_method(current_method, sidebar_group="diagnostics")
    for page_name in diagnostics_pages:
        _add(page_name)
    window._nav_headers.append((diagnostics_header, diagnostics_pages, diagnostics_header_key))

    appearance_header_key = "nav.header.appearance"
    appearance_header = nav.addItemHeader(tr_catalog(appearance_header_key, language=window._ui_language), pos_scroll)
    appearance_pages = get_sidebar_pages_for_method(current_method, sidebar_group="appearance")
    for page_name in appearance_pages:
        _add(page_name)
    window._nav_headers.append((appearance_header, appearance_pages, appearance_header_key))

    for hidden in get_hidden_pages_for_method(current_method):
        page = window.pages.get(hidden)
        if page is not None:
            if not page.objectName():
                page.setObjectName(page.__class__.__name__)
            window.stackedWidget.addWidget(page)
            window._pump_startup_ui()

    window.navigationInterface.setMinimumExpandWidth(700)
    sync_nav_visibility(window)


def attach_sidebar_search_to_titlebar(window) -> None:
    widget = window._sidebar_search_nav_widget
    if widget is None:
        return
    title_bar = getattr(window, "titleBar", None)
    if title_bar is None:
        return
    layout = getattr(title_bar, "hBoxLayout", None)
    if layout is None:
        return
    if widget.parent() is not title_bar:
        widget.setParent(title_bar)
    if layout.indexOf(widget) < 0:
        insert_index = max(0, layout.count() - 1)
        layout.insertWidget(insert_index, widget, 0, Qt.AlignmentFlag.AlignVCenter)
    window._sidebar_search_titlebar_attached = True


def update_titlebar_search_width(window) -> None:
    if not bool(getattr(window, "_sidebar_search_titlebar_attached", False)):
        return
    widget = window._sidebar_search_nav_widget
    if widget is None:
        return
    title_bar = getattr(window, "titleBar", None)
    if title_bar is None:
        return
    title_bar_width = int(title_bar.width())
    if title_bar_width <= 0:
        title_bar_width = max(0, int(window.width()) - 46)
    available_width = max(220, title_bar_width - 340)
    target_width = int(title_bar_width * 0.42)
    target_width = max(280, min(560, target_width, available_width))
    widget.setFixedWidth(target_width)


def sync_nav_visibility(window, method: str | None = None) -> None:
    if not getattr(window, '_nav_items', None):
        return

    if method is None:
        try:
            from strategy_menu import get_strategy_launch_method
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
            add_nav_item(window, page_name, window._nav_scroll_position)
            item = window._nav_items.get(page_name)

        if item is not None:
            mode_visibility[page_name] = bool(should_show)
            log(f"[NAV]   {page_name.name} → modeVisible({should_show})", "DEBUG")
        elif bool(should_show):
            log(f"[NAV]   {page_name.name} → NOT in _nav_items!", "WARNING")

    window._nav_mode_visibility = mode_visibility
    apply_nav_visibility_filter(window)
    update_sidebar_search_suggestions(window)


def on_sidebar_search_changed(window, text: str) -> None:
    window._nav_search_query = (text or "").strip()
    if route_sidebar_search_by_text(window, window._nav_search_query, prefer_first=False):
        return
    apply_nav_visibility_filter(window)
    update_sidebar_search_suggestions(window)


def apply_nav_visibility_filter(window) -> None:
    if not getattr(window, "_nav_items", None):
        return

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


def resolve_ui_language(window) -> str:
    try:
        from config.reg import get_ui_language
        return normalize_language(get_ui_language())
    except Exception:
        return normalize_language(None)


def get_nav_label(window, page_name: PageName) -> str:
    fallback = window._nav_labels.get(page_name, page_name.name)
    return get_nav_page_label(page_name, language=window._ui_language, fallback=fallback)


def get_sidebar_search_pages(window) -> set[PageName]:
    return get_sidebar_search_pages_for_method(window._get_launch_method(), set(window._page_class_specs.keys()))


def setup_sidebar_search_completer(window) -> None:
    if window._sidebar_search_nav_widget is None:
        return

    window._sidebar_search_model = QStandardItemModel(window)
    completer = QCompleter(window._sidebar_search_model, window)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.setMaxVisibleItems(10)
    completer.activated[QModelIndex].connect(window._on_sidebar_search_result_activated)
    completer.activated[str].connect(window._on_sidebar_search_result_text_activated)
    try:
        popup = completer.popup()
        if popup is not None:
            popup.clicked.connect(window._on_sidebar_search_result_activated)
            popup.activated.connect(window._on_sidebar_search_result_activated)
    except Exception:
        pass

    window._sidebar_search_completer = completer
    window._sidebar_search_nav_widget.set_completer(completer)


def update_sidebar_search_suggestions(window) -> None:
    model = window._sidebar_search_model
    completer = window._sidebar_search_completer
    if model is None or completer is None:
        return

    model.clear()
    query = (getattr(window, "_nav_search_query", "") or "").strip()
    if not query:
        try:
            completer.popup().hide()
        except Exception:
            pass
        return

    visible_pages = get_sidebar_search_pages(window)

    matches = find_search_entries(
        query,
        language=window._ui_language,
        visible_pages=visible_pages,
        max_results=10,
    )
    if not matches:
        try:
            completer.popup().hide()
        except Exception:
            pass
        return

    page_role = int(Qt.ItemDataRole.UserRole)
    tab_role = page_role + 1

    for match in matches:
        title, location = format_search_result(match.entry, language=window._ui_language)
        item = QStandardItem(f"{title} - {location}")
        item.setData(match.entry.page_name.name, page_role)
        item.setData(match.entry.tab_key or "", tab_role)
        model.appendRow(item)

    if window._sidebar_search_nav_widget is not None and window._sidebar_search_nav_widget.isVisible():
        window._sidebar_search_nav_widget.show_completions()


def _clear_sidebar_search(window) -> None:
    if window._sidebar_search_nav_widget is not None:
        window._sidebar_search_nav_widget.clear()


def _route_search_result_and_clear(window, page_name: PageName, tab_key: str = "") -> bool:
    if not route_search_result(window, page_name, tab_key):
        return False
    _clear_sidebar_search(window)
    return True


def _build_sidebar_search_target(raw_page_name, tab_key: str | None = "") -> SidebarSearchTarget | None:
    if not isinstance(raw_page_name, str) or not raw_page_name:
        return None
    try:
        page_name = PageName[raw_page_name]
    except Exception:
        return None
    return SidebarSearchTarget(
        page_name=page_name,
        tab_key=str(tab_key or ""),
    )


def _search_target_from_index(index: QModelIndex) -> SidebarSearchTarget | None:
    if not index.isValid():
        return None

    page_role = int(Qt.ItemDataRole.UserRole)
    tab_role = page_role + 1
    return _build_sidebar_search_target(
        index.data(page_role),
        index.data(tab_role),
    )


def _search_target_from_item(item: QStandardItem | None) -> SidebarSearchTarget | None:
    if item is None:
        return None

    page_role = int(Qt.ItemDataRole.UserRole)
    tab_role = page_role + 1
    return _build_sidebar_search_target(
        item.data(page_role),
        item.data(tab_role),
    )


def _find_search_item_in_model(model: QStandardItemModel, text_cf: str, *, prefer_first: bool) -> QStandardItem | None:
    target_item = None
    for row in range(model.rowCount()):
        item = model.item(row, 0)
        if item is None:
            continue
        if (item.text() or "").strip().casefold() == text_cf:
            target_item = item
            break

    if target_item is None and prefer_first and model.rowCount() > 0:
        target_item = model.item(0, 0)

    return target_item


def _resolve_search_target_from_query(window, text: str, *, prefer_first: bool) -> SidebarSearchTarget | None:
    text = (text or "").strip()
    if not text:
        return None

    query = text
    text_cf = text.casefold()
    if " - " in query:
        query = (query.split(" - ", 1)[0] or "").strip() or query

    visible_pages = get_sidebar_search_pages(window)
    matches = find_search_entries(
        query,
        language=window._ui_language,
        visible_pages=visible_pages,
        max_results=10,
    )
    selected_match = None
    for match in matches:
        title, location = format_search_result(match.entry, language=window._ui_language)
        display = f"{title} - {location}".strip().casefold()
        title_cf = (title or "").strip().casefold()
        if display == text_cf or title_cf == text_cf:
            selected_match = match
            break

    if selected_match is None and prefer_first and matches:
        selected_match = matches[0]

    if selected_match is None:
        return None

    return SidebarSearchTarget(
        page_name=selected_match.entry.page_name,
        tab_key=str(selected_match.entry.tab_key or ""),
    )


def on_sidebar_search_result_activated(window, index: QModelIndex) -> None:
    target = _search_target_from_index(index)
    if target is None:
        display_text = index.data(int(Qt.ItemDataRole.DisplayRole))
        if isinstance(display_text, str):
            route_sidebar_search_by_text(window, display_text, prefer_first=False)
        return

    _route_search_result_and_clear(window, target.page_name, target.tab_key)


def on_sidebar_search_result_text_activated(window, text: str) -> None:
    route_sidebar_search_by_text(window, text, prefer_first=False)


def route_sidebar_search_by_text(window, text: str, prefer_first: bool = False) -> bool:
    text = (text or "").strip()
    if not text:
        return False

    model = window._sidebar_search_model
    if model is None:
        return False

    text_cf = text.casefold()
    target_item = _find_search_item_in_model(model, text_cf, prefer_first=prefer_first)

    if target_item is None:
        target = _resolve_search_target_from_query(window, text, prefer_first=prefer_first)
        if target is None:
            return False

        _route_search_result_and_clear(window, target.page_name, target.tab_key)
        return True

    target = _search_target_from_item(target_item)
    if target is None:
        return False

    _route_search_result_and_clear(window, target.page_name, target.tab_key)
    return True


def route_search_result(window, page_name: PageName, tab_key: str = "") -> bool:
    if not window.show_page(page_name):
        return False

    if not tab_key:
        return True

    call_loaded_page_method = getattr(window, "_call_loaded_page_method", None)
    if not callable(call_loaded_page_method):
        return False

    try:
        return bool(call_loaded_page_method(page_name, "switch_to_tab", tab_key))
    except Exception:
        return False


def refresh_navigation_texts(window) -> None:
    if window._sidebar_search_nav_widget is not None:
        window._sidebar_search_nav_widget.set_placeholder_text(
            tr_catalog("sidebar.search.placeholder", language=window._ui_language)
        )

    for page_name, item in getattr(window, "_nav_items", {}).items():
        try:
            item.setText(get_nav_label(window, page_name))
        except Exception:
            pass

    for header, _grouped_pages, header_key in getattr(window, "_nav_headers", []):
        if header is None:
            continue
        try:
            header.setText(tr_catalog(header_key, language=window._ui_language))
        except Exception:
            pass

    apply_nav_visibility_filter(window)
    update_sidebar_search_suggestions(window)


def on_ui_language_changed(window, language: str) -> None:
    window._ui_language = normalize_language(language)
    refresh_navigation_texts(window)
    refresh_pages_language(window)


def apply_ui_language_to_page(window, page: QWidget | None) -> None:
    if page is None:
        return

    for method_name in ("set_ui_language", "retranslate_ui", "apply_ui_language"):
        method = getattr(page, method_name, None)
        if callable(method):
            try:
                method(window._ui_language)
            except TypeError:
                try:
                    method()
                except Exception:
                    pass
            except Exception:
                pass
            return


def refresh_pages_language(window) -> None:
    for page in getattr(window, "pages", {}).values():
        apply_ui_language_to_page(window, page)
