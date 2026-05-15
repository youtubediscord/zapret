from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QCompleter

from ui.navigation.schema import (
    PAGE_ROUTE_SPECS,
    get_sidebar_search_pages_for_method,
)
from ui.page_actions import switch_page_tab
from app.page_names import PageName
from app.text_catalog import (
    find_search_entries,
    format_search_result,
)
from ui.window_ui_session import get_window_ui_session


@dataclass(frozen=True)
class SidebarSearchTarget:
    page_name: PageName
    tab_key: str = ""


def _get_page_host(window):
    session = get_window_ui_session(window)
    return None if session is None else session.page_host


def show_page(window, page_name: PageName) -> bool:
    page_host = _get_page_host(window)
    if page_host is None:
        return False
    return bool(page_host.show_page(page_name))


def attach_sidebar_search_to_titlebar(window) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return
    widget = session.sidebar_search_nav_widget
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
    session.sidebar_search_titlebar_attached = True


def update_titlebar_search_width(window) -> None:
    session = get_window_ui_session(window)
    if session is None or not session.sidebar_search_titlebar_attached:
        return
    widget = session.sidebar_search_nav_widget
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


def on_sidebar_search_changed(window, text: str) -> None:
    from ui.navigation.sidebar_builder import apply_nav_visibility_filter

    session = get_window_ui_session(window)
    if session is None:
        return
    session.nav_search_query = (text or "").strip()
    if route_sidebar_search_by_text(window, session.nav_search_query, prefer_first=False):
        return
    apply_nav_visibility_filter(window)
    update_sidebar_search_suggestions(window)


def get_sidebar_search_pages(window) -> set[PageName]:
    return get_sidebar_search_pages_for_method(
        window.get_launch_method(),
        set(PAGE_ROUTE_SPECS.keys()),
    )


def setup_sidebar_search_completer(window) -> None:
    session = get_window_ui_session(window)
    if session is None or session.sidebar_search_nav_widget is None:
        return

    session.sidebar_search_model = QStandardItemModel(window)
    completer = QCompleter(session.sidebar_search_model, window)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.setMaxVisibleItems(10)
    completer.activated[QModelIndex].connect(
        lambda index, current_window=window: on_sidebar_search_result_activated(current_window, index)
    )
    completer.activated[str].connect(
        lambda text, current_window=window: on_sidebar_search_result_text_activated(current_window, text)
    )
    try:
        popup = completer.popup()
        if popup is not None:
            popup.clicked.connect(
                lambda index, current_window=window: on_sidebar_search_result_activated(current_window, index)
            )
            popup.activated.connect(
                lambda index, current_window=window: on_sidebar_search_result_activated(current_window, index)
            )
    except Exception:
        pass

    session.sidebar_search_completer = completer
    session.sidebar_search_nav_widget.set_completer(completer)


def update_sidebar_search_suggestions(window) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return
    model = session.sidebar_search_model
    completer = session.sidebar_search_completer
    if model is None or completer is None:
        return

    model.clear()
    query = (session.nav_search_query or "").strip()
    if not query:
        try:
            completer.popup().hide()
        except Exception:
            pass
        return

    visible_pages = get_sidebar_search_pages(window)

    matches = find_search_entries(
        query,
        language=session.ui_language,
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
        title, location = format_search_result(match.entry, language=session.ui_language)
        item = QStandardItem(f"{title} - {location}")
        item.setData(match.entry.page_name.name, page_role)
        item.setData(match.entry.tab_key or "", tab_role)
        model.appendRow(item)

    if session.sidebar_search_nav_widget is not None and session.sidebar_search_nav_widget.isVisible():
        session.sidebar_search_nav_widget.show_completions()


def _clear_sidebar_search(window) -> None:
    session = get_window_ui_session(window)
    if session is not None and session.sidebar_search_nav_widget is not None:
        session.sidebar_search_nav_widget.clear()


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
    session = get_window_ui_session(window)
    if session is None:
        return None

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
        language=session.ui_language,
        visible_pages=visible_pages,
        max_results=10,
    )
    selected_match = None
    for match in matches:
        title, location = format_search_result(match.entry, language=session.ui_language)
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

    session = get_window_ui_session(window)
    if session is None:
        return False

    model = session.sidebar_search_model
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
    if not show_page(window, page_name):
        return False

    if not tab_key:
        return True

    try:
        return bool(switch_page_tab(window, page_name, tab_key))
    except Exception:
        return False


__all__ = [
    "SidebarSearchTarget",
    "attach_sidebar_search_to_titlebar",
    "get_sidebar_search_pages",
    "on_sidebar_search_changed",
    "on_sidebar_search_result_activated",
    "on_sidebar_search_result_text_activated",
    "route_search_result",
    "route_sidebar_search_by_text",
    "setup_sidebar_search_completer",
    "show_page",
    "update_sidebar_search_suggestions",
    "update_titlebar_search_width",
]
