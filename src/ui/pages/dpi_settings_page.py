# ui/pages/dpi_settings_page.py
"""Страница настроек DPI"""

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, pyqtSignal, QTimer, QEvent
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QCheckBox, QSpinBox, QComboBox)
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont
import qtawesome as qta

from .base_page import BasePage
from ui.compat_widgets import SettingsCard, ActionButton
from ui.theme import get_theme_tokens, get_card_gradient_qss, get_tinted_surface_gradient_qss, to_qcolor
from ui.text_catalog import tr as tr_catalog
from log import log

try:
    from qfluentwidgets import (
        ComboBox, SpinBox,
        InfoBadge, InfoLevel as _InfoLevel, StrongBodyLabel,
        BodyLabel as _BodyLabel, CaptionLabel as _CaptionLabel,
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
    """Toggle Switch в стиле Windows 11"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._circle_position = 4.0
        self._color_blend = 0.0  # Для совместимости с servers_page версией
        
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
        
        # Фон
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
        
        # Рамка
        if self.isChecked():
            painter.setPen(Qt.GlobalColor.transparent)
        else:
            border_color = tokens.toggle_off_border if self.isEnabled() else tokens.toggle_off_disabled_border
            painter.setPen(to_qcolor(border_color, "#9fa8b7"))
        painter.drawPath(path)
        
        # Круг
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
    """Строка с toggle switch в стиле Windows 11"""
    
    toggled = pyqtSignal(bool)
    
    def __init__(self, icon_name: str, title: str, description: str = "", 
                 icon_color: str = "", parent=None):
        super().__init__(parent)

        self._icon_name = icon_name
        self._icon_color = icon_color
        self._title_label = None
        self._desc_label = None
        self._last_theme_refresh_key: tuple[str, str, str] | None = None
        self._theme_refresh_pending_when_hidden = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)
        
        # Иконка
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        layout.addWidget(self._icon_label)
        self._refresh_icon(get_theme_tokens())
        
        # Текст
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

        # Toggle
        self.toggle = Win11ToggleSwitch()
        self.toggle.toggled.connect(self.toggled.emit)
        layout.addWidget(self.toggle)

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
            self._last_theme_refresh_key = _build_theme_refresh_key(theme_tokens)
            color = self._resolved_icon_color(theme_tokens)
            self._icon_label.setPixmap(qta.icon(self._icon_name, color=color).pixmap(18, 18))
        except Exception:
            return

    def changeEvent(self, event):  # noqa: N802 (Qt override)
        try:
            if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
                tokens = get_theme_tokens()
                theme_key = _build_theme_refresh_key(tokens)
                if theme_key == self._last_theme_refresh_key:
                    return super().changeEvent(event)
                if not self.isVisible():
                    self._theme_refresh_pending_when_hidden = True
                    return super().changeEvent(event)
                self._refresh_icon(tokens)
        except Exception:
            pass
        super().changeEvent(event)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        if not self._theme_refresh_pending_when_hidden:
            return
        self._theme_refresh_pending_when_hidden = False
        tokens = get_theme_tokens()
        if _build_theme_refresh_key(tokens) == self._last_theme_refresh_key:
            return
        self._refresh_icon(tokens)
        
    def setChecked(self, checked: bool, block_signals: bool = False):
        if block_signals:
            self.toggle.blockSignals(True)
        self.toggle.setChecked(checked)
        if block_signals:
            self.toggle.blockSignals(False)
            # Обновляем позицию круга без анимации
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
    """Радио-опция в стиле Windows 11"""
    
    clicked = pyqtSignal()
    
    def __init__(self, title: str, description: str, icon_name: str = None,
                 icon_color: str = "", recommended: bool = False,
                 recommended_badge: str = "рекомендуется", parent=None):
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
        self._last_theme_refresh_key: tuple[str, str, str] | None = None
        self._theme_refresh_pending_when_hidden = False
        initial_tokens = get_theme_tokens()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Радио-круг
        self.radio_circle = QWidget()
        self.radio_circle.setFixedSize(20, 20)
        layout.addWidget(self.radio_circle)
        
        # Иконка (опционально)
        if icon_name:
            self._icon_label = QLabel()
            self._icon_label.setFixedSize(28, 28)
            layout.addWidget(self._icon_label)
            self._refresh_icon(initial_tokens)
        
        # Текстовый блок
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок с бейджем
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
        
        # Описание
        desc_label = _CaptionLabel(description)
        desc_label.setWordWrap(True)
        self._desc_label = desc_label
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout, 1)
        
        self._update_style(initial_tokens)
        self._last_theme_refresh_key = _build_theme_refresh_key(initial_tokens)

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

    def changeEvent(self, event):  # noqa: N802 (Qt override)
        try:
            if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
                if self._applying_theme_styles:
                    return super().changeEvent(event)
                tokens = get_theme_tokens()
                theme_key = _build_theme_refresh_key(tokens)
                if theme_key == self._last_theme_refresh_key:
                    return super().changeEvent(event)
                if not self.isVisible():
                    self._theme_refresh_pending_when_hidden = True
                    return super().changeEvent(event)
                self._last_theme_refresh_key = theme_key
                self._refresh_icon(tokens)
                self._update_style(tokens)
        except Exception:
            pass
        super().changeEvent(event)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        if not self._theme_refresh_pending_when_hidden:
            return
        self._theme_refresh_pending_when_hidden = False
        tokens = get_theme_tokens()
        theme_key = _build_theme_refresh_key(tokens)
        if theme_key == self._last_theme_refresh_key:
            return
        self._last_theme_refresh_key = theme_key
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
            
            self.setStyleSheet(f"""
                Win11RadioOption {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: 8px;
                }}
            """)
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
        
        # Рисуем радио-круг
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Позиция круга
        circle_x = 12 + 10  # margin + half width
        circle_y = self.height() // 2
        
        # Внешний круг
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
        
        # Внутренний круг (если выбран)
        if self._selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(selected_dot)
            painter.drawEllipse(circle_x - 4, circle_y - 4, 8, 8)
            
        painter.end()


class Win11NumberRow(QWidget):
    """Строка с числовым вводом в стиле Windows 11"""
    
    valueChanged = pyqtSignal(int)
    
    def __init__(self, icon_name: str, title: str, description: str = "", 
                 icon_color: str = "", min_val: int = 0, max_val: int = 999,
                 default_val: int = 10, suffix: str = "", parent=None):
        super().__init__(parent)

        self._icon_name = icon_name
        self._icon_color = icon_color
        self._title_label = None
        self._desc_label = None
        self._applying_theme_styles = False
        self._last_theme_refresh_key: tuple[str, str, str] | None = None
        self._theme_refresh_pending_when_hidden = False
        initial_tokens = get_theme_tokens()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)
        
        # Иконка
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        layout.addWidget(self._icon_label)
        self._refresh_icon(initial_tokens)
        
        # Текст
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

        # SpinBox (qfluentwidgets SpinBox when available, else native QSpinBox)
        self.spinbox = SpinBox()
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(max_val)
        self.spinbox.setValue(default_val)
        self.spinbox.setSuffix(suffix)
        self.spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Do NOT force height on qfluentwidgets SpinBox — its default 33px is correct.
        # Forcing 28px squishes the widget and may clip text/padding.
        if not _HAS_FLUENT:
            self.spinbox.setFixedHeight(28)
            self._apply_theme_styles(initial_tokens)
        self._last_theme_refresh_key = _build_theme_refresh_key(initial_tokens)
        self.spinbox.valueChanged.connect(self.valueChanged.emit)
        layout.addWidget(self.spinbox)

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
        # qfluentwidgets SpinBox handles its own theming; skip raw stylesheet.
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

    def changeEvent(self, event):  # noqa: N802 (Qt override)
        try:
            if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
                if self._applying_theme_styles:
                    return super().changeEvent(event)
                tokens = get_theme_tokens()
                theme_key = _build_theme_refresh_key(tokens)
                if theme_key == self._last_theme_refresh_key:
                    return super().changeEvent(event)
                if not self.isVisible():
                    self._theme_refresh_pending_when_hidden = True
                    return super().changeEvent(event)
                self._applying_theme_styles = True
                try:
                    self._last_theme_refresh_key = theme_key
                    self._refresh_icon(tokens)
                    if not _HAS_FLUENT:
                        self._apply_theme_styles(tokens)
                finally:
                    self._applying_theme_styles = False
        except Exception:
            pass
        super().changeEvent(event)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        if not self._theme_refresh_pending_when_hidden:
            return
        self._theme_refresh_pending_when_hidden = False
        tokens = get_theme_tokens()
        theme_key = _build_theme_refresh_key(tokens)
        if theme_key == self._last_theme_refresh_key:
            return
        self._applying_theme_styles = True
        try:
            self._last_theme_refresh_key = theme_key
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
    """Строка с выпадающим списком в стиле Windows 11"""

    currentIndexChanged = pyqtSignal(int)
    currentTextChanged = pyqtSignal(str)

    def __init__(self, icon_name: str, title: str, description: str = "",
                 icon_color: str = "", items: list = None, parent=None):
        super().__init__(parent)

        self._icon_name = icon_name
        self._icon_color = icon_color
        self._title_label = None
        self._desc_label = None
        self._applying_theme_styles = False
        self._last_theme_refresh_key: tuple[str, str, str] | None = None
        self._theme_refresh_pending_when_hidden = False
        initial_tokens = get_theme_tokens()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        # Иконка
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        layout.addWidget(self._icon_label)
        self._refresh_icon(initial_tokens)

        # Текст
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

        # ComboBox (qfluentwidgets ComboBox when available, else native QComboBox)
        self.combo = ComboBox()
        self.combo.setFixedWidth(160)
        if not _HAS_FLUENT:
            self.combo.setFixedHeight(28)
            self._apply_theme_styles(initial_tokens)
        self._last_theme_refresh_key = _build_theme_refresh_key(initial_tokens)

        if items:
            for text, data in items:
                self.combo.addItem(text, userData=data)

        self.combo.currentIndexChanged.connect(self.currentIndexChanged.emit)
        self.combo.currentTextChanged.connect(self.currentTextChanged.emit)
        layout.addWidget(self.combo)

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
        # qfluentwidgets ComboBox handles its own theming; skip raw stylesheet.
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

    def changeEvent(self, event):  # noqa: N802 (Qt override)
        try:
            if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
                if self._applying_theme_styles:
                    return super().changeEvent(event)
                tokens = get_theme_tokens()
                theme_key = _build_theme_refresh_key(tokens)
                if theme_key == self._last_theme_refresh_key:
                    return super().changeEvent(event)
                if not self.isVisible():
                    self._theme_refresh_pending_when_hidden = True
                    return super().changeEvent(event)
                self._applying_theme_styles = True
                try:
                    self._last_theme_refresh_key = theme_key
                    self._refresh_icon(tokens)
                    if not _HAS_FLUENT:
                        self._apply_theme_styles(tokens)
                finally:
                    self._applying_theme_styles = False
        except Exception:
            pass
        super().changeEvent(event)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        if not self._theme_refresh_pending_when_hidden:
            return
        self._theme_refresh_pending_when_hidden = False
        tokens = get_theme_tokens()
        theme_key = _build_theme_refresh_key(tokens)
        if theme_key == self._last_theme_refresh_key:
            return
        self._applying_theme_styles = True
        try:
            self._last_theme_refresh_key = theme_key
            self._refresh_icon(tokens)
            if not _HAS_FLUENT:
                self._apply_theme_styles(tokens)
        finally:
            self._applying_theme_styles = False

    def setCurrentData(self, data, block_signals: bool = False):
        """Устанавливает текущий элемент по данным"""
        if block_signals:
            self.combo.blockSignals(True)
        index = self.combo.findData(data)
        if index >= 0:
            self.combo.setCurrentIndex(index)
        if block_signals:
            self.combo.blockSignals(False)

    def currentData(self):
        """Возвращает данные текущего элемента"""
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


class DpiSettingsPage(BasePage):
    """Страница настроек DPI"""

    launch_method_changed = pyqtSignal(str)
    filters_changed = pyqtSignal()  # Сигнал при изменении фильтров
    
    def __init__(self, parent=None):
        super().__init__(
            "Настройки DPI",
            "Параметры обхода блокировок",
            parent,
            title_key="page.dpi_settings.title",
            subtitle_key="page.dpi_settings.subtitle",
        )
        self._method_card = None
        self._method_desc_label = None
        self._zapret1_header = None
        self._orchestra_label = None
        self._advanced_desc_label = None
        self._applying_theme_styles = False
        self._last_theme_refresh_key: tuple[str, str, str] | None = None
        self._theme_refresh_pending_when_hidden = False
        self._build_ui()
        self._load_settings()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _apply_theme_styles(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        try:
            if hasattr(self, "zapret2_header") and self.zapret2_header is not None:
                self.zapret2_header.setStyleSheet(
                    f"color: {theme_tokens.accent_hex};"
                )
        except Exception:
            pass

        try:
            if hasattr(self, "separator2") and self.separator2 is not None:
                self.separator2.setStyleSheet(f"background-color: {theme_tokens.divider_strong}; margin: 8px 0;")
        except Exception:
            pass

    def changeEvent(self, event):  # noqa: N802 (Qt override)
        try:
            if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
                if self._applying_theme_styles:
                    return super().changeEvent(event)
                tokens = get_theme_tokens()
                theme_key = _build_theme_refresh_key(tokens)
                if theme_key == self._last_theme_refresh_key:
                    return super().changeEvent(event)
                if not self.isVisible():
                    self._theme_refresh_pending_when_hidden = True
                    return super().changeEvent(event)
                self._applying_theme_styles = True
                try:
                    self._last_theme_refresh_key = theme_key
                    self._apply_theme_styles(tokens)
                finally:
                    self._applying_theme_styles = False
        except Exception:
            pass
        super().changeEvent(event)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        if not self._theme_refresh_pending_when_hidden:
            return
        self._theme_refresh_pending_when_hidden = False
        tokens = get_theme_tokens()
        theme_key = _build_theme_refresh_key(tokens)
        if theme_key == self._last_theme_refresh_key:
            return
        self._applying_theme_styles = True
        try:
            self._last_theme_refresh_key = theme_key
            self._apply_theme_styles(tokens)
        finally:
            self._applying_theme_styles = False
        
    def _build_ui(self):
        """Строит UI страницы"""
        
        # Метод запуска
        method_card = SettingsCard(
            self._tr(
                "page.dpi_settings.card.launch_method",
                "Метод запуска стратегий (режим работы программы)",
            )
        )
        self._method_card = method_card
        method_layout = QVBoxLayout()
        method_layout.setSpacing(10)
        
        method_desc = _CaptionLabel(
            self._tr("page.dpi_settings.launch_method.desc", "Выберите способ запуска обхода блокировок")
        )
        self._method_desc_label = method_desc
        method_layout.addWidget(method_desc)

        # ═══════════════════════════════════════
        # ZAPRET 2 (winws2.exe)
        # ═══════════════════════════════════════
        self.zapret2_header = StrongBodyLabel(
            self._tr("page.dpi_settings.section.z2", "Zapret 2 (winws2.exe)")
        )
        self.zapret2_header.setContentsMargins(0, 8, 0, 4)
        method_layout.addWidget(self.zapret2_header)

        # Zapret 2 (direct) - рекомендуется
        self.method_direct = Win11RadioOption(
            self._tr("page.dpi_settings.method.direct_z2.title", "Zapret 2"),
            self._tr(
                "page.dpi_settings.method.direct_z2.desc",
                "Режим со второй версией Zapret (winws2.exe) + готовые пресеты для быстрого запуска. Поддерживает кастомный lua-код чтобы писать свои стратегии.",
            ),
            icon_name="mdi.rocket-launch",
            recommended=True,
            recommended_badge=self._tr("page.dpi_settings.option.recommended", "рекомендуется"),
        )
        self.method_direct.clicked.connect(lambda: self._select_method("direct_zapret2"))
        method_layout.addWidget(self.method_direct)

        # Оркестратор Zapret 2 (direct с другим набором стратегий)
        self.method_direct_zapret2_orchestra = Win11RadioOption(
            self._tr("page.dpi_settings.method.direct_z2_orchestra.title", "Оркестраторный Zapret 2"),
            self._tr(
                "page.dpi_settings.method.direct_z2_orchestra.desc",
                "Запуск Zapret 2 со стратегиями оркестратора внутри каждого профиля. Позволяет настроить для каждого сайта свой оркерстратор. Не сохраняет состояние для повышенной агрессии обхода.",
            ),
            icon_name="mdi.brain",
            icon_color="#9c27b0"
        )
        self.method_direct_zapret2_orchestra.clicked.connect(lambda: self._select_method("direct_zapret2_orchestra"))
        method_layout.addWidget(self.method_direct_zapret2_orchestra)

        # Оркестр (auto-learning)
        self.method_orchestra = Win11RadioOption(
            self._tr("page.dpi_settings.method.orchestra.title", "Оркестратор v0.9.6 (Beta)"),
            self._tr(
                "page.dpi_settings.method.orchestra.desc",
                "Автоматическое обучение. Система сама подбирает лучшие стратегии для каждого домена. Запоминает результаты между запусками.",
            ),
            icon_name="mdi.brain",
            icon_color="#9c27b0"
        )
        self.method_orchestra.clicked.connect(lambda: self._select_method("orchestra"))
        method_layout.addWidget(self.method_orchestra)

        # ───────────────────────────────────────
        # ZAPRET 1 (winws.exe)
        # ───────────────────────────────────────
        zapret1_header = StrongBodyLabel(
            self._tr("page.dpi_settings.section.z1", "Zapret 1 (winws.exe)")
        )
        self._zapret1_header = zapret1_header
        zapret1_header.setContentsMargins(0, 12, 0, 4)
        zapret1_header.setStyleSheet("color: #ff9800;")
        method_layout.addWidget(zapret1_header)

        # Zapret 1 Direct (прямой запуск winws.exe с JSON стратегиями)
        self.method_direct_zapret1 = Win11RadioOption(
            self._tr("page.dpi_settings.method.direct_z1.title", "Zapret 1"),
            self._tr(
                "page.dpi_settings.method.direct_z1.desc",
                "Режим первой версии Zapret 1 (winws.exe) + готовые пресеты для быстрого запуска. Не использует Lua код, нет понятия блобов.",
            ),
            icon_name="mdi.rocket-launch-outline",
            icon_color="#ff9800"
        )
        self.method_direct_zapret1.clicked.connect(lambda: self._select_method("direct_zapret1"))
        method_layout.addWidget(self.method_direct_zapret1)

        # Разделитель 2
        self.separator2 = QFrame()
        self.separator2.setFrameShape(QFrame.Shape.HLine)
        self.separator2.setFixedHeight(1)
        method_layout.addWidget(self.separator2)

        # Перезапуск Discord (только для Zapret 1/2)
        self.discord_restart_container = QWidget()
        discord_layout = QVBoxLayout(self.discord_restart_container)
        discord_layout.setContentsMargins(0, 0, 0, 0)
        discord_layout.setSpacing(0)

        self.discord_restart_toggle = Win11ToggleRow(
            "mdi.discord",
            self._tr("page.dpi_settings.discord_restart.title", "Перезапуск Discord"),
            self._tr("page.dpi_settings.discord_restart.desc", "Автоперезапуск при смене стратегии"),
            "#7289da",
        )
        discord_layout.addWidget(self.discord_restart_toggle)
        method_layout.addWidget(self.discord_restart_container)

        # ─────────────────────────────────────────────────────────────────────
        # НАСТРОЙКИ ОРКЕСТРАТОРА (только в режиме оркестратора)
        # ─────────────────────────────────────────────────────────────────────
        self.orchestra_settings_container = QWidget()
        orchestra_settings_layout = QVBoxLayout(self.orchestra_settings_container)
        orchestra_settings_layout.setContentsMargins(0, 0, 0, 0)
        orchestra_settings_layout.setSpacing(6)

        orchestra_label = StrongBodyLabel(
            self._tr("page.dpi_settings.section.orchestra_settings", "Настройки оркестратора")
        )
        self._orchestra_label = orchestra_label
        orchestra_label.setStyleSheet("color: #9c27b0;")
        orchestra_settings_layout.addWidget(orchestra_label)

        self.strict_detection_toggle = Win11ToggleRow(
            "mdi.check-decagram",
            self._tr("page.dpi_settings.orchestra.strict_detection.title", "Строгий режим детекции"),
            self._tr("page.dpi_settings.orchestra.strict_detection.desc", "HTTP 200 + проверка блок-страниц"),
            "#4CAF50",
        )
        orchestra_settings_layout.addWidget(self.strict_detection_toggle)

        self.debug_file_toggle = Win11ToggleRow(
            "mdi.file-document-outline",
            self._tr("page.dpi_settings.orchestra.debug_file.title", "Сохранять debug файл"),
            self._tr("page.dpi_settings.orchestra.debug_file.desc", "Сырой debug файл для отладки"),
            "#8a2be2",
        )
        orchestra_settings_layout.addWidget(self.debug_file_toggle)

        self.auto_restart_discord_toggle = Win11ToggleRow(
            "mdi.discord",
            self._tr("page.dpi_settings.orchestra.auto_restart_discord.title", "Авторестарт Discord при FAIL"),
            self._tr(
                "page.dpi_settings.orchestra.auto_restart_discord.desc",
                "Перезапуск Discord при неудачном обходе",
            ),
            "#7289da",
        )
        orchestra_settings_layout.addWidget(self.auto_restart_discord_toggle)

        # Количество фейлов для рестарта Discord
        self.discord_fails_spin = Win11NumberRow(
            "mdi.discord",
            self._tr("page.dpi_settings.orchestra.discord_fails.title", "Фейлов для рестарта Discord"),
            self._tr(
                "page.dpi_settings.orchestra.discord_fails.desc",
                "Сколько FAIL подряд для перезапуска Discord",
            ),
            "#7289da",
            min_val=1, max_val=10, default_val=3)
        orchestra_settings_layout.addWidget(self.discord_fails_spin)

        # Успехов для LOCK (сколько успехов подряд для закрепления стратегии)
        self.lock_successes_spin = Win11NumberRow(
            "mdi.lock",
            self._tr("page.dpi_settings.orchestra.lock_successes.title", "Успехов для LOCK"),
            self._tr(
                "page.dpi_settings.orchestra.lock_successes.desc",
                "Количество успешных обходов для закрепления стратегии",
            ),
            "#4CAF50",
            min_val=1, max_val=10, default_val=3)
        orchestra_settings_layout.addWidget(self.lock_successes_spin)

        # Ошибок для AUTO-UNLOCK (сколько ошибок подряд для разблокировки)
        self.unlock_fails_spin = Win11NumberRow(
            "mdi.lock-open",
            self._tr("page.dpi_settings.orchestra.unlock_fails.title", "Ошибок для AUTO-UNLOCK"),
            self._tr(
                "page.dpi_settings.orchestra.unlock_fails.desc",
                "Количество ошибок для автоматической разблокировки стратегии",
            ),
            "#FF5722",
            min_val=1, max_val=10, default_val=3)
        orchestra_settings_layout.addWidget(self.unlock_fails_spin)

        method_layout.addWidget(self.orchestra_settings_container)

        method_card.add_layout(method_layout)
        self.layout.addWidget(method_card)
        
        # ═══════════════════════════════════════════════════════════════════════
        # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ
        # ═══════════════════════════════════════════════════════════════════════
        self.advanced_card = SettingsCard(
            self._tr("page.dpi_settings.card.advanced", "ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ")
        )
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(6)
        
        # Описание
        advanced_desc = _CaptionLabel(
            self._tr("page.dpi_settings.advanced.warning", "⚠ Изменяйте только если знаете что делаете")
        )
        self._advanced_desc_label = advanced_desc
        advanced_desc.setContentsMargins(0, 0, 0, 8)
        advanced_desc.setStyleSheet("color: #ff9800;")
        advanced_layout.addWidget(advanced_desc)
        
        # WSSize
        self.wssize_toggle = Win11ToggleRow(
            "fa5s.ruler-horizontal",
            self._tr("page.dpi_settings.advanced.wssize.title", "Включить --wssize"),
            self._tr("page.dpi_settings.advanced.wssize.desc", "Добавляет параметр размера окна TCP"),
            "#9c27b0",
        )
        advanced_layout.addWidget(self.wssize_toggle)
        
        # Debug лог
        self.debug_log_toggle = Win11ToggleRow(
            "mdi.file-document-outline",
            self._tr("page.dpi_settings.advanced.debug_log.title", "Включить лог-файл (--debug)"),
            self._tr("page.dpi_settings.advanced.debug_log.desc", "Записывает логи winws в папку logs"),
            "#00bcd4",
        )
        advanced_layout.addWidget(self.debug_log_toggle)
        
        self.advanced_card.add_layout(advanced_layout)
        self.layout.addWidget(self.advanced_card)
        
        self.layout.addStretch()

        # Apply token-driven accents/dividers.
        self._apply_theme_styles()
        
    def _load_settings(self):
        """Загружает настройки"""
        try:
            from strategy_menu import get_strategy_launch_method
            method = get_strategy_launch_method()

            # Устанавливаем выбранный метод
            self._update_method_selection(method)

            # Discord restart setting
            self._load_discord_restart_setting()

            # Orchestra settings
            self._load_orchestra_settings()

            self._update_filters_visibility()
            self._load_filter_settings()

        except Exception as e:
            log(f"Ошибка загрузки настроек DPI: {e}", "WARNING")
    
    def _update_method_selection(self, method: str):
        """Обновляет визуальное состояние выбора метода"""
        self.method_direct.setSelected(method == "direct_zapret2")
        self.method_direct_zapret2_orchestra.setSelected(method == "direct_zapret2_orchestra")
        self.method_direct_zapret1.setSelected(method == "direct_zapret1")
        self.method_orchestra.setSelected(method == "orchestra")
    
    def _select_method(self, method: str):
        """Обработчик выбора метода"""
        try:
            from strategy_menu import (
                set_strategy_launch_method, get_strategy_launch_method, invalidate_direct_selections_cache,
            )
            from preset_orchestra_zapret2 import ensure_default_preset_exists

            # Запоминаем предыдущий метод, чтобы понять, затрагиваем ли мы legacy registry-driven ветки.
            previous_method = get_strategy_launch_method()

            if method == "direct_zapret2_orchestra":
                ensure_default_preset_exists()

            set_strategy_launch_method(method)
            self._update_method_selection(method)
            self._update_filters_visibility()

            # Сбрасываем кэш выборов при смене direct-метода: они будут перечитаны из актуального источника.
            direct_methods = ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1")
            if previous_method in direct_methods or method in direct_methods:
                if previous_method != method:
                    log(f"Смена метода {previous_method} -> {method}, сброс direct-кэша...", "INFO")
                    invalidate_direct_selections_cache()

            # Legacy registry reload нужен только для orchestra/registry-driven страниц.
            registry_driven_methods = {"direct_zapret2_orchestra", "orchestra"}
            if (
                previous_method != method
                and (previous_method in registry_driven_methods or method in registry_driven_methods)
            ):
                try:
                    from strategy_menu.strategies_registry import registry

                    registry.reload_strategies()
                except Exception:
                    pass

            self.launch_method_changed.emit(method)
        except Exception as e:
            log(f"Ошибка смены метода: {e}", "ERROR")
    
    def _load_discord_restart_setting(self):
        """Загружает настройку перезапуска Discord"""
        try:
            from discord.discord_restart import get_discord_restart_setting, set_discord_restart_setting
            
            # Загружаем текущее значение (по умолчанию True), блокируя сигналы
            self.discord_restart_toggle.setChecked(get_discord_restart_setting(default=True), block_signals=True)
            
            # Подключаем сигнал сохранения
            self.discord_restart_toggle.toggled.connect(self._on_discord_restart_changed)
            
        except Exception as e:
            log(f"Ошибка загрузки настройки Discord: {e}", "WARNING")
    
    def _on_discord_restart_changed(self, enabled: bool):
        """Обработчик изменения настройки перезапуска Discord"""
        try:
            from discord.discord_restart import set_discord_restart_setting
            set_discord_restart_setting(enabled)
            status = "включён" if enabled else "отключён"
            log(f"Автоперезапуск Discord {status}", "INFO")
        except Exception as e:
            log(f"Ошибка сохранения настройки Discord: {e}", "ERROR")

    def _load_orchestra_settings(self):
        """Загружает настройки оркестратора"""
        try:
            from config import REGISTRY_PATH
            from config.reg import reg

            # Строгий режим детекции (по умолчанию включён)
            saved_strict = reg(f"{REGISTRY_PATH}\\Orchestra", "StrictDetection")
            self.strict_detection_toggle.setChecked(saved_strict is None or bool(saved_strict), block_signals=True)
            self.strict_detection_toggle.toggled.connect(self._on_strict_detection_changed)

            # Debug файл (по умолчанию выключен)
            saved_debug = reg(f"{REGISTRY_PATH}\\Orchestra", "KeepDebugFile")
            self.debug_file_toggle.setChecked(bool(saved_debug), block_signals=True)
            self.debug_file_toggle.toggled.connect(self._on_debug_file_changed)

            # Авторестарт при Discord FAIL (по умолчанию включён)
            saved_auto_restart = reg(f"{REGISTRY_PATH}\\Orchestra", "AutoRestartOnDiscordFail")
            self.auto_restart_discord_toggle.setChecked(saved_auto_restart is None or bool(saved_auto_restart), block_signals=True)
            self.auto_restart_discord_toggle.toggled.connect(self._on_auto_restart_discord_changed)

            # Количество фейлов для рестарта Discord (по умолчанию 3)
            saved_discord_fails = reg(f"{REGISTRY_PATH}\\Orchestra", "DiscordFailsForRestart")
            if saved_discord_fails is not None:
                self.discord_fails_spin.setValue(int(saved_discord_fails))
            self.discord_fails_spin.valueChanged.connect(self._on_discord_fails_changed)

            # Успехов для LOCK (по умолчанию 3)
            saved_lock_successes = reg(f"{REGISTRY_PATH}\\Orchestra", "LockSuccesses")
            if saved_lock_successes is not None:
                self.lock_successes_spin.setValue(int(saved_lock_successes))
            self.lock_successes_spin.valueChanged.connect(self._on_lock_successes_changed)

            # Ошибок для AUTO-UNLOCK (по умолчанию 3)
            saved_unlock_fails = reg(f"{REGISTRY_PATH}\\Orchestra", "UnlockFails")
            if saved_unlock_fails is not None:
                self.unlock_fails_spin.setValue(int(saved_unlock_fails))
            self.unlock_fails_spin.valueChanged.connect(self._on_unlock_fails_changed)

        except Exception as e:
            log(f"Ошибка загрузки настроек оркестратора: {e}", "WARNING")

    def _on_strict_detection_changed(self, enabled: bool):
        """Обработчик изменения строгого режима детекции"""
        try:
            from config import REGISTRY_PATH
            from config.reg import reg

            reg(f"{REGISTRY_PATH}\\Orchestra", "StrictDetection", 1 if enabled else 0)
            log(f"Строгий режим детекции: {'включён' if enabled else 'выключен'}", "INFO")

            # Обновляем orchestra_runner если запущен
            app = self._get_app()
            if app and hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                app.orchestra_runner.set_strict_detection(enabled)

        except Exception as e:
            log(f"Ошибка сохранения настройки строгого режима: {e}", "ERROR")

    def _on_debug_file_changed(self, enabled: bool):
        """Обработчик изменения сохранения debug файла"""
        try:
            from config import REGISTRY_PATH
            from config.reg import reg

            reg(f"{REGISTRY_PATH}\\Orchestra", "KeepDebugFile", 1 if enabled else 0)
            log(f"Сохранение debug файла: {'включено' if enabled else 'выключено'}", "INFO")

        except Exception as e:
            log(f"Ошибка сохранения настройки debug файла: {e}", "ERROR")

    def _on_auto_restart_discord_changed(self, enabled: bool):
        """Обработчик изменения авторестарта при Discord FAIL"""
        try:
            from config import REGISTRY_PATH
            from config.reg import reg

            reg(f"{REGISTRY_PATH}\\Orchestra", "AutoRestartOnDiscordFail", 1 if enabled else 0)
            log(f"Авторестарт при Discord FAIL: {'включён' if enabled else 'выключен'}", "INFO")

            # Обновляем orchestra_runner если запущен
            app = self._get_app()
            if app and hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                app.orchestra_runner.auto_restart_on_discord_fail = enabled

        except Exception as e:
            log(f"Ошибка сохранения настройки авторестарта Discord: {e}", "ERROR")

    def _on_discord_fails_changed(self, value: int):
        """Обработчик изменения количества фейлов для рестарта Discord"""
        try:
            from config import REGISTRY_PATH
            from config.reg import reg

            reg(f"{REGISTRY_PATH}\\Orchestra", "DiscordFailsForRestart", value)
            log(f"Фейлов для рестарта Discord: {value}", "INFO")

            # Обновляем orchestra_runner если запущен
            app = self._get_app()
            if app and hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                app.orchestra_runner.discord_fails_for_restart = value

        except Exception as e:
            log(f"Ошибка сохранения настройки DiscordFailsForRestart: {e}", "ERROR")

    def _on_lock_successes_changed(self, value: int):
        """Обработчик изменения количества успехов для LOCK"""
        try:
            from config import REGISTRY_PATH
            from config.reg import reg

            reg(f"{REGISTRY_PATH}\\Orchestra", "LockSuccesses", value)
            log(f"Успехов для LOCK: {value}", "INFO")

            # Обновляем orchestra_runner если запущен
            app = self._get_app()
            if app and hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                app.orchestra_runner.lock_successes_threshold = value

        except Exception as e:
            log(f"Ошибка сохранения настройки LockSuccesses: {e}", "ERROR")

    def _on_unlock_fails_changed(self, value: int):
        """Обработчик изменения количества ошибок для AUTO-UNLOCK"""
        try:
            from config import REGISTRY_PATH
            from config.reg import reg

            reg(f"{REGISTRY_PATH}\\Orchestra", "UnlockFails", value)
            log(f"Ошибок для AUTO-UNLOCK: {value}", "INFO")

            # Обновляем orchestra_runner если запущен
            app = self._get_app()
            if app and hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                app.orchestra_runner.unlock_fails_threshold = value

        except Exception as e:
            log(f"Ошибка сохранения настройки UnlockFails: {e}", "ERROR")

    def _get_app(self):
        """Получает ссылку на главное приложение"""
        try:
            # Ищем через parent виджетов
            widget = self
            while widget:
                if hasattr(widget, 'dpi_controller'):
                    return widget
                if hasattr(widget, 'parent_app'):
                    return widget.parent_app
                widget = widget.parent()
            
            # Пробуем через QApplication
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if hasattr(app, 'dpi_controller'):
                return app
                
            # Пробуем через main_window
            for widget in QApplication.topLevelWidgets():
                if hasattr(widget, 'parent_app'):
                    return widget.parent_app
        except:
            pass
        return None
    
    def _restart_dpi_async(self):
        """Асинхронно перезапускает DPI если он запущен"""
        try:
            app = self._get_app()
            if not app or not hasattr(app, 'dpi_controller'):
                log("DPI контроллер не найден для перезапуска", "DEBUG")
                return

            # Для режима direct_zapret2 используем унифицированный механизм
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()

            if launch_method == "direct_zapret2":
                from dpi.zapret2_core_restart import trigger_dpi_reload
                trigger_dpi_reload(app, reason="settings_changed")
                return

            # Для остальных режимов (orchestra, zapret1, bat) - старая логика
            # Проверяем, запущен ли процесс
            if not app.dpi_starter.check_process_running_wmi(silent=True):
                log("DPI не запущен, перезапуск не требуется", "DEBUG")
                return

            log("Перезапуск DPI после изменения настроек...", "INFO")

            # Асинхронно останавливаем
            app.dpi_controller.stop_dpi_async()

            # Запускаем таймер для проверки остановки и перезапуска
            self._restart_check_count = 0
            if not hasattr(self, '_restart_timer') or self._restart_timer is None:
                self._restart_timer = QTimer(self)
                self._restart_timer.timeout.connect(self._check_stopped_and_restart)
            self._restart_timer.start(300)  # Проверяем каждые 300мс

        except Exception as e:
            log(f"Ошибка перезапуска DPI: {e}", "ERROR")
    
    def _check_stopped_and_restart(self):
        """Проверяет остановку DPI и запускает заново"""
        try:
            app = self._get_app()
            if not app:
                self._restart_timer.stop()
                return
                
            self._restart_check_count += 1
            
            # Максимум 30 проверок (9 секунд)
            if self._restart_check_count > 30:
                self._restart_timer.stop()
                log("⚠️ Таймаут ожидания остановки DPI", "WARNING")
                self._start_dpi_after_stop()
                return
            
            # Проверяем, остановлен ли процесс
            if not app.dpi_starter.check_process_running_wmi(silent=True):
                self._restart_timer.stop()
                # Небольшая пауза и запуск
                QTimer.singleShot(200, self._start_dpi_after_stop)
                
        except Exception as e:
            if hasattr(self, '_restart_timer'):
                self._restart_timer.stop()
            log(f"Ошибка проверки остановки: {e}", "ERROR")
    
    def _start_dpi_after_stop(self):
        """Запускает DPI после остановки"""
        try:
            app = self._get_app()
            if not app or not hasattr(app, 'dpi_controller'):
                return
                
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            
            if launch_method == "direct_zapret1":
                try:
                    from core.services import get_direct_flow_coordinator

                    selected_mode = get_direct_flow_coordinator().build_selected_mode(
                        "direct_zapret1",
                        require_filters=False,
                    )
                except Exception as e:
                    log(f"Перезапуск Zapret1 пропущен: {e}", "WARNING")
                    return
                app.dpi_controller.start_dpi_async(selected_mode=selected_mode, launch_method=launch_method)
            elif launch_method == "direct_zapret2":
                try:
                    from core.services import get_direct_flow_coordinator

                    selected_mode = get_direct_flow_coordinator().build_selected_mode(
                        "direct_zapret2",
                        require_filters=False,
                    )
                except Exception as e:
                    log(f"Перезапуск direct_zapret2 пропущен: {e}", "WARNING")
                    return
                app.dpi_controller.start_dpi_async(selected_mode=selected_mode, launch_method=launch_method)
            elif launch_method == "direct_zapret2_orchestra":
                # Orchestra direct остаётся на своём runtime-file workflow.
                from preset_orchestra_zapret2 import get_active_preset_path, get_active_preset_name

                preset_path = get_active_preset_path()
                if not preset_path.exists():
                    log("Перезапуск direct_zapret2_orchestra пропущен: runtime config не найден", "WARNING")
                    return
                preset_name = get_active_preset_name() or "Default"
                selected_mode = {
                    "is_preset_file": True,
                    "name": f"Пресет оркестра: {preset_name}",
                    "preset_path": str(preset_path),
                }
                app.dpi_controller.start_dpi_async(selected_mode=selected_mode, launch_method=launch_method)
            else:
                # BAT режим
                app.dpi_controller.start_dpi_async()
                
            log("✅ DPI перезапущен с новыми настройками", "INFO")
            
        except Exception as e:
            log(f"Ошибка запуска DPI: {e}", "ERROR")
        
    def _load_filter_settings(self):
        """Загружает настройки фильтров"""
        try:
            getter_wssize = self._get_filter_state_getter("wssize")
            getter_debug = self._get_filter_state_getter("debug")
            setter_wssize = self._get_filter_state_setter("wssize")
            setter_debug = self._get_filter_state_setter("debug")

            # ═══════════════════════════════════════════════════════════════════════
            # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ — остаются активными
            # ═══════════════════════════════════════════════════════════════════════
            self.wssize_toggle.setChecked(bool(getter_wssize()), block_signals=True)
            self.debug_log_toggle.setChecked(bool(getter_debug()), block_signals=True)

            # Подключаем сигналы только для дополнительных настроек
            self.wssize_toggle.toggled.connect(lambda v: self._on_filter_changed(setter_wssize, v))
            self.debug_log_toggle.toggled.connect(lambda v: self._on_filter_changed(setter_debug, v))

        except Exception as e:
            log(f"Ошибка загрузки фильтров: {e}", "WARNING")
            import traceback
            log(traceback.format_exc(), "DEBUG")

    def update_filter_display(self, filters: dict):
        """
        Совместимость: раньше показывало «Фильтры перехвата трафика» в GUI.
        Теперь блок удалён, метод оставлен как no-op для старых вызовов.
        """
        _ = filters
        return
                
    def _on_filter_changed(self, setter_func, value):
        """Обработчик изменения фильтра"""
        setter_func(value)

        self.filters_changed.emit()

    def _get_direct_toggle_facade(self):
        try:
            from strategy_menu import get_strategy_launch_method

            method = (get_strategy_launch_method() or "").strip().lower()
            if method in ("direct_zapret2", "direct_zapret1"):
                from core.presets.direct_facade import DirectPresetFacade

                return DirectPresetFacade.from_launch_method(method)
        except Exception:
            pass
        return None

    def _get_filter_state_getter(self, kind: str):
        facade = self._get_direct_toggle_facade()
        if facade is not None:
            if kind == "wssize":
                return facade.get_wssize_enabled
            return facade.get_debug_log_enabled

        if kind == "wssize":
            from strategy_menu import get_wssize_enabled

            return get_wssize_enabled

        from strategy_menu import get_debug_log_enabled

        return get_debug_log_enabled

    def _get_filter_state_setter(self, kind: str):
        facade = self._get_direct_toggle_facade()
        if facade is not None:
            if kind == "wssize":
                return lambda value: facade.set_wssize_enabled(bool(value))
            return lambda value: facade.set_debug_log_enabled(bool(value))

        if kind == "wssize":
            from strategy_menu import set_wssize_enabled

            return set_wssize_enabled

        from strategy_menu import set_debug_log_enabled

        return set_debug_log_enabled
        
    def _update_filters_visibility(self):
        """Обновляет видимость фильтров и секций"""
        try:
            from strategy_menu import get_strategy_launch_method
            method = get_strategy_launch_method()

            # Режимы
            is_direct_mode = method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1")
            is_zapret_mode = method in ("direct_zapret2", "direct_zapret1")  # Zapret 1/2 без оркестратора

            # For direct_zapret2 these options are shown on the Strategies/Management page
            # (ui/pages/zapret2/direct_control_page.py), so hide them here.
            self.advanced_card.setVisible(is_direct_mode and method != "direct_zapret2")

            # If we just made the advanced section visible again, re-sync its state
            # from the current mode source of truth (preset for direct preset flow).
            if is_direct_mode and method != "direct_zapret2":
                try:
                    self.wssize_toggle.setChecked(bool(self._get_filter_state_getter("wssize")()), block_signals=True)
                    self.debug_log_toggle.setChecked(bool(self._get_filter_state_getter("debug")()), block_signals=True)
                except Exception:
                    pass

            # Discord restart только для Zapret 1/2 (без оркестратора)
            show_discord_restart = is_zapret_mode and method != "direct_zapret2"
            self.discord_restart_container.setVisible(show_discord_restart)
            if show_discord_restart:
                try:
                    from discord.discord_restart import get_discord_restart_setting

                    self.discord_restart_toggle.setChecked(get_discord_restart_setting(default=True), block_signals=True)
                except Exception:
                    pass

            # Настройки оркестратора только для Python-оркестратора.
            # В direct_zapret2_orchestra оркестрация выполняется Lua-модулем circular —
            # параметры LOCK/UNLOCK/Discord/strict_detection к нему не применяются.
            self.orchestra_settings_container.setVisible(method == "orchestra")

        except:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._method_card is not None:
            self._method_card.set_title(
                self._tr(
                    "page.dpi_settings.card.launch_method",
                    "Метод запуска стратегий (режим работы программы)",
                )
            )
        if self._method_desc_label is not None:
            self._method_desc_label.setText(
                self._tr("page.dpi_settings.launch_method.desc", "Выберите способ запуска обхода блокировок")
            )

        if hasattr(self, "zapret2_header") and self.zapret2_header is not None:
            self.zapret2_header.setText(self._tr("page.dpi_settings.section.z2", "Zapret 2 (winws2.exe)"))
        if self._zapret1_header is not None:
            self._zapret1_header.setText(self._tr("page.dpi_settings.section.z1", "Zapret 1 (winws.exe)"))
        if self._orchestra_label is not None:
            self._orchestra_label.setText(
                self._tr("page.dpi_settings.section.orchestra_settings", "Настройки оркестратора")
            )

        self.method_direct.set_texts(
            self._tr("page.dpi_settings.method.direct_z2.title", "Zapret 2"),
            self._tr(
                "page.dpi_settings.method.direct_z2.desc",
                "Режим со второй версией Zapret (winws2.exe) + готовые пресеты для быстрого запуска. Поддерживает кастомный lua-код чтобы писать свои стратегии.",
            ),
            recommended_badge=self._tr("page.dpi_settings.option.recommended", "рекомендуется"),
        )
        self.method_direct_zapret2_orchestra.set_texts(
            self._tr("page.dpi_settings.method.direct_z2_orchestra.title", "Оркестраторный Zapret 2"),
            self._tr(
                "page.dpi_settings.method.direct_z2_orchestra.desc",
                "Запуск Zapret 2 со стратегиями оркестратора внутри каждого профиля. Позволяет настроить для каждого сайта свой оркерстратор. Не сохраняет состояние для повышенной агрессии обхода.",
            ),
        )
        self.method_orchestra.set_texts(
            self._tr("page.dpi_settings.method.orchestra.title", "Оркестратор v0.9.6 (Beta)"),
            self._tr(
                "page.dpi_settings.method.orchestra.desc",
                "Автоматическое обучение. Система сама подбирает лучшие стратегии для каждого домена. Запоминает результаты между запусками.",
            ),
        )
        self.method_direct_zapret1.set_texts(
            self._tr("page.dpi_settings.method.direct_z1.title", "Zapret 1"),
            self._tr(
                "page.dpi_settings.method.direct_z1.desc",
                "Режим первой версии Zapret 1 (winws.exe) + готовые пресеты для быстрого запуска. Не использует Lua код, нет понятия блобов.",
            ),
        )

        self.discord_restart_toggle.set_texts(
            self._tr("page.dpi_settings.discord_restart.title", "Перезапуск Discord"),
            self._tr("page.dpi_settings.discord_restart.desc", "Автоперезапуск при смене стратегии"),
        )

        self.strict_detection_toggle.set_texts(
            self._tr("page.dpi_settings.orchestra.strict_detection.title", "Строгий режим детекции"),
            self._tr("page.dpi_settings.orchestra.strict_detection.desc", "HTTP 200 + проверка блок-страниц"),
        )
        self.debug_file_toggle.set_texts(
            self._tr("page.dpi_settings.orchestra.debug_file.title", "Сохранять debug файл"),
            self._tr("page.dpi_settings.orchestra.debug_file.desc", "Сырой debug файл для отладки"),
        )
        self.auto_restart_discord_toggle.set_texts(
            self._tr("page.dpi_settings.orchestra.auto_restart_discord.title", "Авторестарт Discord при FAIL"),
            self._tr(
                "page.dpi_settings.orchestra.auto_restart_discord.desc",
                "Перезапуск Discord при неудачном обходе",
            ),
        )
        self.discord_fails_spin.set_texts(
            self._tr("page.dpi_settings.orchestra.discord_fails.title", "Фейлов для рестарта Discord"),
            self._tr(
                "page.dpi_settings.orchestra.discord_fails.desc",
                "Сколько FAIL подряд для перезапуска Discord",
            ),
        )
        self.lock_successes_spin.set_texts(
            self._tr("page.dpi_settings.orchestra.lock_successes.title", "Успехов для LOCK"),
            self._tr(
                "page.dpi_settings.orchestra.lock_successes.desc",
                "Количество успешных обходов для закрепления стратегии",
            ),
        )
        self.unlock_fails_spin.set_texts(
            self._tr("page.dpi_settings.orchestra.unlock_fails.title", "Ошибок для AUTO-UNLOCK"),
            self._tr(
                "page.dpi_settings.orchestra.unlock_fails.desc",
                "Количество ошибок для автоматической разблокировки стратегии",
            ),
        )

        if hasattr(self, "advanced_card") and self.advanced_card is not None:
            self.advanced_card.set_title(
                self._tr("page.dpi_settings.card.advanced", "ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ")
            )
        if self._advanced_desc_label is not None:
            self._advanced_desc_label.setText(
                self._tr("page.dpi_settings.advanced.warning", "⚠ Изменяйте только если знаете что делаете")
            )
        self.wssize_toggle.set_texts(
            self._tr("page.dpi_settings.advanced.wssize.title", "Включить --wssize"),
            self._tr("page.dpi_settings.advanced.wssize.desc", "Добавляет параметр размера окна TCP"),
        )
        self.debug_log_toggle.set_texts(
            self._tr("page.dpi_settings.advanced.debug_log.title", "Включить лог-файл (--debug)"),
            self._tr("page.dpi_settings.advanced.debug_log.desc", "Записывает логи winws в папку logs"),
        )
