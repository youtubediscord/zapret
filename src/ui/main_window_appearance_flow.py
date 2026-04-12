from __future__ import annotations

from ui.animation_policy import (
    apply_window_animation_policy,
    apply_window_editor_smooth_scroll_policy,
    apply_window_smooth_scroll_policy,
)


def on_background_refresh_needed(window) -> None:
    """Повторно применяет фон окна после изменения визуальных параметров."""
    try:
        from ui.theme import apply_window_background

        apply_window_background(window.window())
    except Exception:
        pass


def on_background_preset_changed(window, preset: str) -> None:
    """Применяет выбранный preset фона к окну."""
    try:
        from ui.theme import apply_window_background

        apply_window_background(window.window(), preset=preset)
    except Exception:
        pass


def on_opacity_changed(window, value: int) -> None:
    """Применяет прозрачность окна из настроек оформления."""
    win = window.window()
    if hasattr(win, "set_window_opacity"):
        win.set_window_opacity(value)


def on_mica_changed(window, enabled: bool) -> None:
    """Сохраняет настройку Mica и заново применяет фон окна."""
    try:
        from config.reg import set_mica_enabled

        set_mica_enabled(enabled)
    except Exception:
        pass

    on_background_refresh_needed(window)


def on_animations_changed(window, enabled: bool) -> None:
    """Включает или отключает оконные анимации."""
    apply_window_animation_policy(window, enabled)


def on_smooth_scroll_changed(window, enabled: bool) -> None:
    """Переключает плавную прокрутку списков и страниц."""
    apply_window_smooth_scroll_policy(window, enabled)


def on_editor_smooth_scroll_changed(window, enabled: bool) -> None:
    """Переключает плавную прокрутку только у текстовых редакторов."""
    apply_window_editor_smooth_scroll_policy(window, enabled)
