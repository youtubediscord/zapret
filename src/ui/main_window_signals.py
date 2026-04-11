from __future__ import annotations


def connect_main_window_page_signals(window) -> None:
    """Wire up page signals for MainWindow.

    Kept out of ui.main_window so the window class stays focused on
    composition/navigation instead of event wiring.
    """
    try:
        from core.services import get_preset_store
        store = get_preset_store()
        store.preset_switched.connect(window._preset_runtime_coordinator.handle_preset_switched)
    except Exception:
        pass

    try:
        from preset_orchestra_zapret2.preset_store import get_preset_store

        orchestra_store = get_preset_store()
        orchestra_store.preset_switched.connect(window._preset_runtime_coordinator.handle_preset_switched)
    except Exception:
        pass

    try:
        from core.services import get_preset_store_v1
        store_v1 = get_preset_store_v1()
        store_v1.preset_switched.connect(window._preset_runtime_coordinator.handle_preset_switched)
    except Exception:
        pass

    try:
        window._preset_runtime_coordinator.setup_active_preset_file_watcher()
    except Exception:
        pass

    try:
        from config.reg import get_smooth_scroll_enabled
        window._on_smooth_scroll_changed(get_smooth_scroll_enabled())
    except Exception:
        pass

    try:
        from config.reg import get_editor_smooth_scroll_enabled

        window._on_editor_smooth_scroll_changed(get_editor_smooth_scroll_enabled())
    except Exception:
        pass
