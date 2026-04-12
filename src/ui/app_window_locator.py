from __future__ import annotations

from collections.abc import Iterable


def register_app_window(window) -> None:
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app._zapret_primary_window = window
    except Exception:
        pass


def _get_registered_app_window():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return None
        return getattr(app, "_zapret_primary_window", None)
    except Exception:
        return None


def _iter_app_windows() -> Iterable[object]:
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return ()

        seen_ids: set[int] = set()
        windows: list[object] = []

        active = app.activeWindow()
        if active is not None:
            windows.append(active)

        for widget in app.topLevelWidgets():
            if widget is None:
                continue
            ident = id(widget)
            if ident in seen_ids:
                continue
            seen_ids.add(ident)
            windows.append(widget)

        return tuple(windows)
    except Exception:
        return ()


def _window_matches_attrs(window, required_attrs: tuple[str, ...]) -> bool:
    if not required_attrs:
        return True
    return all(hasattr(window, attr_name) for attr_name in required_attrs)


def find_app_window(*required_attrs: str):
    required = tuple(str(attr or "").strip() for attr in required_attrs if str(attr or "").strip())
    registered = _get_registered_app_window()
    if registered is not None and _window_matches_attrs(registered, required):
        return registered
    for window in _iter_app_windows():
        if _window_matches_attrs(window, required):
            return window
    return None


def emit_window_signal(signal_name: str, payload) -> bool:
    signal_name = str(signal_name or "").strip()
    if not signal_name:
        return False

    target = find_app_window(signal_name)
    if target is None:
        return False

    signal = getattr(target, signal_name, None)
    if signal is None:
        return False

    try:
        signal.emit(payload)
        return True
    except Exception:
        return False


__all__ = [
    "emit_window_signal",
    "find_app_window",
    "register_app_window",
]
