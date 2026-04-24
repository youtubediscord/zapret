from __future__ import annotations

from log.log import log
from settings import store as settings_store


def get_window_position():
    """Получает сохраненную позицию окна из settings.json."""
    try:
        geometry = settings_store.get_window_geometry()
        x = geometry.get("x")
        y = geometry.get("y")
        if x is None or y is None:
            return None
        return int(x), int(y)
    except Exception as e:
        log(f"Ошибка чтения позиции окна: {e}", "DEBUG")
        return None


def set_window_position(x, y):
    """Сохраняет позицию окна в settings.json."""
    try:
        geometry = settings_store.get_window_geometry()
        settings_store.set_window_geometry(
            x=int(x),
            y=int(y),
            width=geometry.get("width"),
            height=geometry.get("height"),
            maximized=bool(geometry.get("maximized")),
        )
        log(f"Позиция окна сохранена: ({x}, {y})", "DEBUG")
        return True
    except Exception as e:
        log(f"Ошибка сохранения позиции окна: {e}", "ERROR")
        return False


def get_window_size():
    """Получает сохраненный размер окна из settings.json."""
    try:
        geometry = settings_store.get_window_geometry()
        width = geometry.get("width")
        height = geometry.get("height")
        if width is None or height is None:
            return None
        return int(width), int(height)
    except Exception as e:
        log(f"Ошибка чтения размера окна: {e}", "DEBUG")
        return None


def set_window_size(width, height):
    """Сохраняет размер окна в settings.json."""
    try:
        geometry = settings_store.get_window_geometry()
        settings_store.set_window_geometry(
            x=geometry.get("x"),
            y=geometry.get("y"),
            width=int(width),
            height=int(height),
            maximized=bool(geometry.get("maximized")),
        )
        log(f"Размер окна сохранен: ({width}x{height})", "DEBUG")
        return True
    except Exception as e:
        log(f"Ошибка сохранения размера окна: {e}", "ERROR")
        return False


def get_window_maximized():
    """Получает сохранённое состояние развёрнутого окна из settings.json."""
    try:
        geometry = settings_store.get_window_geometry()
        return bool(geometry.get("maximized"))
    except Exception as e:
        log(f"Ошибка чтения состояния maximized: {e}", "DEBUG")
        return None


def set_window_maximized(maximized: bool):
    """Сохраняет состояние развёрнутого окна в settings.json."""
    try:
        geometry = settings_store.get_window_geometry()
        settings_store.set_window_geometry(
            x=geometry.get("x"),
            y=geometry.get("y"),
            width=geometry.get("width"),
            height=geometry.get("height"),
            maximized=bool(maximized),
        )
        log(f"Состояние maximized сохранено: {bool(maximized)}", "DEBUG")
        return True
    except Exception as e:
        log(f"Ошибка сохранения состояния maximized: {e}", "ERROR")
        return False
