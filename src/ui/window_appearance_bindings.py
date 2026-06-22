from __future__ import annotations

from log.log import log

from ui.window_appearance_state import (
    on_animations_changed,
    on_editor_smooth_scroll_changed,
    on_smooth_scroll_changed,
)


def initialize_window_appearance_bindings(window) -> None:
    """Применяет сохранённые настройки внешнего вида к окну при старте."""
    from settings.appearance import (
        peek_warmed_animations_enabled,
        peek_warmed_editor_smooth_scroll_enabled,
        peek_warmed_smooth_scroll_enabled,
    )

    on_animations_changed(window, bool(peek_warmed_animations_enabled()))
    on_smooth_scroll_changed(window, bool(peek_warmed_smooth_scroll_enabled()))
    on_editor_smooth_scroll_changed(window, bool(peek_warmed_editor_smooth_scroll_enabled()))


def initialize_window_holiday_effects(window, *, effects_allowed: bool, appearance_actions) -> None:
    """Применяет сохранённые настройки праздничных эффектов к окну."""
    try:
        from settings.appearance import (
            peek_warmed_animations_enabled,
            peek_warmed_premium_effects,
            peek_warmed_window_opacity,
        )

        premium_effects = peek_warmed_premium_effects()
        if premium_effects is None:
            garland_saved = False
            snowflakes_saved = False
        else:
            garland_saved = premium_effects.garland_enabled
            snowflakes_saved = premium_effects.snowflakes_enabled
        log(f"🎄 Инициализация: гирлянда={garland_saved}, снежинки={snowflakes_saved}", "DEBUG")

        animations_enabled = bool(peek_warmed_animations_enabled())

        should_enable_garland = bool(effects_allowed) and animations_enabled and garland_saved
        appearance_actions.set_garland_enabled(should_enable_garland)

        should_enable_snowflakes = bool(effects_allowed) and animations_enabled and snowflakes_saved
        appearance_actions.set_snowflakes_enabled(should_enable_snowflakes)

        opacity_saved = peek_warmed_window_opacity()
        if opacity_saved is None:
            opacity_saved = 100
        log(f"🔮 Инициализация: opacity={opacity_saved}%", "DEBUG")
        appearance_actions.set_window_opacity(opacity_saved)

        if not animations_enabled:
            on_animations_changed(window, False)

    except Exception as e:
        log(f"❌ Ошибка загрузки состояния декораций: {e}", "ERROR")
        import traceback

        log(traceback.format_exc(), "DEBUG")


__all__ = [
    "initialize_window_appearance_bindings",
    "initialize_window_holiday_effects",
]
