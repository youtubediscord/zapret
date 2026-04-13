# filters/ui/strategy_radio_item.py
"""
Карточка target для выбора стратегии.

Новая раскладка намеренно разделена на две смысловые зоны:
- слева идентичность target'а: иконка, название, описание, badge;
- справа статус и выбранная стратегия.

Это делает строку устойчивой к длинным названиям и не позволяет ей
распирать страницу по ширине.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QResizeEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui.compat_widgets import set_tooltip
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_refresh import ThemeRefreshController

try:
    from qfluentwidgets import CardWidget, BodyLabel, CaptionLabel, InfoBadge, InfoLevel
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QFrame as CardWidget  # type: ignore[assignment]
    from PyQt6.QtWidgets import QLabel as BodyLabel  # type: ignore[assignment]
    from PyQt6.QtWidgets import QLabel as CaptionLabel  # type: ignore[assignment]
    InfoBadge = None  # type: ignore[assignment]
    InfoLevel = None  # type: ignore[assignment]
    _HAS_FLUENT = False


class ElidedTextLabel(QLabel):
    """QLabel с аккуратным обрезанием текста многоточием по текущей ширине."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = str(text or "")
        self._apply_elided_text()

    def fullText(self) -> str:
        return self._full_text

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_elided_text()

    def _apply_elided_text(self) -> None:
        metrics = self.fontMetrics()
        available_width = max(0, self.contentsRect().width())
        if available_width <= 0:
            shown_text = self._full_text
        else:
            shown_text = metrics.elidedText(
                self._full_text,
                Qt.TextElideMode.ElideRight,
                available_width,
            )
        super().setText(shown_text)
        if self._full_text:
            set_tooltip(self, self._full_text.replace("\n", "<br>"))
        else:
            set_tooltip(self, "")


