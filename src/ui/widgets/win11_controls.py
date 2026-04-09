from __future__ import annotations

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSpinBox, QComboBox
from PyQt6.QtGui import QPainter, QColor, QPainterPath
import qtawesome as qta

from ui.theme import get_theme_tokens, get_card_gradient_qss, get_tinted_surface_gradient_qss, to_qcolor
from ui.theme_refresh import ThemeRefreshController

try:
    from qfluentwidgets import (
        ComboBox,
        SpinBox,
        InfoBadge,
        InfoLevel as _InfoLevel,
        StrongBodyLabel,
        BodyLabel as _BodyLabel,
        CaptionLabel as _CaptionLabel,
    )

    _HAS_FLUENT = True
    _HAS_INFO_BADGE = True
except ImportError:
    _HAS_FLUENT = False
    _HAS_INFO_BADGE = False
    ComboBox = QComboBox  # type: ignore[assignment,misc]
    SpinBox = QSpinBox  # type: ignore[assignment,misc]
    StrongBodyLabel = QLabel  # type: ignore[assignment,misc]
    _BodyLabel = QLabel  # type: ignore[assignment,misc]
    _CaptionLabel = QLabel  # type: ignore[assignment,misc]

try:
    _LEGACY_DEFAULT_ACCENT = get_theme_tokens("Темная синяя").accent_hex.lower()
except Exception:
    _LEGACY_DEFAULT_ACCENT = ""


def _build_theme_refresh_key(tokens) -> tuple[str, str, str]:
    return (str(tokens.theme_name), str(tokens.accent_hex), str(tokens.font_family_qss))


