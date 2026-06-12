from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QModelIndex, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QListView, QStyledItemDelegate, QStyle, QStyleOptionViewItem

from profile.ui.profile_icon import profile_icon_pixmap
from ui.theme import get_theme_tokens, to_qcolor
from ui.widgets.fluent_item_tooltip import FluentItemToolTipController
from ui.widgets.folder_header import FOLDER_HEADER_HEIGHT, is_folder_toggle_click, paint_folder_header_row
from ui.widgets.hover_row import paint_profile_hover_row, profile_hover_row_rect
from ui.widgets.profile_row_style import (
    PROFILE_BADGE_HOSTLIST_BG,
    PROFILE_BADGE_HOSTLIST_FG,
    PROFILE_BADGE_IPSET_BG,
    PROFILE_BADGE_IPSET_FG,
)

from .profile_list_model import ProfileListModel
from .profile_list_view import PROFILE_DROP_MARKER_PROPERTY


class ProfileListDelegate(QStyledItemDelegate):
    action_triggered = pyqtSignal(str, str)

    _ROW_HEIGHT = 44
    _EMPTY_HEIGHT = 64
    _ICON_SIZE = 18
    _BADGE_HEIGHT = 18
    _BADGE_H_PADDING = 8
    _MIN_NAME_WIDTH = 64
    _MIN_STRATEGY_WIDTH = 72

    def __init__(self, view: QListView):
        super().__init__(view)
        self._view = view
        self._hover_row = -1
        self._pressed_row = -1
        self._selected_rows: set[int] = set()
        self._tooltip = FluentItemToolTipController(view.viewport())

    def setHoverRow(self, row: int) -> None:
        self._hover_row = int(row)

    def setPressedRow(self, row: int) -> None:
        self._pressed_row = int(row)

    def setSelectedRows(self, indexes) -> None:
        rows: set[int] = set()
        try:
            for index in indexes or []:
                row = getattr(index, "row", None)
                row_value = row() if callable(row) else row
                if row_value is None:
                    continue
                rows.add(int(row_value))
        except Exception:
            rows = set()

        self._selected_rows = rows
        if self._pressed_row in self._selected_rows:
            self._pressed_row = -1

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        kind = str(index.data(ProfileListModel.KindRole) or "")
        if kind == "folder":
            return QSize(0, FOLDER_HEADER_HEIGHT)
        if kind == "empty":
            return QSize(0, self._EMPTY_HEIGHT)
        return QSize(0, self._ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        kind = str(index.data(ProfileListModel.KindRole) or "")
        if kind == "folder":
            self._paint_folder_row(painter, option, index)
            self._paint_drop_marker(painter, option, index)
            return
        if kind == "empty":
            self._paint_empty_row(painter, option, str(index.data(ProfileListModel.DisplayNameRole) or ""))
            return
        self._paint_profile_row(painter, option, index)
        self._paint_drop_marker(painter, option, index)

    def editorEvent(self, event, model, option: QStyleOptionViewItem, index: QModelIndex):
        _ = model
        _ = option
        kind = str(index.data(ProfileListModel.KindRole) or "")
        if kind != "folder":
            return False
        if not is_folder_toggle_click(event):
            return False
        group_key = str(index.data(ProfileListModel.GroupRole) or "")
        if not group_key:
            return False
        self.action_triggered.emit("toggle_folder", group_key)
        return True

    def helpEvent(self, event, view, option, index):  # noqa: N802
        if not index.isValid() or not isinstance(event, QEvent):
            return super().helpEvent(event, view, option, index)
        text = str(index.data(ProfileListModel.TooltipRole) or "").strip()
        if not text:
            self._tooltip.hide()
            return False
        pos = event.globalPos() if hasattr(event, "globalPos") else None
        if pos is None and isinstance(event, QMouseEvent):
            pos = event.globalPosition().toPoint()
        if pos is not None:
            self._tooltip.show_text(text.replace("\n", "<br>"), pos)
            return True
        return super().helpEvent(event, view, option, index)

    def _paint_folder_row(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        paint_folder_header_row(
            painter,
            option,
            title=str(index.data(ProfileListModel.GroupNameRole) or ""),
            expanded=not bool(index.data(ProfileListModel.CollapsedRole)),
            count=int(index.data(ProfileListModel.CountRole) or 0),
        )

    def _paint_drop_marker(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        marker = self._view.property(PROFILE_DROP_MARKER_PROPERTY)
        if not isinstance(marker, dict):
            return
        try:
            marker_row = int(marker.get("row", -1))
        except Exception:
            marker_row = -1
        if marker_row != index.row():
            return

        tokens = get_theme_tokens()
        accent = to_qcolor(tokens.accent_hex, "#5caee8")
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if marker.get("mode") == "folder":
            fill = to_qcolor(tokens.accent_soft_bg_hover, tokens.accent_hex)
            fill.setAlpha(70)
            rect = option.rect.adjusted(4, 2, -8, -2)
            painter.setBrush(fill)
            painter.setPen(QPen(accent, 2))
            painter.drawRoundedRect(rect, 6, 6)
        elif marker.get("mode") == "before":
            line_rect = profile_hover_row_rect(option.rect).adjusted(12, 0, -12, 0)
            pen = QPen(accent, 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            y = line_rect.top() + 2
            painter.drawLine(line_rect.left(), y, line_rect.right(), y)
        elif marker.get("mode") == "after":
            line_rect = profile_hover_row_rect(option.rect).adjusted(12, 0, -12, 0)
            pen = QPen(accent, 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            y = line_rect.bottom() - 2
            painter.drawLine(line_rect.left(), y, line_rect.right(), y)

        painter.restore()

    def _paint_empty_row(self, painter: QPainter, option: QStyleOptionViewItem, text: str) -> None:
        painter.save()
        tokens = get_theme_tokens()
        painter.setPen(to_qcolor(tokens.fg_muted, "#9aa2af"))
        painter.drawText(option.rect, int(Qt.AlignmentFlag.AlignCenter), text)
        painter.restore()

    def _paint_profile_row(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        tokens = get_theme_tokens()
        rect = profile_hover_row_rect(option.rect)
        hovered = _profile_row_is_interactive(
            index.row(),
            hovered=bool(option.state & QStyle.StateFlag.State_MouseOver),
            selected=bool(option.state & QStyle.StateFlag.State_Selected),
            hover_row=self._hover_row,
            pressed_row=self._pressed_row,
            selected_rows=self._selected_rows,
        )
        active = str(index.data(ProfileListModel.StrategyIdRole) or "") not in {"", "none"}
        accent_active = _profile_row_uses_accent(active)
        paint_profile_hover_row(
            painter,
            rect,
            active=accent_active,
            hovered=hovered,
            show_active_marker=False,
        )

        strategy_name = str(index.data(ProfileListModel.StrategyNameRole) or "")
        rating = str(index.data(ProfileListModel.RatingRole) or "").strip().lower()
        favorite = bool(index.data(ProfileListModel.FavoriteRole))
        feedback_text = _feedback_text(rating, favorite)
        list_type = str(index.data(ProfileListModel.ListTypeRole) or "")
        badge_text = "Hostlist" if list_type == "hostlist" else ("IPset" if list_type == "ipset" else "")

        meta_font = painter.font()
        meta_font.setBold(False)
        meta_metrics = QFontMetrics(meta_font)
        strategy_text_width = meta_metrics.horizontalAdvance(strategy_name) + 8 if strategy_name else 0
        feedback_text_width = meta_metrics.horizontalAdvance(feedback_text) + 8 if feedback_text else 0
        badge_width = meta_metrics.horizontalAdvance(badge_text) + self._BADGE_H_PADDING * 2 if badge_text else 0
        name = str(index.data(ProfileListModel.DisplayNameRole) or "")
        description = str(index.data(ProfileListModel.DescriptionRole) or "")
        name_font = painter.font()
        name_font.setBold(False)
        name_metrics = QFontMetrics(name_font)
        left_text_width = name_metrics.horizontalAdvance(name)
        if description:
            left_text_width += 8 + meta_metrics.horizontalAdvance(description)
        row_layout = _profile_row_layout(
            rect,
            strategy_text_width=strategy_text_width,
            feedback_text_width=feedback_text_width,
            badge_width=badge_width,
            left_text_width=left_text_width,
        )

        icon_color = str(index.data(ProfileListModel.IconColorRole) or "#888888")
        if not bool(index.data(ProfileListModel.InPresetRole)):
            icon_color = "#888888"
        pixmap = profile_icon_pixmap(
            str(index.data(ProfileListModel.IconNameRole) or ""),
            color=icon_color,
            size=self._ICON_SIZE,
            theme_name=tokens.theme_name,
        )
        if not pixmap.isNull():
            painter.drawPixmap(row_layout.icon_rect, pixmap)

        painter.setFont(name_font)
        painter.setPen(to_qcolor(tokens.fg, "#f5f5f5"))
        elided_name = name_metrics.elidedText(name, Qt.TextElideMode.ElideRight, row_layout.name_rect.width())
        painter.drawText(row_layout.name_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), elided_name)

        if description and name_metrics.horizontalAdvance(elided_name) + 10 < row_layout.name_rect.width():
            desc_left = min(row_layout.name_rect.right(), row_layout.name_rect.left() + name_metrics.horizontalAdvance(elided_name) + 8)
            desc_rect = QRect(desc_left, rect.center().y() - 8, max(0, row_layout.name_rect.right() - desc_left), 16)
            painter.setFont(meta_font)
            painter.setPen(to_qcolor(tokens.fg_muted, "#b7bec8"))
            painter.drawText(
                desc_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                meta_metrics.elidedText(description, Qt.TextElideMode.ElideRight, desc_rect.width()),
            )

        if row_layout.badge_rect.isValid() and badge_text:
            badge_bg, badge_fg = _badge_palette(list_type)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(to_qcolor(badge_bg, badge_bg))
            painter.drawRoundedRect(row_layout.badge_rect, 9, 9)
            painter.setPen(to_qcolor(badge_fg, "#111111"))
            painter.drawText(row_layout.badge_rect, int(Qt.AlignmentFlag.AlignCenter), badge_text)

        dot_color = _status_dot_color(
            active,
            active_color=tokens.accent_hex,
            fallback=str(tokens.fg_faint),
            tinted_background=accent_active,
        )
        painter.setFont(meta_font)
        painter.setPen(to_qcolor(dot_color, "#888888"))
        painter.drawText(row_layout.dot_rect, int(Qt.AlignmentFlag.AlignCenter), "●")

        strategy_color = tokens.fg if active else tokens.fg_muted
        if row_layout.strategy_rect.isValid():
            painter.setPen(to_qcolor(strategy_color, "#b7bec8"))
            painter.drawText(
                row_layout.strategy_rect,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                meta_metrics.elidedText(strategy_name, Qt.TextElideMode.ElideRight, row_layout.strategy_rect.width()),
            )

        if feedback_text and row_layout.feedback_rect.isValid():
            painter.setPen(to_qcolor(_feedback_color(tokens, rating, favorite), "#b7bec8"))
            painter.drawText(
                row_layout.feedback_rect,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                meta_metrics.elidedText(feedback_text, Qt.TextElideMode.ElideRight, row_layout.feedback_rect.width()),
            )

        painter.restore()


@dataclass(frozen=True)
class ProfileRowLayout:
    icon_rect: QRect
    name_rect: QRect
    badge_rect: QRect
    dot_rect: QRect
    strategy_rect: QRect
    feedback_rect: QRect


def _profile_row_layout(
    rect: QRect,
    *,
    strategy_text_width: int,
    feedback_text_width: int,
    badge_width: int,
    left_text_width: int = 0,
) -> ProfileRowLayout:
    icon_size = ProfileListDelegate._ICON_SIZE
    min_name_width = ProfileListDelegate._MIN_NAME_WIDTH
    min_strategy_width = ProfileListDelegate._MIN_STRATEGY_WIDTH
    right_padding = 12
    gap = 4
    dot_width = 10
    row_center_y = rect.center().y()

    icon_rect = QRect(rect.left() + 12, row_center_y - 9, icon_size, icon_size)
    text_left = icon_rect.right() + 10
    right_edge = rect.right() - right_padding
    available_after_name = max(0, right_edge - (text_left + min_name_width))

    requested_strategy_width = max(0, int(strategy_text_width or 0))
    max_strategy_width = max(min_strategy_width, rect.width() // 3)
    strategy_width = min(requested_strategy_width, max_strategy_width)
    required_strategy_width = min(strategy_width, min_strategy_width)
    if strategy_width <= 0 or available_after_name < dot_width + gap + required_strategy_width:
        strategy_width = 0

    feedback_width = max(0, int(feedback_text_width or 0))
    if feedback_width:
        right_block_with_feedback = dot_width + gap + strategy_width + gap + feedback_width
        if strategy_width <= 0 or right_block_with_feedback > available_after_name:
            feedback_width = 0

    right_block_width = dot_width
    if strategy_width:
        right_block_width += gap + strategy_width
    if feedback_width:
        right_block_width += gap + feedback_width

    right_block_left = max(text_left, right_edge - right_block_width)
    dot_rect = QRect(right_block_left, row_center_y - 8, dot_width, 16)
    strategy_rect = QRect()
    feedback_rect = QRect()
    cursor_left = dot_rect.right() + gap
    if strategy_width:
        strategy_rect = QRect(cursor_left, row_center_y - 9, strategy_width, 18)
        cursor_left = strategy_rect.right() + gap
    if feedback_width:
        feedback_rect = QRect(cursor_left, row_center_y - 9, feedback_width, 18)

    left_right = max(text_left, right_block_left - 10)
    left_area_width = max(0, left_right - text_left)
    badge_rect = QRect()
    normalized_badge_width = max(0, int(badge_width or 0))
    badge_gap = 8
    can_show_badge = normalized_badge_width > 0 and left_area_width >= (min_name_width + badge_gap + normalized_badge_width)
    name_width = left_area_width
    if can_show_badge:
        requested_text_width = int(left_text_width or (left_area_width - badge_gap - normalized_badge_width))
        requested_text_width = max(min_name_width, requested_text_width)
        name_width = min(requested_text_width, left_area_width - badge_gap - normalized_badge_width)
        badge_rect = QRect(
            text_left + name_width + badge_gap,
            row_center_y - (ProfileListDelegate._BADGE_HEIGHT // 2),
            normalized_badge_width,
            ProfileListDelegate._BADGE_HEIGHT,
        )

    name_rect = QRect(text_left, row_center_y - 10, max(0, name_width), 20)
    return ProfileRowLayout(
        icon_rect=icon_rect,
        name_rect=name_rect,
        badge_rect=badge_rect,
        dot_rect=dot_rect,
        strategy_rect=strategy_rect,
        feedback_rect=feedback_rect,
    )


def _feedback_text(rating: str, favorite: bool) -> str:
    parts: list[str] = []
    if rating == "work":
        parts.append("стратегия работает")
    elif rating == "notwork":
        parts.append("стратегия не работает")
    if favorite:
        parts.append("стратегия в избранном")
    return " • ".join(parts)


def _badge_palette(list_type: str) -> tuple[str, str]:
    if list_type == "hostlist":
        return PROFILE_BADGE_HOSTLIST_BG, PROFILE_BADGE_HOSTLIST_FG
    if list_type == "ipset":
        return PROFILE_BADGE_IPSET_BG, PROFILE_BADGE_IPSET_FG
    return "#7d8792", "#111114"


def _tinted_background_enabled() -> bool:
    try:
        from settings.appearance import peek_warmed_tinted_settings

        plan = peek_warmed_tinted_settings()
        return bool(getattr(plan, "tinted_background", False))
    except Exception:
        return False


def _profile_row_uses_accent(active: bool, *, tinted_background: bool | None = None) -> bool:
    if not bool(active):
        return False
    if tinted_background is None:
        tinted_background = _tinted_background_enabled()
    return bool(tinted_background)


def _status_dot_color(
    active: bool,
    *,
    active_color: str = "#5caee8",
    fallback: str = "#8f9aa6",
    tinted_background: bool | None = None,
) -> str:
    if _profile_row_uses_accent(active, tinted_background=tinted_background):
        return str(active_color or "#5caee8")
    return str(fallback or "#8f9aa6")


def _profile_row_is_interactive(
    row: int,
    *,
    hovered: bool,
    selected: bool,
    hover_row: int,
    pressed_row: int,
    selected_rows: set[int],
) -> bool:
    row = int(row)
    return (
        bool(hovered)
        or bool(selected)
        or int(hover_row) == row
        or int(pressed_row) == row
        or row in set(selected_rows or set())
    )


def _feedback_color(tokens, rating: str, favorite: bool) -> str:
    if rating == "work":
        return "#49a35f"
    if rating == "notwork":
        return "#d85c5c"
    if favorite:
        return "#d9a441"
    return str(tokens.fg_muted)


__all__ = ["ProfileListDelegate"]
