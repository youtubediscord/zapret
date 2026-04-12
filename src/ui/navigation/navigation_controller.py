from __future__ import annotations

from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QWidget

from ui.navigation.build_impl import (
    add_nav_item,
    apply_nav_visibility_filter,
    apply_ui_language_to_page,
    attach_sidebar_search_to_titlebar,
    get_nav_label,
    get_sidebar_search_pages,
    init_navigation,
    on_sidebar_search_changed,
    on_sidebar_search_result_activated,
    on_sidebar_search_result_text_activated,
    on_ui_language_changed,
    refresh_navigation_texts,
    refresh_pages_language,
    resolve_ui_language,
    route_search_result,
    route_sidebar_search_by_text,
    setup_sidebar_search_completer,
    sync_nav_visibility,
    update_sidebar_search_suggestions,
    update_titlebar_search_width,
)
from ui.page_names import PageName


class WindowNavigationController:
    """Window-facing controller для sidebar/search/titlebar navigation."""

    def __init__(self, window):
        self._window = window

    def add_nav_item(self, page_name: PageName, position) -> None:
        add_nav_item(self._window, page_name, position)

    def init_navigation(self) -> None:
        init_navigation(self._window)

    def attach_sidebar_search_to_titlebar(self) -> None:
        attach_sidebar_search_to_titlebar(self._window)

    def update_titlebar_search_width(self) -> None:
        update_titlebar_search_width(self._window)

    def sync_nav_visibility(self, method: str | None = None) -> None:
        sync_nav_visibility(self._window, method)

    def on_sidebar_search_changed(self, text: str) -> None:
        on_sidebar_search_changed(self._window, text)

    def apply_nav_visibility_filter(self) -> None:
        apply_nav_visibility_filter(self._window)

    def resolve_ui_language(self) -> str:
        return resolve_ui_language(self._window)

    def get_nav_label(self, page_name: PageName) -> str:
        return get_nav_label(self._window, page_name)

    def get_sidebar_search_pages(self) -> set[PageName]:
        return get_sidebar_search_pages(self._window)

    def setup_sidebar_search_completer(self) -> None:
        setup_sidebar_search_completer(self._window)

    def update_sidebar_search_suggestions(self) -> None:
        update_sidebar_search_suggestions(self._window)

    def on_sidebar_search_result_activated(self, index: QModelIndex) -> None:
        on_sidebar_search_result_activated(self._window, index)

    def on_sidebar_search_result_text_activated(self, text: str) -> None:
        on_sidebar_search_result_text_activated(self._window, text)

    def route_sidebar_search_by_text(self, text: str, prefer_first: bool = False) -> bool:
        return route_sidebar_search_by_text(self._window, text, prefer_first=prefer_first)

    def route_search_result(self, page_name: PageName, tab_key: str = "") -> bool:
        return route_search_result(self._window, page_name, tab_key)

    def refresh_navigation_texts(self) -> None:
        refresh_navigation_texts(self._window)

    def apply_ui_language_to_page(self, page: QWidget | None) -> None:
        apply_ui_language_to_page(self._window, page)

    def refresh_pages_language(self) -> None:
        refresh_pages_language(self._window)

    def on_ui_language_changed(self, language: str) -> None:
        on_ui_language_changed(self._window, language)


def ensure_navigation_controller(window) -> WindowNavigationController:
    controller = getattr(window, "_navigation_controller", None)
    if controller is None:
        controller = WindowNavigationController(window)
        window._navigation_controller = controller
    return controller


def resolve_window_ui_language(window) -> str:
    return ensure_navigation_controller(window).resolve_ui_language()


__all__ = [
    "WindowNavigationController",
    "ensure_navigation_controller",
    "resolve_window_ui_language",
]