class Win11ToggleSwitch(QCheckBox):
    """Toggle Switch в стиле Windows 11."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._circle_position = 4.0
        self._color_blend = 0.0

        self._animation = QPropertyAnimation(self, b"circle_position", self)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.setDuration(150)

        self.stateChanged.connect(self._animate)

    def _get_circle_position(self):
        return self._circle_position

    def _set_circle_position(self, pos):
        self._circle_position = pos
        self.update()

    circle_position = pyqtProperty(float, _get_circle_position, _set_circle_position)

    def _get_color_blend(self):
        return self._color_blend

    def _set_color_blend(self, value):
        self._color_blend = value
        self.update()

    color_blend = pyqtProperty(float, _get_color_blend, _set_color_blend)

    def _animate(self, state):
        if not self._animation:
            return
        self._animation.stop()
        if state:
            self._animation.setStartValue(self._circle_position)
            self._animation.setEndValue(self.width() - 18)
        else:
            self._animation.setStartValue(self._circle_position)
            self._animation.setEndValue(4.0)
        self._animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        tokens = get_theme_tokens()

        if self.isChecked():
            bg_color = to_qcolor(tokens.accent_hex, "#5caee8")
        else:
            if self.isEnabled():
                bg_color = to_qcolor(
                    tokens.toggle_off_bg_hover if self.underMouse() else tokens.toggle_off_bg,
                    "#8f97a4",
                )
            else:
                bg_color = to_qcolor(tokens.toggle_off_disabled_bg, "#7c8594")

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 11, 11)
        painter.fillPath(path, bg_color)

        if self.isChecked():
            painter.setPen(Qt.GlobalColor.transparent)
        else:
            border_color = tokens.toggle_off_border if self.isEnabled() else tokens.toggle_off_disabled_border
            painter.setPen(to_qcolor(border_color, "#9fa8b7"))
        painter.drawPath(path)

        if self.isChecked():
            circle_color = to_qcolor(tokens.accent_hex, "#5caee8").lighter(230 if tokens.is_light else 260)
        else:
            circle_color = QColor(250, 250, 250) if tokens.is_light else QColor(236, 241, 247)
        if not self.isEnabled():
            circle_color.setAlpha(200 if tokens.is_light else 185)
        painter.setBrush(circle_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(self._circle_position, 4, 14, 14))

        painter.end()

    def hitButton(self, pos):
        return self.rect().contains(pos)


class Win11ToggleRow(QWidget):
    """Строка с toggle switch в стиле Windows 11."""

    toggled = pyqtSignal(bool)

    def __init__(self, icon_name: str, title: str, description: str = "", icon_color: str = "", parent=None):
        super().__init__(parent)

        self._icon_name = icon_name
        self._icon_color = icon_color
        self._title_label = None
        self._desc_label = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        layout.addWidget(self._icon_label)
        self._refresh_icon(get_theme_tokens())

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_label = _BodyLabel(title)
        self._title_label = title_label
        text_layout.addWidget(title_label)

        if description:
            desc_label = _CaptionLabel(description)
            desc_label.setWordWrap(True)
            self._desc_label = desc_label
            text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        self.toggle = Win11ToggleSwitch()
        self.toggle.toggled.connect(self.toggled.emit)
        layout.addWidget(self.toggle)
        self._theme_refresh = ThemeRefreshController(
            self,
            self._apply_theme_refresh,
            key_builder=_build_theme_refresh_key,
        )

    def _resolved_icon_color(self, tokens=None) -> str:
        theme_tokens = tokens or get_theme_tokens()
        c = str(self._icon_color or "").strip()
        if not c:
            return theme_tokens.accent_hex
        if _LEGACY_DEFAULT_ACCENT and c.lower() == _LEGACY_DEFAULT_ACCENT:
            return theme_tokens.accent_hex
        return c

    def _refresh_icon(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        try:
            color = self._resolved_icon_color(theme_tokens)
            self._icon_label.setPixmap(qta.icon(self._icon_name, color=color).pixmap(18, 18))
        except Exception:
            return

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._refresh_icon(tokens)

    def setChecked(self, checked: bool, block_signals: bool = False):
        if block_signals:
            self.toggle.blockSignals(True)
        self.toggle.setChecked(checked)
        if block_signals:
            self.toggle.blockSignals(False)
            self.toggle._circle_position = (self.toggle.width() - 18) if checked else 4.0
            self.toggle.update()

    def isChecked(self) -> bool:
        return self.toggle.isChecked()

    def set_texts(self, title: str, description: str = "") -> None:
        try:
            if self._title_label is not None:
                self._title_label.setText(title)
            if self._desc_label is not None:
                self._desc_label.setText(description)
        except Exception:
            pass


class Win11RadioOption(QWidget):
    """Радио-опция в стиле Windows 11."""

    clicked = pyqtSignal()

    def __init__(
        self,
        title: str,
        description: str,
        icon_name: str | None = None,
        icon_color: str = "",
        recommended: bool = False,
        recommended_badge: str = "рекомендуется",
        parent=None,
    ):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._selected = False
        self._hover = False
        self._recommended = recommended

        self._icon_name = icon_name
        self._icon_color = icon_color
        self._icon_label: QLabel | None = None
        self._badge_label = None
        self._title_label = None
        self._desc_label = None
        self._applying_theme_styles = False
        initial_tokens = get_theme_tokens()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.radio_circle = QWidget()
        self.radio_circle.setFixedSize(20, 20)
        layout.addWidget(self.radio_circle)

        if icon_name:
            self._icon_label = QLabel()
            self._icon_label.setFixedSize(28, 28)
            layout.addWidget(self._icon_label)
            self._refresh_icon(initial_tokens)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_label = StrongBodyLabel(title)
        self._title_label = title_label
        title_layout.addWidget(title_label)

        if recommended:
            if _HAS_INFO_BADGE:
                self._badge_label = InfoBadge(recommended_badge, level=_InfoLevel.ATTENTION)
            else:
                self._badge_label = QLabel(recommended_badge)
                self._badge_label.setStyleSheet(
                    "QLabel { background: #0078d4; color: #fff; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 3px; }"
                )
            title_layout.addWidget(self._badge_label)

        title_layout.addStretch()
        text_layout.addLayout(title_layout)

        desc_label = _CaptionLabel(description)
        desc_label.setWordWrap(True)
        self._desc_label = desc_label
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        self._update_style(initial_tokens)
        self._theme_refresh = ThemeRefreshController(
            self,
            self._apply_theme_refresh,
            key_builder=_build_theme_refresh_key,
        )

    def _resolved_icon_color(self, tokens=None) -> str:
        theme_tokens = tokens or get_theme_tokens()
        c = str(self._icon_color or "").strip()
        if not c:
            return theme_tokens.accent_hex
        if _LEGACY_DEFAULT_ACCENT and c.lower() == _LEGACY_DEFAULT_ACCENT:
            return theme_tokens.accent_hex
        return c

    def _refresh_icon(self, tokens=None) -> None:
        if self._icon_label is None or not self._icon_name:
            return
        theme_tokens = tokens or get_theme_tokens()
        try:
            self._icon_label.setPixmap(qta.icon(self._icon_name, color=self._resolved_icon_color(theme_tokens)).pixmap(24, 24))
        except Exception:
            return

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._refresh_icon(tokens)
        self._update_style(tokens)

    def setSelected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def isSelected(self) -> bool:
        return self._selected

    def set_texts(self, title: str, description: str, recommended_badge: str | None = None) -> None:
        try:
            if self._title_label is not None:
                self._title_label.setText(title)
            if self._desc_label is not None:
                self._desc_label.setText(description)
            if recommended_badge is not None and self._badge_label is not None and hasattr(self._badge_label, "setText"):
                self._badge_label.setText(recommended_badge)
        except Exception:
            pass

    def _update_style(self, tokens=None):
        if self._applying_theme_styles:
            return

        self._applying_theme_styles = True
        try:
            theme_tokens = tokens or get_theme_tokens()

            if self._selected:
                selected_bg = theme_tokens.accent_soft_bg_hover if self._hover else theme_tokens.accent_soft_bg
                bg = get_tinted_surface_gradient_qss(
                    selected_bg,
                    theme_name=theme_tokens.theme_name,
                    hover=self._hover,
                )
                border_alpha = "0.68" if self._hover else "0.60"
                border = f"rgba({theme_tokens.accent_rgb_str}, {border_alpha})"
            elif self._hover:
                bg = get_card_gradient_qss(theme_tokens.theme_name, hover=True)
                border = theme_tokens.surface_border_hover
            else:
                bg = get_card_gradient_qss(theme_tokens.theme_name)
                border = theme_tokens.surface_border

            self.setStyleSheet(
                f"""
                Win11RadioOption {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: 8px;
                }}
                """
            )
        finally:
            self._applying_theme_styles = False

        self.update()

    def enterEvent(self, event):
        self._hover = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        circle_x = 12 + 10
        circle_y = self.height() // 2

        tokens = get_theme_tokens()
        accent_r, accent_g, accent_b = tokens.accent_rgb
        selected_ring = QColor(accent_r, accent_g, accent_b, 245)
        selected_dot = QColor(accent_r, accent_g, accent_b, 255)
        unselected_ring = QColor(accent_r, accent_g, accent_b, 140 if tokens.is_light else 165)

        if not selected_ring.isValid():
            selected_ring = QColor(tokens.accent_hex)
            selected_ring.setAlpha(245)
        if not selected_dot.isValid():
            selected_dot = QColor(tokens.accent_hex)
            selected_dot.setAlpha(255)
        if not unselected_ring.isValid():
            unselected_ring = QColor(tokens.accent_hex)
            unselected_ring.setAlpha(140 if tokens.is_light else 165)

        ring_color = selected_ring if self._selected else unselected_ring
        pen = painter.pen()
        pen.setColor(ring_color)
        pen.setWidth(2 if self._selected else 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(circle_x - 8, circle_y - 8, 16, 16)

        if self._selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(selected_dot)
            painter.drawEllipse(circle_x - 4, circle_y - 4, 8, 8)

        painter.end()


class Win11NumberRow(QWidget):
    """Строка с числовым вводом в стиле Windows 11."""

    valueChanged = pyqtSignal(int)

    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str = "",
        icon_color: str = "",
        min_val: int = 0,
        max_val: int = 999,
        default_val: int = 10,
        suffix: str = "",
        parent=None,
    ):
        super().__init__(parent)

        self._icon_name = icon_name
        self._icon_color = icon_color
        self._title_label = None
        self._desc_label = None
        self._applying_theme_styles = False
        initial_tokens = get_theme_tokens()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        layout.addWidget(self._icon_label)
        self._refresh_icon(initial_tokens)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_label = _BodyLabel(title)
        self._title_label = title_label
        text_layout.addWidget(title_label)

        if description:
            desc_label = _CaptionLabel(description)
            desc_label.setWordWrap(True)
            self._desc_label = desc_label
            text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        self.spinbox = SpinBox()
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(max_val)
        self.spinbox.setValue(default_val)
        self.spinbox.setSuffix(suffix)
        self.spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not _HAS_FLUENT:
            self.spinbox.setFixedHeight(28)
            self._apply_theme_styles(initial_tokens)
        self.spinbox.valueChanged.connect(self.valueChanged.emit)
        layout.addWidget(self.spinbox)
        self._theme_refresh = ThemeRefreshController(
            self,
            self._apply_theme_refresh,
            key_builder=_build_theme_refresh_key,
        )

    def _resolved_icon_color(self, tokens=None) -> str:
        theme_tokens = tokens or get_theme_tokens()
        c = str(self._icon_color or "").strip()
        if not c:
            return theme_tokens.accent_hex
        if _LEGACY_DEFAULT_ACCENT and c.lower() == _LEGACY_DEFAULT_ACCENT:
            return theme_tokens.accent_hex
        return c

    def _refresh_icon(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        try:
            self._icon_label.setPixmap(qta.icon(self._icon_name, color=self._resolved_icon_color(theme_tokens)).pixmap(18, 18))
        except Exception:
            return

    def _apply_theme_styles(self, tokens=None) -> None:
        if _HAS_FLUENT:
            return
        theme_tokens = tokens or get_theme_tokens()
        self.spinbox.setStyleSheet(
            f"""
            QSpinBox {{
                background-color: {theme_tokens.surface_bg};
                border: 1px solid {theme_tokens.surface_border};
                border-radius: 4px;
                padding: 2px 10px;
                color: {theme_tokens.fg};
                font-size: 12px;
            }}
            QSpinBox:hover {{
                background-color: {theme_tokens.surface_bg_hover};
                border: 1px solid {theme_tokens.surface_border_hover};
            }}
            QSpinBox:focus {{
                border: 1px solid {theme_tokens.accent_hex};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 0px;
                height: 0px;
                border: none;
                background: none;
            }}
            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                width: 0px;
                height: 0px;
            }}
            """
        )

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._applying_theme_styles = True
        try:
            self._refresh_icon(tokens)
            if not _HAS_FLUENT:
                self._apply_theme_styles(tokens)
        finally:
            self._applying_theme_styles = False

    def setValue(self, value: int, block_signals: bool = False):
        if block_signals:
            self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        if block_signals:
            self.spinbox.blockSignals(False)

    def value(self) -> int:
        return self.spinbox.value()

    def set_texts(self, title: str, description: str = "") -> None:
        try:
            if self._title_label is not None:
                self._title_label.setText(title)
            if self._desc_label is not None:
                self._desc_label.setText(description)
        except Exception:
            pass


class Win11ComboRow(QWidget):
    """Строка с выпадающим списком в стиле Windows 11."""

    currentIndexChanged = pyqtSignal(int)
    currentTextChanged = pyqtSignal(str)

    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str = "",
        icon_color: str = "",
        items: list | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self._icon_name = icon_name
        self._icon_color = icon_color
        self._title_label = None
        self._desc_label = None
        self._applying_theme_styles = False
        initial_tokens = get_theme_tokens()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        layout.addWidget(self._icon_label)
        self._refresh_icon(initial_tokens)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_label = _BodyLabel(title)
        self._title_label = title_label
        text_layout.addWidget(title_label)

        if description:
            desc_label = _CaptionLabel(description)
            desc_label.setWordWrap(True)
            self._desc_label = desc_label
            text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        self.combo = ComboBox()
        self.combo.setFixedWidth(160)
        if not _HAS_FLUENT:
            self.combo.setFixedHeight(28)
            self._apply_theme_styles(initial_tokens)

        if items:
            for text, data in items:
                self.combo.addItem(text, userData=data)

        self.combo.currentIndexChanged.connect(self.currentIndexChanged.emit)
        self.combo.currentTextChanged.connect(self.currentTextChanged.emit)
        layout.addWidget(self.combo)
        self._theme_refresh = ThemeRefreshController(
            self,
            self._apply_theme_refresh,
            key_builder=_build_theme_refresh_key,
        )

    def _resolved_icon_color(self, tokens=None) -> str:
        theme_tokens = tokens or get_theme_tokens()
        c = str(self._icon_color or "").strip()
        if not c:
            return theme_tokens.accent_hex
        if _LEGACY_DEFAULT_ACCENT and c.lower() == _LEGACY_DEFAULT_ACCENT:
            return theme_tokens.accent_hex
        return c

    def _refresh_icon(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        try:
            self._icon_label.setPixmap(qta.icon(self._icon_name, color=self._resolved_icon_color(theme_tokens)).pixmap(18, 18))
        except Exception:
            return

    def _apply_theme_styles(self, tokens=None) -> None:
        if _HAS_FLUENT:
            return
        theme_tokens = tokens or get_theme_tokens()
        popup_bg = theme_tokens.surface_bg_hover
        popup_fg = theme_tokens.fg
        self.combo.setStyleSheet(
            f"""
            QComboBox {{
                background-color: {theme_tokens.surface_bg};
                border: 1px solid {theme_tokens.surface_border};
                border-radius: 4px;
                padding: 2px 10px;
                color: {theme_tokens.fg};
                font-size: 12px;
            }}
            QComboBox:hover {{
                background-color: {theme_tokens.surface_bg_hover};
                border: 1px solid {theme_tokens.surface_border_hover};
            }}
            QComboBox:focus {{
                border: 1px solid {theme_tokens.accent_hex};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {theme_tokens.fg};
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {popup_bg};
                border: 1px solid {theme_tokens.surface_border};
                selection-background-color: {theme_tokens.accent_soft_bg};
                color: {popup_fg};
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                background-color: transparent;
                padding: 4px 8px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {theme_tokens.surface_bg_hover};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {theme_tokens.accent_soft_bg_hover};
            }}
            QScrollBar:vertical {{
                width: 0px;
            }}
            QScrollBar:horizontal {{
                height: 0px;
            }}
            QComboBox::indicator {{
                width: 0px;
                height: 0px;
            }}
            """
        )

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._applying_theme_styles = True
        try:
            self._refresh_icon(tokens)
            if not _HAS_FLUENT:
                self._apply_theme_styles(tokens)
        finally:
            self._applying_theme_styles = False

    def setCurrentData(self, data, block_signals: bool = False):
        if block_signals:
            self.combo.blockSignals(True)
        index = self.combo.findData(data)
        if index >= 0:
            self.combo.setCurrentIndex(index)
        if block_signals:
            self.combo.blockSignals(False)

    def currentData(self):
        return self.combo.currentData()

    def setCurrentIndex(self, index: int, block_signals: bool = False):
        if block_signals:
            self.combo.blockSignals(True)
        self.combo.setCurrentIndex(index)
        if block_signals:
            self.combo.blockSignals(False)

    def currentIndex(self) -> int:
        return self.combo.currentIndex()

    def set_texts(self, title: str, description: str = "") -> None:
        try:
            if self._title_label is not None:
                self._title_label.setText(title)
            if self._desc_label is not None:
                self._desc_label.setText(description)
        except Exception:
            pass


__all__ = [
    "Win11ToggleSwitch",
    "Win11ToggleRow",
    "Win11RadioOption",
    "Win11NumberRow",
    "Win11ComboRow",
]