class StrategyRadioItem(CardWidget):
    """
    Карточка target для выбора стратегии.

    В отличие от старой версии, строка теперь состоит из двух зон:
    - слева смысловая часть target'а;
    - справа компактная status/strategy колонка.

    Это даёт более предсказуемое поведение на узких окнах и при длинных названиях.
    """

    item_activated = pyqtSignal(str)

    def __init__(
        self,
        target_key: str,
        name: str,
        description: str = "",
        icon_name: Optional[str] = None,
        icon_color: str = "#2196F3",
        tooltip: str = "",
        list_type: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._target_key = target_key
        self._name = name
        self._description = description
        self._icon_name = icon_name
        self._icon_color = icon_color
        self._tooltip = tooltip
        self._list_type = list_type
        self._icon_label = None
        self._desc_label = None
        self._list_badge = None

        self._strategy_id = "none"
        self._strategy_name = "Отключено"

        self._build_ui()

        self.clicked.connect(self._emit_item_activated)
        self.setProperty("clickable", True)
        self.setProperty("noDrag", True)

        if self._tooltip:
            set_tooltip(self, self._tooltip.replace("\n", "<br>"))
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme_refresh)

    def _emit_item_activated(self):
        self.item_activated.emit(self._target_key)

    @property
    def target_key(self) -> str:
        return self._target_key

    def _build_ui(self):
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 8, 12, 8)
        root_layout.setSpacing(10)
        self._layout = root_layout

        if self._icon_name:
            try:
                self._icon_label = QLabel()
                self._icon_label.setFixedSize(18, 18)
                self._icon_label.setStyleSheet("background: transparent;")
                root_layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)
            except Exception:
                pass

        left_widget = QWidget(self)
        left_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        top_row = QWidget(left_widget)
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(8)
        self._top_row_layout = top_row_layout

        self._name_label = ElidedTextLabel(self._name, top_row)
        top_row_layout.addWidget(self._name_label, 1)

        if self._list_type:
            self._ensure_list_badge(parent=top_row)

        left_layout.addWidget(top_row)

        if self._description:
            self._desc_label = ElidedTextLabel(self._description, left_widget)
            self._desc_label.setProperty("tone", "muted")
            left_layout.addWidget(self._desc_label)

        root_layout.addWidget(left_widget, 1)

        right_widget = QWidget(self)
        right_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        right_widget.setMaximumWidth(320)
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("background: transparent; color: #888888;")
        right_layout.addWidget(self._status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self._strategy_label = ElidedTextLabel("Отключено", right_widget)
        self._strategy_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_layout.addWidget(self._strategy_label, 1)

        root_layout.addWidget(right_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        self._apply_style()
        self._apply_icon_color()

    def _ensure_list_badge(self, parent=None):
        if self._list_badge is None:
            if InfoBadge is not None:
                self._list_badge = InfoBadge("", parent or self)
            else:
                self._list_badge = QLabel(parent or self)
            try:
                self._top_row_layout.addWidget(self._list_badge, 0, Qt.AlignmentFlag.AlignVCenter)
            except Exception:
                pass
        self._apply_list_badge()

    def _apply_list_badge(self):
        if not self._list_badge:
            return
        if not self._list_type:
            self._list_badge.hide()
            return

        if InfoBadge is not None and isinstance(self._list_badge, InfoBadge):
            if self._list_type == "hostlist":
                self._list_badge.setText("Hostlist")
                self._list_badge.lightBackgroundColor = None
                self._list_badge.darkBackgroundColor = None
                self._list_badge.level = InfoLevel.SUCCESS
            else:
                self._list_badge.setText("IPset")
                self._list_badge.setCustomBackgroundColor("#8B5CF6", "#8B5CF6")
            self._list_badge.adjustSize()
            self._list_badge.update()
        else:
            badge_text = "Hostlist" if self._list_type == "hostlist" else "IPset"
            badge_bg = "#00B900" if self._list_type == "hostlist" else "#8B5CF6"
            self._list_badge.setText(badge_text)
            self._list_badge.setStyleSheet(
                f"""
                QLabel {{
                    background: {badge_bg};
                    color: rgba(245, 245, 245, 0.95);
                    border-radius: 8px;
                    padding: 1px 6px;
                    font-size: 9px;
                    font-weight: 600;
                }}
                """
            )

        self._list_badge.show()

    def _apply_style(self):
        if self.is_active():
            self._status_dot.setStyleSheet("background: transparent; color: #6ccb5f;")
        else:
            try:
                tokens = get_theme_tokens()
                self._status_dot.setStyleSheet(
                    f"background: transparent; color: {tokens.fg_faint};"
                )
            except Exception:
                self._status_dot.setStyleSheet("background: transparent; color: #888888;")

    def _apply_icon_color(self):
        if not self._icon_name or self._icon_label is None:
            return
        try:
            tokens = get_theme_tokens()
            color = self._icon_color if self.is_active() else (
                "#808080" if tokens.is_light else "#BFC5CF"
            )
            self._icon_label.setPixmap(
                get_cached_qta_pixmap(
                    self._icon_name,
                    color=color,
                    size=18,
                    theme_name=tokens.theme_name,
                )
            )
        except Exception:
            pass

    def set_strategy(self, strategy_id: str, strategy_name: str):
        self._strategy_id = strategy_id
        self._strategy_name = strategy_name
        self._strategy_label.setText(strategy_name)
        self._apply_icon_color()
        self._apply_style()

    def set_list_type(self, list_type: str | None):
        self._list_type = list_type
        if self._list_type:
            self._ensure_list_badge()
        elif self._list_badge:
            self._apply_list_badge()

    def get_strategy_id(self) -> str:
        return self._strategy_id

    def is_active(self) -> bool:
        return self._strategy_id != "none"

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = tokens
        _ = force
        self._apply_style()
        self._apply_icon_color()

    def set_visible_by_filter(self, visible: bool):
        self.setVisible(visible)
