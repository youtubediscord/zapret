from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from app.page_names import PageName
from app.ui_texts import (
    get_nav_page_label,
    normalize_language,
    tr as tr_catalog,
)
from ui.window_ui_session import get_window_ui_session


def resolve_ui_language(window) -> str:
    _ = window
    try:
        from settings.appearance import peek_warmed_ui_language

        return normalize_language(peek_warmed_ui_language())
    except Exception:
        return normalize_language(None)


def get_nav_label(window, page_name: PageName) -> str:
    session = get_window_ui_session(window)
    fallback = page_name.name if session is None else session.nav_labels.get(page_name, page_name.name)
    language = None if session is None else session.ui_language
    return get_nav_page_label(page_name, language=language, fallback=fallback)


def refresh_navigation_texts(window) -> None:
    from ui.navigation.search import update_sidebar_search_suggestions
    from ui.navigation.sidebar_builder import apply_nav_visibility_filter

    session = get_window_ui_session(window)
    if session is None:
        return

    if session.sidebar_search_nav_widget is not None:
        session.sidebar_search_nav_widget.set_placeholder_text(
            tr_catalog("sidebar.search.placeholder", language=session.ui_language)
        )

    for page_name, item in session.nav_items.items():
        try:
            item.setText(get_nav_label(window, page_name))
        except Exception:
            pass

    for header, _grouped_pages, header_key in session.nav_headers:
        if header is None:
            continue
        try:
            header.setText(tr_catalog(header_key, language=session.ui_language))
        except Exception:
            pass

    apply_nav_visibility_filter(window)
    update_sidebar_search_suggestions(window)


def on_ui_language_changed(window, language: str) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return
    session.ui_language = normalize_language(language)
    refresh_navigation_texts(window)
    refresh_pages_language(window)


def apply_ui_language_to_page(window, page: QWidget | None) -> None:
    if page is None:
        return

    session = get_window_ui_session(window)
    language = normalize_language("ru" if session is None else session.ui_language)
    if getattr(page, "_last_applied_ui_language", None) == language:
        return
    page_language = getattr(page, "_ui_language", None)
    if page_language is not None and normalize_language(page_language) == language:
        setattr(page, "_last_applied_ui_language", language)
        return

    for method_name in ("set_ui_language", "retranslate_ui", "apply_ui_language"):
        method = getattr(page, method_name, None)
        if callable(method):
            try:
                method(language)
                setattr(page, "_last_applied_ui_language", language)
            except TypeError:
                try:
                    method()
                    setattr(page, "_last_applied_ui_language", language)
                except Exception:
                    pass
            except Exception:
                pass
            return


def refresh_pages_language(window) -> None:
    session = get_window_ui_session(window)
    if session is None:
        return
    for page in session.pages.values():
        apply_ui_language_to_page(window, page)


__all__ = [
    "apply_ui_language_to_page",
    "get_nav_label",
    "on_ui_language_changed",
    "refresh_navigation_texts",
    "refresh_pages_language",
    "resolve_ui_language",
]
