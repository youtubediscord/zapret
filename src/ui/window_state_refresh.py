from __future__ import annotations

from ui.window_display_state import (
    get_direct_strategy_summary,
    update_current_strategy_display,
)


def on_direct_mode_changed(window, mode: str) -> None:
    """Сообщает UI-слою, что direct mode изменился и нужно обновить revision."""
    _ = mode
    try:
        if getattr(window, "ui_state_store", None) is not None:
            window.ui_state_store.bump_mode_revision()
    except Exception:
        pass


def refresh_pages_after_preset_switch(window) -> None:
    """Обновляет краткое отображение активной стратегии после смены source preset."""
    try:
        display_name = get_direct_strategy_summary(window)
        if display_name:
            update_current_strategy_display(window, display_name)
    except Exception as e:
        from log import log

        log(f"Ошибка обновления display стратегии после смены пресета: {e}", "DEBUG")
