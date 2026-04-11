"""Target-enabled UI helper'ы для страницы деталей стратегии Z2."""

from __future__ import annotations

from PyQt6.QtWidgets import QGraphicsOpacityEffect


def set_target_block_dimmed(widget, *, dimmed: bool) -> None:
    if widget is None:
        return

    try:
        widget.setProperty("targetDisabled", bool(dimmed))
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()
    except Exception:
        pass

    try:
        if dimmed:
            effect = widget.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)
            effect.setOpacity(0.56)
        else:
            widget.setGraphicsEffect(None)
    except Exception:
        pass


def set_target_enabled_ui(
    *,
    enabled: bool,
    toolbar_frame,
    strategies_block,
    layout,
    set_block_dimmed_fn,
    refresh_scroll_range_fn,
) -> None:
    is_enabled = bool(enabled)
    try:
        if toolbar_frame is not None:
            toolbar_frame.setVisible(True)
            set_block_dimmed_fn(toolbar_frame, dimmed=not is_enabled)
    except Exception:
        pass
    try:
        if strategies_block is not None:
            strategies_block.setVisible(True)
            set_block_dimmed_fn(strategies_block, dimmed=not is_enabled)
            if layout is not None:
                layout.setStretchFactor(strategies_block, 1)
            strategies_block.setMaximumHeight(16777215)
    except Exception:
        pass
    try:
        refresh_scroll_range_fn()
    except Exception:
        pass
