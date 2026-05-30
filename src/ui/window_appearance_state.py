from __future__ import annotations

from log.log import log

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
    """Заново применяет фон окна после изменения Mica."""
    _ = enabled
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


def ensure_holiday_effects_manager(window):
    effects = window.visual_state.holiday_effects
    if effects is not None:
        return effects

    try:
        from ui.holiday_effects import HolidayEffectsManager

        effects = HolidayEffectsManager(window)
        window.visual_state.holiday_effects = effects
        return effects
    except Exception as e:
        log(f"❌ Ошибка создания праздничных эффектов: {e}", "DEBUG")
        return None


def apply_garland_enabled(window, enabled: bool) -> None:
    """Применяет готовое состояние гирлянды к окну."""
    effects = ensure_holiday_effects_manager(window)
    if effects is not None:
        effects.set_garland_enabled(bool(enabled))


def apply_snowflakes_enabled(window, enabled: bool) -> None:
    """Применяет готовое состояние снежинок к окну."""
    effects = ensure_holiday_effects_manager(window)
    if effects is not None:
        effects.set_snowflakes_enabled(bool(enabled))


def apply_window_opacity_value(window, value: int) -> None:
    """Применяет готовое значение прозрачности к окну."""
    from settings.appearance import peek_warmed_background_preset, peek_warmed_mica_enabled

    if (peek_warmed_background_preset() or "standard") != "standard":
        log("Transparent effect проигнорирован (не standard пресет)", "DEBUG")
        return

    from ui.theme import apply_aero_effect, apply_window_background

    mica_enabled = peek_warmed_mica_enabled()
    if mica_enabled is None or bool(mica_enabled):
        apply_aero_effect(window, value)
    else:
        apply_window_background(window)
    log(f"Прозрачность обновлена: {value}%", "DEBUG")
