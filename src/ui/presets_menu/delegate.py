from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEvent, QModelIndex, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QHelpEvent, QMouseEvent, QPainter, QTransform
from PyQt6.QtWidgets import QListView, QStyledItemDelegate, QStyle, QStyleOptionViewItem, QToolTip

from ui.theme import get_theme_tokens
from ui.widgets.hover_row import paint_profile_hover_row, profile_hover_row_rect

from .common import (
    cached_icon,
    normalize_preset_icon_color,
    pick_contrast_color,
    to_qcolor,
    tr_text,
)
from .model import PresetListModel


class PresetListDelegate(QStyledItemDelegate):
    action_triggered = pyqtSignal(str, str)

    _ROW_HEIGHT = 44
    _SECTION_HEIGHT = 24
    _EMPTY_HEIGHT = 64
    _ACTION_SIZE = 28
    _ACTION_SPACING = 6
    _BADGE_HEIGHT = 18
    _BADGE_H_PADDING = 8
    _BADGE_GAP = 8
    _PIN_SIZE = 14
    _PIN_COLUMN_WIDTH = 18
    _PIN_TO_ICON_SPACING = 8

    _ACTION_ICONS = {
        "folder": "fa5s.folder-open",
        "rating": "fa5s.star-half-alt",
        "edit": "fa5s.ellipsis-v",
    }

    _PENDING_SHAKE_ROTATIONS = (0, -8, 8, -6, 6, -4, 4, -2, 0)
    _PENDING_SHAKE_INTERVAL_MS = 50

    def __init__(self, view: QListView, *, language_scope: str = "winws2", help_name_role: str = "name"):
        super().__init__(view)
        self._view = view
        self._language_scope = str(language_scope or "winws2")
        self._help_name_role = str(help_name_role or "name")
        self._ui_language = "ru"
        self._action_tooltips: dict[str, str] = {}
        self._hover_row = -1
        self._pressed_row = -1
        self._selected_rows: set[int] = set()
        self._pending_destructive: Optional[tuple[str, str]] = None
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.timeout.connect(self._clear_pending_destructive)
        self._pending_shake_step = 0
        self._pending_shake_rotation = 0
        self._pending_shake_timer = QTimer(self)
        self._pending_shake_timer.timeout.connect(self._advance_pending_shake)
        self.set_ui_language("ru")

    def _tr(self, key: str, default: str, **kwargs) -> str:
        return tr_text(key, self._ui_language, default, **kwargs)

    def set_ui_language(self, language: str) -> None:
        self._ui_language = language
        prefix = f"page.{self._language_scope}_user_presets.delegate.tooltip"
        self._action_tooltips = {
            "rating": self._tr(f"{prefix}.rating", "Поставить рейтинг"),
            "edit": self._tr(f"{prefix}.edit", "Меню пресета"),
            "pin": self._tr(f"{prefix}.pin", "Закрепить сверху"),
        }

    def reset_interaction_state(self):
        self._clear_pending_destructive(update=False)
        self.setHoverRow(-1)
        self.setPressedRow(-1)
        self.setSelectedRows([])

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

    def _icon_rect_for_row(self, row_rect: QRect, depth: int) -> QRect:
        pin_rect = self._pin_rect(row_rect, "preset", depth)
        if pin_rect is not None:
            icon_left = pin_rect.left() + self._PIN_COLUMN_WIDTH + self._PIN_TO_ICON_SPACING
        else:
            icon_left = row_rect.left() + 12 + depth * 18
        return QRect(icon_left, row_rect.center().y() - 10, 20, 20)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        kind = index.data(PresetListModel.KindRole)
        if kind == "section":
            return QSize(0, self._SECTION_HEIGHT)
        if kind == "empty":
            return QSize(0, self._EMPTY_HEIGHT)
        return QSize(0, self._ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        kind = index.data(PresetListModel.KindRole)

        if kind == "section":
            self._paint_section_row(painter, option, str(index.data(PresetListModel.TextRole) or ""))
            return

        if kind == "empty":
            self._paint_empty_row(painter, option, str(index.data(PresetListModel.TextRole) or ""))
            return

        self._paint_preset_row(painter, option, index)

    def editorEvent(self, event, model, option: QStyleOptionViewItem, index: QModelIndex):
        _ = model
        kind = str(index.data(PresetListModel.KindRole) or "")
        if kind != "preset":
            return False
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        if not isinstance(event, QMouseEvent):
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        item_id = str(index.data(PresetListModel.FileNameRole) or "")
        if not item_id:
            return False

        self._view.setCurrentIndex(index)
        is_active = bool(index.data(PresetListModel.ActiveRole))
        is_builtin = bool(index.data(PresetListModel.BuiltinRole))
        depth = int(index.data(PresetListModel.DepthRole) or 0)
        action = self._action_at(option.rect, kind, is_active, is_builtin, depth, event.position().toPoint())

        if action:
            self._handle_action_click(item_id, action, event)
            return True

        self._clear_pending_destructive(update=False)
        self.action_triggered.emit("activate", item_id)
        return True

    def helpEvent(self, event: QHelpEvent, view, option: QStyleOptionViewItem, index: QModelIndex) -> bool:
        kind = str(index.data(PresetListModel.KindRole) or "")
        if kind != "preset":
            return super().helpEvent(event, view, option, index)

        if self._help_name_role == "file_name":
            name = str(index.data(PresetListModel.FileNameRole) or "")
        else:
            name = str(index.data(PresetListModel.NameRole) or "")
        is_active = bool(index.data(PresetListModel.ActiveRole))
        is_builtin = bool(index.data(PresetListModel.BuiltinRole))
        depth = int(index.data(PresetListModel.DepthRole) or 0)
        action = self._action_at(option.rect, kind, is_active, is_builtin, depth, event.pos())
        if not action:
            return super().helpEvent(event, view, option, index)

        tooltip = self._action_tooltips.get(action, "")
        if tooltip:
            QToolTip.showText(event.globalPos(), tooltip, view)
            return True
        return super().helpEvent(event, view, option, index)

    def _handle_action_click(self, name: str, action: str, _event: QMouseEvent):
        self._clear_pending_destructive(update=False)
        self.action_triggered.emit(action, name)
        self._view.viewport().update()

    def _clear_pending_destructive(self, update: bool = True):
        self._pending_timer.stop()
        self._pending_shake_timer.stop()
        self._pending_shake_step = 0
        self._pending_shake_rotation = 0
        if self._pending_destructive is None:
            return
        self._pending_destructive = None
        if update:
            self._view.viewport().update()

    def _advance_pending_shake(self):
        self._pending_shake_step += 1
        if self._pending_shake_step >= len(self._PENDING_SHAKE_ROTATIONS):
            self._pending_shake_timer.stop()
            self._pending_shake_step = 0
            self._pending_shake_rotation = 0
            self._view.viewport().update()
            return

        self._pending_shake_rotation = int(self._PENDING_SHAKE_ROTATIONS[self._pending_shake_step])
        self._view.viewport().update()

    def _visible_actions(self, kind: str, is_active: bool, is_builtin: bool) -> list[str]:
        _ = (kind, is_active, is_builtin)
        return ["rating", "edit"]

    def _action_rects(self, row_rect: QRect, kind: str, is_active: bool, is_builtin: bool) -> list[tuple[str, QRect]]:
        actions = self._visible_actions(kind, is_active, is_builtin)
        if not actions:
            return []

        total_width = len(actions) * self._ACTION_SIZE + (len(actions) - 1) * self._ACTION_SPACING
        x = row_rect.right() - 12 - total_width + 1
        y = row_rect.center().y() - (self._ACTION_SIZE // 2)

        rects: list[tuple[str, QRect]] = []
        for action in actions:
            rects.append((action, QRect(x, y, self._ACTION_SIZE, self._ACTION_SIZE)))
            x += self._ACTION_SIZE + self._ACTION_SPACING
        return rects

    def _action_at(self, option_rect: QRect, kind: str, is_active: bool, is_builtin: bool, depth: int, pos) -> Optional[str]:
        pin_rect = self._pin_rect(option_rect, kind, depth)
        if pin_rect is not None and pin_rect.contains(pos):
            return "pin"

        for action, rect in self._action_rects(option_rect, kind, is_active, is_builtin):
            if rect.contains(pos):
                return action
        return None

    def _paint_action_icon(self, painter: QPainter, icon_name: str, icon_color: str, icon_rect: QRect, rotation: int = 0):
        icon = cached_icon(icon_name, icon_color)
        if not rotation:
            icon.paint(painter, icon_rect)
            return

        painter.save()
        center = icon_rect.center()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(rotation)
        transform.translate(-center.x(), -center.y())
        painter.setTransform(transform, combine=True)
        icon.paint(painter, icon_rect)
        painter.restore()

    def _pin_rect(self, row_rect: QRect, kind: str, depth: int) -> QRect | None:
        if kind != "preset":
            return None
        x = row_rect.left() + 12 + depth * 18
        return QRect(x, row_rect.center().y() - (self._PIN_SIZE // 2), self._PIN_SIZE, self._PIN_SIZE)

    def _paint_section_row(self, painter: QPainter, option: QStyleOptionViewItem, text: str) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = option.rect.adjusted(12, 0, -12, 0)
        tokens = get_theme_tokens()

        painter.setPen(to_qcolor(tokens.fg_muted, "#9aa2af"))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)

        line_y = rect.center().y()
        text_width = painter.fontMetrics().horizontalAdvance(text)
        left_end = rect.left() + text_width + 12
        if left_end < rect.right():
            painter.setPen(to_qcolor(tokens.divider, "#5f6368"))
            painter.drawLine(left_end, line_y, rect.right(), line_y)

        painter.restore()

    def _paint_empty_row(self, painter: QPainter, option: QStyleOptionViewItem, text: str) -> None:
        painter.save()
        tokens = get_theme_tokens()
        painter.setPen(to_qcolor(tokens.fg_muted, "#9aa2af"))
        painter.drawText(option.rect, int(Qt.AlignmentFlag.AlignCenter), text)
        painter.restore()

    def _paint_preset_row(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        tokens = get_theme_tokens()
        rect = profile_hover_row_rect(option.rect)

        name = str(index.data(PresetListModel.NameRole) or "")
        date_text = str(index.data(PresetListModel.DateRole) or "")
        is_active = bool(index.data(PresetListModel.ActiveRole))
        is_builtin = bool(index.data(PresetListModel.BuiltinRole))
        depth = int(index.data(PresetListModel.DepthRole) or 0)
        is_pinned = bool(index.data(PresetListModel.PinnedRole))
        rating = int(index.data(PresetListModel.RatingRole) or 0)

        hovered = option.state & QStyle.StateFlag.State_MouseOver
        pressed = self._pressed_row == index.row()

        row_paint = paint_profile_hover_row(
            painter,
            rect,
            active=is_active,
            hovered=bool(hovered),
            pressed=pressed,
        )
        bg = row_paint.background

        icon_rect = self._icon_rect_for_row(rect, depth)
        icon_color = pick_contrast_color(
            normalize_preset_icon_color(str(index.data(PresetListModel.IconColorRole) or "")),
            bg,
            [tokens.accent_hex, tokens.fg],
            minimum_ratio=2.6,
        )
        cached_icon("fa5s.file-alt", icon_color).paint(painter, icon_rect)

        text_left = icon_rect.right() + 10
        actions = self._action_rects(rect, "preset", is_active, is_builtin)
        right_bound = rect.right() - 12
        if actions:
            right_bound = actions[0][1].left() - 10

        pin_rect = self._pin_rect(rect, "preset", depth)
        if pin_rect is not None and pin_rect.left() < icon_rect.left():
            text_left = icon_rect.right() + 10

        meta_font = painter.font()
        meta_font.setBold(False)
        painter.setFont(meta_font)
        meta_metrics = QFontMetrics(meta_font)

        badge_text = self._tr("page.user_presets.delegate.active_badge", "Активный") if is_active else ""
        badge_rect = QRect()
        top_right_cursor = right_bound
        if badge_text:
            badge_text_width = meta_metrics.horizontalAdvance(badge_text)
            badge_width = badge_text_width + self._BADGE_H_PADDING * 2
            badge_width = min(max(badge_width, 68), max(0, right_bound - text_left))
            if badge_width > 0:
                badge_rect = QRect(
                    max(text_left, top_right_cursor - badge_width),
                    rect.center().y() - (self._BADGE_HEIGHT // 2),
                    badge_width,
                    self._BADGE_HEIGHT,
                )
                top_right_cursor = max(text_left, badge_rect.left() - self._BADGE_GAP)

        date_rect = QRect()
        name_right_bound = right_bound
        if date_text:
            date_available_width = max(0, top_right_cursor - text_left)
            if date_available_width > 48:
                desired_date_width = meta_metrics.horizontalAdvance(date_text)
                date_width = min(desired_date_width, max(72, date_available_width // 3))
                date_rect = QRect(
                    max(text_left, top_right_cursor - date_width),
                    rect.center().y() - 9,
                    min(date_width, date_available_width),
                    18,
                )
                if date_rect.width() > 0:
                    name_right_bound = max(text_left, date_rect.left() - 12)
                else:
                    date_rect = QRect()

        name_rect = QRect(text_left, rect.top() + 8, max(0, name_right_bound - text_left), 18)
        meta_rect = QRect(text_left, rect.bottom() - 22, max(0, right_bound - text_left), 16)

        name_font = painter.font()
        name_font.setBold(is_active)
        painter.setFont(name_font)
        painter.setPen(to_qcolor(tokens.fg, "#f5f5f5"))
        name_metrics = QFontMetrics(name_font)
        elided_name = name_metrics.elidedText(name, Qt.TextElideMode.ElideRight, name_rect.width())
        painter.drawText(name_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), elided_name)

        painter.setFont(meta_font)
        if date_rect.width() > 0:
            painter.setPen(to_qcolor(tokens.fg_faint, "#aeb5c1"))
            elided_date = meta_metrics.elidedText(date_text, Qt.TextElideMode.ElideLeft, date_rect.width())
            painter.drawText(date_rect, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), elided_date)
        if badge_rect.width() > 0 and badge_text:
            badge_bg = to_qcolor(tokens.accent_soft_bg_hover, tokens.accent_hex)
            badge_text_color = to_qcolor(tokens.accent_hex, "#5caee8")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(badge_bg)
            painter.drawRoundedRect(badge_rect, 9, 9)
            painter.setPen(badge_text_color)
            painter.drawText(
                badge_rect,
                int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
                meta_metrics.elidedText(badge_text, Qt.TextElideMode.ElideRight, max(0, badge_rect.width() - self._BADGE_H_PADDING * 2)),
            )

        meta_parts = []
        if rating:
            meta_parts.append(f"Рейтинг: {rating}")
        meta_text = " • ".join(meta_parts)
        if meta_text:
            painter.setPen(to_qcolor(tokens.fg_faint, "#aeb5c1"))
            painter.drawText(meta_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), meta_text)

        if pin_rect is not None:
            pin_color = tokens.accent_hex if is_pinned else tokens.fg_faint
            self._paint_action_icon(
                painter,
                "fa5s.thumbtack",
                pin_color,
                pin_rect.adjusted(2, 2, -2, -2),
            )

        for action, action_rect in actions:
            btn_bg = to_qcolor(tokens.surface_bg_hover, tokens.surface_bg)
            icon_color = pick_contrast_color(
                str(tokens.fg_muted),
                btn_bg,
                [tokens.fg],
                minimum_ratio=2.6,
            )

            painter.setBrush(btn_bg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(action_rect, 6, 6)

            icon_name = self._ACTION_ICONS.get(action, "fa5s.circle")
            rotation = (
                self._pending_shake_rotation
                if self._pending_destructive == (str(index.data(PresetListModel.FileNameRole) or ""), action)
                else 0
            )
            self._paint_action_icon(
                painter,
                icon_name,
                icon_color,
                action_rect.adjusted(7, 7, -7, -7),
                rotation=rotation,
            )

        painter.restore()


__all__ = ["PresetListDelegate"]
