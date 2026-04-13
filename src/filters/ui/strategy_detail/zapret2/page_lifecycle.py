from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtWidgets import QApplication

from log.log import log
from ui.theme import get_theme_tokens, get_themed_qta_icon


def after_content_built(page) -> None:
    page._content_built = True

    # Close hover/pinned preview when the main window hides/deactivates (e.g. tray).
    QTimer.singleShot(0, lambda: (not page._cleanup_in_progress) and install_host_window_event_filter(page))

    apply_pending_target_request_if_ready(page)


def install_host_window_event_filter(page) -> None:
    if page._cleanup_in_progress:
        return
    try:
        window = page.window()
    except Exception:
        window = None
    if not window or window is page._host_window:
        return
    page._host_window = window
    try:
        window.installEventFilter(page)
    except Exception:
        pass


def handle_host_window_event_filter(page, obj, event, *, super_handler: Callable[[], object]):
    try:
        if obj is page._host_window and event is not None:
            event_type = event.type()
            if event_type in (
                QEvent.Type.Hide,
                QEvent.Type.Close,
                QEvent.Type.WindowDeactivate,
                QEvent.Type.WindowStateChange,
            ):
                # Don't close if focus went to the preview dialog itself.
                if event_type == QEvent.Type.WindowDeactivate and page._preview_dialog is not None:
                    try:
                        active = QApplication.activeWindow()
                        if active is not None and active is page._preview_dialog:
                            return super_handler()
                    except Exception:
                        pass
                page._close_preview_dialog(force=True)
                close_filter_combo_popup(page)
    except Exception:
        pass
    return super_handler()


def close_filter_combo_popup(page) -> None:
    """Close the technique filter ComboBox dropdown if it is open."""
    try:
        combo = getattr(page, "_filter_combo", None)
        if combo is not None and hasattr(combo, "_closeComboMenu"):
            combo._closeComboMenu()
    except Exception:
        pass


def apply_page_theme(page, tokens=None, force: bool = False) -> None:
    try:
        tokens = tokens or get_theme_tokens()
    except Exception:
        return

    key = (
        str(tokens.theme_name),
        str(tokens.fg),
        str(tokens.fg_muted),
        str(tokens.fg_faint),
        str(tokens.accent_hex),
    )
    if not force and key == page._last_theme_overrides_key:
        return
    page._last_theme_overrides_key = key

    try:
        detail_text_color = tokens.fg_muted if tokens.is_light else tokens.fg
        if getattr(page, "_subtitle_strategy", None) is not None:
            subtitle_style = f"background: transparent; padding-left: 10px; color: {detail_text_color};"
            if page._subtitle_strategy.styleSheet() != subtitle_style:
                page._subtitle_strategy.setStyleSheet(subtitle_style)
    except Exception:
        pass

    try:
        if getattr(page, "_parent_link", None) is not None:
            parent_color = str(tokens.fg_muted)
            if parent_color != page._last_parent_link_icon_color:
                page._parent_link.setIcon(get_themed_qta_icon("fa5s.chevron-left", color=parent_color))
                page._last_parent_link_icon_color = parent_color
    except Exception:
        pass

    try:
        if not getattr(page, "_HAS_FLUENT", False) and getattr(page, "_edit_args_btn", None) is not None:
            edit_color = str(tokens.fg_faint)
            if edit_color != page._last_edit_args_icon_color:
                page._edit_args_btn.setIcon(get_themed_qta_icon("fa5s.edit", color=edit_color))
                page._last_edit_args_icon_color = edit_color
    except Exception:
        pass

    try:
        page._update_sort_button_ui()
    except Exception:
        pass


def handle_hide_event(page, event, *, super_handler: Callable[[], object]):
    # Ensure floating preview/tool windows do not keep intercepting mouse events
    # after navigation away from this page.
    try:
        save_scroll_state(page)
    except Exception:
        pass
    try:
        page._close_preview_dialog(force=True)
    except Exception:
        pass
    try:
        close_filter_combo_popup(page)
    except Exception:
        pass
    try:
        page._stop_loading()
    except Exception:
        pass
    page._preset_refresh_runtime.mark_pending()
    try:
        page._strategies_load_runtime.reset(delete_later=False)
    except Exception:
        pass
    return super_handler()


def handle_page_activated(page) -> None:
    apply_pending_target_request_if_ready(page)
    if page._preset_refresh_runtime.consume_pending():
        page.refresh_from_preset_switch()


def refresh_scroll_range(page) -> None:
    # Ensure QScrollArea recomputes range after dynamic content growth.
    try:
        if page.layout is not None:
            page.layout.invalidate()
            page.layout.activate()
    except Exception:
        pass


def apply_pending_target_request_if_ready(page) -> None:
    if page._cleanup_in_progress:
        return
    pending_target_key = page._target_payload_runtime.take_pending_target_if_ready(
        is_visible=page.isVisible(),
        content_built=bool(getattr(page, "_content_built", False)),
    )
    if not pending_target_key:
        return

    try:
        page._request_target_payload(pending_target_key, refresh=False, reason="show_target")
    except Exception:
        page._target_payload_runtime.restore_pending_target(pending_target_key)
    try:
        if hasattr(page, "content") and page.content is not None:
            page.content.updateGeometry()
            page.content.adjustSize()
    except Exception:
        pass
    try:
        page.updateGeometry()
        page.viewport().update()
    except Exception:
        pass


def save_scroll_state(page, target_key: str | None = None) -> None:
    key = str(target_key or page._target_key or "").strip()
    if not key:
        return

    try:
        bar = page.verticalScrollBar()
        page._page_scroll_by_target[key] = int(bar.value())
    except Exception:
        pass

    try:
        if page._strategies_tree:
            tree_bar = page._strategies_tree.verticalScrollBar()
            page._tree_scroll_by_target[key] = int(tree_bar.value())
    except Exception:
        pass


def restore_scroll_state(page, target_key: str | None = None, defer: bool = False) -> None:
    key = str(target_key or page._target_key or "").strip()
    if not key:
        return

    def _apply() -> None:
        if page._cleanup_in_progress:
            return
        try:
            page_bar = page.verticalScrollBar()
            saved_page = page._page_scroll_by_target.get(key)
            if saved_page is None:
                page_bar.setValue(page_bar.minimum())
            else:
                page_bar.setValue(max(page_bar.minimum(), min(int(saved_page), page_bar.maximum())))
        except Exception:
            pass

        try:
            if not page._strategies_tree:
                return
            tree_bar = page._strategies_tree.verticalScrollBar()
            saved_tree = page._tree_scroll_by_target.get(key)
            if saved_tree is None:
                return
            tree_bar.setValue(max(tree_bar.minimum(), min(int(saved_tree), tree_bar.maximum())))
        except Exception:
            pass

    if defer:
        QTimer.singleShot(0, lambda: (not page._cleanup_in_progress) and _apply())
        QTimer.singleShot(40, lambda: (not page._cleanup_in_progress) and _apply())
    else:
        _apply()
