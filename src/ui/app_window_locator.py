from __future__ import annotations

def register_app_window(window) -> None:
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.setProperty("zapret_primary_window", window)
    except Exception:
        pass

__all__ = [
    "register_app_window",
]
