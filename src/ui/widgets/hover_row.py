from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QPainter

from ui.theme import get_theme_tokens, to_qcolor


@dataclass(frozen=True)
class HoverRowPaintResult:
    rect: QRect
    background: QColor


def profile_hover_row_rect(source_rect: QRect) -> QRect:
    """Единая геометрия hover-строки в списках profile/preset/стратегий."""

    return source_rect.adjusted(8, 2, -8, -2)


def paint_profile_hover_row(
    painter: QPainter,
    rect: QRect,
    *,
    active: bool = False,
    hovered: bool = False,
    pressed: bool = False,
    selected: bool = False,
    fill_idle: bool = True,
) -> HoverRowPaintResult:
    """
    Рисует общий фон строки списка.

    Используется там, где строка рисуется через delegate: «Мои пресеты» и
    список готовых стратегий. Так hover, активная подложка и акцентная полоска
    остаются одинаковыми.
    """

    tokens = get_theme_tokens()
    if active:
        background = to_qcolor(
            tokens.accent_soft_bg_hover if (hovered or pressed or selected) else tokens.accent_soft_bg,
            tokens.accent_hex,
        )
    elif hovered or pressed or selected:
        background = to_qcolor(tokens.surface_bg_hover, tokens.surface_bg)
    elif fill_idle:
        background = to_qcolor(tokens.surface_bg, "#1f1f1f")
    else:
        background = QColor(0, 0, 0, 0)

    if active or hovered or pressed or selected or fill_idle:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 10, 10)

    if active:
        marker_rect = QRect(rect.left() + 6, rect.top() + 6, 4, max(12, rect.height() - 12))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(to_qcolor(tokens.accent_hex, "#5caee8"))
        painter.drawRoundedRect(marker_rect, 2, 2)

    return HoverRowPaintResult(rect=rect, background=background)


__all__ = [
    "HoverRowPaintResult",
    "paint_profile_hover_row",
    "profile_hover_row_rect",
]
