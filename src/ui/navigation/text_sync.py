from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from ui.page_names import PageName
from ui.text_catalog import (
    get_nav_page_label,
    normalize_language,
    tr as tr_catalog,
)


def resolve_ui_language(window) -> str:
    try:
        from config.reg import get_ui_language

        return normalize_language(get_ui_language())
    except Exception:
        return normalize_language(None)


def get_nav_label(window, page_name: PageName) -> str:
    fallback = window._nav_labels.get(page_name, page_name.name)
    return get_nav_page_label(page_name, language=window._ui_language, fallback=fallback)


def refresh_navigation_texts(window) -> None:
    from ui.navigation.search import update_sidebar_search_suggestions
    from ui.navigation.sidebar_builder import apply_nav_visibility_filter

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


__all__ = [
    "apply_ui_language_to_page",
    "get_nav_label",
    "on_ui_language_changed",
    "refresh_navigation_texts",
    "refresh_pages_language",
    "resolve_ui_language",
]
