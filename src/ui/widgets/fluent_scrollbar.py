from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractScrollArea
from qfluentwidgets import ScrollBar, ScrollBarHandleDisplayMode


@dataclass(frozen=True)
class FluentScrollBars:
    vertical: ScrollBar | None = None
    horizontal: ScrollBar | None = None


def install_fluent_scrollbars(
    widget: QAbstractScrollArea,
    *,
    vertical: bool = True,
    horizontal: bool = False,
    handle_mode: ScrollBarHandleDisplayMode = ScrollBarHandleDisplayMode.ALWAYS,
    reserve_vertical_space: bool = False,
    vertical_reserved_margin: int = 12,
) -> FluentScrollBars:
    """Ставит библиотечный scrollbar qfluentwidgets на обычный Qt-список."""

    current = getattr(widget, "_zapret_fluent_scrollbars", None)
    if isinstance(current, FluentScrollBars):
        if reserve_vertical_space and current.vertical is not None:
            _install_vertical_viewport_reserve(widget, int(vertical_reserved_margin))
        return current

    vertical_bar = None
    horizontal_bar = None
    if vertical:
        vertical_bar = ScrollBar(Qt.Orientation.Vertical, widget)
        vertical_bar.setHandleDisplayMode(handle_mode)
    if horizontal:
        horizontal_bar = ScrollBar(Qt.Orientation.Horizontal, widget)
        horizontal_bar.setHandleDisplayMode(handle_mode)

    bars = FluentScrollBars(vertical=vertical_bar, horizontal=horizontal_bar)
    setattr(widget, "_zapret_fluent_scrollbars", bars)
    if reserve_vertical_space and vertical_bar is not None:
        _install_vertical_viewport_reserve(widget, int(vertical_reserved_margin))
    return bars


def _install_vertical_viewport_reserve(widget: QAbstractScrollArea, margin: int) -> None:
    margin = max(0, int(margin or 0))
    if margin <= 0:
        return
    if getattr(widget, "_zapret_fluent_scrollbar_reserve_installed", False):
        setattr(widget, "_zapret_fluent_scrollbar_reserved_margin", margin)
        _sync_vertical_viewport_reserve(widget)
        return

    setattr(widget, "_zapret_fluent_scrollbar_base_margins", widget.viewportMargins())
    setattr(widget, "_zapret_fluent_scrollbar_reserved_margin", margin)
    setattr(widget, "_zapret_fluent_scrollbar_reserve_installed", True)

    native_bar = widget.verticalScrollBar()
    native_bar.rangeChanged.connect(lambda _minimum, _maximum: _sync_vertical_viewport_reserve(widget))
    native_bar.valueChanged.connect(lambda _value: _sync_vertical_viewport_reserve(widget))
    _sync_vertical_viewport_reserve(widget)


def _sync_vertical_viewport_reserve(widget: QAbstractScrollArea) -> None:
    base_margins = getattr(widget, "_zapret_fluent_scrollbar_base_margins", None)
    if base_margins is None:
        return

    native_bar = widget.verticalScrollBar()
    has_scroll_range = native_bar.maximum() > native_bar.minimum()
    margin = int(getattr(widget, "_zapret_fluent_scrollbar_reserved_margin", 0) or 0)
    right_margin = base_margins.right() + (margin if has_scroll_range else 0)
    current = widget.viewportMargins()
    if (
        current.left() == base_margins.left()
        and current.top() == base_margins.top()
        and current.right() == right_margin
        and current.bottom() == base_margins.bottom()
    ):
        return
    widget.setViewportMargins(
        base_margins.left(),
        base_margins.top(),
        right_margin,
        base_margins.bottom(),
    )


__all__ = ["FluentScrollBars", "install_fluent_scrollbars"]
