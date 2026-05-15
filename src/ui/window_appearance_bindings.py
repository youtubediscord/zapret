from __future__ import annotations

from ui.window_appearance_state import (
    on_animations_changed,
    on_editor_smooth_scroll_changed,
    on_smooth_scroll_changed,
)


def initialize_window_appearance_bindings(window) -> None:
    """Применяет сохранённые настройки внешнего вида к окну при старте."""
    from settings.appearance import (
        load_animations_enabled,
        load_editor_smooth_scroll_enabled,
        load_smooth_scroll_enabled,
    )

    on_animations_changed(window, load_animations_enabled().enabled)
    on_smooth_scroll_changed(window, load_smooth_scroll_enabled().enabled)
    on_editor_smooth_scroll_changed(window, load_editor_smooth_scroll_enabled().enabled)


__all__ = ["initialize_window_appearance_bindings"]
